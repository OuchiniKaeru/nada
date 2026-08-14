from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
import enum
from app.core.database import Base


class Visibility(str, enum.Enum):
    public = "public"
    private = "private"
    ad_group = "ad_group"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    visibility: Mapped[Visibility] = mapped_column(String(20), nullable=False, default=Visibility.private)
    ad_group: Mapped[str | None] = mapped_column(String(255),  nullable=True)
    mcp_server_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("mcp_servers.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    mcp_server_ids: Mapped[list[str]] = mapped_column(JSON, nullable=True, default=list)
    skill_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tools_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    workspace_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    skills_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    mcp_tools_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    icon: Mapped[str | None] = mapped_column(String(255), nullable=True)
    theme: Mapped[str | None] = mapped_column(String(50), nullable=False, default="dark-emerald")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
