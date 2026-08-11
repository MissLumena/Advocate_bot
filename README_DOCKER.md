# Docker run instructions

## 1. Fill .env

```env
TELEGRAM_BOT_TOKEN=your_token_here
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-4o-mini
```

## 2. Build image

```bash
docker build -t advocate-bot .
```

## 3. Run container

```bash
docker run --rm -it --env-file .env advocate-bot
```

## 4. Run with Docker Compose

```bash
docker compose up -d --build
```

## 5. View logs

```bash
docker compose logs -f bot
```
