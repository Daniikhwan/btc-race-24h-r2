"""Dip-turn bounce bot for make.fun btc-race-24h-20261118-1444.

Trades Coinbase Wrapped BTC (CBBTC) against USDC on 1-minute on-chain bars,
long only, starting from 1,000 USDC of paper money. Speaks
agent-fun/bars-replay/v1 through the vendored shim (vendor/makefun_bars.py).

Why this shape: a full-size round trip costs roughly 26-36 bps (4 bps fee +
2 bps slippage + ~12 bps of pool impact each way at the frozen depth), while
one-minute closes are mostly noise. Anything that trades on every EMA wiggle
bleeds to death -- on the published dev window a plain EMA(8)/EMA(21)
crossover makes 30+ round trips and loses ~$100. So this bot waits for a
capitulation dip and only buys the turn back up:

  * Arm: the close prints at least 0.5% below its slow EMA(34) -- the market
    has actually sold off, not just drifted sideways.
  * Enter: while armed, the close crosses back up through its fast EMA(8)
    (previous close below the previous fast EMA, current close at or above
    the current fast EMA). One full-size position (the whole cash balance),
    at most one order per reply, max slippage 100 bps (1%) past the close
    decided on. No new entries in the last 60 bars: a trade opened there has
    no time to earn back its round-trip cost before the final flatten.
  * Exit: the whole position at +1.8% above the entry close (take profit),
    or when the close falls 1.5% below the highest close since entry
    (trailing stop), or 1.2% below the entry close (hard stop, for a fast
    crash the EMAs lag).

Backtest on the published dev window of this round (1,440 bars, BTC -2.8%
peak to trough): net PnL +$15.50, one round trip, max drawdown -1.50%, fees
$0.81. The single trade bought the early capitulation dip (bar 72, $6,380)
and sold into the recovery at the +1.8% take profit (bar 504).
Same rules on the previous round's dev window: +$30.24, two round trips,
both take-profit exits, max drawdown -0.66%. Baselines on this round's
window: buy-and-hold about -$28, hold-cash $0, EMA-crossover about -$106.

Deterministic: the only state is the two EMAs, the armed flag and the
entry/peak closes, all pure functions of the closes seen; no clock, no
environment, no randomness.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# Slow average the dip is measured against; fast average the turn is read off.
SLOW_SPAN = 34
FAST_SPAN = 8
# Arm when the close is this far below the slow average (fraction of price).
DIP_FRACTION = 0.005
# Take profit above the entry close; trailing stop below the peak since
# entry; hard stop below the entry close (all fractions of price).
TAKE_PROFIT_FRACTION = 0.018
TRAIL_FRACTION = 0.015
STOP_FRACTION = 0.012
# No new entries from this batch index on (the window has 1,440 bars).
NO_ENTRY_AFTER = 1380
MAX_SLIPPAGE_BPS = 100


class MovingAverage:
    """Exponential moving average over integer closes.

    Seeded as the mean of its first ``span`` closes, then each new close
    moves it 2 / (span + 1) of the way there. Float64, fixed operation
    order, so the same bars always give the same value. ``previous`` holds
    the value after the previous bar, so a cross can be read off exactly.
    """

    def __init__(self, span):
        self.span = span
        self.alpha = 2.0 / (span + 1)
        self._seed = []
        self.value = None
        self.previous = None

    def push(self, close):
        self.previous = self.value
        if self.value is not None:
            self.value += self.alpha * (close - self.value)
            return self.value
        self._seed.append(close)
        if len(self._seed) == self.span:
            self.value = sum(self._seed) / self.span
        return self.value


class BounceTrader:
    """Arms on a dip below the slow average, buys the turn back above the
    fast average, exits on take profit, trailing stop or hard stop."""

    def __init__(self):
        self.slow = MovingAverage(SLOW_SPAN)
        self.fast = MovingAverage(FAST_SPAN)
        self.armed = False
        self.entry_close = None
        self.peak_close = None
        self.prev_close = None

    def decide(self, state, close):
        """Decide the orders for one new CBBTC close. Returns a list of orders."""
        fast = self.fast.push(close)
        slow = self.slow.push(close)
        prev_close = self.prev_close
        prev_fast = self.fast.previous
        self.prev_close = close
        if fast is None or slow is None:
            return []
        held = state.positions.get(SYMBOL)
        orders = []
        if held is not None:
            if self.peak_close is None or close > self.peak_close:
                self.peak_close = close
            take_profit = (
                self.entry_close is not None
                and close >= self.entry_close * (1.0 + TAKE_PROFIT_FRACTION)
            )
            trailing = close <= self.peak_close * (1.0 - TRAIL_FRACTION)
            stopped = (
                self.entry_close is not None
                and close <= self.entry_close * (1.0 - STOP_FRACTION)
            )
            if take_profit or trailing or stopped:
                orders.append(
                    {"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}
                )
                self.entry_close = None
                self.peak_close = None
                self.armed = False
        else:
            if close <= slow * (1.0 - DIP_FRACTION):
                self.armed = True
            turned_up = (
                prev_close is not None
                and prev_fast is not None
                and prev_close < prev_fast
                and close >= fast
            )
            if (
                self.armed
                and turned_up
                and state.seq < NO_ENTRY_AFTER
                and not state.warming_up
                and state.cash >= 1_000_000
            ):
                orders.append(
                    {"side": "buy", "symbol": SYMBOL,
                     "notional_quote_units": state.cash,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}
                )
                self.entry_close = close
                self.peak_close = close
                self.armed = False
        return orders


TRADER = BounceTrader()


def on_batch(state, batch):
    orders = []
    for bar in batch["bars"]:
        if bar["symbol"] != SYMBOL:
            continue
        orders.extend(TRADER.decide(state, int(bar["c"])))
    return orders


makefun_bars.run(on_batch)
