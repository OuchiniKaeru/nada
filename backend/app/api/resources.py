from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.resource import (
    ResourceConfigResponse,
    ResourceCreate,
    ResourceResponse,
    ResourceUpdate,
)
from app.schemas.resource_link import (
    EnabledResourcesResponse,
    ResourceLinksResponse,
    ResourceLinksUpdate,
)
from app.schemas.resource_config_validate import (
    ResourceConfigValidateRequest,
    ResourceConfigValidateResponse,
)
from app.services import resource_service
from app.services.config_store import validate_config

router = APIRouter()


# NOTE: このエンドポイントは動的ルート /resources/{resource_type} より先に登録する必要がある。
# 後ろで定義すると "validate-config" が resource_type パスパラメータとして
# create_resource にマッチし、422 エラー (type/name 必須) になってしまう。
@router.post("/resources/validate-config", response_model=ResourceConfigValidateResponse)
async def validate_config_endpoint(
    body: ResourceConfigValidateRequest,
    user=Depends(get_current_user),
):
    ok, err = validate_config(body.config_format, body.config_text)
    return ResourceConfigValidateResponse(ok=ok, error=err)


@router.get("/resources/{resource_type}", response_model=list[ResourceResponse])
async def list_resources(
    resource_type: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await resource_service.get_resources(db, user.id, resource_type)


@router.post("/resources/{resource_type}", response_model=ResourceResponse)
async def create_resource(
    resource_type: str,
    data: ResourceCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # URLパスの type を優先する
    data.type = resource_type  # type: ignore[assignment]
    try:
        return await resource_service.create_resource(db, user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/resources/{resource_type}/{resource_id}", response_model=ResourceResponse)
async def read_resource(
    resource_type: str,
    resource_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resource = await resource_service.get_resource(db, user.id, resource_id)
    if not resource or resource.type != resource_type:
        raise HTTPException(status_code=404, detail="リソースが見つかりません。")
    return resource


@router.patch("/resources/{resource_type}/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_type: str,
    resource_id: str,
    data: ResourceUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        resource = await resource_service.update_resource(db, user.id, resource_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not resource or resource.type != resource_type:
        raise HTTPException(status_code=404, detail="リソースが見つかりません。")
    return resource


@router.delete("/resources/{resource_type}/{resource_id}")
async def delete_resource(
    resource_type: str,
    resource_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await resource_service.delete_resource(db, user.id, resource_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="リソースが見つかりません。")
    return {"status": "deleted"}


@router.get("/resources/{resource_type}/{resource_id}/config", response_model=ResourceConfigResponse)
async def read_resource_config(
    resource_type: str,
    resource_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resource = await resource_service.get_resource(db, user.id, resource_id)
    if not resource or resource.type != resource_type:
        raise HTTPException(status_code=404, detail="リソースが見つかりません。")
    try:
        with open(resource.config_path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="設定ファイルが見つかりません。")
    return ResourceConfigResponse(
        resource_id=resource.id,
        config_format=resource.config_format,
        config_text=text,
    )


@router.put("/resources/{resource_type}/{resource_id}/config", response_model=ResourceConfigResponse)
async def update_resource_config(
    resource_type: str,
    resource_id: str,
    body: ResourceConfigResponse,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.resource import ResourceUpdate

    resource = await resource_service.get_resource(db, user.id, resource_id)
    if not resource or resource.type != resource_type:
        raise HTTPException(status_code=404, detail="リソースが見つかりません。")
    try:
        updated = await resource_service.update_resource(
            db,
            user.id,
            resource_id,
            ResourceUpdate(config_text=body.config_text),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    assert updated is not None
    return ResourceConfigResponse(
        resource_id=updated.id,
        config_format=updated.config_format,
        config_text=body.config_text,
    )


# ---- Hermes トグル (エージェント/スクワッド/Workflow へのリソース紐付け) ----


@router.get("/links/{parent_type}/{parent_id}", response_model=ResourceLinksResponse)
async def get_links(
    parent_type: str,
    parent_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if parent_type not in ("agent", "squad", "workflow"):
        raise HTTPException(status_code=400, detail="parent_type は agent/squad/workflow のいずれかです")
    links = await resource_service.get_links(db, parent_type, parent_id)
    return ResourceLinksResponse(
        parent_type=parent_type,
        parent_id=parent_id,
        links=[
            {"resource_id": l.resource_id, "enabled": l.enabled}
            for l in links
        ],
    )


@router.put("/links/{parent_type}/{parent_id}", response_model=ResourceLinksResponse)
async def set_links(
    parent_type: str,
    parent_id: str,
    body: ResourceLinksUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if parent_type not in ("agent", "squad", "workflow"):
        raise HTTPException(status_code=400, detail="parent_type は agent/squad/workflow のいずれかです")
    links = await resource_service.set_links(
        db, parent_type, parent_id,
        [entry.model_dump() for entry in body.links],
    )
    return ResourceLinksResponse(
        parent_type=parent_type,
        parent_id=parent_id,
        links=[
            {"resource_id": l.resource_id, "enabled": l.enabled}
            for l in links
        ],
    )


@router.get("/links/{parent_type}/{parent_id}/enabled", response_model=EnabledResourcesResponse)
async def get_enabled_resources(
    parent_type: str,
    parent_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    grouped = await resource_service.get_enabled_resources(db, parent_type, parent_id)
    return EnabledResourcesResponse(
        parent_type=parent_type,
        parent_id=parent_id,
        resources={
            rtype: [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "config_format": r.config_format,
                    "config_path": r.config_path,
                }
                for r in items
            ]
            for rtype, items in grouped.items()
        },
    )
