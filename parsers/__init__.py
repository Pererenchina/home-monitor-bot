"""Парсеры для различных сайтов объявлений."""
from .onliner import OnlinerParser
from .kufar import KufarParser
from .realt import RealtParser
from .domovita import DomovitaParser

__all__ = ['OnlinerParser', 'KufarParser', 'RealtParser', 'DomovitaParser']
