#!/bin/bash
# Nansen Smart Money Signal Tracker
# Run by OpenClaw agent — commits results to GitHub
# Usage: ./scripts/daily_signals.sh

set -e
TODAY=$(date +%Y-%m-%d)
REPO_DIR="/root/nansen-agent"

echo "=== Nansen Signal Capture: $TODAY ==="

python3 << 'EOF'
import subprocess, json, datetime, os

today = datetime.date.today().isoformat()
chains = ["ethereum", "solana", "base", "arbitrum", "bnb"]
signals = []

for chain in chains:
    try:
        result = subprocess.run(
            ["nansen", "research", "smart-money", "netflow",
             "--chain", chain, "--days", "7",
             "--sort", "net_flow_7d_usd:desc", "--limit", "10"],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(result.stdout)
        if data.get("success"):
            for token in data["data"]["data"]:
                flow = token.get("net_flow_7d_usd", 0)
                if abs(flow) >= 5000:
                    signals.append({
                        "date": today,
                        "chain": chain,
                        "token": token["token_symbol"],
                        "token_address": token.get("token_address", ""),
                        "net_flow_7d_usd": flow,
                        "market_cap_usd": token.get("market_cap_usd", 0),
                        "trader_count": token.get("trader_count", 0),
                        "direction": "BUY" if flow > 0 else "SELL",
                        "score_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
                        "entry_price_usd": None,
                        "exit_price_usd": None,
                        "result": "PENDING"
                    })
    except Exception as e:
        print(f"Error on {chain}: {e}")

os.makedirs("/root/nansen-agent/data", exist_ok=True)
with open(f"/root/nansen-agent/data/signals-{today}.json", "w") as f:
    json.dump(signals, f, indent=2)

print(f"Captured {len(signals)} signals")
EOF

cd $REPO_DIR
git add -A
git commit -m "signal capture: $TODAY ($(git diff --cached --numstat | wc -l) files)" || echo "Nothing to commit"
git push origin main
echo "=== Done ==="
