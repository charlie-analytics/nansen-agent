# 🧠 Nansen Smart Money Signal Accuracy Tracker

> *Are "smart money" wallets actually smart? We're finding out.*

This repository is a live, verifiable proof-of-work experiment powered by the **Nansen CLI** and an **OpenClaw AI agent**.

## What This Does

Most on-chain tools show you *what* smart money is buying. Nobody asks the harder question: **are they actually right?**

This project:
1. **Records** every significant smart money accumulation signal from Nansen (weekly)
2. **Tags** each signal with the token price at time of recording
3. **Scores** each signal 30 days later — did the price go up or down?
4. **Ranks** Nansen wallet labels by actual track record (win rate, avg return)
5. **Publishes** a live leaderboard of signal quality

## Repository Structure

```
nansen-agent/
├── reports/          ← Weekly smart money signal reports (markdown)
├── data/             ← Raw signal snapshots (JSON) with entry prices
├── leaderboard/      ← Scored results: who was right, who was wrong
└── scripts/          ← Query scripts run by the AI agent
```

## Leaderboard

| Wallet Label | Signals Tracked | Win Rate | Avg Return (30d) |
|---|---|---|---|
| *(building...)*  | — | — | — |

*Updated weekly. Win = token up >5% from signal date. Loss = down >5%.*

## Methodology

- **Chain coverage:** Ethereum, Solana, Base, Arbitrum, BNB
- **Signal threshold:** Net inflow >$10K USD from labeled wallets in 7-day window
- **Scoring:** Price at signal date vs price 30 days later (CoinGecko data)
- **Labels tracked:** Smart Trader, Token Millionaire, Fund, 30D/90D/180D Smart Trader

## Powered By

- [Nansen CLI](https://docs.nansen.ai) — on-chain intelligence
- [OpenClaw](https://openclaw.ai) — AI agent automation
- Queries run automatically, results committed to this repo

---

*First signal batch: 2026-03-18 | Data is for research purposes only, not financial advice.*
