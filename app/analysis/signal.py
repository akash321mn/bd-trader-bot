from __future__ import annotations
from typing import Dict, Any, List, Tuple
import pandas as pd
from .indicators import ema, rsi_wilder, macd

# ---------- Compute indicators from candles ----------

def compute_indicators(candles: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    candles: list of dicts {epoch, open, high, low, close} sorted ASC
    """
    df = pd.DataFrame(candles)
    if df.empty or len(df) < 50:
        raise ValueError("Not enough candle data (need >= 50).")

    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["rsi14"] = rsi_wilder(df["close"], 14)
    macd_line, signal_line, hist = macd(df["close"], 12, 26, 9)
    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = hist
    return df

# ---------- Voting + confidence ----------

def vote_and_confidence(row: pd.Series) -> Tuple[str | None, int, Dict[str, str]]:
    price = float(row["close"])
    rsi = float(row["rsi14"])
    ema9 = float(row["ema9"])
    ema21 = float(row["ema21"])
    macd_v = float(row["macd"])
    macd_sig = float(row["macd_signal"])
    hist = float(row["macd_hist"])

    bullish = 0
    bearish = 0
    rationale: Dict[str, str] = {}

    # RSI
    if rsi < 30:
        bullish += 1; rationale["rsi"] = f"RSI at {rsi:.0f} (Oversold)"
    elif rsi > 70:
        bearish += 1; rationale["rsi"] = f"RSI at {rsi:.0f} (Overbought)"
    else:
        rationale["rsi"] = f"RSI at {rsi:.0f}"

    # EMA cross
    if ema9 > ema21:
        bullish += 1; rationale["ema"] = "EMA(9) above EMA(21) (Bullish)"
    elif ema9 < ema21:
        bearish += 1; rationale["ema"] = "EMA(9) below EMA(21) (Bearish)"
    else:
        rationale["ema"] = "EMA(9) equals EMA(21)"

    # MACD
    if hist > 0 and macd_v > macd_sig:
        bullish += 1; rationale["macd"] = "MACD histogram positive (Bullish)"
    elif hist < 0 and macd_v < macd_sig:
        bearish += 1; rationale["macd"] = "MACD histogram negative (Bearish)"
    else:
        rationale["macd"] = "MACD mixed"

    signal = None
    if bullish >= 2 and bullish > bearish:
        signal = "CALL"
    elif bearish >= 2 and bearish > bullish:
        signal = "PUT"

    base = 60 if ((bullish == 2) or (bearish == 2)) else 70 if ((bullish == 3) or (bearish == 3)) else 50
    bonus = 0
    if rsi < 25 or rsi > 75:
        bonus += 5
    ema_dist = abs(ema9 - ema21) / max(price, 1e-9)
    bonus += min(int(ema_dist * 800), 10)
    macd_strength = abs(hist) / max(price, 1e-9)
    bonus += min(int(macd_strength * 3000), 10)

    confidence = max(50, min(base + bonus, 95))
    return signal, int(confidence), rationale

def build_signal_text(pair: str, tf: str, row: pd.Series, signal: str | None, confidence: int, rationale: Dict[str, str]) -> str:
    last_price = float(row["close"])
    level = "High Conviction" if confidence >= 85 else "Medium-High" if confidence >= 80 else "Medium" if confidence >= 70 else "Low"
    stype = signal if signal else "⚠️ No Clear Direction"

    lines = [
        "⚡BD TRADER AUTO BOT⚡",
        "",
        f"🔹 Signal Type: {stype}",
        "🔹 Entry: Next Candle Opening",
        f"🔹 Last Price: {last_price:.5f}",
        f"🔹 Confidence Level: {confidence}% ({level})",
        "🔹 Technical Rationale:",
        f" - {rationale.get('rsi','')}",
        f" - {rationale.get('ema','')}",
        f" - {rationale.get('macd','')}",
        "",
        "⚠️ Risk Disclaimer: Binary options involve substantial risk. Ensure proper risk management and education before trading.",
    ]
    return "\n".join(lines)

def build_risk_text(confidence: int) -> str:
    return (
        "⚠️ **Risk Warning**\n"
        f"Confidence is {confidence}%, which indicates increased risk. Consider waiting for a cleaner setup or trying another pair/timeframe."
    )

def analyze_and_signal(df: pd.DataFrame, pair: str, tf: str) -> Dict[str, Any]:
    row = df.iloc[-1]
    signal, confidence, rationale = vote_and_confidence(row)
    msg = build_signal_text(pair, tf, row, signal, confidence, rationale)
    risky = (confidence < 70) or (signal is None)
    return {
        "message": msg,
        "risky": risky,
        "confidence": confidence,
        "signal": signal or "NONE",
        "price": float(row["close"]),
    }
