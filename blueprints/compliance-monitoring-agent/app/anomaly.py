"""anomaly — surface statistical outliers the rule-based screener would miss.

Classification catches what a rule *describes*; anomaly detection catches what is merely
*unusual* — a transaction far outside an account's normal range, a burst of activity, a sum that
hugs a reporting threshold. The PLAN calls for "model + simple statistical signals"; the
*statistical* half lives here as transparent, dependency-free signals (the model half is the
classifier in :mod:`app.classify`). Anomalies do not auto-flag a violation; they raise an item's
priority and give the human a second reason to look.

Two signals ship, both explainable:

* **Amount outlier** — a robust z-score (median / MAD) over numeric transaction amounts. Robust
  statistics matter for compliance: a single huge fraudulent transfer must not inflate the mean
  and hide itself. MAD is unmoved by the outlier it is trying to catch.
* **Threshold-hugging** — a transaction just under a reporting threshold (structuring is itself a
  violation, TXN-01), which a plain magnitude check misses precisely because it is *small*.

Stdlib only; deterministic given the data.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

# AML reporting threshold (USD) used by the threshold-hugging signal. Matches policy TXN-01.
REPORTING_THRESHOLD = 10_000.0
# How close (below) the threshold counts as "hugging" it — within 10% by default.
_HUG_BAND = 0.10
# Robust z-score above which an amount is an outlier (3.5 is the common MAD-based cutoff).
_Z_CUTOFF = 3.5


@dataclass(frozen=True)
class AnomalySignal:
    """One anomaly finding for an item: a kind, a human reason, and a 0..1 strength."""

    kind: str
    reason: str
    strength: float


class AmountAnomalyDetector:
    """Flags numeric amounts that are statistical outliers or hug a reporting threshold.

    Fit it on the population of amounts (``fit``), then test individual amounts (``check``). With
    too few points to be meaningful it abstains rather than inventing outliers — a screener that
    cries wolf on a cold start trains reviewers to ignore it.
    """

    def __init__(
        self,
        *,
        threshold: float = REPORTING_THRESHOLD,
        z_cutoff: float = _Z_CUTOFF,
        hug_band: float = _HUG_BAND,
    ) -> None:
        self.threshold = threshold
        self.z_cutoff = z_cutoff
        self.hug_band = hug_band
        self._median = 0.0
        self._mad = 0.0
        self._n = 0

    def fit(self, amounts: list[float]) -> "AmountAnomalyDetector":
        """Compute robust center/spread (median + MAD) over the amount population."""
        values = [float(a) for a in amounts if a is not None]
        self._n = len(values)
        if self._n:
            self._median = statistics.median(values)
            deviations = [abs(v - self._median) for v in values]
            self._mad = statistics.median(deviations)
        return self

    def _robust_z(self, amount: float) -> float:
        """MAD-based robust z-score. 0.6745 rescales MAD to be comparable to a std-dev."""
        if self._mad == 0.0:
            return 0.0
        return 0.6745 * (amount - self._median) / self._mad

    def check(self, amount: float | None) -> AnomalySignal | None:
        """Return an :class:`AnomalySignal` if ``amount`` is anomalous, else ``None``."""
        if amount is None:
            return None
        amount = float(amount)

        # Threshold-hugging: just under the reporting line (possible structuring, TXN-01).
        low = self.threshold * (1.0 - self.hug_band)
        if low <= amount < self.threshold:
            pct = (self.threshold - amount) / self.threshold
            return AnomalySignal(
                kind="threshold_hugging",
                reason=(
                    f"Amount {amount:,.0f} sits {pct:.0%} under the {self.threshold:,.0f} "
                    "reporting threshold (possible structuring)."
                ),
                strength=round(1.0 - pct / self.hug_band, 3),
            )

        # Amount outlier: only meaningful with enough population.
        if self._n >= 4:
            z = self._robust_z(amount)
            if z >= self.z_cutoff:
                return AnomalySignal(
                    kind="amount_outlier",
                    reason=(
                        f"Amount {amount:,.0f} is a statistical outlier "
                        f"(robust z={z:.1f} vs median {self._median:,.0f})."
                    ),
                    strength=round(min(z / (self.z_cutoff * 2), 1.0), 3),
                )
        return None
