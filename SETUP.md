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

## 6. Enable RAG (optional)

1. Create the `document_chunks` table and `match_document_chunks` function by running [supabase_schema.sql](supabase_schema.sql) in Supabase SQL Editor.
2. Add `OPENAI_API_KEY`, `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to `.env`. The OpenAI key is used only for `text-embedding-3-small` embeddings; chat can continue using DeepSeek.
3. Put Markdown documents with YAML frontmatter under `knowledge/` and run:

```bash
python reindex.py
```

Reindexing is safe to repeat. It replaces all chunks for changed files and removes chunks for deleted files. Without complete RAG variables, the bot keeps its existing non-RAG behavior.
