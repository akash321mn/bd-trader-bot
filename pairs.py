# User input -> Deriv symbol mapping
USER_TO_DERIV = {
    # Forex
    "EURUSD": "frxEURUSD",
    "GBPUSD": "frxGBPUSD",
    "USDJPY": "frxUSDJPY",
    "AUDUSD": "frxAUDUSD",
    "USDCAD": "frxUSDCAD",
    "GBPJPY": "frxGBPJPY",
    "EURGBP": "frxEURGBP",
    "EURJPY": "frxEURJPY",
    "XAUUSD": "frxXAUUSD",  # Gold
    # Crypto
    "BTCUSD": "cryBTCUSD",
    "ETHUSD": "cryETHUSD",
    "LTCUSD": "cryLTCUSD",
    "BCHUSD": "cryBCHUSD",
}

# Normalize variants (USDT -> USD)
NORMALIZE = {
    "BTCUSDT": "BTCUSD",
    "ETHUSDT": "ETHUSD",
    "LTCUSDT": "LTCUSD",
    "BCHUSDT": "BCHUSD",
}

# Timeframe -> seconds
TF_TO_GRAN = {
    "M5": 300,
    "M10": 600,
    "M15": 900,
}

def normalize_symbol(sym):
    if not sym:
        return None
    s = str(sym).strip().upper()
    return NORMALIZE.get(s, s)

def to_deriv_symbol(sym):
    s = normalize_symbol(sym)
    return USER_TO_DERIV.get(s)

def is_supported_tf(tf):
    if not tf:
        return False
    return str(tf).strip().upper() in TF_TO_GRAN

def granularity(tf):
    tf_str = str(tf).strip().upper()
    return TF_TO_GRAN.get(tf_str)

def supported_user_symbols():
    return list(USER_TO_DERIV.keys())

def supported_timeframes():
    return list(TF_TO_GRAN.keys())
