"""
Trading strategy - Agent modifies this file

engine.py injects research.yaml config into Strategy._config:
  - _config["tickers"]  e.g. ["SPY", "TLT"]
  - _config["weights"]  e.g. {"SPY": 0.5, "TLT": 0.5}
  - _config["roles"]    e.g. {"SPY": "equity", "TLT": "bond"}

You can change anything: params, indicators, buy/sell logic, position sizing.
Only requirement: define a class called Strategy that inherits bt.Strategy.
"""

import backtrader as bt


class Strategy(bt.Strategy):
    """再平衡策略 + 可选止损。"""

    params = (
        ("stock_weight", 0.5),
        ("bond_weight", 0.5),
        ("rebalance_freq", "quarterly"),
        ("stop_loss", None),
        ("stop_loss_mode", "rebalance"),
    )

    def __init__(self):
        cfg = self._config
        self.equity = self.datas[0]
        self.bond = self.datas[1]

        self.last_quarter = None
        self.last_month = None
        self.last_year = None
        self.entry_price = None
        self.stopped_out = False
        self._initial_value = None

    @property
    def today(self):
        return self.datas[0].datetime.date(0)

    def _should_rebalance(self):
        d = self.today
        freq = self.params.rebalance_freq
        if freq == "monthly":
            if self.last_month is None:
                return True
            return d.month != self.last_month
        elif freq == "quarterly":
            if self.last_quarter is None:
                return True
            return (d.month - 1) // 3 != self.last_quarter
        elif freq == "yearly":
            if self.last_year is None:
                return True
            return d.year != self.last_year
        return False

    def _do_rebalance(self):
        if self.stopped_out:
            self.stopped_out = False
        self.order_target_percent(self.equity, self.params.stock_weight)
        self.order_target_percent(self.bond, self.params.bond_weight)
        d = self.today
        self.last_quarter = (d.month - 1) // 3
        self.last_month = d.month
        self.last_year = d.year
        pos = self.getposition(self.equity)
        if pos.size > 0:
            self.entry_price = self.equity.close[0]

    def _check_stop(self):
        if self.params.stop_loss is None:
            return
        mode = self.params.stop_loss_mode
        pos = self.getposition(self.equity)
        if pos.size == 0 or self.entry_price is None:
            return

        if mode == "portfolio":
            total = self.broker.getvalue()
            if self._initial_value is None:
                self._initial_value = total
            dd = (total - self._initial_value) / self._initial_value
            if dd < -self.params.stop_loss:
                self.close(self.equity)
                self.close(self.bond)
                self.stopped_out = True
                self._initial_value = total

        elif mode == "position":
            loss = (self.equity.close[0] - self.entry_price) / self.entry_price
            if loss < -self.params.stop_loss:
                self.close(self.equity)
                self.stopped_out = True

        elif mode == "rebalance":
            loss = (self.equity.close[0] - self.entry_price) / self.entry_price
            if loss < -self.params.stop_loss:
                self.order_target_percent(self.equity, 0.5)
                self.order_target_percent(self.bond, 0.5)
                self.stopped_out = True

    def next(self):
        if (self.getposition(self.equity).size == 0
                and self.getposition(self.bond).size == 0):
            self._do_rebalance()
            return

        self._check_stop()

        if self._should_rebalance():
            self._do_rebalance()
