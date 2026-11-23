"""Slow trend-following cbBTC bot for make.fun's btc-race-24h-20261123-0511.

Long only, at most one position, at most one order per batch. Decisions run
on 1-minute closes but only on slow (1-2 hour) returns, so a single noisy
minute never moves it: entry needs a confirmed uptrend, and exit is a slower
trend flip, a stop below the entry cost, or a trailing stop below the
holding's high-water close. Entry and exit thresholds differ (hysteresis),
so the bot does not flip in and out on chop.

Everything is integer math in basis points: no clock, no environment, no
randomness, so two runs on the same bars answer byte for byte alike. The
bot speaks agent-fun/bars-replay/v1 through the kit's Python shim, vendored
unchanged under vendor/.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- Strategy constants (all plain round values; nothing tuned to decimals) ---
FAST_BARS = 60        # fast trend window: 1 hour of closes
SLOW_BARS = 120       # slow trend window: 2 hours of closes
ENTER_FAST_BPS = 100  # enter when the 1-hour return beats +1.00%
ENTER_SLOW_BPS = 100  # ... and the 2-hour return beats +1.00% too
EXIT_SLOW_BPS = -200  # exit on signal when the 2-hour return falls below -2.00%
STOP_BPS = 150        # stop: exit when the close is 1.50% under the entry cost
TRAIL_BPS = 250       # trailing stop: exit 2.50% under the holding's high-water close
COOLDOWN_BARS = 30    # no re-entry for 30 bars after an exit
MAX_SLIP_BPS = 100    # every order caps its fill at 1.00% from the latest close
NO_ENTER_AFTER = 1380  # no new entries in the last 60 bars of the window
PROBE_BAR = 1200      # if nothing has traded by bar 1200, take one small probe
PROBE_CASH_BPS = 1000  # the probe risks 10% of the cash
HISTORY_BARS = 240    # closes kept (twice the slow window)

# --- Run state (plain ints and lists; reset every run) ---
_closes = []
_entry_price = None   # average entry price (price-scale units), cost basis incl. fee
_high_water = None    # highest close since the current entry
_trades = 0           # filled orders seen so far
_last_exit_seq = None  # seq of the last exit order sent (cooldown)
_probe = False        # True while the holding is the guardrail probe (held to the end)


def _ret_bps(bars_back):
    """Return over the last `bars_back` bars in bps, or None without the history."""
    if len(_closes) <= bars_back:
        return None
    old = _closes[-1 - bars_back]
    new = _closes[-1]
    return (new - old) * 10000 // old


def _entry_price_from(state, holding):
    """Average entry price from the position's cost basis (price-scale units)."""
    sym = state.symbols[SYMBOL]
    quote_scale = state.hello["capital"]["quote_scale"]
    num = holding.cost * 10 ** (sym["qty_scale"] + sym["price_scale"])
    den = holding.qty * 10 ** quote_scale
    return num // den


def _buy(state, notional):
    return [{
        "side": "buy",
        "symbol": SYMBOL,
        "notional_quote_units": notional,
        "max_slippage_bps": MAX_SLIP_BPS,
    }]


def _sell_all(state, holding):
    return [{
        "side": "sell",
        "symbol": SYMBOL,
        "qty": holding.qty,
        "max_slippage_bps": MAX_SLIP_BPS,
    }]


def on_batch(state, batch):
    global _entry_price, _high_water, _trades, _last_exit_seq, _probe
    close = state.close(SYMBOL)
    if close is None:
        return []
    _closes.append(close)
    if len(_closes) > HISTORY_BARS:
        del _closes[:-HISTORY_BARS]
    for fill in batch.get("fills", []):
        if fill.get("status") == "filled":
            _trades += 1

    holding = state.positions.get(SYMBOL)
    if holding is not None and holding.qty > 0:
        # The guardrail probe is held to the end of the window: it is small,
        # and selling it would only reopen the door to a full entry on a
        # market that never showed a real uptrend.
        if _probe:
            return []
        if _entry_price is None:
            _entry_price = _entry_price_from(state, holding)
            _high_water = close
        if close > _high_water:
            _high_water = close
        # Stop: the close fell too far under what the position cost.
        if close * 10000 <= _entry_price * (10000 - STOP_BPS):
            _last_exit_seq = state.seq
            return _sell_all(state, holding)
        # Trailing stop: the close gave back too much of the holding's high.
        if close * 10000 <= _high_water * (10000 - TRAIL_BPS):
            _last_exit_seq = state.seq
            return _sell_all(state, holding)
        # Signal exit: the slow trend turned down hard.
        slow = _ret_bps(SLOW_BARS)
        if slow is not None and slow < EXIT_SLOW_BPS:
            _last_exit_seq = state.seq
            return _sell_all(state, holding)
        return []

    _entry_price = None
    _high_water = None
    _probe = False

    # Entry: a confirmed uptrend on both windows, not too late to matter,
    # and not straight after an exit (the cooldown stops flip-flopping).
    if state.seq <= NO_ENTER_AFTER and (_last_exit_seq is None
                                        or state.seq - _last_exit_seq >= COOLDOWN_BARS):
        fast = _ret_bps(FAST_BARS)
        slow = _ret_bps(SLOW_BARS)
        if fast is not None and fast > ENTER_FAST_BPS and (slow is None or slow > ENTER_SLOW_BPS):
            if state.cash > 0:
                return _buy(state, state.cash)

    # Probe: a window that never showed an uptrend still needs one trade to
    # meet the race's guardrail, so risk a small slice late rather than none.
    if state.seq >= PROBE_BAR and _trades == 0 and state.cash > 0:
        _probe = True
        return _buy(state, state.cash * PROBE_CASH_BPS // 10000)

    return []


makefun_bars.run(on_batch)
