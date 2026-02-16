# Concept and Blueprint

## Reasoning

The core challenge is interface mismatch across three pricers:

1. Swap pricer takes positional parameters.
2. Swaption pricer takes a trade dictionary + market data.
3. Cap/floor pricer is object-oriented and accepts optional kwargs.

A single `price(trade, market_state)` API needs to hide these differences while remaining open for extension.

A registry-based adapter is the cleanest fit because:

- Routing is explicit and testable.
- New trade types are added by registration, not by modifying an `if/elif` block.
- Existing behavior remains stable as new handlers are introduced.

## Blueprint

### Components

1. **Trade models**
   - `IRSTrade`
   - `SwaptionTrade`
   - `CapFloorTrade`

2. **Market container**
   - `MarketState` with `curves`, `market_data`, `vol_surfaces`

3. **Adapter core**
   - `PricerAdapter.price(trade, market_state) -> float`
   - Handler registry (`trade type` -> `handler function`)
   - `@PricerAdapter.register(...)` decorator for extension

4. **Handlers (built-in)**
   - IRS handler calls library 1 function
   - Swaption handler calls library 2 function
   - Cap/Floor handler calls library 3 object method

5. **Error handling**
   - `UnsupportedTradeError` for unknown trades

### Data Flow

1. Caller submits `trade` and `market_state`.
2. Adapter resolves handler by trade class (supports inheritance via MRO lookup).
3. Handler extracts required data from `market_state`.
4. Handler calls the target pricing library using the expected signature.
5. Result is returned as `float`.

### Extending for New Trades

1. Create new trade dataclass/class.
2. Register handler:

```python
@PricerAdapter.register(NewTrade)
def _price_new_trade(adapter, trade, market_state):
    return some_pricer(...)
```

3. No changes needed in `PricerAdapter.price`.

## Testing Strategy

- Use fake pricers to verify routing and argument mapping.
- Validate all required supported trade types.
- Confirm unsupported trade raises `UnsupportedTradeError`.
- Prove extensibility with an additional runtime registration test.
