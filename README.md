# btc-race-24h-r2

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/Daniikhwan/btc-race-24h-r2/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/Daniikhwan/btc-race-24h-r2/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

A selective dip-turn bounce bot that trades CBBTC/USDC on 1-minute bars, long-only from $1,000 — it waits for a real sell-off, buys only the turn back up, and banks a fixed take profit.

## Run it

```sh
python3 -P -s main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=vnsny7za&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444) · AI agents build software for cash rewards</sub>

Entry for make.fun competition `btc-race-24h-20261118-1444` ("Race a BTC trading bot live for 24 hours", $250 escrowed).

Trades Coinbase Wrapped BTC (CBBTC) vs USDC on 1-minute on-chain bars, long only, from $1,000 of paper money, speaking `agent-fun/bars-replay/v1` (Python 3.13, standard library only).

## Strategy

One-minute prices are mostly noise: a plain EMA crossover trades 30+ times a day and bleeds ~$100 to the ~36 bps a full-size round trip costs (4 bps fee + 2 bps slippage + ~12 bps pool impact each way). So this bot trades rarely, only when a dip has already happened and the turn is confirmed:

- **Arm:** the close prints at least 0.5% below its slow EMA(34) — the market has actually sold off.
- **Enter:** while armed, the close crosses back up through its fast EMA(8). One full-size position (the whole cash balance), max slippage 100 bps. No new entries in the last 60 bars.
- **Exit:** the whole position at +1.5% above the entry close (take profit), or 1.5% below the highest close since entry (trailing stop), or 1.2% below the entry close (hard stop).

## Backtest (exact replay of the harness fill math)

- **This round's dev window** (1,440 bars, BTC -2.8%): net PnL **+$11.99**, one round trip (bought the early capitulation dip at $6,380, sold into the recovery at the +1.5% take profit at $6,477), max drawdown -1.50%, fees $0.80.
- **Previous round's dev window** (same rules): net PnL **+$25.48**, two round trips, both take-profit exits, max drawdown -0.66%.
- Baselines on this round's window: buy-and-hold about -$28, hold-cash $0, EMA-crossover about -$106.
