"""
Unified strategy: deposits + rebalance + stop-loss.

Three independent actions per bar, no mode branching:
  1. Deposit day → inject cash, buy by target weights (new money only)
  2. Rebalance day → order_target_percent (sell + buy to restore targets)
  3. Stop loss → clear all positions

Config via _config:
  _config["weights"]      target weights per asset
  _config["deposits"]     {total_capital, initial, amount, freq, day, day_mode}
  _config["params"]       {rebalance_freq: "never"|"monthly"|"quarterly"|"yearly",
                           stop_loss: null|float}

Combinations (all from params, no code branching):
  - Pure buy-and-hold:    rebalance_freq=never, stop_loss=null, deposits.amount=0
  - Allocation:           rebalance_freq=monthly, stop_loss=0.15, deposits.amount=0
  - DCA:                  rebalance_freq=never, deposits.amount=auto
  - DCA + rebalance:      rebalance_freq=yearly, deposits.amount=auto
"""

import backtrader as bt


class Strategy(bt.Strategy):
    params = (
        ("rebalance_freq", "never"),
        ("stop_loss", None),
    )

    def __init__(self):
        # Parse YAML params
        for key, val in self._config.get("params", {}).items():
            if key in self.params._getpairs():
                setattr(self.params, key, val)

        # Target weights
        self.targets = {}
        for data in self.datas:
            self.targets[data] = self._config["weights"].get(data._name, 0.0)

        # Deposit state
        dep = self._config.get("deposits", {})
        self.dep_remaining = dep.get("total_capital", 0) - dep.get("initial", 0)
        self.dep_initial = dep.get("initial", 0)
        self.dep_amount = dep.get("amount", 0)
        self.dep_freq = dep.get("freq", "monthly")
        self.dep_day = dep.get("day", 1)
        self.dep_day_mode = dep.get("day_mode", "exact")
        self.deposits_active = dep.get("total_capital", 0) > 0
        self.total_deposited = 0.0
        self.last_dep_period = None

        # Rebalance state
        self.last_rebalance_period = None

        # Stop loss state
        self.peak_value = None
        self.stopped_out = False

        # Trade log
        self.trade_log: list[dict] = []
        self.initial_done = False

    @property
    def today(self):
        return self.datas[0].datetime.date(0)

    # ------------------------------------------------------------------
    # Period helpers
    # ------------------------------------------------------------------

    def _period_key(self, freq):
        d = self.today
        if freq == "weekly":
            return (d.year, d.isocalendar()[1])
        elif freq == "monthly":
            return (d.year, d.month)
        elif freq == "quarterly":
            return (d.year, (d.month - 1) // 3)
        elif freq == "yearly":
            return (d.year,)
        return (d.year, d.month)

    def _is_deposit_day(self):
        if not self.deposits_active or self.dep_remaining <= 0:
            return False
        today = self.today
        if self.dep_freq == "weekly":
            return today.weekday() == self.dep_day
        mode = self.dep_day_mode
        if mode == "exact":
            return today.day == self.dep_day
        elif mode == "first":
            return today.month != getattr(self, "_last_deposit_month", None)
        elif mode == "last":
            nxt = today.replace(day=min(today.day + 1, 28))
            if nxt.month != today.month:
                return today.month != getattr(self, "_last_deposit_month", None)
        return False

    def _is_rebalance_day(self):
        if self.params.rebalance_freq == "never":
            return False
        key = self._period_key(self.params.rebalance_freq)
        return self.last_rebalance_period is None or key != self.last_rebalance_period

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _buy_by_weight(self, cash_amount):
        """Split new cash by target weights. Does NOT touch existing positions."""
        if cash_amount <= 0:
            return
        for data, w in self.targets.items():
            amount = cash_amount * w
            if amount > 0 and data.close[0] > 0:
                self.buy(data=data, size=amount / data.close[0])

    def _do_deposit(self) -> float:
        amount = min(self.dep_amount, self.dep_remaining)
        if amount <= 0:
            return 0.0
        self.dep_remaining -= amount
        self.total_deposited += amount
        self.last_dep_period = self._period_key(self.dep_freq)
        self._last_deposit_month = self.today.month
        self.trade_log.append({"date": self.today, "type": "deposit", "amount": amount})
        return amount

    def _do_rebalance(self):
        for data, w in self.targets.items():
            self.order_target_percent(data, w)
        self.last_rebalance_period = self._period_key(self.params.rebalance_freq)
        self.stopped_out = False
        if self.peak_value is None:
            self.peak_value = self.broker.getvalue()

    def _check_stop_loss(self):
        if self.params.stop_loss is None:
            return
        total = self.broker.getvalue()
        if self.peak_value is None:
            self.peak_value = total
        self.peak_value = max(self.peak_value, total)
        if (total - self.peak_value) / self.peak_value < -self.params.stop_loss:
            for data in self.targets:
                self.order_target_percent(data, 0.0)
            self.stopped_out = True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def next(self):
        # Day 1
        if not self.initial_done:
            if self.dep_initial > 0:
                self.broker.set_cash(self.dep_initial)
                self.trade_log.append({"date": self.today, "type": "deposit",
                                       "amount": self.dep_initial})
                self.total_deposited += self.dep_initial
                self._buy_by_weight(self.dep_initial)
            elif not self.deposits_active:
                self._buy_by_weight(self.broker.getcash())
            self.initial_done = True
            return

        # 1. Deposit
        if self.deposits_active and self.dep_remaining > 0 and self._is_deposit_day():
            cur = self._period_key(self.dep_freq)
            if cur != self.last_dep_period:
                deposited = self._do_deposit()
                if deposited > 0:
                    self.broker.add_cash(deposited)
                    self._buy_by_weight(deposited)

        # 2. Rebalance
        if not self.stopped_out and self._is_rebalance_day():
            self._do_rebalance()

        # 3. Stop loss
        self._check_stop_loss()
