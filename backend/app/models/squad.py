from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base


class Squad(Base):
    __tablename__ = "squads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), default="coordinate")
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    leader_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True)
    visibility: Mapped[str] = mapped_column(String(50), default="private")
    tools_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    workspace_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    skills_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    mcp_tools_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    icon: Mapped[str | None] = mapped_column(String(255), nullable=True)
    theme: Mapped[str | None] = mapped_column(String(50), nullable=False, default="dark-emerald")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    members: Mapped[list["SquadMember"]] = relationship("SquadMember", back_populates="squad", lazy="selectin")
