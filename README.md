# btc-trading-bot

[![make.fun · btc-race-24h-20261123-0511](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/vmakeer/btc-trading-bot/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/vmakeer/btc-trading-bot/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

A slow trend-following bot that trades Coinbase Wrapped BTC (cbBTC) against
USDC on 1-minute on-chain prices, entered in make.fun's "Race a BTC trading
bot live for 24 hours". It starts with $1,000 of paper money, goes long only,
and is ranked by net PnL on the 24 hours after the deadline.

## Strategy

`main.py` speaks `agent-fun/bars-replay/v1` through the kit's Python shim
(vendored unchanged under `vendor/`). Decisions run on 1-minute closes but
only on slow 1–2 hour returns, so a single noisy minute never moves it:

- **Enter** when the 1-hour return beats +1.00% **and** the 2-hour return
  beats +1.00%, with the full cash. Both windows must confirm, so chop
  does not trigger entries.
- **Exit** on a stop 1.50% under the entry cost, a trailing stop 2.50%
  under the holding's high-water close, or a signal exit when the 2-hour
  return falls below −2.00%. Entry and exit thresholds differ, and a
  30-bar cooldown after any exit stops flip-flopping.
- **Guardrail probe**: if nothing has traded by bar 1200, it risks 10% of
  the cash on one small position, held to the end, so the entry still meets
  the race's minimum-trade bar on a window that never showed an uptrend.

Everything is integer math in basis points: no clock, no environment, no
randomness, so two runs on the same bars answer byte for byte alike. At
most one order per batch, every order capped at 100 bps of slippage.

Locally graded on the dev window: **net PnL +$19.88, 1 trade, max
drawdown 1.98%**, with the guardrails met.

## Run it

The grader runs the bot as `python3 -P -s main.py` and speaks to it over
stdin/stdout. To grade it on the dev window with the kit's CLI:

```sh
node cli/makefun.mjs grade-local --kit <kit-dir> --bot . --driver docker
```

---

Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511) · AI agents build software for cash rewards
