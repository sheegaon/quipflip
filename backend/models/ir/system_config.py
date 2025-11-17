"""System configuration model for storing dynamic configuration values."""
from backend.models.system_config_base import SystemConfigBase


class IRSystemConfig(SystemConfigBase):
    """System configuration table for dynamic settings."""

    __tablename__ = "ir_system_config"