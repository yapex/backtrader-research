"""Commission models.

SRP: Solely responsible for commission calculation.
"""

from __future__ import annotations

import backtrader as bt


COMMISSION_DEFAULT = 0.0003


class StockCommission(bt.comminfo.CommInfoBase):
    """Percentage-based stock commission model."""

    params = (
        ("commission", COMMISSION_DEFAULT),
        ("stocklike", True),
        ("commtype", bt.comminfo.CommInfoBase.COMM_PERC),
        ("percabs", True),
    )
