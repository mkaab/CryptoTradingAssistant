import pytest
import pandas as pd
from bot_runner import fetch_candles, TARGET_SYMBOLS

def test_kucoin_crypto_data():
    """Verify that Kucoin correctly returns 4H and 5m data for Crypto pairs."""
    crypto_symbols = [s for s in TARGET_SYMBOLS if "USDT" in s]
    
    for symbol in crypto_symbols:
        # Test 4H
        df_4h = fetch_candles(symbol, '4H')
        assert not df_4h.empty, f"Failed to fetch 4H data for {symbol}"
        assert all(col in df_4h.columns for col in ['time', 'open', 'close', 'high', 'low', 'volume']), f"Missing columns in {symbol} 4H data"
        assert len(df_4h) > 0, f"4H DataFrame is empty for {symbol}"
        
        # Test 5m
        df_5m = fetch_candles(symbol, '5m')
        assert not df_5m.empty, f"Failed to fetch 5m data for {symbol}"
        assert all(col in df_5m.columns for col in ['time', 'open', 'close', 'high', 'low', 'volume']), f"Missing columns in {symbol} 5m data"
        assert len(df_5m) > 0, f"5m DataFrame is empty for {symbol}"

def test_twelvedata_forex_gold_data():
    """Verify that TwelveData correctly returns 4H and 5m data for Forex/Gold.
    NOTE: This requires TWELVEDATA_API_KEY to be set in the environment or .env.
    """
    import os
    if not os.environ.get("TWELVEDATA_API_KEY"):
        pytest.skip("Skipping TwelveData tests because TWELVEDATA_API_KEY is not set.")
        
    td_symbols = [s for s in TARGET_SYMBOLS if "USDT" not in s]
    
    for symbol in td_symbols:
        # Test 4H
        df_4h = fetch_candles(symbol, '4H')
        assert not df_4h.empty, f"Failed to fetch 4H data for {symbol} via TwelveData"
        assert all(col in df_4h.columns for col in ['time', 'open', 'close', 'high', 'low', 'volume']), f"Missing columns in {symbol} 4H data"
        assert len(df_4h) > 0, f"4H DataFrame is empty for {symbol}"
        
        # Test 5m
        df_5m = fetch_candles(symbol, '5m')
        assert not df_5m.empty, f"Failed to fetch 5m data for {symbol} via TwelveData"
        assert all(col in df_5m.columns for col in ['time', 'open', 'close', 'high', 'low', 'volume']), f"Missing columns in {symbol} 5m data"
        assert len(df_5m) > 0, f"5m DataFrame is empty for {symbol}"
