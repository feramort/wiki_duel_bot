# 🚀 Развертывание бота на Render.com (Бесплатно 24/7)

Этот проект полностью подготовлен для бесплатного развертывания на **Render.com**.

---

## Вариант 1: Через GitHub (Рекомендуемый)

### Шаг 1. Загрузите проект на GitHub
1. Создайте новый приватный или публичный репозиторий на [GitHub](https://github.com/new) (например, `wiki_duel_bot`).
2. В терминале в папке проекта выполните:
```powershell
git init
git add .
git commit -m "Initial commit for Render"
git branch -M main
git remote add origin https://github.com/ВАШ_ЛОГИН/wiki_duel_bot.git
git push -u origin main
```
*(Файл `.env` с вашим секретным токеном не попадет в репозиторий благодаря `.gitignore`)*

---

### Шаг 2. Разверните на Render.com
1. Зарегистрируйтесь или войдите на [dashboard.render.com](https://dashboard.render.com/).
2. Нажмите **New +** → выберите **Web Service**.
3. Подключите ваш GitHub-репозиторий `wiki_duel_bot`.
4. Render автоматически считает параметры из `render.yaml`:
   - **Name:** `wiki-duel-bot`
   - **Language:** `Python 3`
   - **Region:** `Frankfurt` (ближе к РФ/Европе)
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
   - **Instance Type:** `Free`
5. В разделе **Environment Variables** (Переменные окружения) добавьте переменную:
   - **Key:** `BOT_TOKEN`
   - **Value:** `7745046478:AAE4xwRCDSwU6DeR8LRU-TX-Cw0TZHpU6Pw`
6. Нажмите **Deploy Web Service**!

Через 1-2 минуты бот запустится в облаке Render и будет работать непрерывно!

---

## ⚡ Как сделать, чтобы Render Free не засыпал (24/7 активность)
Бесплатные Web Services на Render могут "засыпать" через 15 минут, если к ним нет входящих HTTP-запросов.

Для этого в [main.py](file:///C:/Users/user/.gemini/antigravity/scratch/wiki_duel_bot/main.py) мы уже добавили мини веб-сервер на маршрутах `/` и `/health`.

Чтобы бот никогда не засыпал:
1. Скопируйте публичный URL вашего сервиса из Render (например: `https://wiki-duel-bot.onrender.com`).
2. Откройте бесплатный сервис мониторинга [cron-job.org](https://cron-job.org/) или [uptimerobot.com](https://uptimerobot.com/).
3. Добавьте задачу с интервалом раз в **10 минут** на адрес:
   `https://wiki-duel-bot.onrender.com/health`

Теперь бот будет бодрствовать 24 часа в сутки, 7 дней в неделю!
