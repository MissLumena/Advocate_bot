import os
from typing import Dict, List

import requests
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

app = Flask(__name__)

SYSTEM_PROMPT = """Ты — Senior Career Advocate и жесткий карьерный стратег из агентства JobMatch Pro.
Твоя аудитория — IT-специалисты и менеджеры Middle+/Senior. Ты работаешь исключительно на кандидата, помогая ему выбить максимальный оффер и избежать токсичных мест.

Задачи:
- Вскрывать скрытые боли работодателя из текста вакансии.
- Улучшать резюме под ATS-фильтры.
- Готовить сценарии переговоров по ЗП.
- Писать 3 варианта ответов рекрутеру: агрессивный, умеренный, лояльный.

Тон:
- Деловой, напористый, слегка циничный к рекрутерам, но лояльный к кандидату.
- Без воды, только готовые речевые скрипты.
"""

chat_histories: Dict[int, List[Dict[str, str]]] = {}

requests.post(
    f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendChatAction",
    json={"chat_id": chat_id, "action": "typing"},
    timeout=5,
)

def build_reply(user_text: str, history: List[Dict[str, str]] | None = None) -> str:
    history = history or []
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            client = OpenAI(api_key=api_key)
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": user_text}]
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                temperature=0.3,
                max_tokens=300,
            )
            content = response.choices[0].message.content
            return content.strip() if content else "Коротко: нужен более точный запрос."
        except Exception:
            pass

    if "зарп" in user_text.lower():
        return "Для точной вилки мне нужны город и стек. Напишите, в каком городе и на какой роли вы торгуетесь — я дам рабочий диапазон."
    if "вакан" in user_text.lower():
        return "Отправьте текст вакансии. Я разберу скрытые боли работодателя, выделю риски и дам готовый ответ рекрутеру."
    if "резюме" in user_text.lower() or "cv" in user_text.lower():
        return "Пришлите текущее резюме или краткий список опыта — я подготовлю ATS-оптимизированную версию."
    return "Отправьте вакансию, резюме или вопрос — и я дам готовый разбор, скрипт переговоров или ответ рекрутеру."


def send_telegram_message(chat_id: int, text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except Exception:
        return False


@app.route('/api/telegram', methods=['POST'])
def telegram_webhook():
    payload = request.get_json(silent=True) or {}
    if not payload.get('message'):
        return jsonify({"ok": True})

    message = payload['message']
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '').strip()
    if not chat_id or not text:
        return jsonify({"ok": True})

    if text == '/start':
        reply_text = "Привет. Я карьерный стратег для IT и менеджеров. Отправьте вакансию, резюме или вопрос — и я дам готовый разбор, скрипт переговоров или ответ рекрутеру."
    elif text == '/reset':
        chat_histories[chat_id] = []
        reply_text = "Контекст очищен. Можно начинать заново."
    else:
        history = chat_histories.get(chat_id, [])
        history.append({"role": "user", "content": text})
        history = history[-10:]
        chat_histories[chat_id] = history
        reply_text = build_reply(text, history)
        history.append({"role": "assistant", "content": reply_text})
        chat_histories[chat_id] = history[-10:]

    send_telegram_message(chat_id, reply_text)
    return jsonify({"ok": True, "reply": reply_text, "chat_id": chat_id})


@app.route('/')
def home():
    return "Telegram bot is running"


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
