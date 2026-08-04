# Telegram Career Bot

Минимальный Telegram-бот для карьерного консультирования по заданному промпту.

## Что умеет
- Приветствие по команде /start
- Сброс контекста по команде /reset
- Хранение последних 10 сообщений диалога
- Поддержка OpenAI API через переменные окружения
- Вебхук-эндпоинт для Vercel

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

1. Скопируйте [.env.example](.env.example) в .env
2. Заполните токены
3. Для локального теста запустите:

```bash
python api/telegram.py
```

## Vercel

1. Установите Vercel CLI:

```bash
npm i -g vercel
```

2. В Telegram создайте вебхук:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<your-vercel-app>.vercel.app/api/telegram"
```

3. Разверните проект:

```bash
vercel --prod
```

## Переменные окружения
- TELEGRAM_BOT_TOKEN — токен Telegram-бота
- OPENAI_API_KEY — ключ OpenAI (необязательно, бот будет работать в fallback-режиме)
- OPENAI_MODEL — модель OpenAI, по умолчанию gpt-4o-mini
