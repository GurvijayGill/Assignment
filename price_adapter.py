"""Unified trade pricing adapter."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date


def price_swap(notional: float, fixed_rate: float, start: date, end: date, curve: Mapping[str, object],
) -> float:
    """Fixed stub value."""
    return 100.0


def swaption_pv(trade_dict: Mapping[str, object], market_data: Mapping[str, object]) -> float:
    """Fixed stub value."""
    return 200.0


class CapFloorPricer:
    """Object-style cap/floor pricer."""

    def price(self, cap: Mapping[str, object], curve: Mapping[str, object], vol_surface: Mapping[str, object],
        **kwargs: object,
    ) -> float:
        """Fixed stub value."""
        return 300.0


@dataclass(frozen=True)
class IRSTrade:
    notional: float 
    fixed_rate: float
    start: date
    end: date
    curve_id: str


@dataclass(frozen=True)
class SwaptionTrade:
    trade_dict: Mapping[str, object]


@dataclass(frozen=True)
class CapFloorTrade:
    cap: Mapping[str, object]
    curve_id: str
    vol_surface_id: str
    kwargs: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketState:
    curves: Mapping[str, object] = field(default_factory=dict)
    market_data: Mapping[str, object] = field(default_factory=dict)
    vol_surfaces: Mapping[str, object] = field(default_factory=dict)


class UnsupportedTradeError(TypeError):
    """Raised when no trade handler is registered."""


class PricerAdapter:
    """Single pricing interface backed by a trade-type registry."""

    _registry: dict[type, Callable] = {}

    def __init__(
        self,
        *,
        swap_pricer: Callable = price_swap,
        swaption_pricer: Callable = swaption_pv,
        capfloor_pricer: CapFloorPricer | None = None,
    ) -> None:
        self._swap_pricer = swap_pricer
        self._swaption_pricer = swaption_pricer
        self._capfloor_pricer = capfloor_pricer or CapFloorPricer()

    @classmethod
    def register(cls, trade_type: type) -> Callable:
        def decorator(func: Callable) -> Callable:
            cls._registry[trade_type] = func
            return func

        return decorator

    @classmethod
    def _resolve_handler(cls, trade_type: type) -> Callable | None:
        for base in trade_type.__mro__:
            handler = cls._registry.get(base)
            if handler is not None:
                return handler
        return None

    def price(self, trade: object, market_state: MarketState) -> float:
        handler = self._resolve_handler(type(trade))
        if handler is None:
            raise UnsupportedTradeError(f"Unsupported trade type: {type(trade).__name__}")
        return float(handler(self, trade, market_state))


@PricerAdapter.register(IRSTrade)
def _price_irs(adapter: PricerAdapter, trade: IRSTrade, market_state: MarketState) -> float:
    curve = market_state.curves[trade.curve_id]
    return adapter._swap_pricer(trade.notional, trade.fixed_rate, trade.start, trade.end, curve)


@PricerAdapter.register(SwaptionTrade)
def _price_swaption(adapter: PricerAdapter, trade: SwaptionTrade, market_state: MarketState) -> float:
    return adapter._swaption_pricer(trade.trade_dict, market_state.market_data)


@PricerAdapter.register(CapFloorTrade)
def _price_capfloor(adapter: PricerAdapter, trade: CapFloorTrade, market_state: MarketState) -> float:
    curve = market_state.curves[trade.curve_id]
    vol_surface = market_state.vol_surfaces[trade.vol_surface_id]
    return adapter._capfloor_pricer.price(trade.cap, curve, vol_surface, **dict(trade.kwargs))
