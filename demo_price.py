from dataclasses import dataclass
from datetime import date

from price_adapter import (
    CapFloorTrade,
    IRSTrade,
    MarketState,
    PricerAdapter,
    SwaptionTrade,
    UnsupportedTradeError,
)


@dataclass(frozen=True)
class ExoticTrade:
    """Unsupported trade used to demonstrate adapter error handling."""

    name: str = "snowball"


def main() -> None:
    """Run a few sample pricing calls through the unified adapter."""
    adapter = PricerAdapter()
    market_state = MarketState(
        curves={
            "usd_ois": {"par_rate": 0.03},
            "usd_3m": {"forward": 0.031},
        },
        market_data={"implied_vol": 0.22},
        vol_surfaces={"usd_3m_caps": {"atm_vol": 0.19}},
    )

    irs_trade = IRSTrade(
        notional=1_000_000,
        fixed_rate=0.032,
        start=date(2026, 1, 1),
        end=date(2031, 1, 1),
        curve_id="usd_ois",
    )
    swaption_trade = SwaptionTrade(
        trade_dict={"notional": 5_000_000, "annuity": 4.1, "strike": 0.028}
    )
    capfloor_trade = CapFloorTrade(
        cap={"type": "cap", "strike": 0.03, "notional": 2_000_000},
        curve_id="usd_3m",
        vol_surface_id="usd_3m_caps",
        kwargs={"scale": 1.2},
    )

    print(f"IRS PV: {adapter.price(irs_trade, market_state):,.2f}")
    print(f"Swaption PV: {adapter.price(swaption_trade, market_state):,.2f}")
    print(f"Cap/Floor PV: {adapter.price(capfloor_trade, market_state):,.2f}")

    try:
        adapter.price(ExoticTrade(), market_state)
    except UnsupportedTradeError as exc:
        print(f"Unsupported trade example: {exc}")


if __name__ == "__main__":
    main()
