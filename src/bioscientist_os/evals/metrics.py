"""Proportion metrics with honest denominators and Wilson intervals (Milestone 8).

Every rate the evaluation harness reports is a :class:`Proportion` — a count
``k`` out of a denominator ``n`` — never a bare percentage. The denominator
travels with the estimate so a reader cannot mistake ``2/2 = 100%`` for a strong
result, and a 95% **Wilson score interval** is attached to convey the (often
wide) uncertainty at the small N this workbench evaluates on.

The Wilson interval is used in preference to the normal (Wald) approximation
because it is well behaved at small N and near 0/1: it never leaves ``[0, 1]``,
and it gives a sensible interval even when ``k = 0`` or ``k = n`` (where Wald
collapses to a zero-width interval). The critical value ``z`` is computed from the
stdlib :class:`statistics.NormalDist`, so no third-party numerics are required and
any confidence level is supported.

These helpers are intentionally tiny and pure (no I/O); :mod:`bioscientist_os.evals.harness`
composes them into the per-task evaluators.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

# Rounding applied only in JSON/text output (mirrors search/extract/evidence).
_NDIGITS = 4

# Default two-sided confidence level for reported intervals.
DEFAULT_CONFIDENCE = 0.95


def z_for_confidence(level: float) -> float:
    """Two-sided normal critical value for a confidence ``level`` in ``(0, 1)``.

    ``z_for_confidence(0.95) == 1.959963984540054``. Computed via the stdlib
    inverse normal CDF, so any level works without a numerics dependency.
    """
    if not 0.0 < level < 1.0:
        raise ValueError(f"confidence level must be in (0, 1), got {level}")
    return NormalDist().inv_cdf(0.5 + level / 2.0)


def wilson_interval(k: int, n: int, *, level: float = DEFAULT_CONFIDENCE) -> tuple[float, float]:
    """The Wilson score interval for ``k`` successes out of ``n`` trials.

    Returns ``(low, high)`` clamped to ``[0, 1]``. With ``n == 0`` the proportion
    is undefined, so the maximally-uncertain ``(0.0, 1.0)`` is returned (the
    caller surfaces ``n`` so this is never mistaken for a measurement).
    """
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"need 0 <= k <= n, got k={k}, n={n}")
    if n == 0:
        return (0.0, 1.0)
    z = z_for_confidence(level)
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1.0 - p) / n + z2 / (4 * n * n))
    return (max(0.0, center - margin), min(1.0, center + margin))


@dataclass(frozen=True)
class Proportion:
    """A count ``k`` out of ``n`` with its point estimate and Wilson interval.

    ``point`` is ``None`` for an empty denominator (``n == 0``) — there is nothing
    to estimate — rather than a misleading ``0.0``. ``ci_low`` / ``ci_high`` are
    the Wilson bounds at :attr:`level`.
    """

    label: str
    numerator: int
    denominator: int
    level: float = DEFAULT_CONFIDENCE

    @property
    def point(self) -> float | None:
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    @property
    def ci(self) -> tuple[float, float]:
        return wilson_interval(self.numerator, self.denominator, level=self.level)

    def to_dict(self) -> dict:
        low, high = self.ci
        point = self.point
        return {
            "label": self.label,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "point_estimate": None if point is None else round(point, _NDIGITS),
            "ci_low": round(low, _NDIGITS),
            "ci_high": round(high, _NDIGITS),
            "confidence_level": self.level,
            "interval_method": "wilson",
        }

    def format_line(self) -> str:
        """A compact one-line rendering, e.g. ``recall@3: 14/16 = 0.875 [0.640, 0.964]``."""
        if self.point is None:
            return f"{self.label}: 0/0 (undefined — no data)"
        low, high = self.ci
        return (
            f"{self.label}: {self.numerator}/{self.denominator} = "
            f"{self.point:.3f} [{low:.3f}, {high:.3f}] "
            f"({int(self.level * 100)}% Wilson)"
        )


def f1_score(precision: float | None, recall: float | None) -> float | None:
    """Harmonic mean of precision and recall, or ``None`` if either is undefined/zero-sum."""
    if precision is None or recall is None:
        return None
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


__all__ = [
    "DEFAULT_CONFIDENCE",
    "z_for_confidence",
    "wilson_interval",
    "Proportion",
    "f1_score",
]
