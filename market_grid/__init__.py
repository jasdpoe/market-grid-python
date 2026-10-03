"""Independent market data and indicator library."""

from .market import calculate_indicators, get_market_data, validate_request

__all__ = ["calculate_indicators", "get_market_data", "validate_request"]
__version__ = "1.0.0"
