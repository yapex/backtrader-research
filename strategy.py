"""
Trading strategy — Agent modifies this file.

面向普通用户，策略简单到可以手动执行。
所有行为由 research.yaml 的 params 控制。

engine.py injects research.yaml config into Strategy._config:
  - _config["tickers"]  e.g. ["SPY", "TLT", "GLD"]
  - _config["weights"]  e.g. {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25}
  - _config["roles"]    e.g. {"SPY": "equity", "TLT": "bond", "GLD": "gold"}
  - _config["params"]   e.g. {"rebalance_freq": "yearly", "stop_loss": null}

权重之和 <= 1.0，剩余部分自动留为现金。
例如 25/25/25 = 75%，剩余 25% 现金。

Only requirement: define a class called Strategy that inherits bt.Strategy.
"""

import backtrader as bt


class Strategy(bt.Strategy):
    """配置驱动的定期再平衡策略，可选止损。

    行为由 research.yaml → params 控制：

      rebalance_freq: "monthly" | "quarterly" | "yearly"
      stop_loss: null | 0.15             — 组合从高点回撤超过此值，全部清仓留现金
    """

    params = (
        ("rebalance_freq", "quarterly"),
        ("stop_loss", None),
    )

    def __init__(self):
        yaml_params = self._config.get("params", {})
        for key, val in yaml_params.items():
            if key in self.params._getpairs():
                setattr(self.params, key, val)

        # 通用：支持 N 个资产，每个带权重
        self.targets = {}  # data → target_weight
        for data in self.datas:
            name = data._name
            w = self._config["weights"].get(name, 0.0)
            self.targets[data] = w

        self.last_period = None
        self.peak_value = None
        self.stopped_out = False

    @property
    def today(self):
        return self.datas[0].datetime.date(0)

    def _period_key(self):
        d = self.today
        freq = self.params.rebalance_freq
        if freq == "monthly":
            return (d.year, d.month)
        elif freq == "quarterly":
            return (d.year, (d.month - 1) // 3)
        elif freq == "yearly":
            return (d.year,)
        return (d.year, d.month)

    def _do_rebalance(self):
        for data, weight in self.targets.items():
            self.order_target_percent(data, weight)
        self.last_period = self._period_key()
        self.stopped_out = False
        if self.peak_value is None:
            self.peak_value = self.broker.getvalue()

    def _check_stop(self):
        if self.params.stop_loss is None:
            return
        total = self.broker.getvalue()
        if self.peak_value is None:
            self.peak_value = total
        self.peak_value = max(self.peak_value, total)
        dd = (total - self.peak_value) / self.peak_value
        if dd < -self.params.stop_loss:
            # 全部清仓，留现金
            for data in self.targets:
                self.order_target_percent(data, 0.0)
            self.stopped_out = True

    def next(self):
        # 首次建仓
        has_position = any(self.getposition(d).size > 0 for d in self.targets)
        if not has_position:
            self._do_rebalance()
            return

        self._check_stop()

        key = self._period_key()
        if key != self.last_period and not self.stopped_out:
            self._do_rebalance()
