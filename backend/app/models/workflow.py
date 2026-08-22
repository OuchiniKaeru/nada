import uuid
from datetime import datetime

from sqlalchemy import JSON, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Workflow(Base):
    """エージェント/スクワッドを順次実行する Workflow。

    steps: [{"kind": "agent"|"squad", "ref_id": "...", "prompt_template": "..."}]
    実行時、前ステップの出力を次の入力へ単純連結する。
    """

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visibility: Mapped[str] = mapped_column(String(50), default="private")
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
