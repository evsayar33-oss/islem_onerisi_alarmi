"""Central configuration: assets, timeframe roles and the full parameter grid."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AssetSpec:
    key: str
    name: str
    # Session definition used for D / W / M bucketing.
    tz: str
    rollover_hour: int  # local hour at which a new trading day starts
    # Round-trip cost in basis points of price (spread + commission + slippage).
    cost_bps: float
    # Data source symbols.
    dukascopy: str | None = None
    binance: str | None = None
    yahoo: str | None = None


ASSETS: dict[str, AssetSpec] = {
    "NQ": AssetSpec("NQ", "Nasdaq 100", "America/New_York", 18, 1.0,
                    dukascopy="USATECHIDXUSD", yahoo="NQ=F"),
    "SPX": AssetSpec("SPX", "S&P 500", "America/New_York", 18, 1.0,
                     dukascopy="USA500IDXUSD", yahoo="ES=F"),
    "XAU": AssetSpec("XAU", "Gold", "America/New_York", 18, 2.0,
                     dukascopy="XAUUSD", yahoo="GC=F"),
    "XAG": AssetSpec("XAG", "Silver", "America/New_York", 18, 8.0,
                     dukascopy="XAGUSD", yahoo="SI=F"),
    "BTC": AssetSpec("BTC", "Bitcoin", "UTC", 0, 10.0,
                     binance="BTCUSDT", yahoo="BTC-USD"),
    "ETH": AssetSpec("ETH", "Ethereum", "UTC", 0, 10.0,
                     binance="ETHUSDT", yahoo="ETH-USD"),
}

# Timeframe roles requested by the research plan.
#   1M : liquidity, order blocks, FVG
#   1W : FVG, order blocks
#   1D : FVG, order blocks
#   4H : market structure break, FVG, order blocks
#   1H : FVG / order block entry
CONDITIONS: tuple[str, ...] = (
    "M_LIQ", "M_FVG", "M_OB",
    "W_FVG", "W_OB",
    "D_FVG", "D_OB",
    "H4_MSB", "H4_FVG", "H4_OB",
)
ENTRY_TYPES: tuple[str, ...] = ("FVG", "OB", "ANY")


@dataclass(frozen=True)
class StopSpec:
    name: str
    kind: str  # zone | atr | swing | pattern
    value: float  # ATR buffer (zone/swing/pattern) or ATR multiple (atr)


STOPS: tuple[StopSpec, ...] = (
    StopSpec("zone", "zone", 0.0),
    StopSpec("zone+0.1atr", "zone", 0.1),
    StopSpec("zone+0.25atr", "zone", 0.25),
    StopSpec("zone+0.5atr", "zone", 0.5),
    StopSpec("atr1.0", "atr", 1.0),
    StopSpec("atr1.5", "atr", 1.5),
    StopSpec("atr2.0", "atr", 2.0),
    StopSpec("atr3.0", "atr", 3.0),
    StopSpec("swing+0.1atr", "swing", 0.1),
    StopSpec("pattern+0.1atr", "pattern", 0.1),
)

RR_GRID: tuple[float, ...] = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)
ENTRY_MODES: tuple[str, ...] = ("market", "limit_edge", "limit_ce")
# Trade management: none, or move stop to break-even once price reaches +1R.
MGMT: tuple[str, ...] = ("none", "be1r")
KIND_CODE = {"zone": 0, "atr": 1, "swing": 2, "pattern": 3}
ENTRY_CODE = {"market": 0, "limit_edge": 1, "limit_ce": 2}


@dataclass
class ResearchParams:
    atr_len: int = 14
    fvg_min_atr: float = 0.10  # minimum FVG height in ATR of its own timeframe
    swing_k: int = 2  # fractal half-width used for swings / MSB / OB
    zone_max_age: dict[str, int] = field(default_factory=lambda: {
        "M": 36, "W": 104, "D": 250, "H4": 360, "H1": 0,
    })
    msb_max_age_h4: int = 42  # 4H MSB stays "fresh" for N 4H bars (~1 week)
    liq_lookback_h1: int = 24 * 22  # monthly sweep stays valid for ~1 trading month
    overlap_mode: str = "overlap"  # overlap | inside
    limit_valid_bars: int = 24
    max_hold_bars: int = 120
    min_risk_atr: float = 0.05
    min_trades: int = 30
    oos_fraction: float = 0.30
    max_combo_size: int = 10
    pt_seed: int = 7
