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
    "NQ": AssetSpec("NQ", "Nasdaq 100", "America/New_York", 18, 2.0,
                    dukascopy="USATECHIDXUSD", yahoo="NQ=F"),
    "SPX": AssetSpec("SPX", "S&P 500", "America/New_York", 18, 2.0,
                     dukascopy="USA500IDXUSD", yahoo="ES=F"),
    "XAU": AssetSpec("XAU", "Gold", "America/New_York", 18, 3.0,
                     dukascopy="XAUUSD", yahoo="GC=F"),
    "XAG": AssetSpec("XAG", "Silver", "America/New_York", 18, 8.0,
                     dukascopy="XAGUSD", yahoo="SI=F"),
    "BTC": AssetSpec("BTC", "Bitcoin", "UTC", 0, 10.0,
                     binance="BTCUSDT", yahoo="BTC-USD"),
    "ETH": AssetSpec("ETH", "Ethereum", "UTC", 0, 10.0,
                     binance="ETHUSDT", yahoo="ETH-USD"),
}

# Timeframe roles requested by the research plan.
#   1M : liquidity + FVG + every block type
#   1W : FVG + every block type
#   1D : FVG + every block type
#   4H : market structure break + FVG + every block type
#   1H : entry on an FVG or any block type
HTF: tuple[str, ...] = ("M", "W", "D", "H4")
ZONE_TYPES: tuple[str, ...] = ("FVG", "OB", "BB", "MB", "RB", "PB", "VB")
BLOCK_TYPES: tuple[str, ...] = ZONE_TYPES[1:]
# Condition bits: 8 per HTF (7 zone types + ANYB = any block), then M_LIQ, H4_MSB.
# Rule filters (named so that no HTF slot prefix such as "D_" or "W_" matches them):
#   BIAS_D  daily close on the trade side of its 50-day EMA
#   BIAS_W  latest weekly structure break in the trade direction
#   KZ      entry hour inside a killzone (London 02-05, New York 07-11, NY time)
#   PD      long in discount / short in premium of the previous week's range
FILTERS: tuple[str, ...] = ("BIAS_D", "BIAS_W", "KZ", "PD")
CONDITIONS: tuple[str, ...] = tuple(
    [f"{tf}_{z}" for tf in HTF for z in (*ZONE_TYPES, "ANYB")] + ["M_LIQ", "H4_MSB"]
    + list(FILTERS))
BIT = {name: i for i, name in enumerate(CONDITIONS)}
# Entry filters over the 1h trigger kind (index into ZONE_TYPES) as kind bitmasks.
ENTRY_FILTERS: dict[str, int] = {
    **{z: 1 << i for i, z in enumerate(ZONE_TYPES)},
    "ANYB": sum(1 << i for i in range(1, len(ZONE_TYPES))),
    "ANY": (1 << len(ZONE_TYPES)) - 1,
}
ENTRY_TYPES: tuple[str, ...] = tuple(ENTRY_FILTERS)


def filter_options() -> list[tuple[str, int]]:
    """Choices for the rule-filter slot (single filters and the main pairing)."""
    b = lambda name: 1 << BIT[name]  # noqa: E731
    return [("-", 0), ("BIAS_D", b("BIAS_D")), ("BIAS_W", b("BIAS_W")), ("KZ", b("KZ")),
            ("PD", b("PD")), ("BIAS_D+KZ", b("BIAS_D") | b("KZ"))]


def slot_options(tf: str) -> list[tuple[str, int]]:
    """Choices for one HTF slot: none, one zone type, any block, FVG inside a block."""
    b = lambda name: 1 << BIT[f"{tf}_{name}"]  # noqa: E731
    opts = [("-", 0)]
    opts += [(z, b(z)) for z in ZONE_TYPES]
    opts.append(("ANYB", b("ANYB")))
    opts += [(f"FVG+{k}", b("FVG") | b(k)) for k in BLOCK_TYPES]
    opts.append(("FVG+ANYB", b("FVG") | b("ANYB")))
    return opts


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

RR_GRID: tuple[float, ...] = (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)
ENTRY_MODES: tuple[str, ...] = ("market", "limit_edge", "limit_ce")
# Trade management: none, or move stop to break-even once price reaches +1R.
# Trade management: none; break-even once +1R; or trail the stop 2 ATR behind the best
# price once +1R is reached.
MGMT: tuple[str, ...] = ("none", "be1r", "trail2atr")
KIND_CODE = {"zone": 0, "atr": 1, "swing": 2, "pattern": 3}
ENTRY_CODE = {"market": 0, "limit_edge": 1, "limit_ce": 2}


@dataclass
class ResearchParams:
    atr_len: int = 14
    fvg_min_atr: float = 0.10  # minimum FVG height in ATR of its own timeframe
    swing_k: int = 2  # fractal half-width used for swings / MSB / OB
    rejection_wick: float = 0.5  # rejection block: wick share of the candle range
    vacuum_gap_atr: float = 0.25  # vacuum block: minimum open gap in ATR
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
