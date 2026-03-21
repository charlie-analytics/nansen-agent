#!/usr/bin/env python3
"""
@charliebic Telegram Bot
- /start      → latest Nansen snapshot
- /latest     → same as /start
- /status     → ping all integrations
- /dune       → Solana DEX activity (last 30d) via Dune
- /defillama  → Top Solana protocols by TVL via DefiLlama
- Freeform    → Claude AI chat (owner only)
"""
import os
import json
import glob
import time
import requests
import anthropic
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

BOT_TOKEN        = os.environ.get("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
DUNE_API_KEY     = os.environ.get("DUNE_API_KEY")

REPO_DIR         = "/root/nansen-agent"
SUBSCRIBERS_FILE = "/root/.nansen-agent/subscribers.json"
OWNER_IDS        = {5544932741}  # Charlie

# Known public Dune query: Solana daily DEX volume (by ilemi)
DUNE_SOLANA_DEX_QUERY = 2844701


# ── helpers ──────────────────────────────────────────────────────────────────

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
    reports = sorted(glob.glob(f"{REPO_DIR}/reports/*.md"), reverse=True)
    if not reports:
        return None, None
    latest = reports[0]
    date = Path(latest).stem
    with open(latest) as f:
        content = f.read()
    return date, content

def format_for_telegram(content, date):
    lines = content.split("\n")
    trimmed = "\n".join(lines[:60])
    return f"📊 *Latest Signal Snapshot — {date}*\n\n{trimmed}\n\n_Next update: daily at 10pm IST_"


# ── status checks ─────────────────────────────────────────────────────────────

def check_nansen() -> str:
    try:
        result = os.popen("nansen account 2>&1").read().strip()
        data = json.loads(result.split("\n")[0])
        if data.get("success"):
            credits = data["data"]["credits_remaining"]
            plan = data["data"]["plan"]
            return f"✅ Nansen — {plan} plan, {credits:,} credits"
        return "❌ Nansen — unexpected response"
    except Exception as e:
        return f"❌ Nansen — {e}"

def check_dune() -> str:
    if not DUNE_API_KEY:
        return "⚠️ Dune — no API key set"
    try:
        r = requests.get(
            "https://api.dune.com/api/v1/query/1/results",
            headers={"X-DUNE-API-KEY": DUNE_API_KEY},
            timeout=5
        )
        if r.status_code in (401, 403):
            return "❌ Dune — invalid API key"
        return "✅ Dune — API key valid"
    except Exception as e:
        return f"❌ Dune — {e}"

def check_defillama() -> str:
    try:
        r = requests.get("https://api.llama.fi/protocols", timeout=5)
        if r.status_code == 200:
            count = len(r.json())
            return f"✅ DefiLlama — reachable ({count} protocols indexed)"
        return f"❌ DefiLlama — HTTP {r.status_code}"
    except Exception as e:
        return f"❌ DefiLlama — {e}"

def check_claude() -> str:
    if not ANTHROPIC_API_KEY:
        return "⚠️ Claude — no API key set"
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=5,
            messages=[{"role": "user", "content": "hi"}]
        )
        return "✅ Claude — API key valid"
    except Exception as e:
        return f"❌ Claude — {e}"


# ── dune: solana dex activity ─────────────────────────────────────────────────

def dune_execute_and_wait(query_id: int, timeout: int = 60) -> dict | None:
    """Execute a Dune query and poll until done."""
    headers = {"X-DUNE-API-KEY": DUNE_API_KEY, "Content-Type": "application/json"}

    # Trigger execution
    r = requests.post(
        f"https://api.dune.com/api/v1/query/{query_id}/execute",
        headers=headers, json={}, timeout=10
    )
    if r.status_code != 200:
        return None
    exec_id = r.json().get("execution_id")

    # Poll for results
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(5)
        r = requests.get(
            f"https://api.dune.com/api/v1/execution/{exec_id}/results?limit=35",
            headers=headers, timeout=10
        )
        data = r.json()
        if data.get("is_execution_finished"):
            return data.get("result", {}).get("rows", [])
    return None

def dune_latest_results(query_id: int) -> list | None:
    """Try to get cached results first, fall back to executing."""
    headers = {"X-DUNE-API-KEY": DUNE_API_KEY}
    r = requests.get(
        f"https://api.dune.com/api/v1/query/{query_id}/results?limit=35",
        headers=headers, timeout=10
    )
    data = r.json()
    if "result" in data and data["result"].get("rows"):
        return data["result"]["rows"]
    # No cached results — execute fresh
    return dune_execute_and_wait(query_id)


# ── defillama: solana protocols ───────────────────────────────────────────────

