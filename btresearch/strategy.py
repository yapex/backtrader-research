"""Unified strategy: deposits + rebalance + stop-loss.

Four independent actions per bar, no mode branching:
  1. Deposit day → inject cash, buy by target weights (new money only)
  2. Rebalance day → order_target_percent (sell + buy to restore targets)
  3. Stop loss → clear all / shift to crisis weights / contrarian (buy dip)
  4. Threshold rebalance → rebalance when any asset deviates beyond threshold

Config via _config:
  _config["weights"]      target weights per asset
  _config["deposits"]     {total_capital, initial, amount, freq, day, day_mode}
  _config["params"]       {rebalance_freq, stop_loss, rebalance_threshold,
                           stop_loss_mode, crisis_weights, recovery_threshold,
                           profit_take, profit_take_weights}

YAML params (all optional, defaults in parentheses):
  rebalance_freq:      "never" | "monthly" | "quarterly" | "yearly"  (never)
  stop_loss:           null | float  (null)  — drawdown threshold to trigger action
  stop_loss_mode:      "clear" | "crisis" | "contrarian"  ("clear")
  crisis_weights:      {ticker: weight, ...}  (null)  — weights when crisis active
                           (crisis=defensive, contrarian=aggressive)
  rebalance_threshold: null | float  (null)  — rebalance when any asset deviates
                           beyond this fraction (e.g. 0.05 = 5%), checked daily
  recovery_threshold:  null | float  (null)  — contrarian: exit when drawdown < this
  profit_take:         null | float  (null)  — contrarian: enter profit-take when
                           gain from trough exceeds this fraction
  profit_take_weights: {ticker: weight, ...}  (null)  — weights during profit-take

Combinations (all from params, no code branching):
  - Pure buy-and-hold:    rebalance_freq=never, stop_loss=null, deposits.amount=0
  - Allocation:           rebalance_freq=monthly, stop_loss=0.15, deposits.amount=0
  - DCA:                  rebalance_freq=never, deposits.amount=auto
  - DCA + rebalance:      rebalance_freq=yearly, deposits.amount=auto
  - Threshold rebalance:  rebalance_freq=never, rebalance_threshold=0.05
  - Crisis mode:          stop_loss=0.15, stop_loss_mode=crisis, crisis_weights={...}
  - Contrarian mode:      stop_loss=0.10, stop_loss_mode=contrarian,
                           crisis_weights={...more equity}, recovery_threshold=0.05
"""

import backtrader as bt


