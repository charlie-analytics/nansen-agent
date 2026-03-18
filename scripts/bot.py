#!/usr/bin/env python3
"""
@charliebic Telegram Bot
- /start → sends latest snapshot from GitHub repo
- All other messages → polite redirect, no queries fired
- Zero Nansen credits used by users
"""
import os
import json
import glob
import asyncio
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7938176049:AAFYUdTQaOJLX7_e7cvfs-WRyBfNUgYzsJ4")
REPO_DIR = "/root/nansen-agent"
SUBSCRIBERS_FILE = "/root/.nansen-agent/subscribers.json"

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
    # Keep first 60 lines — covers the key signals
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
    # Telegram has 4096 char limit
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
    """Handle any other message — no queries, no token burn."""
    await update.message.reply_text(
        "📡 This bot delivers daily smart money signals — no live queries.\n\n"
        "New signals drop every day at *10pm IST*.\n"
        "Use /latest to see today's snapshot.\n\n"
        "Full data & history: github.com/charlie-analytics/nansen-agent",
        parse_mode="Markdown"
    )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("latest", latest))
    app.add_handler(MessageHandler(filters.ALL, catch_all))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
