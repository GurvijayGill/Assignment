"""Unit tests for the unified pricing adapter.

These tests verify:
1. Correct routing from trade types to underlying pricing backends.
2. Argument mapping integrity between adapter handlers and libraries.
3. Explicit failure behavior for unsupported trade types.
4. Extensibility through runtime registration of a new trade type.
"""

from dataclasses import dataclass
from datetime import date

import pytest

from pricer_adapter import (
    CapFloorTrade,
    IRSTrade,
    MarketState,
    PricerAdapter,
    SwaptionTrade,
    UnsupportedTradeError,
)


def test_routes_irs_trade_to_swap_library() -> None:
    """Ensure ``IRSTrade`` dispatches to the swap pricing function."""
    calls = {}

    def fake_swap_pricer(notional, fixed_rate, start, end, curve):
        calls["args"] = (notional, fixed_rate, start, end, curve)
        return 101.25

    adapter = PricerAdapter(swap_pricer=fake_swap_pricer)
    trade = IRSTrade(
        notional=1_000_000,
        fixed_rate=0.032,
        start=date(2026, 1, 1),
        end=date(2031, 1, 1),
        curve_id="usd_ois",
    )
    market_state = MarketState(curves={"usd_ois": {"par_rate": 0.03}})

    result = adapter.price(trade, market_state)

    assert result == 101.25
    assert calls["args"] == (
        1_000_000,
        0.032,
        date(2026, 1, 1),
        date(2031, 1, 1),
        {"par_rate": 0.03},
    )


def test_routes_swaption_trade_to_swaption_library() -> None:
    """Ensure ``SwaptionTrade`` dispatches to the swaption pricing function."""
    calls = {}

    def fake_swaption_pricer(trade_dict, market_data):
        calls["args"] = (trade_dict, market_data)
        return 250_000.0

    adapter = PricerAdapter(swaption_pricer=fake_swaption_pricer)
    trade = SwaptionTrade(trade_dict={"notional": 5_000_000, "annuity": 4.1, "strike": 0.028})
    market_state = MarketState(market_data={"implied_vol": 0.22, "valuation_date": "2026-02-15"})

    result = adapter.price(trade, market_state)

    assert result == 250_000.0
    assert calls["args"] == (
        {"notional": 5_000_000, "annuity": 4.1, "strike": 0.028},
        {"implied_vol": 0.22, "valuation_date": "2026-02-15"},
    )


def test_routes_capfloor_trade_to_capfloor_library() -> None:
    """Ensure ``CapFloorTrade`` dispatches to ``CapFloorPricer.price``."""

    class FakeCapFloorPricer:
        """Spy object used to verify cap/floor call forwarding."""

        def __init__(self):
            """Initialize call capture storage."""
            self.calls = []

        def price(self, cap, curve, vol_surface, **kwargs):
            """Capture incoming args and return deterministic test PV."""
            self.calls.append((cap, curve, vol_surface, kwargs))
            return 42_500.5

    fake_capfloor_pricer = FakeCapFloorPricer()
    adapter = PricerAdapter(capfloor_pricer=fake_capfloor_pricer)

    trade = CapFloorTrade(
        cap={"type": "cap", "strike": 0.03, "notional": 2_000_000},
        curve_id="usd_3m",
        vol_surface_id="usd_3m_caps",
        kwargs={"scale": 1.2, "greeks": True},
    )
    market_state = MarketState(
        curves={"usd_3m": {"forward": 0.031}},
        vol_surfaces={"usd_3m_caps": {"atm_vol": 0.19}},
    )

    result = adapter.price(trade, market_state)

    assert result == 42_500.5
    assert fake_capfloor_pricer.calls == [
        (
            {"type": "cap", "strike": 0.03, "notional": 2_000_000},
            {"forward": 0.031},
            {"atm_vol": 0.19},
            {"scale": 1.2, "greeks": True},
        )
    ]


def test_unsupported_trade_raises_custom_error() -> None:
    """Ensure unknown trade classes raise ``UnsupportedTradeError``."""

    @dataclass(frozen=True)
    class ExoticTrade:
        """Minimal unsupported trade payload for negative-path testing."""

        descriptor: str = "snowball"

    adapter = PricerAdapter()

    with pytest.raises(UnsupportedTradeError, match="Unsupported trade type: ExoticTrade"):
        adapter.price(ExoticTrade(), MarketState())


def test_registry_allows_new_trade_type_without_adapter_edit() -> None:
    """Ensure registry extension works without modifying adapter internals."""

    @dataclass(frozen=True)
    class FxForwardTrade:
        """Synthetic trade used to prove runtime extensibility."""

        notional: float

    @PricerAdapter.register(FxForwardTrade)
    def _price_fx_forward(adapter, trade, market_state):
        """Simple extension handler used only in this test."""
        return trade.notional * 0.01

    adapter = PricerAdapter()
    result = adapter.price(FxForwardTrade(notional=3_000_000), MarketState())

    assert result == 30_000.0
