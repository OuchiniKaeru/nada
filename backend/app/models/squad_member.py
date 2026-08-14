from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base


class SquadMember(Base):
    __tablename__ = "squad_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    squad_id: Mapped[str] = mapped_column(String(36), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    squad: Mapped["Squad"] = relationship("Squad", back_populates="members")
