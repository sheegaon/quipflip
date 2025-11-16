"""System configuration model for storing dynamic configuration values."""
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from backend.database import Base


class SystemConfig(Base):
    """System configuration table for dynamic settings."""

    __tablename__ = "qf_system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'int', 'float', 'string', 'bool'
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 'economics', 'timing', 'validation', 'ai'
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)  # player_id

    def __repr__(self) -> str:
        return f"<SystemConfig(key={self.key}, value={self.value}, type={self.value_type})>"
