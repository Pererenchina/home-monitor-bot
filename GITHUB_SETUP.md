# Инструкция по загрузке проекта в GitHub

## Шаг 1: Создайте репозиторий на GitHub

1. Перейдите на [GitHub](https://github.com)
2. Нажмите кнопку **"+"** в правом верхнем углу → **"New repository"**
3. Заполните форму:
   - **Repository name**: `bot_arenda` (или любое другое имя)
   - **Description**: "Telegram bot for filtering apartment rental listings from Onliner, Kufar, and Realt.by"
   - Выберите **Public** или **Private**
   - **НЕ** ставьте галочки на "Add a README file", "Add .gitignore", "Choose a license" (все уже есть)
4. Нажмите **"Create repository"**

## Шаг 2: Подключите локальный репозиторий к GitHub

После создания репозитория GitHub покажет инструкции. Выполните команды:

```bash
# Добавьте удаленный репозиторий (замените YOUR_USERNAME на ваш GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/bot_arenda.git

# Переименуйте ветку в main (если нужно)
git branch -M main

# Загрузите код в GitHub
git push -u origin main
```

## Альтернативный способ (через SSH)

Если у вас настроен SSH ключ:

```bash
git remote add origin git@github.com:YOUR_USERNAME/bot_arenda.git
git branch -M main
git push -u origin main
```

## Проверка

После выполнения команд ваш код будет загружен на GitHub. Проверьте:
- Откройте ваш репозиторий на GitHub
- Убедитесь, что все файлы загружены
- README.md должен отображаться на главной странице

## Дополнительные команды

Если нужно обновить код на GitHub после изменений:

```bash
git add .
git commit -m "Описание изменений"
git push
```
