# Setup guide

## 1. Fill .env

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

## 2. Run locally

```bash
python bot.py
```

## 3. Run with Docker

```bash
docker build -t advocate-bot .
docker run --rm -it --env-file .env advocate-bot
```

## 4. Run with Docker Compose

```bash
docker compose up -d --build
docker compose logs -f bot
```

## 5. Configure Telegram webhook

If you deploy behind a public URL:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://your-domain.example/bot"
```

For local testing you can leave polling mode enabled.