class Strategy(bt.Strategy):
    params = (
        ("rebalance_freq", "never"),
        ("stop_loss", None),
        ("stop_loss_mode", "clear"),
        ("rebalance_threshold", None),
        ("recovery_threshold", None),
        ("profit_take", None),
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

        # Crisis weights (for stop_loss_mode="crisis")
        crisis_cfg = self._config.get("params", {}).get("crisis_weights")
        self.crisis_weights = None
        if crisis_cfg:
            # crisis_weights in YAML: {"510300.SS": 0.10, "511010.SS": 0.60, ...}
            # Build lookup by data object, same pattern as self.targets
            self.crisis_weights = {}
            for data in self.datas:
                w = crisis_cfg.get(data._name, None)
                if w is not None:
                    self.crisis_weights[data] = w

        # Profit take weights (for contrarian mode: reduce equity after recovery)
        pt_cfg = self._config.get("params", {}).get("profit_take_weights")
        self.profit_take_weights = None
        if pt_cfg:
            self.profit_take_weights = {}
            for data in self.datas:
                w = pt_cfg.get(data._name, None)
                if w is not None:
                    self.profit_take_weights[data] = w

        # Contrarian state
        self.in_contrarian = False
        self.in_profit_take = False
        self.trough_value = None

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

    def _get_active_weights(self):
        """Get target weights based on current state (normal/contrarian/profit_take)."""
        if self.in_profit_take and self.profit_take_weights:
            return self.profit_take_weights
        if self.in_contrarian and self.crisis_weights:
            return self.crisis_weights
        return self.targets

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

    def _is_threshold_rebalance(self):
        """Check if any asset deviates beyond rebalance_threshold from active target."""
        threshold = self.params.rebalance_threshold
        if threshold is None or threshold <= 0:
            return False
        total = self.broker.getvalue()
        if total <= 0:
            return False
        active = self._get_active_weights()
        for data, target_w in active.items():
            current_w = self.broker.getposition(data).size * data.close[0] / total
            if abs(current_w - target_w) > threshold:
                return True
        return False

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _buy_by_weight(self, cash_amount):
        """Split new cash by target weights. Does NOT touch existing positions."""
        if cash_amount <= 0:
            return
        for data, w in self.targets.items():
            if w > 0 and data.close[0] > 0:
                total = self.broker.getvalue()
                if total <= 0:
                    continue
                target_pct = w * cash_amount / total
                # Cap at 0.98 to leave room for commission costs
                target_pct = min(target_pct, 0.98)
                if target_pct > 0:
                    self.order_target_percent(data, target_pct)

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

    def _do_rebalance(self, weights=None):
        if weights is None:
            weights = self.targets
        for data, w in weights.items():
            self.order_target_percent(data, w)
        self.last_rebalance_period = self._period_key(self.params.rebalance_freq)
        self.stopped_out = False
        if self.peak_value is None:
            self.peak_value = self.broker.getvalue()

    def _do_crisis_rebalance(self):
        """Shift to crisis weights (more conservative allocation)."""
        if not self.crisis_weights:
            return
        self._do_rebalance(weights=self.crisis_weights)
        self.stopped_out = True

    def _check_stop_loss(self):
        if self.params.stop_loss is None:
            return
        total = self.broker.getvalue()
        if self.peak_value is None:
            self.peak_value = total
        self.peak_value = max(self.peak_value, total)
        dd = (total - self.peak_value) / self.peak_value

        # --- Existing modes: crisis (defensive) / clear (sell all) ---
        if self.params.stop_loss_mode == "crisis":
            if dd < -self.params.stop_loss and not self.stopped_out:
                if self.crisis_weights:
                    self._do_crisis_rebalance()
                else:
                    for data in self.targets:
                        self.order_target_percent(data, 0.0)
                self.stopped_out = True
            return

        if self.params.stop_loss_mode != "contrarian":
            # "clear" or default: sell everything on stop loss
            if dd < -self.params.stop_loss and not self.stopped_out:
                for data in self.targets:
                    self.order_target_percent(data, 0.0)
                self.stopped_out = True
            return

        # --- Contrarian mode: buy more equity on drawdown ---
        # Enter contrarian when drawdown exceeds threshold
        if not self.in_contrarian and not self.in_profit_take:
            if dd < -self.params.stop_loss:
                self.in_contrarian = True
                self.trough_value = total
                if self.crisis_weights:
                    self._do_rebalance(weights=self.crisis_weights)

        if self.in_contrarian:
            self.trough_value = min(self.trough_value, total)
            # Profit take FIRST (别人贪婪我恐惧): reduce equity when
            # portfolio has bounced significantly from trough.
            # This should fire BEFORE recovery — a strong bounce from trough
            # means the rally is mature even if we haven't fully recovered.
            pt = self.params.profit_take
            if pt and self.trough_value > 0 and self.profit_take_weights:
                gain = (total - self.trough_value) / self.trough_value
                if gain > pt:
                    self.in_contrarian = False
                    self.in_profit_take = True
                    self._do_rebalance(weights=self.profit_take_weights)
                    return
            # Recovery SECOND: exit contrarian when drawdown improves enough
            recovery = self.params.recovery_threshold
            if recovery is not None and dd >= -recovery:
                self.in_contrarian = False
                self._do_rebalance(weights=self.targets)
                return

        if self.in_profit_take:
            # Exit profit take if drawdown exceeds stop_loss again
            # (new fear → back to greedy)
            if dd < -self.params.stop_loss:
                self.in_profit_take = False
                self.in_contrarian = True
                self.trough_value = total
                if self.crisis_weights:
                    self._do_rebalance(weights=self.crisis_weights)
            # Also exit profit take when fully recovered (back to normal)
            elif dd >= -0.02:
                self.in_profit_take = False
                self._do_rebalance(weights=self.targets)

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

        # 2. Rebalance (scheduled)
        if not self.stopped_out and self._is_rebalance_day():
            self._do_rebalance()

        # 2b. Rebalance (threshold-based)
        if not self.stopped_out and not self._is_rebalance_day() and self._is_threshold_rebalance():
            self._do_rebalance(weights=self._get_active_weights())

        # 3. Stop loss
        self._check_stop_loss()
