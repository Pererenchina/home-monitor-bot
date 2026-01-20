"""Парсеры для различных сайтов объявлений."""
from .onliner import OnlinerParser
from .kufar import KufarParser
from .realt import RealtParser

__all__ = ['OnlinerParser', 'KufarParser', 'RealtParser']
