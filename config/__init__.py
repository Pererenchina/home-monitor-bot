"""Конфигурация приложения."""
from .settings import Settings

__all__ = ['Settings', 'settings']

# Глобальный экземпляр настроек
settings = Settings()
