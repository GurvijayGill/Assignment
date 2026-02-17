# Unified Pricing Adapter

Single public API for pricing multiple trade types with different backend signatures:

- `PricerAdapter.price(trade, market_state) -> float`

## Supported Routing

- `IRSTrade` -> `price_swap(notional, fixed_rate, start, end, curve)`
- `SwaptionTrade` -> `swaption_pv(trade_dict, market_data)`
- `CapFloorTrade` -> `CapFloorPricer.price(cap, curve, vol_surface, **kwargs)`

Unsupported types raise `UnsupportedTradeError`.

## Extending

Register a new trade handler without editing `PricerAdapter.price`:

```python
@PricerAdapter.register(NewTrade)
def _price_new_trade(adapter, trade, market_state):
    return some_pricer(...)
```

## Project Files

- `price_adapter.py` - adapter + trade models + handlers
- `tests/test_pricer_adapter.py` - pytest coverage
- `demo_price.py` - runnable usage demo
- `concept.md` - brief design notes

## Setup

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
python -m pytest -q tests/test_pricer_adapter.py
python demo_price.py
```

```
