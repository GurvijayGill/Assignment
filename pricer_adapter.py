"""Unified pricing adapter across heterogeneous pricing library signatures.

This module exposes a single entry point, :class:`PricerAdapter`, that routes
domain trade objects to underlying pricers with incompatible call interfaces.
It demonstrates an extensible registry pattern where each trade type registers
its own pricing handler without modifying the core adapter routing logic.

The sample pricers in this file intentionally keep formulas simple because the
focus is interface adaptation and dispatch rather than quantitative accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Dict, Mapping, Optional, Type, TypeVar


# -----------------------
# Existing pricing library signatures
# -----------------------
def price_swap(notional: float, fixed_rate: float, start: date, end: date, curve: Mapping[str, Any]) -> float:
    """Price a vanilla fixed-for-floating swap with a toy formula.

    Args:
        notional: Trade notional amount.
        fixed_rate: Contract fixed rate paid or received.
        start: Effective date of the swap.
        end: Maturity date of the swap.
        curve: Curve-like mapping, optionally containing ``par_rate``.

    Returns:
        A toy present value, computed as ``notional * (fixed_rate - par_rate)``
        multiplied by an ACT/365 year fraction.
    """
    year_fraction = max((end - start).days / 365.0, 0.0)
    par_rate = float(curve.get("par_rate", fixed_rate))
    return notional * (fixed_rate - par_rate) * year_fraction


def swaption_pv(trade_dict: Mapping[str, Any], market_data: Mapping[str, Any]) -> float:
    """Price a swaption from generic trade and market mappings.

    Args:
        trade_dict: Dictionary-like trade payload. Expected keys include
            ``notional`` and ``annuity``.
        market_data: Market inputs. Expected key: ``implied_vol``.

    Returns:
        A toy present value ``notional * annuity * implied_vol``.
    """
    notional = float(trade_dict.get("notional", 0.0))
    annuity = float(trade_dict.get("annuity", 1.0))
    implied_vol = float(market_data.get("implied_vol", 0.0))
    return notional * annuity * implied_vol


class CapFloorPricer:
    """Object-style cap/floor pricer representing the third library API."""

    def price(
        self,
        cap: Mapping[str, Any],
        curve: Mapping[str, Any],
        vol_surface: Mapping[str, Any],
        **kwargs: Any,
    ) -> float:
        """Price a cap/floor instrument using curve and volatility inputs.

        Args:
            cap: Cap/floor payload, typically including ``notional`` and
                ``strike``.
            curve: Curve inputs, typically including ``forward``.
            vol_surface: Volatility inputs, typically including ``atm_vol``.
            **kwargs: Optional model controls. This sample supports ``scale``.

        Returns:
            A toy value equal to ``intrinsic * notional * atm_vol * scale``.
        """
        notional = float(cap.get("notional", 1.0))
        strike = float(cap.get("strike", 0.0))
        forward = float(curve.get("forward", strike))
        atm_vol = float(vol_surface.get("atm_vol", 0.0))
        scale = float(kwargs.get("scale", 1.0))
        intrinsic = max(forward - strike, 0.0)
        return intrinsic * notional * atm_vol * scale


# -----------------------
# Domain models
# -----------------------
@dataclass(frozen=True)
class IRSTrade:
    """Interest rate swap trade payload used by the adapter.

    Attributes:
        notional: Swap notional.
        fixed_rate: Contract fixed rate.
        start: Swap effective date.
        end: Swap maturity date.
        curve_id: Key used to lookup the pricing curve in ``MarketState.curves``.
    """

    notional: float
    fixed_rate: float
    start: date
    end: date
    curve_id: str


@dataclass(frozen=True)
class SwaptionTrade:
    """Swaption trade payload represented as a dictionary-like object.

    Attributes:
        trade_dict: Free-form mapping consumed by ``swaption_pv``.
    """

    trade_dict: Mapping[str, Any]


@dataclass(frozen=True)
class CapFloorTrade:
    """Cap/floor trade payload used by :class:`CapFloorPricer`.

    Attributes:
        cap: Instrument payload expected by ``CapFloorPricer.price``.
        curve_id: Key used to fetch a curve from ``MarketState.curves``.
        vol_surface_id: Key used to fetch a surface from
            ``MarketState.vol_surfaces``.
        kwargs: Optional keyword arguments forwarded to the cap/floor pricer.
    """

    cap: Mapping[str, Any]
    curve_id: str
    vol_surface_id: str
    kwargs: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketState:
    """Container for market objects used by adapter handlers.

    Attributes:
        curves: Mapping of curve identifiers to curve payloads.
        market_data: Generic market inputs used by dictionary-style pricers.
        vol_surfaces: Mapping of volatility surface identifiers to payloads.
    """

    curves: Mapping[str, Any] = field(default_factory=dict)
    market_data: Mapping[str, Any] = field(default_factory=dict)
    vol_surfaces: Mapping[str, Any] = field(default_factory=dict)


# -----------------------
# Adapter
# -----------------------
class UnsupportedTradeError(TypeError):
    """Raised when the adapter does not know how to price a given trade."""


TTrade = TypeVar("TTrade")
Handler = Callable[["PricerAdapter", Any, MarketState], float]


class PricerAdapter:
    """
    Single public interface that routes to library-specific pricers.

    Extensibility comes from the class-level registry and @register decorator.
    New trade handlers can be added without editing .price() or existing handlers.
    """

    _registry: Dict[Type[Any], Handler] = {}

    def __init__(
        self,
        *,
        swap_pricer: Callable[[float, float, date, date, Mapping[str, Any]], float] = price_swap,
        swaption_pricer: Callable[[Mapping[str, Any], Mapping[str, Any]], float] = swaption_pv,
        capfloor_pricer: Optional[CapFloorPricer] = None,
    ) -> None:
        """Create an adapter with injectable underlying pricer dependencies.

        Args:
            swap_pricer: Callable matching the ``price_swap`` signature.
            swaption_pricer: Callable matching the ``swaption_pv`` signature.
            capfloor_pricer: Object exposing ``price(cap, curve, vol_surface,
                **kwargs)``.
        """
        self._swap_pricer = swap_pricer
        self._swaption_pricer = swaption_pricer
        self._capfloor_pricer = capfloor_pricer or CapFloorPricer()

    @classmethod
    def register(
        cls, trade_type: Type[TTrade]
    ) -> Callable[
        [Callable[["PricerAdapter", TTrade, MarketState], float]],
        Callable[["PricerAdapter", TTrade, MarketState], float],
    ]:
        """Register a pricing handler for a trade type.

        Args:
            trade_type: Class of trade that the decorated handler can price.

        Returns:
            A decorator that stores the handler in the class-level registry.
        """

        def decorator(func: Callable[["PricerAdapter", TTrade, MarketState], float]) -> Callable[
            ["PricerAdapter", TTrade, MarketState], float
        ]:
            cls._registry[trade_type] = func  # type: ignore[assignment]
            return func

        return decorator

    @classmethod
    def _resolve_handler(cls, trade_type: Type[Any]) -> Optional[Handler]:
        """Resolve the nearest registered handler for a trade type.

        The lookup walks the trade type's method resolution order (MRO) to
        allow base-class registrations to support derived trade classes.

        Args:
            trade_type: Concrete class for the incoming trade object.

        Returns:
            A registered handler if found, otherwise ``None``.
        """
        for base in trade_type.__mro__:
            handler = cls._registry.get(base)
            if handler is not None:
                return handler
        return None

    def price(self, trade: Any, market_state: MarketState) -> float:
        """Price a trade by dispatching to its registered handler.

        Args:
            trade: Trade instance to price.
            market_state: Aggregated market inputs referenced by handlers.

        Returns:
            The trade present value as ``float``.

        Raises:
            UnsupportedTradeError: If no handler is registered for the trade
                type (or any base type in its MRO).
        """
        handler = self._resolve_handler(type(trade))
        if handler is None:
            raise UnsupportedTradeError(f"Unsupported trade type: {type(trade).__name__}")
        return float(handler(self, trade, market_state))


# -----------------------
# Built-in registrations
# -----------------------
@PricerAdapter.register(IRSTrade)
def _price_irs(adapter: PricerAdapter, trade: IRSTrade, market_state: MarketState) -> float:
    """Adapter handler for IRS trades using Library 1 swap pricer."""
    curve = market_state.curves[trade.curve_id]
    return adapter._swap_pricer(trade.notional, trade.fixed_rate, trade.start, trade.end, curve)


@PricerAdapter.register(SwaptionTrade)
def _price_swaption(adapter: PricerAdapter, trade: SwaptionTrade, market_state: MarketState) -> float:
    """Adapter handler for swaptions using Library 2 dictionary pricer."""
    return adapter._swaption_pricer(trade.trade_dict, market_state.market_data)


@PricerAdapter.register(CapFloorTrade)
def _price_capfloor(adapter: PricerAdapter, trade: CapFloorTrade, market_state: MarketState) -> float:
    """Adapter handler for cap/floor trades using Library 3 object pricer."""
    curve = market_state.curves[trade.curve_id]
    vol_surface = market_state.vol_surfaces[trade.vol_surface_id]
    return adapter._capfloor_pricer.price(trade.cap, curve, vol_surface, **dict(trade.kwargs))


__all__ = [
    "CapFloorPricer",
    "CapFloorTrade",
    "IRSTrade",
    "MarketState",
    "PricerAdapter",
    "SwaptionTrade",
    "UnsupportedTradeError",
    "price_swap",
    "swaption_pv",
]
