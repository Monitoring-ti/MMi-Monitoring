"""Métricas de latencia y throughput para pruebas de carga."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Sequence


@dataclass
class LatencyStats:
    count: int
    ok: int
    errors: int
    min_ms: float
    max_ms: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    total_ms: float
    rps: float

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "ok": self.ok,
            "errors": self.errors,
            "error_rate_pct": round(100 * self.errors / self.count, 2) if self.count else 0,
            "min_ms": round(self.min_ms, 1),
            "max_ms": round(self.max_ms, 1),
            "mean_ms": round(self.mean_ms, 1),
            "p50_ms": round(self.p50_ms, 1),
            "p95_ms": round(self.p95_ms, 1),
            "p99_ms": round(self.p99_ms, 1),
            "total_ms": round(self.total_ms, 1),
            "rps": round(self.rps, 2),
        }


def percentile(sorted_values: Sequence[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    k = (len(sorted_values) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return float(sorted_values[f])
    return float(sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f))


def summarize_latencies(
    latencies_ms: list[float],
    *,
    errors: int = 0,
    wall_ms: float | None = None,
) -> LatencyStats:
    ok_latencies = [x for x in latencies_ms if x >= 0]
    err_count = errors + sum(1 for x in latencies_ms if x < 0)
    ok_count = len(ok_latencies)
    total_count = ok_count + err_count
    if not ok_latencies:
        total_ms = wall_ms or 0.0
        return LatencyStats(
            count=total_count,
            ok=0,
            errors=err_count,
            min_ms=0,
            max_ms=0,
            mean_ms=0,
            p50_ms=0,
            p95_ms=0,
            p99_ms=0,
            total_ms=total_ms,
            rps=0,
        )
    sorted_ok = sorted(ok_latencies)
    total_ms = wall_ms if wall_ms is not None else sum(ok_latencies)
    return LatencyStats(
        count=total_count,
        ok=ok_count,
        errors=err_count,
        min_ms=min(sorted_ok),
        max_ms=max(sorted_ok),
        mean_ms=statistics.mean(sorted_ok),
        p50_ms=percentile(sorted_ok, 50),
        p95_ms=percentile(sorted_ok, 95),
        p99_ms=percentile(sorted_ok, 99),
        total_ms=total_ms,
        rps=(ok_count / (total_ms / 1000)) if total_ms > 0 else 0,
    )
