"""
🧬 DNA: v16.6 (Sovereign Purity & Psycho-Kinematic Sensors) [DNA Header]
🏢 UNIT: PSYCHO_KINEMATIC_SENSOR (A03 Extension)
🛠️ ROLE: NEURO_WARFARE_RADAR
📖 DESC: 4 Algorithms to Extract Psychological Frequency (Psycho-Kinematic Sensors).
         Measure the "devil's music" of the Elite on the price chart.
         Detect: Boiling Frog (HDR), Choppy Grinder (CWG), Dead Cat Bounce (DTA), Capitulation (MPI).
         Data: pure OHLCV from Yahoo Finance or A01.
🔗 CALLS: yfinance, tools/imperial_state.py
📟 I/O: Redis: zcl:psycho:sensors (TTL 30m)
🛡️ INTEGRITY: Read-only price data, no trading actions.
"""

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))

import os
import json
import time
import logging
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, Optional

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from tools.imperial_state import matrix
except ImportError:
    from imperial_state import matrix

log = logging.getLogger("PSYCHO_KINEMATIC_SENSORS")
if not log.handlers:
    log.setLevel(logging.INFO)
    log.addHandler(logging.StreamHandler())

_CACHE: Dict[str, Any] = {}
_CACHE_TTL = 1800
_EPSILON = 1e-10


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS: OHLCV Data
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_ohlcv(ticker: str, period: str = "3mo", interval: str = "1d") -> Optional[Dict]:
    """Get OHLCV data from Yahoo Finance. Cache 30 minutes."""
    cache_key = f"ohlcv_{ticker}_{period}_{interval}"
    now = time.time()
    if cache_key in _CACHE:
        data, ts = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    if yf is None:
        log.error("yfinance not installed. Run: pip install yfinance")
        return None

    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        df = df.dropna()
        if df.empty:
            return None
        result = {
            "open": df["Open"].values.astype(float).flatten(),
            "high": df["High"].values.astype(float).flatten(),
            "low": df["Low"].values.astype(float).flatten(),
            "close": df["Close"].values.astype(float).flatten(),
            "volume": df["Volume"].values.astype(float).flatten(),
        }
        _CACHE[cache_key] = (result, now)
        return result
    except Exception as e:
        log.error(f"[PSYCHO] Fetch error for {ticker}: {e}")
        return None


