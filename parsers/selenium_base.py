"""Базовый класс для Selenium-парсеров."""
import asyncio
import logging
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

from config import settings

logger = logging.getLogger(__name__)


class SeleniumBaseParser:
    """Базовый класс для парсеров с использованием Selenium."""
    
    def __init__(self) -> None:
        """Инициализация Selenium парсера."""
        self.driver: Optional[webdriver.Chrome] = None
        self._setup_driver()
    
    def _setup_driver(self) -> None:
        """Настройка Chrome WebDriver."""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # Запуск в фоновом режиме
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--user-agent={settings.user_agent}')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(settings.http_timeout)
        except Exception as e:
            logger.error(f"Ошибка при настройке WebDriver: {e}")
            self.driver = None
    
    async def fetch_page_selenium(self, url: str, wait_time: int = 5) -> Optional[str]:
        """
        Получить HTML страницы с помощью Selenium.
        
        Args:
            url: URL страницы для получения
            wait_time: Время ожидания загрузки страницы (в секундах)
        
        Returns:
            Optional[str]: HTML содержимое страницы или None при ошибке
        """
        if not self.driver:
            self._setup_driver()
            if not self.driver:
                return None
        
        try:
            # Запускаем в отдельном потоке, так как Selenium синхронный
            loop = asyncio.get_event_loop()
            html = await loop.run_in_executor(
                None,
                self._fetch_page_sync,
                url,
                wait_time
            )
            return html
        except Exception as e:
            logger.error(f"Ошибка при получении страницы {url} через Selenium: {e}")
            return None
    
    def _fetch_page_sync(self, url: str, wait_time: int) -> Optional[str]:
        """Синхронный метод для получения страницы."""
        try:
            if not self.driver:
                self._setup_driver()
                if not self.driver:
                    return None
            
            self.driver.get(url)
            # Ждем загрузки страницы
            WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Дополнительное ожидание для динамического контента
            import time
            time.sleep(3)  # Увеличиваем время для загрузки динамического контента
            
            # Прокручиваем страницу вниз для загрузки динамического контента (для Kufar и подобных)
            try:
                # Прокручиваем до конца несколько раз, пока не перестанет загружаться контент
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                scrolls = 0
                max_scrolls = 10
                
                while scrolls < max_scrolls:
                    # Прокручиваем вниз
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)  # Ждем загрузки
                    
                    # Проверяем, изменилась ли высота страницы
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        # Высота не изменилась, значит контент больше не загружается
                        break
                    last_height = new_height
                    scrolls += 1
                
                # Возвращаемся наверх
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Ошибка при прокрутке страницы: {e}")
            
            return self.driver.page_source
        except TimeoutException:
            logger.warning(f"Таймаут при загрузке страницы {url}, возвращаем текущий HTML")
            return self.driver.page_source if self.driver else None
        except WebDriverException as e:
            logger.error(f"Ошибка WebDriver при получении {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении {url}: {e}")
            return None
    
    def close(self) -> None:
        """Закрыть WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Ошибка при закрытии WebDriver: {e}")
            finally:
                self.driver = None
    
    def __del__(self) -> None:
        """Деструктор - закрываем WebDriver."""
        self.close()
