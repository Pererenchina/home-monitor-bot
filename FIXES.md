# Исправленные ошибки

## Дата: 20 января 2026

### Ошибка 1: TypeError в ReplyKeyboardMarkup ✅ ИСПРАВЛЕНО

**Проблема:**
```
TypeError: ReplyKeyboardMarkup.__init__() got an unexpected keyword argument 'persistent'
```

**Причина:**
Параметр `persistent` не поддерживается в версии python-telegram-bot 20.7

**Исправление:**
Удален параметр `persistent=True` из функции `get_main_keyboard()` в файле `bot/utils/keyboard.py`

**Было:**
```python
return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, persistent=True)
```

**Стало:**
```python
return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
```

### Ошибка 2: Отсутствие обработчика ошибок ✅ ДОБАВЛЕНО

**Проблема:**
Ошибки не обрабатывались должным образом, что приводило к неинформативным сообщениям в логах.

**Исправление:**
Добавлен глобальный обработчик ошибок в `bot/main.py` для корректной обработки исключений.

## Статус

✅ Все ошибки исправлены
✅ Бот работает без ошибок
✅ Логи записываются корректно
