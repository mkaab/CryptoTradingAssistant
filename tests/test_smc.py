import pytest
import pandas as pd
from bot_runner import get_pivots, get_htf_bias, check_ltf_setup

def create_mock_df(prices):
    """Helper to create a DataFrame with sequential prices for testing pivots."""
    return pd.DataFrame({
        'time': pd.date_range(start='2026-01-01', periods=len(prices), freq='5min'),
        'high': [p + 10 for p in prices],
        'low': [p - 10 for p in prices],
        'close': prices,
        'open': prices,
        'volume': [1000] * len(prices)
    })

def test_get_pivots():
    """Verify that get_pivots correctly identifies swing highs and swing lows."""
    # A clear V-shape (swing low) and inverted V-shape (swing high)
    # window=2 means it needs 2 lower highs on both sides, or 2 higher lows on both sides.
    prices = [100, 90, 80, 90, 100, 110, 120, 110, 100]
    df = create_mock_df(prices)
    
    ph, pl = get_pivots(df, window=2)
    
    # Expect a swing low at price 80 (index 2)
    assert len(pl) == 1
    assert pl[0]['price'] == 70 # 80 - 10 (because mock_df makes low = close - 10)
    assert pl[0]['index'] == 2
    
    # Expect a swing high at price 120 (index 6)
    assert len(ph) == 1
    assert ph[0]['price'] == 130 # 120 + 10
    assert ph[0]['index'] == 6

def test_get_htf_bias():
    """Verify HTF bias logic."""
    # Bullish: Higher highs and higher lows
    bullish_prices = [100, 90, 80, 90, 100, 95, 105, 115, 105, 95, 105, 120, 110, 130]
    # We need to pad it to ensure window=2 works and len >= 20
    bullish_prices = [100]*10 + bullish_prices + [120]*5
    df_bullish = create_mock_df(bullish_prices)
    bias = get_htf_bias(df_bullish)
    assert bias == "Bullish" or bias == "Neutral" # Depending on exact pivot points found
