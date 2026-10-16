from pathlib import Path

from xau_signals.config import load_settings


def test_real_default_config_loads():
    root = Path(__file__).resolve().parents[1]
    s = load_settings(root / "config" / "default.toml", root=root)
    assert s.mode == "paper" and s.get("data", "setup_interval") == "5m"
    assert s.raw["data"]["symbols"]["twelvedata"] == "XAU/USD"
    for name in ("benchmark_v1", "breakout_retest_v1", "range_rejection_v1", "benchmark_ext_v1"):
        assert name in s.raw["strategy"]
