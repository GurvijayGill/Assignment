# Concept and Blueprint

## Why This Design

The three pricing libraries use different interfaces (function args, dict input, class method).  
`PricerAdapter.price(trade, market_state)` provides one stable entry point and hides those differences.

A registry-based adapter is used to keep extension simple:
- routing is explicit and testable
- new trade types are added by registration
- no edits are needed in `PricerAdapter.price`

## Blueprint

- Trade models: `IRSTrade`, `SwaptionTrade`, `CapFloorTrade`
- Market container: `MarketState` (`curves`, `market_data`, `vol_surfaces`)
- Core API: `PricerAdapter.price(trade, market_state) -> float`
- Dispatch: registry + `@PricerAdapter.register(...)`
- Error path: `UnsupportedTradeError` for unknown trade types

Built-in handlers map directly to each library:
- IRS -> `price_swap(...)`
- Swaption -> `swaption_pv(...)`
- Cap/Floor -> `CapFloorPricer.price(...)`

## Flow

1. Call `adapter.price(trade, market_state)`.
2. Resolve a handler from the trade type (MRO-aware).
3. Pull required market inputs from `market_state`.
4. Call the corresponding backend pricer.
5. Return `float`.

## Extending New Trades

Register a new handler:

```python
@PricerAdapter.register(NewTrade)
def _price_new_trade(adapter, trade, market_state):
    return some_pricer(...)
```

## Testing Strategy

- Verify routing for IRS, swaption, and cap/floor.
- Verify argument forwarding to underlying pricers.
- Verify unsupported trade raises `UnsupportedTradeError`.
- Verify runtime registration works for a new trade type.
