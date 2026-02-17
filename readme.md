# Unified Pricing Adapter

This project implements a single adapter interface for trade pricing across multiple legacy libraries with different signatures.

## Public Interface

- `PricerAdapter.price(trade, market_state) -> float`

The adapter detects trade type and routes to the correct underlying pricing function/object.

## Trade Types Covered

- `IRSTrade` -> routes to `price_swap(notional, fixed_rate, start, end, curve)`
- `SwaptionTrade` -> routes to `swaption_pv(trade_dict, market_data)`
- `CapFloorTrade` -> routes to `CapFloorPricer.price(cap, curve, vol_surface, **kwargs)`

## Extensibility

The adapter uses a class-level registry and `@PricerAdapter.register(TradeType)` decorator.
New trade support can be plugged in by registering a handler for a new trade class without modifying existing `price` logic.

## How to Add a New Trade Type

```python
from dataclasses import dataclass
from price_adapter import MarketState, PricerAdapter


@dataclass(frozen=True)
class FxForwardTrade:
    notional: float
    forward_points: float


@PricerAdapter.register(FxForwardTrade)
def _price_fx_forward(adapter: PricerAdapter, trade: FxForwardTrade, market_state: MarketState) -> float:
    spot = float(market_state.market_data.get("fx_spot", 1.0))
    return trade.notional * (spot + trade.forward_points - spot)
```

After registration, call `adapter.price(FxForwardTrade(...), market_state)` with no changes to `PricerAdapter.price`.

## Error Handling

Unsupported trades raise `UnsupportedTradeError`.

## Files

- `price_adapter.py`: Adapter, trade models, sample library signatures.
- `tests/test_pricer_adapter.py`: Pytest tests for routing, unsupported trades, and registry extensibility.
- `demo_price.py`: Runnable demo for the adapter public interface.
- `concept.md`: Reasoning and design blueprint.
- `requirements.txt`: Python test dependency list.
- `Makefile`: `install` and `test` shortcuts.
- `run_tests.ps1`: Windows-friendly test runner script.

## Setup

```bash
python -m pip install -r requirements.txt
```

## Run Tests

```bash
python -m pytest -q -p no:cacheprovider
```

## Convenience Commands

```bash
make install
make test
```

```powershell
.\run_tests.ps1 -Install
# or
.\run_tests.ps1
```

## Example Usage

```python
from datetime import date
from price_adapter import IRSTrade, MarketState, PricerAdapter

adapter = PricerAdapter()
trade = IRSTrade(
    notional=1_000_000,
    fixed_rate=0.032,
    start=date(2026, 1, 1),
    end=date(2031, 1, 1),
    curve_id="usd_ois",
)
market_state = MarketState(curves={"usd_ois": {"par_rate": 0.03}})

pv = adapter.price(trade, market_state)
print(pv)
```