def _sma(prices: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average for the entire series."""
    if len(prices) < period:
        return prices.copy()
    kernel = np.ones(period) / period
    # Pad to maintain length
    padded = np.pad(prices, (period - 1, 0), mode='edge')
    return np.convolve(padded, kernel, mode='valid')


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    """Average True Range."""
    if len(high) < 2:
        return _EPSILON
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    if len(tr) < period:
        return float(np.mean(tr)) if len(tr) > 0 else _EPSILON
    return float(np.mean(tr[-period:]))


def _z_score(value: float, series: list) -> float:
    """Z-Score."""
    if len(series) < 5:
        return 0.0
    mean = np.mean(series)
    std = np.std(series)
    if std < _EPSILON:
        return 0.0
    return float((value - mean) / std)


# ══════════════════════════════════════════════════════════════════════════════
# SENSOR 1: HDR — Hope-Decay Rate (Boiling Frog Slowly)
# ══════════════════════════════════════════════════════════════════════════════

def compute_hdr(ticker: str = "BTC-USD", sma_period: int = 20,
                lookback: int = 60) -> Dict[str, Any]:
    """
    Hope-Decay Index.
    HDR = Number of consecutive candles below SMA / (ATR + ε)

    HDR -> infinity: Waiting time too long + range shrinking.
    Elite finished "boiling the frog". Retail dumps because of BOREDOM, not FEAR.
    Floating Supply depleted -> Ready for violent Markup.
    """
    data = _fetch_ohlcv(ticker, period="3mo")
    if data is None:
        return {"hdr": 0.0, "status": "NO_DATA", "alert": "NO_DATA",
                "interpretation": f"Cannot retrieve OHLCV for '{ticker}'."}

    close = data["close"][-lookback:]
    high = data["high"][-lookback:]
    low = data["low"][-lookback:]

    if len(close) < sma_period + 5:
        return {"hdr": 0.0, "status": "INSUFFICIENT", "alert": "NO_DATA",
                "interpretation": "Insufficient data."}

    sma = _sma(close, sma_period)

    # Count consecutive candles BELOW SMA (from the end)
    consecutive_below = 0
    for i in range(len(close) - 1, -1, -1):
        idx = min(i, len(sma) - 1)
        if close[i] < sma[idx]:
            consecutive_below += 1
        else:
            break

    atr = _atr(high, low, close, 14)

    # Add: Bounce decay (bounces getting weaker)
    bounces = []
    for i in range(1, len(close) - 1):
        if close[i] > close[i-1] and close[i] > close[i+1]:
            bounce_pct = (close[i] - close[i-1]) / (close[i-1] + _EPSILON) * 100
            bounces.append(bounce_pct)

    bounce_decay = 0.0
    if len(bounces) >= 4:
        first_half_avg = np.mean(bounces[:len(bounces)//2])
        second_half_avg = np.mean(bounces[len(bounces)//2:])
        if first_half_avg > _EPSILON:
            bounce_decay = (second_half_avg - first_half_avg) / first_half_avg * 100

    hdr = consecutive_below / (atr + _EPSILON)

    if hdr > 5.0 and bounce_decay < -30:
        interpretation = (
            f"🔴 BOILING FROG COMPLETE: {consecutive_below} consecutive candles below SMA{sma_period}, "
            f"ATR shrunk to {atr:.2f}. Bounces decayed by {bounce_decay:.0f}%. "
            f"Retail dumped due to BOREDOM. Floating Supply depleted. "
            f"Ready for violent Markup. AMBUSH TO ACCUMULATE."
        )
        alert = "HOPE_EXHAUSTED"
    elif hdr > 3.0:
        interpretation = (
            f"🟡 Boiling frog in progress: {consecutive_below} candles below SMA, "
            f"HDR={hdr:.2f}. Crowd is exhausted."
        )
        alert = "BLEEDING"
    elif consecutive_below == 0 and atr > np.mean(data["close"][-lookback:]) * 0.03:
        interpretation = (
            f"🟢 Price above SMA, healthy volatility. No signs of boiling frog."
        )
        alert = "HEALTHY"
    else:
        interpretation = f"⚪ Neutral (HDR={hdr:.2f}, below SMA: {consecutive_below} candles)."
        alert = "NEUTRAL"

    return {
        "hdr": round(hdr, 4),
        "consecutive_below_sma": consecutive_below,
        "atr": round(atr, 4),
        "bounce_decay_pct": round(bounce_decay, 2),
        "alert": alert,
        "interpretation": interpretation,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SENSOR 2: CWG — Cognitive Whipsaw Grinder (Choppy Meat Grinder)
# ══════════════════════════════════════════════════════════════════════════════

def compute_cwg(ticker: str = "BTC-USD", sma_period: int = 20,
                lookback: int = 40) -> Dict[str, Any]:
    """
    Cognitive Whipsaw Grinder.
    CWG = (Number of SMA crossovers) * (Total Wicks / Total Bodies)

    CWG exploded -> Price wicking wildly up and down, sweeping stops of both sides.
    Elite activated "Grinder" mode. Every Breakout = TRAP.
    Action: PULL THE PLUG, FLAT.
    """
    data = _fetch_ohlcv(ticker, period="3mo")
    if data is None:
        return {"cwg": 0.0, "status": "NO_DATA", "alert": "NO_DATA",
                "interpretation": f"Cannot retrieve OHLCV for '{ticker}'."}

    close = data["close"][-lookback:]
    o = data["open"][-lookback:]
    h = data["high"][-lookback:]
    l = data["low"][-lookback:]

    if len(close) < sma_period + 5:
        return {"cwg": 0.0, "status": "INSUFFICIENT", "alert": "NO_DATA",
                "interpretation": "Insufficient data."}

    sma = _sma(close, sma_period)

    # Count number of Close crossovers across SMA
    crossovers = 0
    for i in range(1, min(len(close), len(sma))):
        if (close[i] > sma[i] and close[i-1] <= sma[i-1]) or \
           (close[i] < sma[i] and close[i-1] >= sma[i-1]):
            crossovers += 1

    # Wick / Body Ratio
    total_wick = 0.0
    total_body = 0.0
    for i in range(len(close)):
        body = abs(close[i] - o[i])
        upper_wick = h[i] - max(close[i], o[i])
        lower_wick = min(close[i], o[i]) - l[i]
        total_wick += upper_wick + lower_wick
        total_body += body

    wick_body_ratio = total_wick / (total_body + _EPSILON)

    cwg = crossovers * wick_body_ratio

    if cwg > 15:
        interpretation = (
            f"🔴 WHIPSAW GRINDER: {crossovers} SMA crossovers in {lookback} candles, "
            f"wick/body ratio = {wick_body_ratio:.2f}. CWG={cwg:.2f}. "
            f"Elite activated chaos mode. Every Breakout = TRAP. "
            f"PULL THE PLUG, FLAT!"
        )
        alert = "GRINDER_ACTIVE"
    elif cwg > 8:
        interpretation = (
            f"🟡 Grinder active: {crossovers} crossovers, "
            f"wicky candles (ratio={wick_body_ratio:.2f}). CWG={cwg:.2f}."
        )
        alert = "CHOPPY"
    elif cwg < 3 and crossovers <= 2:
        interpretation = (
            f"🟢 Clear trend: only {crossovers} crossovers, CWG={cwg:.2f}. "
            f"No signs of choppy grinder."
        )
        alert = "TRENDING"
    else:
        interpretation = f"⚪ Neutral (CWG={cwg:.2f}, crossovers={crossovers})."
        alert = "NEUTRAL"

    return {
        "cwg": round(cwg, 4),
        "crossovers": crossovers,
        "wick_body_ratio": round(wick_body_ratio, 4),
        "alert": alert,
        "interpretation": interpretation,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SENSOR 3: DTA — Dopamine Trap Asymmetry (Dead Cat Bounce)
# ══════════════════════════════════════════════════════════════════════════════

def compute_dta(ticker: str = "BTC-USD", lookback: int = 30) -> Dict[str, Any]:
    """
    Asymmetric Dopamine Trap.
    DTA = max(Green candle acceleration at bottom) / (Average velocity of adjacent Red candles)

    High DTA -> Green candles bouncing unreasonably fast (Dead Cat Bounce),
    but subsequent red candles drifting down slowly (hidden distribution).
    Elite pump price to attract buy side liquidity -> Trap.
    """
    data = _fetch_ohlcv(ticker, period="3mo")
    if data is None:
        return {"dta": 0.0, "status": "NO_DATA", "alert": "NO_DATA",
                "interpretation": f"Cannot retrieve OHLCV for '{ticker}'."}

    close = data["close"][-lookback:]
    o = data["open"][-lookback:]

    if len(close) < 10:
        return {"dta": 0.0, "status": "INSUFFICIENT", "alert": "NO_DATA",
                "interpretation": "Insufficient data."}

    # Detect bottom zone: close < SMA20 (downtrend context)
    sma = _sma(close, min(20, len(close) - 1))

    # Separate green/red candles
    green_accels = []  # Green candle acceleration
    red_speeds = []    # Red candle velocity

    for i in range(len(close)):
        if close[i] >= sma[i]:
            continue
            
        change_pct = (close[i] - o[i]) / (o[i] + _EPSILON) * 100
        if change_pct > 0:
            green_accels.append(abs(change_pct))
        else:
            red_speeds.append(abs(change_pct))

    if not green_accels or not red_speeds:
        return {"dta": 0.0, "status": "NO_CANDLES", "alert": "NEUTRAL",
                "interpretation": "Insufficient green/red candles for analysis."}

    max_green_accel = max(green_accels)
    avg_red_speed = np.mean(red_speeds)

    dta = max_green_accel / (avg_red_speed + _EPSILON)

    # Add: check for huge green candle after red streak (Dead Cat Bounce pattern: >=3 consecutive red candles then 1 huge green candle)
    dcb_detected = False
    for i in range(3, len(close)):
        all_red_before = all(close[j] < o[j] for j in range(i-3, i))
        big_green = (close[i] - o[i]) / (o[i] + _EPSILON) * 100 > 3.0
        if all_red_before and big_green:
            dcb_detected = True
            break

    if dta > 3.0 and dcb_detected:
        interpretation = (
            f"🔴 DEAD CAT BOUNCE: Green candle acceleration {max_green_accel:.1f}% "
            f"far exceeds average Red speed {avg_red_speed:.1f}%. DTA={dta:.2f}. "
            f"Dead Cat Bounce confirmed. Decoy trap to attract liquidity. "
            f"OPEN SHORT AT THE PEAK OF BOUNCE!"
        )
        alert = "DEAD_CAT_BOUNCE"
    elif dta > 2.5:
        interpretation = (
            f"🟡 Suspicious asymmetry: Green candle too fast compared to Red. "
            f"DTA={dta:.2f}. Possible technical bounce trap."
        )
        alert = "SUSPICIOUS_BOUNCE"
    elif dta < 1.2:
        interpretation = (
            f"🟢 Balanced: Green/Red candles symmetric (DTA={dta:.2f}). "
            f"No signs of Dead Cat Bounce."
        )
        alert = "BALANCED"
    else:
        interpretation = f"⚪ Neutral (DTA={dta:.2f})."
        alert = "NEUTRAL"

    return {
        "dta": round(dta, 4),
        "max_green_accel": round(max_green_accel, 4),
        "avg_red_speed": round(avg_red_speed, 4),
        "dcb_detected": dcb_detected,
        "alert": alert,
        "interpretation": interpretation,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SENSOR 3: MPI — Maximum Pain Integral (Capitulation Pain Integral)
# ══════════════════════════════════════════════════════════════════════════════

def compute_mpi(ticker: str = "BTC-USD", lookback: int = 60) -> Dict[str, Any]:
    """
    Maximum Pain Integral.
    MPI = Σ max(0, peak_VWAP - Price_t) * Volume_t * t

    MPI Z-Score > 3 -> Mental rubber band snapped.
    The herd panic sells at all costs. CAPITULATION.
    Tier 1 stands below with buckets to accumulate.
    ACTIVATE LONG FOR ALL POSITIONS!
    """
    data = _fetch_ohlcv(ticker, period="6mo")
    if data is None:
        return {"mpi": 0.0, "status": "NO_DATA", "alert": "NO_DATA",
                "interpretation": f"Cannot retrieve OHLCV for '{ticker}'."}

    close = data["close"]
    volume = data["volume"]

    if len(close) < lookback + 10:
        return {"mpi": 0.0, "status": "INSUFFICIENT", "alert": "NO_DATA",
                "interpretation": "Insufficient data."}

    # VWAP from the nearest peak (Anchored VWAP)
    peak_idx = np.argmax(close[-lookback*2:]) + max(0, len(close) - lookback*2)
    peak_vwap = float(close[peak_idx])

    # Compute MPI from peak to present
    mpi_raw = 0.0
    mpi_series = []
    t = 0
    for i in range(peak_idx, len(close)):
        t += 1
        pain = max(0.0, peak_vwap - close[i])
        weighted_pain = pain * volume[i] * t
        mpi_raw += weighted_pain
        mpi_series.append(mpi_raw)

    # Normalize MPI using rolling Z-Score
    if len(mpi_series) >= 10:
        mpi_z = _z_score(mpi_series[-1], mpi_series)
    else:
        mpi_z = 0.0

    # Add: Volume spike at bottom (capitulation confirmation)
    recent_vol = float(np.mean(volume[-5:])) if len(volume) >= 5 else 0
    avg_vol = float(np.mean(volume[-lookback:])) if len(volume) >= lookback else _EPSILON
    vol_spike = recent_vol / (avg_vol + _EPSILON)

    # Drawdown from peak
    drawdown_pct = (peak_vwap - close[-1]) / (peak_vwap + _EPSILON) * 100

    if mpi_z > 3.0 and vol_spike > 2.0:
        interpretation = (
            f"🔴 CAPITULATION! MPI Z-Score={mpi_z:.2f}, Volume spike={vol_spike:.1f}x. "
            f"Drawdown from peak: {drawdown_pct:.1f}%. "
            f"Mental rubber band snapped. The herd sells at all costs. "
            f"Tier 1 catching with buckets. "
            f"ACTIVATE LONG FOR ALL POSITIONS!"
        )
        alert = "CAPITULATION"
    elif mpi_z > 2.0:
        interpretation = (
            f"🟡 Extreme pain: MPI Z={mpi_z:.2f}. Drawdown {drawdown_pct:.1f}%. "
            f"Crowd is exhausted. Nearing capitulation point."
        )
        alert = "EXTREME_PAIN"
    elif mpi_z > 1.0:
        interpretation = (
            f"🟡 Elevated pain: MPI Z={mpi_z:.2f}. Drawdown {drawdown_pct:.1f}%."
        )
        alert = "ELEVATED_PAIN"
    elif drawdown_pct < 5:
        interpretation = (
            f"🟢 Near peak: Drawdown only {drawdown_pct:.1f}%. "
            f"No pain. Caution - the most comfortable place is the most dangerous one."
        )
        alert = "EUPHORIA_ZONE"
    else:
        interpretation = f"⚪ Neutral (MPI Z={mpi_z:.2f}, DD={drawdown_pct:.1f}%)."
        alert = "NEUTRAL"

    return {
        "mpi_z": round(mpi_z, 4),
        "drawdown_pct": round(drawdown_pct, 2),
        "vol_spike": round(vol_spike, 4),
        "peak_price": round(peak_vwap, 2),
        "current_price": round(float(close[-1]), 2),
        "alert": alert,
        "interpretation": interpretation,
    }


# ══════════════════════════════════════════════════════════════════════════════
# COMPOSITE: Psycho-Kinematic Matrix (Psychological Warfare)
# ══════════════════════════════════════════════════════════════════════════════

def compute_psycho_matrix(ticker: str = "BTC-USD") -> Dict[str, Any]:
    """
    Synthesize 4 dimensions of Psychology into Psycho State Vector.

    Detect:
    - CAPITULATION_BUY: HDR max + MPI spike + CWG low -> ACCUMULATE
    - GRINDER_FLAT: CWG max -> STAY FLAT
    - DEAD_CAT_SHORT: DTA max -> SHORT technical peak
    - HEALTHY: No signs of psychological manipulation

    Publish: zcl:psycho:sensors (TTL 30m) for A03/A05 to read.
    """
    hdr = compute_hdr(ticker)
    cwg = compute_cwg(ticker)
    dta = compute_dta(ticker)
    mpi = compute_mpi(ticker)

    # ── SIGNAL ENGINE ──
    signals = []

    # Capitulation Buy: Crowd collapses -> Elite accumulates
    if mpi.get("alert") == "CAPITULATION" and hdr.get("alert") in ("HOPE_EXHAUSTED", "BLEEDING"):
        signals.append("MPI+HDR: CAPITULATION BUY — Crowd capitulates after prolonged boiling frog")

    # Grinder Flat: Do not play in choppy grinder zone
    if cwg.get("alert") == "GRINDER_ACTIVE":
        signals.append("CWG: GRINDER ACTIVE — FLAT, refusing to participate")

    # Dead Cat Short: Fake green candle
    if dta.get("alert") == "DEAD_CAT_BOUNCE":
        signals.append("DTA: DEAD CAT BOUNCE — SHORT peak of technical bounce")

    # Euphoria Warning: Near peak, crowd is comfortable
    if mpi.get("alert") == "EUPHORIA_ZONE" and cwg.get("alert") == "TRENDING":
        signals.append("MPI: EUPHORIA — Too comfortable = danger")

    # Verdict
    if any("CAPITULATION BUY" in s for s in signals):
        psycho_verdict = "CAPITULATION_BUY_SIGNAL"
    elif any("FLAT" in s for s in signals):
        psycho_verdict = "GRINDER_FLAT"
    elif any("SHORT" in s for s in signals):
        psycho_verdict = "DEAD_CAT_SHORT"
    elif any("EUPHORIA" in s for s in signals):
        psycho_verdict = "EUPHORIA_WARNING"
    else:
        psycho_verdict = "NEUTRAL"

    psycho_state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "sensors": {
            "HDR": hdr,
            "CWG": cwg,
            "DTA": dta,
            "MPI": mpi,
        },
        "psycho_verdict": psycho_verdict,
        "signals": signals,
        "signal_count": len(signals),
        "interpretation": _build_psycho_narrative(hdr, cwg, dta, mpi, signals, psycho_verdict),
    }

    # Publish to Redis
    try:
        matrix.set("PSYCHO", "sensors", psycho_state, ttl=1800)
        log.info(f"[PSYCHO] Published psycho:sensors | Verdict: {psycho_verdict} | Signals: {len(signals)}")
    except Exception as e:
        log.error(f"[PSYCHO] Redis publish error: {e}")

    return psycho_state


def _build_psycho_narrative(hdr, cwg, dta, mpi, signals, verdict) -> str:
    """Synthesized narrative for A03/A05."""
    parts = []

    if verdict == "CAPITULATION_BUY_SIGNAL":
        parts.append("🔴 CAPITULATION SIGNAL: The crowd has completely collapsed.")
        parts.append("Elite is accumulating from shaky hands. ACTIVATE LONG.")
    elif verdict == "GRINDER_FLAT":
        parts.append("🟡 WHIPSAW GRINDER IS RUNNING. PULL THE PLUG, FLAT.")
        parts.append("Refuse to participate in this chaotic rhythm.")
    elif verdict == "DEAD_CAT_SHORT":
        parts.append("🔴 DEAD CAT BOUNCE. Fake green candle after a red streak.")
        parts.append("SHORT peak of technical bounce. Dopamine trap active.")
    elif verdict == "EUPHORIA_WARNING":
        parts.append("🟡 EUPHORIA: Crowd is overly comfortable.")
        parts.append("The most comfortable zone = the most dangerous zone.")

    for sig in signals:
        parts.append(f"  ⚠️ {sig}")

    parts.append(f"\nHDR: {hdr.get('interpretation', 'N/A')}")
    parts.append(f"CWG: {cwg.get('interpretation', 'N/A')}")
    parts.append(f"DTA: {dta.get('interpretation', 'N/A')}")
    parts.append(f"MPI: {mpi.get('interpretation', 'N/A')}")

    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# CLI & MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Psycho-Kinematic Sensors (HDR/CWG/DTA/MPI)")
    parser.add_argument("--ticker", default="BTC-USD", help="Ticker")
    parser.add_argument("--once", action="store_true", help="Run once")
    parser.add_argument("--interval", type=int, default=1800, help="Interval (s)")
    args = parser.parse_args()

    if args.once:
        result = compute_psycho_matrix(ticker=args.ticker)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        log.info(f"[PSYCHO] Starting Psycho-Kinematic Sensor loop | ticker={args.ticker}")
        while True:
            try:
                result = compute_psycho_matrix(ticker=args.ticker)
                log.info(f"[PSYCHO] Cycle complete | Verdict: {result['psycho_verdict']}")
            except Exception as e:
                log.error(f"[PSYCHO] Cycle error: {e}")
            time.sleep(args.interval)
