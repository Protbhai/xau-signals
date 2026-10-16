from .base import Evaluation, Setup, SetupState, Strategy
from .benchmark import BenchmarkV1
from .experimental import BenchmarkExtV1, BreakoutRetestV1, RangeRejectionV1
from .old_monitor import OldMonitorCloudV1, OldMonitorSessionV1

REGISTRY: dict[str, type[Strategy]] = {
    "benchmark_v1": BenchmarkV1,
    "breakout_retest_v1": BreakoutRetestV1,
    "range_rejection_v1": RangeRejectionV1,
    "benchmark_ext_v1": BenchmarkExtV1,
    "old_session_v1": OldMonitorSessionV1,
    "old_cloud_v1": OldMonitorCloudV1,
}


def make(name: str, params: dict) -> Strategy:
    try:
        cls = REGISTRY[name]
    except KeyError as e:
        raise ValueError(f"unknown strategy {name!r}; known: {sorted(REGISTRY)}") from e
    return cls(**params)


__all__ = ["Evaluation", "Setup", "SetupState", "Strategy", "BenchmarkV1", "REGISTRY", "make"]
