import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Resource(Base):
    """名前・概要・公開範囲のみDB保存し、設定本体はファイルで管理するリソース。

    type: model | system_prompt | rule | skill | mcp | tool | hook | loop
    設定本体は storage/config/<type>/<id>.<json|yaml|py> に保存される。
    """

    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visibility: Mapped[str] = mapped_column(String(50), default="private")
    config_format: Mapped[str] = mapped_column(String(10), nullable=False, default="json")
    config_path: Mapped[str] = mapped_column(String(512), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResourceLink(Base):
    """エージェント/スクワッド/Workflow とリソースの紐付け (Hermes トグル用)。

    parent_type: agent | squad | workflow
    enabled: トグルの ON/OFF
    """

    __tablename__ = "resource_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parent_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    parent_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