def get_solana_tvl_change() -> str:
    """Fetch Solana chain TVL history and compute 30d change."""
    try:
        r = requests.get("https://api.llama.fi/v2/historicalChainTvl/Solana", timeout=10)
        data = r.json()
        if not data:
            return "No TVL data available."

        # Get last 30 days
        now = int(time.time())
        thirty_days_ago = now - (30 * 86400)
        recent = [d for d in data if d["date"] >= thirty_days_ago]

        if len(recent) < 2:
            return "Not enough data for 30d comparison."

        tvl_now   = recent[-1]["tvl"]
        tvl_start = recent[0]["tvl"]
        change    = ((tvl_now - tvl_start) / tvl_start) * 100
        arrow     = "📈" if change >= 0 else "📉"

        lines = [
            f"*Solana TVL — 30d Change*",
            f"{arrow} {change:+.1f}%",
            f"Now:   ${tvl_now/1e9:.2f}B",
            f"30d ago: ${tvl_start/1e9:.2f}B",
            ""
        ]

        # Top Solana protocols by TVL
        r2 = requests.get("https://api.llama.fi/protocols", timeout=10)
        protocols = r2.json()
        solana_protos = [
            p for p in protocols
            if "Solana" in (p.get("chains") or []) and p.get("tvl", 0) > 0
        ]
        solana_protos.sort(key=lambda x: x.get("tvl", 0), reverse=True)

        lines.append("*Top 10 Solana Protocols by TVL:*")
        for i, p in enumerate(solana_protos[:10], 1):
            tvl = p.get("tvl", 0)
            change1d = p.get("change_1d") or 0
            arrow2 = "🟢" if change1d >= 0 else "🔴"
            lines.append(f"{i}. *{p['name']}* — ${tvl/1e6:.0f}M {arrow2}{change1d:+.1f}%")

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching DefiLlama data: {e}"


def get_solana_dex_dune() -> str:
    """Pull Solana DEX volume from Dune (30d)."""
    if not DUNE_API_KEY:
        return "⚠️ Dune API key not set."

    try:
        rows = dune_latest_results(DUNE_SOLANA_DEX_QUERY)
        if not rows:
            return "⚠️ No data returned from Dune. Query may still be running — try again in 30s."

        # Try to detect volume column
        vol_col = next((k for k in rows[0] if "volume" in k.lower() or "amount" in k.lower()), None)
        date_col = next((k for k in rows[0] if "day" in k.lower() or "date" in k.lower() or "month" in k.lower()), None)

        if not vol_col or not date_col:
            # Fallback: just show raw columns and first few rows
            cols = list(rows[0].keys())
            lines = [f"*Dune Query #{DUNE_SOLANA_DEX_QUERY} — Raw Data*", f"Columns: {', '.join(cols)}", ""]
            for row in rows[:10]:
                lines.append(str(row))
            return "\n".join(lines)

        total = sum(r.get(vol_col, 0) or 0 for r in rows)
        lines = [
            f"*Solana DEX Activity — Last 30d (Dune)*",
            f"Total volume: ${total/1e9:.2f}B",
            "",
            "*Daily breakdown (recent 10 days):*"
        ]
        for row in rows[:10]:
            d = str(row.get(date_col, "?"))[:10]
            v = row.get(vol_col, 0) or 0
            lines.append(f"• {d}: ${v/1e6:.0f}M")

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching Dune data: {e}"


# ── handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_subscriber(chat_id)

    date, content = get_latest_snapshot()
    if not content:
        await update.message.reply_text(
            "👋 Welcome to @charliebic — Smart Money Signal Bot by Charlie (BeInCrypto).\n\n"
            "No snapshot available yet. Check back after 10pm IST today!\n\n"
            "Commands: /status /dune /defillama"
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
    await start(update, context)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Checking integrations...")
    date, _ = get_latest_snapshot()
    report_line = f"📁 Latest report: `{date}`" if date else "⚠️ Reports — no snapshots found"
    lines = [
        "🛠 *Integration Status*\n",
        check_nansen(),
        check_dune(),
        check_defillama(),
        check_claude(),
        "",
        report_line,
        "",
        "_Commands: /dune /defillama /latest_"
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def dune_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching Solana DEX data from Dune (may take ~30s)...")
    msg = get_solana_dex_dune()
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n_...truncated_"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def defillama_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching Solana TVL from DefiLlama...")
    msg = get_solana_tvl_change()
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n_...truncated_"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def catch_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        if len(reply) > 4000:
            reply = reply[:4000] + "\n\n_...truncated_"
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("latest",     latest))
    app.add_handler(CommandHandler("status",     status))
    app.add_handler(CommandHandler("dune",       dune_cmd))
    app.add_handler(CommandHandler("defillama",  defillama_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_all))
    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
