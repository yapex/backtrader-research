"""Portfolio value tracker — backtrader Analyzer.

SRP: Solely responsible for recording daily portfolio state.
"""

from __future__ import annotations

import backtrader as bt
import pandas as pd


class Tracker(bt.Analyzer):
    """Records daily portfolio value and deposit events from Strategy.trade_log."""

    def __init__(self):
        self.values: list[float] = []
        self.dates: list = []
        self.total_deposited: float = 0.0
        self.deposit_dates: list = []
        self.deposit_amounts: list = []
        self._last_count: int = 0

    def next(self):
        self.values.append(self.strategy.broker.getvalue())
        self.dates.append(self.strategy.datas[0].datetime.date(0))
        trade_log = getattr(self.strategy, "trade_log", [])
        new = trade_log[self._last_count :]
        for t in new:
            if t["type"] == "deposit":
                self.total_deposited += t["amount"]
                self.deposit_dates.append(t["date"])
                self.deposit_amounts.append(t["amount"])
        self._last_count = len(trade_log)

    def get_analysis(self):
        return {
            "value": pd.Series(self.values, index=self.dates),
            "total_deposited": self.total_deposited,
            "deposit_dates": self.deposit_dates,
            "deposit_amounts": self.deposit_amounts,
        }
