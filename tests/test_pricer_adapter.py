from dataclasses import dataclass
from datetime import date

import pytest

from price_adapter import (
    CapFloorTrade,
    IRSTrade,
    MarketState,
    PricerAdapter,
    SwaptionTrade,
    UnsupportedTradeError,
)


def test_routes_irs_trade_to_swap_library():
    calls = {}

    def fake_swap_pricer(notional, fixed_rate, start, end, curve):
        calls["args"] = (notional, fixed_rate, start, end, curve)
        return 101.25

    adapter = PricerAdapter(swap_pricer=fake_swap_pricer)
    trade = IRSTrade(1_000_000, 0.032, date(2026, 1, 1), date(2031, 1, 1), "cad_ois")
    market_state = MarketState(curves={"cad_ois": {"par_rate": 0.03}})

    assert adapter.price(trade, market_state) == 101.25
    assert calls["args"] == (
        1_000_000,
        0.032,
        date(2026, 1, 1),
        date(2031, 1, 1),
        {"par_rate": 0.03},
    )


def test_routes_swaption_trade_to_swaption_library():
    calls = {}

    def fake_swaption_pricer(trade_dict, market_data):
        calls["args"] = (trade_dict, market_data)
        return 250_000.0

    adapter = PricerAdapter(swaption_pricer=fake_swaption_pricer)
    trade = SwaptionTrade({"notional": 5_000_000, "annuity": 4.1, "strike": 0.028})
    market_state = MarketState(market_data={"implied_vol": 0.22, "valuation_date": "2026-02-15"})

    assert adapter.price(trade, market_state) == 250_000.0
    assert calls["args"] == (
        {"notional": 5_000_000, "annuity": 4.1, "strike": 0.028},
        {"implied_vol": 0.22, "valuation_date": "2026-02-15"},
    )


def test_routes_capfloor_trade_to_capfloor_library():
    class FakeCapFloorPricer:
        def __init__(self):
            self.calls = []

        def price(self, cap, curve, vol_surface, **kwargs):
            self.calls.append((cap, curve, vol_surface, kwargs))
            return 42_500.5

    fake = FakeCapFloorPricer()
    adapter = PricerAdapter(capfloor_pricer=fake)
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

    assert adapter.price(trade, market_state) == 42_500.5
    assert fake.calls == [
        (
            {"type": "cap", "strike": 0.03, "notional": 2_000_000},
            {"forward": 0.031},
            {"atm_vol": 0.19},
            {"scale": 1.2, "greeks": True},
        )
    ]


def test_unsupported_trade_raises_custom_error():
    @dataclass(frozen=True)
    class ExoticTrade:
        descriptor: str = "snowball"

    with pytest.raises(UnsupportedTradeError, match="Unsupported trade type: ExoticTrade"):
        PricerAdapter().price(ExoticTrade(), MarketState())


def test_registry_allows_new_trade_type_without_adapter_edit():
    @dataclass(frozen=True)
    class FxForwardTrade:
        notional: float

    @PricerAdapter.register(FxForwardTrade)
    def _price_fx_forward(adapter, trade, market_state):
        return trade.notional * 0.01

    assert PricerAdapter().price(FxForwardTrade(3_000_000), MarketState()) == 30_000.0
