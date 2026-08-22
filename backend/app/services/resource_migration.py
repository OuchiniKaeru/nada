"""既存 Skill/MCP レコードを新方式 (resources + 設定ファイル) へ移行する。

冪等: 既に resources に同IDが存在すればスキップ。
起動時 (main.py lifespan) に自動実行され、失敗しても起動を妨げない。
"""
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import MCPServer
from app.models.resource import Resource
from app.models.skill import Skill
from app.services import config_store

logger = logging.getLogger(__name__)


def _skill_config_text(skill: Skill) -> str:
    return json.dumps(
        {"content": skill.content},
        ensure_ascii=False,
        indent=2,
    )


def _mcp_config_text(mcp: MCPServer) -> str:
    payload = {
        "url": mcp.url,
        "transport": mcp.transport or "streamable-http",
        "auth_type": mcp.auth_type or "none",
        "enabled": bool(mcp.enabled),
    }
    if mcp.config:
        payload["config"] = mcp.config
    # auth_secret_encrypted は平文保存を避けるため移行しない(再設定が必要)
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def migrate_existing_skills_and_mcps(db: AsyncSession) -> dict:
    """skills / mcps テーブルの全レコードを resources へ移行する。

    Returns:
        {"skills_migrated": n, "mcps_migrated": n, "skipped": n}
    """
    stats = {"skills_migrated": 0, "mcps_migrated": 0, "skipped": 0}

    # 既存の resources ID を一括取得
    result = await db.execute(select(Resource.id))
    existing_ids = {row[0] for row in result.all()}

    result = await db.execute(select(Skill))
    for skill in result.scalars().all():
        if skill.id in existing_ids:
            stats["skipped"] += 1
            continue
        try:
            path = config_store.save_config("skill", skill.id, "json", _skill_config_text(skill))
            db.add(Resource(
                id=skill.id,
                type="skill",
                name=skill.name,
                description=skill.description,
                visibility=skill.visibility or "private",
                config_format="json",
                config_path=str(path),
                owner_id=skill.owner_id,
                created_at=skill.created_at,
                updated_at=skill.updated_at,
            ))
            stats["skills_migrated"] += 1
        except Exception:
            logger.exception("[resource_migration] skill %s failed", skill.id)
            stats["skipped"] += 1

    result = await db.execute(select(MCPServer))
    for mcp in result.scalars().all():
        if mcp.id in existing_ids:
            stats["skipped"] += 1
            continue
        try:
            path = config_store.save_config("mcp", mcp.id, "json", _mcp_config_text(mcp))
            db.add(Resource(
                id=mcp.id,
                type="mcp",
                name=mcp.name,
                description=mcp.description,
                visibility="private",
                config_format="json",
                config_path=str(path),
                owner_id=mcp.owner_id,
                created_at=mcp.created_at,
                updated_at=mcp.updated_at,
            ))
            stats["mcps_migrated"] += 1
        except Exception:
            logger.exception("[resource_migration] mcp %s failed", mcp.id)
            stats["skipped"] += 1

    await db.commit()
    return stats
