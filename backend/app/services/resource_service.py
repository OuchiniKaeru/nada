import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource import Resource, ResourceLink
from app.schemas.resource import ResourceCreate, ResourceUpdate
from app.services import config_store


async def create_resource(db: AsyncSession, user_id: str, data: ResourceCreate) -> Resource:
    resource_id = str(uuid.uuid4())
    config_path = config_store.save_config(data.type, resource_id, data.config_format, data.config_text or "")

    resource = Resource(
        id=resource_id,
        type=data.type,
        name=data.name,
        description=data.description,
        visibility=data.visibility,
        config_format=data.config_format,
        config_path=str(config_path),
        owner_id=user_id,
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource


def _visibility_filter(resource: Resource, user_id: str):
    """private は所有者のみ、team/public は全ユーザー閲覧可。"""
    return (resource.visibility != "private") | (resource.owner_id == user_id)


async def get_resources(db: AsyncSession, user_id: str, resource_type: str | None = None) -> list[Resource]:
    stmt = select(Resource).where(_visibility_filter(Resource, user_id))
    if resource_type:
        stmt = stmt.where(Resource.type == resource_type)
    stmt = stmt.order_by(Resource.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_resource(db: AsyncSession, user_id: str, resource_id: str) -> Resource | None:
    result = await db.execute(select(Resource).where(Resource.id == resource_id))
    resource = result.scalar_one_or_none()
    if not resource or not _visibility_filter(resource, user_id):
        return None
    return resource


async def update_resource(db: AsyncSession, user_id: str, resource_id: str, data: ResourceUpdate) -> Resource | None:
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id, Resource.owner_id == user_id)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # 設定本文の更新(フォーマット変更を含む)
    new_text = update_data.get("config_text")
    new_fmt = update_data.get("config_format") or resource.config_format
    if new_text is not None:
        config_path = config_store.save_config(resource.type, resource.id, new_fmt, new_text)
        resource.config_path = str(config_path)
        resource.config_format = new_fmt
    elif "config_format" in update_data and update_data["config_format"] != resource.config_format:
        # 本文なしでフォーマットだけ変わることはないため、既存本文を変換せずエラーにする
        raise ValueError("config_format を変更する場合は config_text も指定してください")

    if "name" in update_data:
        resource.name = update_data["name"]
    if "description" in update_data:
        resource.description = update_data["description"]
    if "visibility" in update_data:
        resource.visibility = update_data["visibility"]

    await db.commit()
    await db.refresh(resource)
    return resource


async def delete_resource(db: AsyncSession, user_id: str, resource_id: str) -> bool:
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id, Resource.owner_id == user_id)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        return False
    config_store.delete_config(resource.config_path)
    await db.delete(resource)
    await db.commit()
    return True


async def load_resource_config(resource: Resource):
    """リソースの設定ファイルを読み込む。"""
    return config_store.load_config(resource.config_path)


# ---- Hermes トグル用のリンク管理 ----


async def set_links(
    db: AsyncSession,
    parent_type: str,
    parent_id: str,
    links: list[dict],
) -> list[ResourceLink]:
    """親(agent/squad/workflow)のリソースリンクを一括更新する。

    links: [{"resource_id": ..., "enabled": true/false}, ...]
    """
    result = await db.execute(
        select(ResourceLink).where(
            ResourceLink.parent_type == parent_type,
            ResourceLink.parent_id == parent_id,
        )
    )
    existing = {link.resource_id: link for link in result.scalars().all()}

    for entry in links:
        rid = entry.get("resource_id")
        enabled = bool(entry.get("enabled", True))
        if not rid:
            continue
        if rid in existing:
            existing[rid].enabled = enabled
        else:
            link = ResourceLink(
                id=str(uuid.uuid4()),
                parent_type=parent_type,
                parent_id=parent_id,
                resource_id=rid,
                enabled=enabled,
            )
            db.add(link)
            existing[rid] = link

    await db.commit()
    return await get_links(db, parent_type, parent_id)


async def get_links(db: AsyncSession, parent_type: str, parent_id: str) -> list[ResourceLink]:
    result = await db.execute(
        select(ResourceLink).where(
            ResourceLink.parent_type == parent_type,
            ResourceLink.parent_id == parent_id,
        )
    )
    return list(result.scalars().all())


async def get_enabled_resources(db: AsyncSession, parent_type: str, parent_id: str) -> dict[str, list[Resource]]:
    """有効化されたリソースを type ごとにグルーピングして返す。"""
    links = [l for l in await get_links(db, parent_type, parent_id) if l.enabled]
    if not links:
        return {}

    result = await db.execute(select(Resource).where(Resource.id.in_([l.resource_id for l in links])))
    resources_by_id = {r.id: r for r in result.scalars().all()}

    grouped: dict[str, list[Resource]] = {}
    for link in links:
        resource = resources_by_id.get(link.resource_id)
        if resource is None:
            continue
        grouped.setdefault(resource.type, []).append(resource)
    return grouped
