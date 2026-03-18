#!/usr/bin/env python3
"""
@charliebic Telegram Bot
- /start → sends latest snapshot from GitHub repo
- /latest → same as /start
- Freeform messages → AI chat for owner only, silent for everyone else
"""
import os
import json
import glob
import asyncio
import anthropic
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7938176049:AAFYUdTQaOJLX7_e7cvfs-WRyBfNUgYzsJ4")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
REPO_DIR = "/root/nansen-agent"
SUBSCRIBERS_FILE = "/root/.nansen-agent/subscribers.json"
OWNER_IDS = {5544932741}  # Charlie

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE) as f:
            return json.load(f)
    return []

def save_subscriber(chat_id):
    subs = load_subscribers()
    if chat_id not in subs:
        subs.append(chat_id)
        os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)
        with open(SUBSCRIBERS_FILE, "w") as f:
            json.dump(subs, f)

def get_latest_snapshot():
    """Read the most recent report from the repo."""
    reports = sorted(glob.glob(f"{REPO_DIR}/reports/*.md"), reverse=True)
    if not reports:
        return None, None
    latest = reports[0]
    date = Path(latest).stem
    with open(latest) as f:
        content = f.read()
    return date, content

def format_for_telegram(content, date):
    """Trim the markdown report for Telegram (keep key tables, cut fluff)."""
    lines = content.split("\n")
    trimmed = "\n".join(lines[:60])
    return f"📊 *Latest Signal Snapshot — {date}*\n\n{trimmed}\n\n_Next update: daily at 10pm IST_"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_subscriber(chat_id)

    date, content = get_latest_snapshot()
    if not content:
        await update.message.reply_text(
            "👋 Welcome to @charliebic — Smart Money Signal Bot by Charlie (BeInCrypto).\n\n"
            "No snapshot available yet. Check back after 10pm IST today!"
        )
        return

    msg = format_for_telegram(content, date)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n_...truncated. Full data: github.com/charlie-analytics/nansen-agent_"

    await update.message.reply_text(
        f"👋 Welcome! Here's the latest smart money snapshot:\n\n{msg}",
        parse_mode="Markdown"
    )

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Same as /start — show latest snapshot."""
    await start(update, context)

async def catch_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Freeform chat — owner gets Claude AI, everyone else gets silence."""
    if not update.effective_user or update.effective_user.id not in OWNER_IDS:
        return

    user_message = update.message.text
    if not user_message:
        return

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system="You are a helpful assistant for Charlie, a crypto analyst at BeInCrypto. You have context about Nansen smart money signals and on-chain analytics. Be concise and useful.",
            messages=[{"role": "user", "content": user_message}]
        )
        reply = response.content[0].text
        # Telegram 4096 char limit
        if len(reply) > 4000:
            reply = reply[:4000] + "\n\n_...truncated_"
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("latest", latest))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_all))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
