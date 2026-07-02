"""
🧬 DNA: v16.6 (Sovereign Purity) [DNA Header]
🏢 UNIT: SCHOLAR (A04) - BOOSTING
🛠️ ROLE: CM Fingerprint DPO Generator (VSA 4.0 Kinematics)
📖 DESC: Blind prediction contest among models to generate Kinematic-compliant DPO pairs.
"""
import sys
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env")
sys.path.insert(0, str(BASE_DIR / "tools"))
import json
import time
import uuid
import logging
import threading
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from collections import deque

# ── Dynamic Path Injection (Stage 20: Imperial Context) ───────────────────────
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

# 🔱 SOVEREIGN LIMITS 🔱
BOOST_HEARTBEAT_SEC = 300  # 5-minute heartbeat (300s) — Yield Cerebras bandwidth to A05 Deep Diagnosis


from imperial_state import matrix

# ------------------------------------------------------------------------------
# Performance Metrics Helpers (v16.9)
# ------------------------------------------------------------------------------
def _calculate_metrics_from_local_files():
    """Calculate metrics from dpo_lab/ (Stateless-ish)"""
    res = {
        "dataset_size": {"tong_cap_dpo_real": 0, "chosen_hom_nay": 0, "rejected_hom_nay": 0},
        "winrate": {"7_ngay": {"win_rate_pct": 0, "so_lenh": 0}, "all_time": {"win_rate_pct": 0}},
        "drawdown": {"chi_so_suc_khoe": 0, "avg_max_drawdown_pct": 0},
        "blind_health": {"accuracy_blind_pct": 0, "tong_blind_pairs": 0, "health_status": "Good"}
    }
    try:
        import glob
        # [STAIRS v16.10] Update path to A04/boosting and count total pairs (lines)
        target_dir = os.path.join(BASE_DIR, "dpo_lab", "A04", "boosting")
        count = 0
        if os.path.exists(target_dir):
            for f_path in glob.glob(os.path.join(target_dir, "pairs_*.jsonl")):
                try:
                    with open(f_path, 'r', encoding='utf-8') as f:
                        count += sum(1 for _ in f)
                except:
                    continue
        
        # Use a temporary dict for update to satisfy strict linter
        size_data: dict[str, int] = res["dataset_size"] # type: ignore
        size_data["tong_cap_dpo_real"] = count
    except Exception as e:
        log.error(f"Error calculating metrics: {e}")
    return res

def _publish_metrics_to_matrix():
    """Publish all metrics to the Matrix"""
    try:
        m = _calculate_metrics_from_local_files()
        matrix.set("A04", "dataset_size:latest", m["dataset_size"], ttl=86400)
        matrix.set("A04", "winrate:latest", m["winrate"], ttl=86400)
        matrix.set("A04", "drawdown:latest", m["drawdown"], ttl=86400)
        matrix.set("A04", "blind_health:latest", m["blind_health"], ttl=86400)
        log.info("[BOOST] Performance metrics published to Matrix.")
    except Exception as e:
        log.error(f"Error publishing metrics to Matrix: {e}")

# ------------------------------------------------------------------------------

# Intelligence Routing (Unified Empire Router)
# load_dotenv moved to top for Redis sync

# REDIS_URL deprecated in favor of Matrix interface
# Intelligence Routing (Unified Empire Router)
from llm_router import router_api_call
from imperial_brain import brain
from nlm_quota_router import cerebras_router as cerebras_tracker, gemini_router as gemini_tracker
from A04_BRAIN_HELPER import phan_tich_realtime, fingerprint_composite_man, tinh_kinematics
import nlm_changelog

# Paths (operations — not I/O storage)
DPO_LAB_DIR      = BASE_DIR / "dpo_lab"
BOOST_SCENARIOS  = BASE_DIR / "boost_scenarios_v19"
BOOST_LOGS       = BASE_DIR / "logs" / "a4_boost_v19"
# NOTE: BOOST_OUTPUT removed — DPO pairs now go through ImperialBrain (store_a04_lesson mode='boost')

for d in [DPO_LAB_DIR, BOOST_SCENARIOS, BOOST_LOGS]:
    d.mkdir(parents=True, exist_ok=True)

# Logging
from imperial_state import setup_agent_logger
log = setup_agent_logger("A04", "A04_BOOST")

# See is_rate_limit_error in nlm_quota_router


# Unified Empire Router active.


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-RESOLUTION OHLCV FETCH — The Four Scholars read 5 frames simultaneously
# ══════════════════════════════════════════════════════════════════════════════

# Large Cap: BTC, ETH, BNB — CM accumulates slowly, rallies long, dump is signaled
# Mid Cap: SOL, AVAX, MATIC, etc — CM pumps fast, distribution is short
# Penny/Alt: < 200M mcap — Pump & dump extremely fast, trap is most obvious

# ── 15 CORE COINS DIRECTORY & LISTING DATE (T0) ──────────────────────────
# Used to pick a random scenario from the past (Listing + 51w)
HISTORICAL_SYMBOLS = {
    "BTC/USDT": 1502942400000,
    "ETH/USDT": 1502942400000,
    "BNB/USDT": 1509926400000,
    "ADA/USDT": 1523937600000,
    "XRP/USDT": 1525420800000,
    "SOL/USDT": 1597118400000,
    "DOT/USDT": 1597780800000,
    "LINK/USDT": 1547625600000,
    "AVAX/USDT": 1600747200000,
    "LTC/USDT": 1513123200000,
    "ATOM/USDT": 1556510400000,
    "NEAR/USDT": 1602648000000,
    "TRX/USDT": 1528704000000,
    "ETC/USDT": 1528761600000,
    "MATIC/USDT": 1556200000000
}

# [DNA v20.0] Absolute timestamp for BTC Manual (1511136000000 + 101w)
BTC_MANUAL_MIN_T0 = 1572220800000 # 2019-10-28 00:00:00 UTC
BTC_MANUAL_MAX_T0 = 1774828800000 # 2026-03-30 00:00:00 UTC (Yesterday)

LARGE_CAP_SYMBOLS = {
    "BTC", "BITCOIN", "ETH", "ETHEREUM", "BNB", "BINANCE COIN"
}
MID_CAP_SYMBOLS = {
    "SOL", "SOLANA", "AVAX", "AVALANCHE", "MATIC", "POLYGON",
    "DOT", "POLKADOT", "LINK", "CHAINLINK", "UNI", "UNISWAP",
    "ADA", "CARDANO", "TON", "NEAR", "ATOM", "ICP", "APT", "SUI"
}


def classify_coin_type(ticker: str) -> str:
    """
    Classify coins by market cap to adjust CM analysis logic.
    Large Cap: Entity (Whale/Composite Man) behaves completely differently from Penny.
    """
    base = ticker.split("/")[0].split("-")[0].upper()
    if base in LARGE_CAP_SYMBOLS:
        return "LARGE_CAP"
    elif base in MID_CAP_SYMBOLS:
        return "MID_CAP"
    else:
        return "PENNY_ALT"


COIN_TYPE_CONTEXT = {
    "LARGE_CAP": (
        "This is Large Cap (BTC/ETH). Entity (Whale / Composite Man) behavior: "
        "silently accumulates weekly without changing the downtrend, "
        "gradually distributes during recovery without drawing abnormal volume, "
        "dumps only when distribution is sufficient — usually indicated by a long warning candle wick on the 4H timeframe."
    ),
    "MID_CAP": (
        "This is Mid Cap (SOL/AVAX/...). Entity behavior: "
        "accumulates faster (1-2 weeks), pushes price (pump) short but strong, "
        "distributes more clearly through divergence with BTC, "
        "dumps following BTC but with 2-3 times larger amplitude."
    ),
    "PENNY_ALT": (
        "This is Penny/Alt coin. Entity behavior: "
        "pumps & dumps extremely fast (hours to days), bull trap is most obvious at the peak, "
        "abruptly spiking volume = sign of Entity pumping price, "
        "distribution does NOT require much time — sells quickly before momentum dies out."
    ),
}


def lay_ohlcv_multi(ticker: str, ts_end_ms: int, exchange=None) -> dict:
    """
    Get multi-resolution candle data ending at ts_end_ms.
    Returns a dictionary of 5 timeframes for the Four Scholars to analyze simultaneously.

    Principles:
    - 1D x 200: Overall Wyckoff Phase context (6 months)
    - 4H x 168: Accumulation/distribution pattern of CM (4 weeks)
    - 1H x 120: CM pushes liquidity, setting up breakdown/breakout (5 days)
    - 15m x 288: Detailed CM order flow (3 days)
    - 1m x 480: Sudden spike / instant manipulation (last 8 hours)
    """
    import ccxt
    result = {
        "ticker": ticker,
        "ts_end_ms": ts_end_ms,
        "coin_type": classify_coin_type(ticker),
        "timeframes": {}
    }

    if exchange is None:
        try:
            exchange = ccxt.binance({"enableRateLimit": True})
        except Exception as e:
            log.error(f"[OHLCV_MULTI] Failed to create exchange: {e}")
            return result

    frames = [
        ("1d",  200, "Overall Wyckoff phase 6 months"),
        ("4h",  168, "CM accumulation/distribution 4 weeks"),
        ("1h",  120, "CM pushes liquidity 5 days"),
        ("15m", 288, "Detailed CM order flow 3 days"),
        ("1m",  480, "Spike / manipulation last 8 hours"),
    ]

    for tf, count, desc in frames:
        try:
            # Tính since từ ts_end_ms lùi về
            tf_ms = {"1d": 86400000, "4h": 14400000, "1h": 3600000,
                     "15m": 900000, "1m": 60000}.get(tf, 60000)
            since_ms = ts_end_ms - (count * tf_ms)

            candles = exchange.fetch_ohlcv(
                ticker, tf,
                since=since_ms,
                limit=count,
                params={"endTime": ts_end_ms}
            )
            # Filter to only get candles before ts_end_ms
            candles = [c for c in candles if c[0] <= ts_end_ms]
            # EMERGENCY Purity: Check for sufficient data (80%)
            if len(candles) < count * 0.8:
                log.warning(f"[OHLCV_MULTI] {ticker} {tf} missing candles ({len(candles)}/{count}) -> Rejected T0.")
                return None
            result["timeframes"][tf] = {
                "desc": desc,
                "count": len(candles),
                # Chỉ gửi OHLCV đã tóm tắt để tiết kiệm token
                "summary": _summarize_candles(candles, tf),
                "raw_tail": candles[-20:] if candles else [],  # 20 nến gần nhất raw
            }
            log.debug(f"[OHLCV_MULTI] {ticker} {tf}: {len(candles)} candles")
        except Exception as e:
            log.warning(f"[OHLCV_MULTI] {ticker} {tf} error: {e}")
            result["timeframes"][tf] = {"desc": desc, "count": 0, "summary": {}, "raw_tail": []}

    return result


def _summarize_candles(candles: list, tf: str) -> dict:
    """
    Summarize key statistics from candle list.
    Saves tokens when inputting into LLM.
    """
    if not candles:
        return {}
    closes = [c[4] for c in candles]
    volumes = [c[5] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]

    avg_vol = sum(volumes) / len(volumes) if volumes else 0
    last_vol = volumes[-1] if volumes else 0
    # Use int rounding to satisfy strict linter
    vol_ratio = int((last_vol / avg_vol) * 100) / 100.0 if avg_vol > 0 else 0

    # Calculate trend: % change from beginning to end
    price_change_pct = round((closes[-1] - closes[0]) / closes[0] * 100, 2) if closes[0] else 0

    # Detect volume spikes (> 2 times average)
    spikes = [i for i, v in enumerate(volumes) if v > avg_vol * 2]
    
    # Calculate candle wick ratio (long wick = sign of rejection)
    last_candle = candles[-1]
    body = abs(last_candle[4] - last_candle[1])  # close - open
    upper_wick = last_candle[2] - max(last_candle[1], last_candle[4])
    lower_wick = min(last_candle[1], last_candle[4]) - last_candle[3]
    wick_ratio_up = round(upper_wick / body, 2) if body > 0 else 0
    wick_ratio_dn = round(lower_wick / body, 2) if body > 0 else 0

    # VSA 4.0 Kinematics summary
    kin = tinh_kinematics(candles, lookback=min(50, len(candles)))

    return {
        "tf": tf,
        "n_candles": len(candles),
        "price_start": round(closes[0], 4),
        "price_end": round(closes[-1], 4),
        "price_change_pct": price_change_pct,
        "price_high": round(max(highs), 4),
        "price_low": round(min(lows), 4),
        "avg_volume": round(avg_vol, 2),
        "last_volume": round(last_vol, 2),
        "vol_ratio_vs_avg": vol_ratio,  # > 2 = spike
        "volume_spike_count": len(spikes),
        "volume_spike_positions": spikes[-5:],  # 5 most recent spikes
        "last_candle_wick_up": wick_ratio_up,   # > 2 = strong rejection
        "last_candle_wick_dn": wick_ratio_dn,   # > 2 = strong absorption
        "consecutive_bull": _count_consecutive(candles, bull=True),
        "consecutive_bear": _count_consecutive(candles, bull=False),
        "kinematics": {
            "kar": kin["kar"],
            "pei": kin["pei"],
            "mnr": kin["mnr"],
            "ca": kin["ca"],
            "tier": kin["tier"]
        }
    }


def _count_consecutive(candles: list, bull: bool) -> int:
    """Count consecutive bullish/bearish candles from the tail."""
    count = 0
    for c in reversed(candles):
        is_bull = c[4] >= c[1]  # close >= open
        if (bull and is_bull) or (not bull and not is_bull):
            count += 1
        else:
            break
    return count


def analyze_cm_fingerprint(nen_dict: dict) -> dict:
    """
    Analyze Composite Man footprints from multi-frame data.
    Returns opinions on CM behavior to be fed into the prompt for 32B.

    4 footprints to detect:
    1. Silent buying (Accumulation): steady 4H volume, small 1D step changes, rising bottoms
    2. Pump Impulse: 15m volume spike + long 1H body + gap up
    3. Silent selling (Distribution): price still rises slightly, volume increases, long upper wick on 4H
    4. Crash dump: very long bear body on 1m/15m + volume explosion
    """
    coin_type = nen_dict.get("coin_type", "MID_CAP")
    tfs = nen_dict.get("timeframes", {})

    d_1d  = tfs.get("1d",  {}).get("summary", {})
    d_4h  = tfs.get("4h",  {}).get("summary", {})
    d_1h  = tfs.get("1h",  {}).get("summary", {})
    d_15m = tfs.get("15m", {}).get("summary", {})
    d_1m  = tfs.get("1m",  {}).get("summary", {})

    signals = []
    cm_phase = "UNKNOWN"
    cm_tactic_score = {  # scoring each footprint
        "ACCUMULATE": 0,
        "MARKUP": 0,
        "DISTRIBUTE": 0,
        "MARKDOWN": 0,
    }

    # ── Footprint 1: Silent Accumulation ──────────────────────────────────
    # Steady 4H volume (no spikes), 1D slightly down or sideway, long lower wick on 1H
    if d_4h.get("vol_ratio_vs_avg", 1) < 1.3 and d_4h.get("volume_spike_count", 5) < 3:
        if d_1d.get("price_change_pct", 0) > -8 and d_1d.get("price_change_pct", 0) < 3:
            cm_tactic_score["ACCUMULATE"] += 2
            signals.append("📉→🔄 Steady 4H volume without spikes while price is sideways/slightly down — sign of silent absorption")
    if d_1h.get("last_candle_wick_dn", 0) > 1.5:
        cm_tactic_score["ACCUMULATE"] += 1
        signals.append("📌 Long lower wick on 1H (absorbing selling, CM is buying)")

    # ── Footprint 2: Strong Markup (Markup) ─────────────────────────────────────
    # Sudden 15m volume spike + consecutive bull 1H + strong 1D increase
    if d_15m.get("vol_ratio_vs_avg", 1) > 2.5:
        cm_tactic_score["MARKUP"] += 2
        signals.append(f"🚀 Volume spike 15m x{d_15m.get('vol_ratio_vs_avg')} vs avg — CM is pumping")
    if d_1h.get("consecutive_bull", 0) >= 4:
        cm_tactic_score["MARKUP"] += 1
        signals.append(f"🕯️ {d_1h.get('consecutive_bull')} consecutive bull candles on 1H — impulse is running")
    if d_1d.get("price_change_pct", 0) > 5 and d_1d.get("vol_ratio_vs_avg", 1) > 1.5:
        cm_tactic_score["MARKUP"] += 2
        signals.append("💹 1D increase >5% with high volume — Wyckoff Sign of Strength (SOS)")

    # ── Footprint 3: Silent Distribution ──────────────────────────────────
    # 1D price still increases, but long upper wick on 4H + increased 4H volume = CM is selling
    if d_4h.get("last_candle_wick_up", 0) > 1.8 and d_4h.get("vol_ratio_vs_avg", 1) > 1.2:
        cm_tactic_score["DISTRIBUTE"] += 2
        signals.append("🔔 Long upper wick on 4H + increased volume = Upthrust (UTAD) — CM is selling peak")
    if d_1d.get("price_change_pct", 0) > 0 and d_4h.get("volume_spike_count", 0) > 5:
        cm_tactic_score["DISTRIBUTE"] += 1
        signals.append("⚠️ Multiple 4H volume spikes while 1D is still green — hidden distribution")
    if d_1m.get("vol_ratio_vs_avg", 1) > 3 and d_1h.get("price_change_pct", 0) > 2:
        cm_tactic_score["DISTRIBUTE"] += 1
        signals.append("🧐 Volume 1m exploding at 1H peak — fast distribution before reversal")

    # ── Footprint 4: Crash Dump (Markdown) ───────────────────────────────────
    # Long bear body on 15m + volume explosion + consecutive bear on 1H
    if d_15m.get("consecutive_bear", 0) >= 5 and d_15m.get("vol_ratio_vs_avg", 1) > 2:
        cm_tactic_score["MARKDOWN"] += 2
        signals.append(f"💥 {d_15m.get('consecutive_bear')} consecutive bear candles on 15m + vol spike = Selling Climax")
    if d_1m.get("price_change_pct", 0) < -3 and d_1m.get("vol_ratio_vs_avg", 1) > 3:
        cm_tactic_score["MARKDOWN"] += 2
        signals.append("🔴 Decrease >3% with vol x3 in 1m — Panic sell / CM trap")

    # Determine overall CM phase
    cm_phase = max(cm_tactic_score, key=cm_tactic_score.get)
    if cm_tactic_score[cm_phase] == 0:
        cm_phase = "UNCLEAR"

    return {
        "coin_type": coin_type,
        "coin_context": COIN_TYPE_CONTEXT.get(coin_type, ""),
        "cm_phase": cm_phase,
        "cm_tactic_scores": cm_tactic_score,
        "signals": signals,
        "signal_count": len(signals),
    }


# ══════════════════════════════════════════════════════════════════════════════
# SMART ROUTED CALLS — With auto-rotation and fallback
# ══════════════════════════════════════════════════════════════════════════════

def call_contestant(prompt: str, est_tokens: int = 1200) -> tuple:
    """Call Qwen via Router using CONTESTANT flow (32B -> 9B -> 235B)."""
    text = brain.think_as("A04_BOOST", prompt, est_tokens=est_tokens, 
                          brain_mode="A04_BOOSTING_CONTESTANT", role="STUDY")
    if text and "ERROR" not in text:
        return text, "contestant_efficient_flow"
    
    # 🔱 DNA v20.7: Forward exhaustion error to upper layer
    if text and "EXHAUSTED" in text and "ERROR:" not in text:
        return text, "exhausted"
        
    log.warning(f"[ROUTER] Contestant error: {text[:200]}...") if text else None
    return None, "failed"

def call_judge(prompt: str, est_tokens: int = 2000) -> tuple:
    """Call Qwen via Router using JUDGE flow (235B -> 32B -> 9B)."""
    text = brain.think_as("A04_BOOST", prompt, est_tokens=est_tokens, 
                          brain_mode="A04_BOOSTING_JUDGE", role="TEACHER")
    if text and "ERROR" not in text:
        return text, "judge_precision_flow"
        
    # 🔱 DNA v20.7: Forward exhaustion error to upper layer
    if text and "EXHAUSTED" in text and "ERROR:" not in text:
        return text, "exhausted"
        
    log.warning(f"[ROUTER] Judge error: {text[:200]}...") if text else None
    return None, "failed"


CONTESTANT_PROMPT_BULL = """You are the Four Scholars — major disciples of Wyckoff and Elliott Wave. Task: identify Composite Man (CM) tactics.

=== UNBREAKABLE LAWS ===
✅ ONLY USE: Wyckoff Phase (A/B/C/D), Elliott Wave (wave count/ABC), pure volume, price action structures.
❌ ABSOLUTELY FORBIDDEN: RSI, MACD, Bollinger, MA cross, Stochastic, or any lagging indicators.
If forbidden indicators are used -> the trading pair is automatically disqualified. No exceptions.

=== COIN CLASSIFICATION AND ENTITY CONTEXT ===
{coin_context}

=== DETECTED ENTITY FOOTPRINTS ===
{cm_signals}

=== MULTI-TIMEFRAME MARKET DATA (T-0, CURRENT) ===
(Note: If some long-term timeframes like 100w are missing due to newly listed coins, please use the entire range of longest available data).
{multi_tf_data}

=== DECODING KINEMATICS VECTOR (VSA 4.0) ===
- KAR: >3.0 = Level 1 Apex Wall (Iceberg). <0.5 = Low supply/demand.
- PEI: >0.8 = Level 2 Bot smooth control. <0.3 = Micro noise.
- MNR: >0.7 = Level 3 Dump yard (Churning). STAND ASIDE.
- CA: >2.0 = Level 4 Panic/FOMO. If high CA + high KAR = Reversal at the wick.

=== MULTI-TIER RAG KNOWLEDGE (FROM COIN HISTORY) ===
{rag_context}

=== BOUNDED RATIONALITY INFORMATION SETUP ===
Note: You are analyzing aggregated historical data (OFI Candles). You are completely BLIND to the Order Book and Tick-data at T0. You cannot see Iceberg or Spoofing orders directly.

Therefore, you MUST perform "Ghost Footprints" tracking:
1. Do not make definitive judgments about hidden orders. Use probability: "The asymmetry between OFI and Price Delta indicates a high probability of absorption at this wick area."
2. Find "Failure Contexts": If OFI is extremely large (Long dominant) but price does NOT breakout -> That is indirect evidence of an Elite iceberg ask wall.
3. Never trust appearances: A large green volume candle is not necessarily bullish if it is accompanied by an abnormally high Absorption Ratio (AR).

STEP 1: TECHNICAL DEPTH & MICROSTRUCTURE (40% WEIGHT)
- OFI Anatomy: Anomalies between Net Order Flow (OFI) and price spread.
- Wyckoff Examination: Position in the Accumulation / Distribution cycle.
- Elliott Fractal Cycle: Waves within waves and Retracement levels.

STEP 2: ELITE / COMPOSITE MAN INTENT (40% WEIGHT)
- Reverse-engineer all technical indicators into ARTIFICIAL ACTION.
- Determine whether Elite is Absorbing or Trapping through "indirect footprints".

STEP 3: OUTCOME COMMAND (20% WEIGHT)
- Based on Elite intent, find the STRONGEST REASON indicating CM is about to PUMP price (Markup).

Return pure JSON:
{{
  "direction": "BULL",
  "wyckoff_phase": "...",
  "elliott_wave": "...",
  "cm_tactic": "...",
  "reasoning": "...",
  "pattern_shortcut": "...",
  "confidence": 0.0-1.0,
  "key_signals": [...]
}}"""

CONTESTANT_PROMPT_BEAR = """You are the Four Scholars — major disciples of Wyckoff and Elliott Wave. Task: identify Composite Man (CM) tactics.

=== UNBREAKABLE LAWS ===
✅ ONLY USE: Wyckoff Phase (A/B/C/D), Elliott Wave (wave count/ABC), pure volume, price action structures.
❌ ABSOLUTELY FORBIDDEN: RSI, MACD, Bollinger, MA cross, Stochastic, or any lagging indicators.
If forbidden indicators are used -> the trading pair is automatically disqualified. No exceptions.

=== COIN CLASSIFICATION AND ENTITY CONTEXT ===
{coin_context}

=== DETECTED ENTITY FOOTPRINTS ===
{cm_signals}

=== MULTI-TIMEFRAME MARKET DATA (T-0, CURRENT) ===
(Note: If some long-term timeframes like 100w are missing due to newly listed coins, please use the entire range of longest available data).
{multi_tf_data}

=== DECODING KINEMATICS VECTOR (VSA 4.0) ===
- KAR: >3.0 = Level 1 Apex Wall (Iceberg). <0.5 = Low supply/demand.
- PEI: >0.8 = Level 2 Bot smooth control. <0.3 = Micro noise.
- MNR: >0.7 = Level 3 Dump yard (Churning). STAND ASIDE.
- CA: >2.0 = Level 4 Panic/FOMO. If high CA + high KAR = Reversal at the wick.

=== MULTI-TIER RAG KNOWLEDGE (FROM COIN HISTORY) ===
{rag_context}

=== BOUNDED RATIONALITY INFORMATION SETUP ===
Note: You are analyzing aggregated historical data (OFI Candles). You are completely BLIND to the Order Book and Tick-data at T0. You cannot see Iceberg or Spoofing orders directly.

Therefore, you MUST perform "Ghost Footprints" tracking:
1. Do not make definitive judgments about hidden orders. Use probability: "The asymmetry between OFI and Price Delta indicates a high probability of absorption at this wick area."
2. Find "Failure Contexts": If OFI is extremely large (Short dominant) but price does NOT dump -> That is indirect evidence of an Elite iceberg bid wall.
3. Confirmation delay: Be wary of overly clear bearish signals, as Market Makers often create traps before actual Markdown.

STEP 1: TECHNICAL DEPTH & MICROSTRUCTURE (40% WEIGHT)
- OFI Anatomy: Anomalies between Net Order Flow (OFI) and price spread.
- Wyckoff Examination: Position in the Accumulation / Distribution cycle.
- Elliott Fractal Cycle: Waves within waves and Retracement levels.

STEP 2: ELITE / COMPOSITE MAN INTENT (40% WEIGHT)
- Reverse-engineer all technical indicators into ARTIFICIAL ACTION.
- Determine whether Elite is Absorbing or Trapping through "indirect footprints".

STEP 3: OUTCOME COMMAND (20% WEIGHT)
- Based on Elite intent, find the STRONGEST REASON indicating CM is about to DUMP price (Markdown).

Return pure JSON:
{{
  "direction": "BEAR",
  "wyckoff_phase": "...",
  "elliott_wave": "...",
  "cm_tactic": "...",
  "reasoning": "...",
  "pattern_shortcut": "...",
  "confidence": 0.0-1.0,
  "key_signals": [...]
}}"""

JUDGE_PROMPT = """You are the SUPREME MASTER — Wyckoff and Elliott Wave Master of the Zero-Cutloss Empire.
Task: Use historical data and actual results to teach your disciples. You must be extremely strict.

=== MONEY FLOW ANATOMY DATA (CM FINGERPRINT) ===
{cm_analysis}

=== MULTI-TIMEFRAME MARKET DATA (T-0) ===
<scenario>
{scenario_data}
</scenario>

=== STUDENT HYPOTHESIS (REJECTED) ===
{student_hypothesis}

=== ACTUAL RESULTS (T+30) ===
Direction: {actual_direction} | Magnitude: {actual_magnitude}

=== 4-LEVEL KINEMATICS AUDIT (MASTER CHECK) ===
- Level 1 (KAR): Check if there is absorption at the Climax candle?
- Level 2 (PEI): Is the trend actually smooth and controlled by bots, or is it just scattered noise?
- Level 3 (MNR): Are there signs of stop-hunt wicks from HFT Scavenger?
- Level 4 (CA): Is retail panicking or FOMO liquidating?

=== SOVEREIGN ANATOMY PROCESS (MUST COMPLY STEP BY STEP): ===
STEP 0 — KINEMATICS & BOUNDED RATIONALITY AUDIT:
   Check if the student uses the 4-level vector (KAR/PEI/MNR/CA) to infer Elite intent. If the student makes definitive judgments about "hidden orders" without indirect Kinematics evidence -> MUST CRITICIZE SEVERELY for violating Bounded Rationality.

STEP 1 — KINEMATICS & MICROSTRUCTURE AUDIT:
   Point out exactly which KAR/PEI/MNR/CA metrics the student misread or ignored. For example: KAR > 3 but the student failed to recognize the Iceberg wall, or PEI < 0.3 but they still called it a trend. Explain the connection between Kinematics and actual Composite Man behavior.

STEP 2 — ACADEMIC REASONING (ELIMINATING HALLUCINATION):
   Explain why the student's logic led to hallucination. Use pure Wyckoff/Elliott theory to refute shallow thinking.

STEP 3 — INVESTIGATING REAL INTENT OF ELITE:
   Based on the actual result, decode the dark intent of the Composite Man behind the wicks and volume explosion at T-0.

STEP 4 — CONSEQUENCES AND LESSONS LEARNED:
   Illustrate the connection between Elite intent and the T+30 wave. Summarize the lesson so the student doesn't get "shaved" by Market Makers next time.

STEP 5 — MODEL LESSON (CHOSEN RESPONSE):
   Summarize pure, concise knowledge for the student to absorb.

Return pure JSON:
{{
  "chosen_direction": "{actual_direction}",
  "rejected_direction": "{student_direction}",
  "step1_giam_dinh_ky_thuat": "...",
  "step2_ly_luan_diet_ao_giac": "...",
  "step3_tham_do_y_do_elite": "...",
  "step4_hau_qua_bai_hoc": "...",
  "step5_bai_giang_mau": "...",
  "wyckoff_phase": "...",
  "cm_confirmed_tactic": "...",
  "quality_score": 0.0-1.0
}}"""


# ══════════════════════════════════════════════════════════════════════════════
# WYCKOFF PURITY CHECKER — Filter technical hallucinations
# ══════════════════════════════════════════════════════════════════════════════

WYCKOFF_TERMS = [
    "wyckoff", "phase", "spring", "upthrust", "accumulation", "distribution",
    "sign of strength", "sos", "selling climax", "test", "creek", "ice",
    "smart money", "money flow", "phase", "accumulation", "distribution",
    "supply zone", "demand zone", "absorption",
    "utad", "sow", "lpsy", "lps", "markdown", "markup", "sign of weakness"
]
ELLIOTT_TERMS = [
    "elliott", "wave 1", "wave 2", "wave 3", "wave 4", "wave 5",
    "impulse", "corrective", "wave a", "wave b", "wave c",
    "w1", "w2", "w3", "w4", "w5", "abc", "zigzag", "flat wave",
    "fibonacci", "fibo", "0.618", "0.382", "1.618"
]
# "Hallucination" indicators — if it is the ONLY CORE reason, reject
LAGGING_INDICATOR_TERMS = [
    "rsi", "macd", "bollinger", "ma 20", "ma 50", "ema 20",
    "stochastic", "moving average cross", "golden cross", "death cross"
]


def check_wyckoff_purity(text: str) -> dict:
    """
    Check if an analysis is pure Wyckoff/Elliott.
    Returns: {
        'is_pure': bool,
        'wyckoff_score': int,  # Number of Wyckoff terms used
        'elliott_score': int,  # Number of Elliott terms used  
        'has_volume': bool,    # Whether Volume is mentioned
        'hallucination_risk': float,  # 0.0 = pure, 1.0 = completely hallucinated
        'detail': str
    }
    """
    text_lower = text.lower()

    wyckoff_hits = sum(1 for t in WYCKOFF_TERMS if t in text_lower)
    elliott_hits = sum(1 for t in ELLIOTT_TERMS if t in text_lower)
    has_volume   = any(v in text_lower for v in ["volume", "vol", "turnover"])

    # Detect lagging indicators
    lagging_hits = [t for t in LAGGING_INDICATOR_TERMS if t in text_lower]

    # Calculate hallucination_risk
    # If no Wyckoff/Elliott -> high risk
    # If lagging indicator exists but NO Wyckoff -> very high risk
    risk = 0.0
    if wyckoff_hits < 1 and elliott_hits < 1:
        risk += 0.6
    elif wyckoff_hits < 2 and elliott_hits < 1:
        risk += 0.3
    if not has_volume:
        risk += 0.2
    if lagging_hits and wyckoff_hits < 2:
        # Lagging indicators dominate
        risk += 0.3

    risk = min(risk, 1.0)
    is_pure = (wyckoff_hits >= 2 or (wyckoff_hits >= 1 and elliott_hits >= 1)) and risk < 0.5

    detail_parts = []
    if lagging_hits:
        detail_parts.append(f"⚠️ Used lagging indicators: {lagging_hits}")
    if not has_volume:
        detail_parts.append("⚠️ Missing Volume context")
    if wyckoff_hits == 0:
        detail_parts.append("❌ No Wyckoff terms used")
    if elliott_hits == 0:
        detail_parts.append("❌ No Elliott wave counting")

    return {
        "is_pure":          is_pure,
        "wyckoff_score":    wyckoff_hits,
        "elliott_score":    elliott_hits,
        "has_volume":       has_volume,
        "hallucination_risk": round(risk, 2),
        "lagging_used":     lagging_hits,
        "detail":           " | ".join(detail_parts) if detail_parts else "✅ Pure Wyckoff/Elliott"
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT PRIORITY YIELD — Yield resources to 4 other agents
# ══════════════════════════════════════════════════════════════════════════════



def check_agent_priority_yield() -> tuple[bool, str]:
    """
    Check if any agent needs prioritized LLM resources.
    (Disabled: 235B vs 32B are dedicated to A04, no need to yield shared resources)
    Returns: (should_yield: bool, reason: str)
    """
    return False, ""


def run_blind_contest(scenario: dict, nen_dict=None):
    """
    Run 1 round of blind CM Fingerprint contest:
    1. lay_ohlcv_multi (5 frames down to 1m) if not fetched
    2. analyze_cm_fingerprint -> pre-detect 4 CM footprints
    3. 32B generates BULL + BEAR hypothesis (reads all 5 frames + CM signals)
    4. 235B judges: 3 steps of teaching — dissect errors + shortcut + core lessons
    """
    import re
    ticker  = scenario.get("ticker", "UNK")
    date    = scenario.get("date", "unknown")
    ts_end  = scenario.get("ts_end_ms") or int(datetime.now(timezone.utc).timestamp() * 1000)

    log.info(f"[BOOST_CM] ▶ Contest: {ticker} @ {date}")

    # ── Layer 0: Multi-Resolution Fetch ─────────────────────────
    if nen_dict is None:
        log.info(f"[BOOST_CM] Fetching multi-res OHLCV: {ticker}")
        nen_dict = lay_ohlcv_multi(ticker, ts_end)
        if nen_dict is None:
            return None

    # ── Layer 0.5: CM Fingerprint Analysis (Integrated v19.6) ────────
    cm_fp = analyze_cm_fingerprint(nen_dict)
    
    # Supplement detailed VSA Fingerprint from Helper for each Timeframe
    helper_fps = {}
    for tf, tf_data in nen_dict.get("timeframes", {}).items():
        raw_candles = tf_data.get("raw_tail", [])
        if raw_candles:
            helper_fps[tf] = fingerprint_composite_man(raw_candles)
            
    cm_signals_str = json.dumps(helper_fps, indent=2, ensure_ascii=False)
    log.info(f"[HELPER] VSA Fingerprint (Money Flow):\n{cm_signals_str[:500]}...")
    coin_context   = cm_fp.get("coin_context", "")
    cm_phase       = cm_fp.get("cm_phase", "UNKNOWN")

    tf_summaries = {}
    for tf, tfd in nen_dict.get("timeframes", {}).items():
        s = tfd.get("summary", {})
        if s:
            tf_summaries[tf] = s
    multi_tf_data = json.dumps(tf_summaries, ensure_ascii=False, indent=1)[:3000]

    scenario_full = (
        f"TICKER: {ticker} | DATE: {date} | CM_PHASE_DETECTED: {cm_phase}\n\n"
        f"=== VSA FINGERPRINTS (DETECTED) ===\n{cm_signals_str}\n\n"
        f"=== MULTI-TIMEFRAME SUMMARY (1D→1m) ===\n{multi_tf_data}"
    )

    # ── RAG Layer Step: Query Knowledge ───────────────────────
    from engram_helper import A04EngramHelper
    log.info(f"[RAG] Querying knowledge base for signal: {ticker}")
    try:
        rag_context = A04EngramHelper().recall_knowledge_deep(query=cm_signals_str, ticker=ticker)
        log.info(f"[RAG] Recall results ({len(rag_context.split())} tokens):\n" + rag_context[:300] + "...")
    except Exception as e:
        log.error(f"[RAG] Error recalling knowledge: {e}")
        rag_context = ""

    import concurrent.futures

    # ── Step 1 & 2: Students CONCURRENTLY ──────────────────────
    bull_prompt = CONTESTANT_PROMPT_BULL.format(
        coin_context=coin_context,
        cm_signals=cm_signals_str,
        multi_tf_data=scenario_full,
        rag_context=rag_context
    )
    bear_prompt = CONTESTANT_PROMPT_BEAR.format(
        coin_context=coin_context,
        cm_signals=cm_signals_str,
        multi_tf_data=scenario_full,
        rag_context=rag_context
    )

    import time

    # ── Step 1 & 2: Students SEQUENTIALLY (Fix 429 Spam) ─────────
    # TO AVOID 429 EXPLOSION FROM TOO MANY REQS/SEC:
    bull_resp, bull_provider = call_contestant(bull_prompt, 1500)
    time.sleep(3) # Anti-Spam breathing space
    
    bear_resp, bear_provider = call_contestant(bear_prompt, 1500)
    time.sleep(3) # Anti-Spam breathing space

    if not bull_resp or "EXHAUSTED" in str(bull_resp):
        if bull_resp and "EXHAUSTED" in str(bull_resp):
            log.warning(f"[CONTEST] BULL Contestant EXHAUSTED for {ticker}/{date}")
            return {"EXHAUSTED": True}
        log.error(f"[CONTEST] BULL failed for {ticker}/{date}")
        return None

    if not bear_resp or "EXHAUSTED" in str(bear_resp):
        if bear_resp and "EXHAUSTED" in str(bear_resp):
            log.warning(f"[CONTEST] BEAR Contestant EXHAUSTED for {ticker}/{date}")
            return {"EXHAUSTED": True}
        log.error(f"[CONTEST] BEAR failed for {ticker}/{date}")
        return None

    # ── Step 3: Judge Sovereign — 3-step dissection ──────────────────
    actual_direction = scenario.get("actual_direction", "unknown")
    actual_magnitude = scenario.get("actual_magnitude", "unknown")
    
    # Determine the "incorrect" disciple (REJECTED) for the Master to dissect
    if actual_direction.upper() == "BULL":
        student_direction = "BEAR"
        student_resp = bear_resp
    else:
        student_direction = "BULL"
        student_resp = bull_resp

    judge_prompt_fmt = JUDGE_PROMPT.format(
        cm_analysis=cm_signals_str,
        scenario_data=scenario_full,
        student_hypothesis=student_resp,
        student_direction=student_direction,
        actual_direction=actual_direction,
        actual_magnitude=actual_magnitude,
    )
    
    judge_resp, judge_provider = call_judge(judge_prompt_fmt, est_tokens=2500)
    
    # [V19.6] Handle Judge Exhaustion status (Sovereign Deep Sleep)
    if not judge_resp or "ERROR" in str(judge_resp):
        if judge_resp and "EXHAUSTED" in str(judge_resp):
             log.warning(f"[CONTEST] Judge TRULY EXHAUSTED for {ticker}/{date}")
             return {"EXHAUSTED": True}
        log.warning(f"[CONTEST] Judge failed or error for {ticker}/{date}: {judge_resp}")
        return None

    # ── Step 4: Parse verdict -> DPO pair ───────────────────────
    try:
        clean = judge_resp
        if "<thinking>" in clean:
            clean = re.sub(r"<thinking>.*?</thinking>", "", clean, flags=re.DOTALL).strip()
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start < 0 or end <= start:
            log.warning(f"[CONTEST] Judge not JSON for {ticker}/{date}")
            return None

        verdict = json.loads(clean[start:end])
        quality = verdict.get("quality_score", 0.5)
        chosen_dir = verdict.get("chosen_direction", "BULL")
        if chosen_dir.upper() == "BULL":
            chosen_resp, rejected_resp = bull_resp, bear_resp
        else:
            chosen_resp, rejected_resp = bear_resp, bull_resp

        # Wyckoff Purity Check
        purity_chosen   = check_wyckoff_purity(chosen_resp)
        purity_rejected = check_wyckoff_purity(rejected_resp)
        if purity_chosen["hallucination_risk"] >= 0.7:
            log.warning(f"[PURITY] ⚠️ CHOSEN hallucination -> SWAP")
            chosen_resp, rejected_resp = rejected_resp, chosen_resp
            purity_chosen, purity_rejected = purity_rejected, purity_chosen
            verdict["hallucination_swap"] = True
        if purity_chosen["hallucination_risk"] >= 0.5 and purity_rejected["hallucination_risk"] >= 0.5:
            log.warning(f"[PURITY] ❌ Both lack Wyckoff/Elliott -> DROP PAIR")
            return None

        purity_bonus = (purity_chosen["wyckoff_score"] + purity_chosen["elliott_score"]) * 0.03
        adjusted_quality = min(quality + purity_bonus - (purity_chosen["hallucination_risk"] * 0.2), 1.0)

        prompt_for_model = (
            f"[FOUR SCHOLARS - CM FINGERPRINT] Analyzing {ticker} at {date}.\n"
            f"Coin Type: {cm_fp.get('coin_type')} | CM Phase: {cm_phase}\n"
            f"CM Footprints:\n{cm_signals_str}\n\n"
            f"5 timeframe data (1D->1m):\n{multi_tf_data[:800]}"
        )

        dpo_pair = {
            "pair_id":    str(uuid.uuid4())[:12],
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "ticker":     ticker,
            "date":       date,
            "coin_type":  cm_fp.get("coin_type", "UNKNOWN"),
            "cm_phase":   cm_phase,
            "prompt":     prompt_for_model,
            "chosen":     chosen_resp,
            "rejected":   rejected_resp,
            "teacher_note": {
                "step1_giam_dinh_ky_thuat":  verdict.get("step1_giam_dinh_ky_thuat", "") or verdict.get("step1_giám_định_kỹ_thuật", ""),
                "step2_ly_luan_diet_ao_giac": verdict.get("step2_ly_luan_diet_ao_giac", "") or verdict.get("step2_lý_luận_diệt_ảo_giác", ""),
                "step3_tham_do_y_do_elite":   verdict.get("step3_tham_do_y_do_elite", "") or verdict.get("step3_thăm_dò_ý_đồ_elite", ""),
                "step4_hau_qua_bai_hoc":      verdict.get("step4_hau_qua_bai_hoc", "") or verdict.get("step4_hậu_quả_bài_học", ""),
                "step5_bai_giang_mau":        verdict.get("step5_bai_giang_mau", "") or verdict.get("step5_bài_giảng_mẫu", "")
            },
            "verdict":       verdict,
            "quality_score": round(adjusted_quality, 3),
            "wyckoff_phase": verdict.get("wyckoff_phase", "UNKNOWN"),
            "elliott_wave":  verdict.get("elliott_wave_position", "UNKNOWN"),
            "cm_confirmed":  verdict.get("cm_confirmed_tactic", cm_phase),
            "hallucination": verdict.get("hallucination_detected", False),
            "purity": {
                "chosen_wyckoff":     purity_chosen["wyckoff_score"],
                "chosen_elliott":     purity_chosen["elliott_score"],
                "chosen_volume":      purity_chosen["has_volume"],
                "chosen_hall_risk":   purity_chosen["hallucination_risk"],
                "rejected_hall_risk": purity_rejected["hallucination_risk"],
            },
            "providers": {"bull": bull_provider, "bear": bear_provider, "judge": judge_provider},
            "source":  "a04_boosting_cm_fingerprint",
            "version": "v2.0",
        }
        log.info(
            f"[CONTEST] ✅ {ticker}/{date} -> CHOSEN={chosen_dir} CM={cm_phase} "
            f"q={adjusted_quality:.2f} shortcut: {verdict.get('step2_pattern_shortcut','')[:60]}..."
        )
        _track_boosting_performance(dpo_pair)
        return dpo_pair

    except Exception as e:
        log.error(f"[CONTEST] Parse error {ticker}/{date}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# METRICS TRACKING (Migrated from A05)
# ══════════════════════════════════════════════════════════════════════════════

def _track_boosting_performance(pair: dict):
    """
    Track performance of the 9B model during Boosting.
    Legacy dpo_report logic unified into A04.
    """
    try:
        from imperial_state import matrix
        ticker = pair.get("ticker", "UNK")
        verdict = pair.get("verdict", {})
        
        # 1. Winrate Logic
        actual_dir = pair.get("actual_direction", "").upper()
        chosen_dir = verdict.get("chosen_direction", "").upper()
        is_correct = (chosen_dir == actual_dir)
        
        # 2. Brier Score (Calibration)
        conf = verdict.get("quality_score", 0.5)
        outcome = 1.0 if is_correct else 0.0
        brier = round((conf - outcome) ** 2, 4)
        
        # 3. Drawdown Proxy
        magnitude = pair.get("actual_magnitude", 0)
        drawdown_proxy = 0
        if isinstance(magnitude, (int, float)) and magnitude < 0:
            drawdown_proxy = abs(magnitude)

        # Save to Matrix (Use hash to manage by Ticker)
        stats = {
            "last_pair_id": pair.get("pair_id"),
            "ticker": ticker,
            "correct": is_correct,
            "brier_score": brier,
            "drawdown_proxy": drawdown_proxy,
            "ts": int(time.time())
        }
        matrix.hset("A04", "boosting:latest_stats", ticker, json.dumps(stats, ensure_ascii=False))
        
        log.info(f"[METRIC] {ticker} | Win: {is_correct} | Brier: {brier} | Q: {conf}")

    except Exception as e:
        log.warning(f"[METRIC] Error tracking performance: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP — Continuous Boosting Pipeline
# ══════════════════════════════════════════════════════════════════════════════

# matrix singleton is used directly


def _doc_redis_safe(namespace: str, subkey: str) -> Optional[Dict]:
    """Helper to read Redis key to dict via Matrix, supporting both String and Stream"""
    try:
        # matrix.get internally handles basic key get and decoding
        # If it might be a stream, we need more specific logic if matrix doesn't handle it
        # Actually StateMatrix handles streams differently via xread
        return matrix.get(namespace, subkey)
    except Exception:
        return None


def _get_boost_mode() -> str:
    """Read boosting mode from Matrix. Default ON."""
    return matrix.get("SYSTEM", "boost:mode") or os.getenv("A04_BOOST_DEFAULT", "ON")


def _check_cloud_health() -> str:
    """
    Read cloud health from cloud_health_prober.py via Matrix.
    """
    try:
        health = matrix.get("SYSTEM", "cloud:health")
        if not health:
            return "HEALTHY"
        overall = health.get("overall", "UNKNOWN")
        if overall == "DOWN":
            return "DOWN"
        elif "DEGRADED" in overall:
            return "DEGRADED"
        return "HEALTHY"
    except Exception:
        return "HEALTHY"


# ── Graceful Shutdown ─────────────────────────────────────────────────────────
_shutdown_requested: bool = False


def _on_shutdown_signal(signum, frame):
    """SIGTERM / SIGINT handler — graceful shutdown."""
    global _shutdown_requested
    _shutdown_requested = True
    log.warning(f"[BOOST] Received signal {signum} -> starting graceful shutdown")
    rc = matrix._client
    matrix.set("A04", "boost:state", {
        "status":  "STOPPING",
        "reason":  f"signal_{signum}",
        "ts":      int(time.time()),
    }, ttl=300)


try:
    import signal as _signal
    _signal.signal(_signal.SIGTERM, _on_shutdown_signal)
    _signal.signal(_signal.SIGINT,  _on_shutdown_signal)
except Exception:
    pass  # Windows might not support SIGTERM


def _generate_single_memory_scenario(exchange) -> dict:
    """Generate 1 random In-Memory scenario (Not saved to disk)"""
    import random
    while True:
        ticker = "BTC/USDT"
        random_ts = random.randint(BTC_MANUAL_MIN_T0, BTC_MANUAL_MAX_T0)
        date_str = datetime.utcfromtimestamp(random_ts/1000).strftime('%Y-%m-%d_%H%M')
        
        log.info(f"[BOOST] 🎲 Finding T0 In-Memory: {ticker} @ {date_str}")
        
        try:
            nen_dict = lay_ohlcv_multi(ticker, random_ts, exchange=exchange)
            if not nen_dict or not nen_dict.get("timeframes"):
                continue
                
            future_ohlcv = exchange.fetch_ohlcv(ticker, '1d', since=random_ts, limit=31)
            if not future_ohlcv or len(future_ohlcv) < 25:
                continue
            
            p_start = future_ohlcv[0][1]
            p_end = future_ohlcv[-1][4]
            direction = "BULL" if p_end >= p_start else "BEAR"
            magnitude = round(((p_end - p_start) / p_start) * 100, 2)
            
            return {
                "ticker": ticker,
                "date": date_str,
                "ts_end_ms": random_ts,
                "actual_direction": direction,
                "actual_magnitude": magnitude,
                "nen_dict": nen_dict,
                "is_historical": True
            }
        except Exception as e:
            log.warning(f"[BOOST] Error generating scenario for {ticker}: {e}")
            time.sleep(1)

def _save_dpo_pair(pair: dict):
    """Double Pillars Repository — push DPO pair to ImperialBrain/boost."""
    from engram_helper import A04EngramHelper
    A04EngramHelper().store_a04_lesson(
        ma_tien_ao=pair.get("ticker", "UNK"),
        content=pair,
        mode="boost",
        metadata={
            "cm_phase":      pair.get("cm_phase"),
            "coin_type":     pair.get("coin_type"),
            "quality_score": pair.get("quality_score"),
        }
    )

def _publish_heartbeat():
    matrix.set("A04", "boost:heartbeat", {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": _get_boost_mode(),
        "cerebras": cerebras_tracker.get_status(),
    }, ttl=120)

def run_boost_loop(step_mode=False):
    """
    Main boosting loop — runs continuously purely In-Memory (Sovereign v20.1)
     Modes: ON -> run full | PAUSE -> sleep | SLOW -> reduce rate by 50%
     SOUL IDENTITY: 04_THE_FOUR_SCHOLARS (Claw 2)
    """
    global _shutdown_requested

    log.info("=" * 60)
    log.info(f"🚀 A04 BOOSTING MODE — Eight Trigrams Furnace starting (Mode: {'STEP' if step_mode else 'AUTO'})")
    log.info(f"   Soul: 04_THE_FOUR_SCHOLARS (Claw 2)")
    log.info(f"   Cerebras keys: {cerebras_tracker.num_keys}")
    log.info("=" * 60)

    # 🔱 DNA v24.0: Load progress using Dual Checkpoint (Redis + Disk)
    ckpt_key = 'a04:boosting:checkpoint:total_pairs'
    checkpoint_file = BASE_DIR / "dpo_lab" / "A04" / "boosting" / "distill_checkpoints.json"
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    
    disk_checkpoints = {}
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                disk_checkpoints = json.load(f)
        except Exception as e:
            log.error(f"Error reading {checkpoint_file.name}: {e}")
            
    redis_val = int(matrix.get('SYSTEM', ckpt_key) or 0)
    disk_val = disk_checkpoints.get(ckpt_key, 0)
    total_engrams = max(redis_val, disk_val)
    
    # Auto-heal Redis if disk is ahead
    if total_engrams > redis_val:
        matrix.set('SYSTEM', ckpt_key, total_engrams)
        
    log.info(f"📊 [PROGRESS] Dual Checkpoint: Saved {total_engrams} lessons historically.")

    pairs_generated = 0
    batch_count = 0
    import ccxt
    try:
        exchange = ccxt.binance({"enableRateLimit": True})
    except Exception as e:
        log.error(f"[BOOST] Error initializing exchange: {e}")
        return

    matrix.set("A04", "boost:state", {
        "status": "RUNNING",
        "mode": "STEP" if step_mode else "AUTO",
        "ts":     int(time.time()),
    }, ttl=86400)
    
    # 🔱 AUTO-DISTILL (Background killer)
    def _auto_check_distill_boost():
        try:
            from pathlib import Path
            from engram_helper import A04EngramHelper
            engram_runner = A04EngramHelper()
            boost_dir = BASE_DIR / "dpo_lab" / "A04" / "boosting"
            if not boost_dir.exists(): return
            
            # Scan all pairs files
            for target_file in boost_dir.glob("pairs_*.jsonl"):
                with open(target_file, 'r', encoding='utf-8') as f:
                    sum_val = sum(1 for _ in f)
                    
                ckpt_key_distill = f"a04:boosting:checkpoint:distilled:{target_file.stem}"
                checkpoint_val = int(matrix.get("SYSTEM", ckpt_key_distill) or 0)
                undistilled_count = sum_val - checkpoint_val
                
                if undistilled_count >= 50:
                    log.info(f"🚀 [AUTO_DISTILL] Backlog of {undistilled_count} Pairs in {target_file.name}. Resting 30s before compression...")
                    time.sleep(30)
                    log.info(f"🔥 [AUTO_DISTILL] Executing Holmes Distillation!")
                    
                    result_file = engram_runner.distill_boost_pairs_holmes(target_file)
                    if result_file:
                        matrix.set("SYSTEM", ckpt_key_distill, sum_val)
                        log.info(f"✨ [AUTO_DISTILL] Holmes completed squeezing {target_file.name}! Checkpoint pulled up to {sum_val}.")
        except Exception as e:
            log.warning(f"⚠️ [BOOST_DISTILL_ERROR] Distillation circuit stuck: {e}")

    while not _shutdown_requested:
        # 🔱 Call Distill check before entering Cerebras logic (clear Exhaustion deadlock)
        _auto_check_distill_boost()

        # Removed Limit 5000, allowing Boosting to grind forever

        # NLM Heartbeat
        nlm_changelog.log_heartbeat("A04_BOOST", {
            "status": "RUNNING",
            "pairs_session": pairs_generated,
            "mode": _get_boost_mode(),
            "cloud_health": _check_cloud_health()
        })
        try:


            # ── AGENT PRIORITY YIELD ─────────────────────────────────────────
            should_yield, yield_reason = check_agent_priority_yield()
            if should_yield:
                log.info(f"[PRIORITY] ⏸️ Yielding resources: {yield_reason}")
                _publish_heartbeat()
                time.sleep(8)
                continue

            mode = _get_boost_mode()
            if mode == "PAUSE":
                log.info("[BOOST] Mode=PAUSE -> sleeping 5 minutes to accumulate quota")
                _publish_heartbeat()
                time.sleep(300)
                continue
                
            if mode == "OFF":
                log.info("[BOOST] Mode=OFF -> sleeping 60s")
                _publish_heartbeat()
                time.sleep(60)
                continue

            # Check exhaustion state
            if matrix.get("SYSTEM", "a04:boost:exhausted_today"):
                log.warning("[BOOST] 💤 JUDGING PANEL EXHAUSTED. Deep sleep until tomorrow.")
                _publish_heartbeat()
                time.sleep(200) # Quick sleep check
                if datetime.now().hour == 7 and datetime.now().minute <= 5:
                    matrix.delete("SYSTEM", "a04:boost:exhausted_today")
                continue

            # Check cloud health
            cloud_health = _check_cloud_health()
            if cloud_health == "DOWN":
                log.warning("[BOOST] Cloud DOWN. Local mode warning.")

            # QUOTA SMART SLEEP Prevent loop spam
            if cerebras_tracker.all_exhausted(caller="A04"):
                seconds_to_wait = cerebras_tracker.get_wait_time()
                
                if seconds_to_wait > 30:
                    wait_until = datetime.now() + timedelta(seconds=seconds_to_wait + 2)
                    log.warning(f"[BOOST] 🛑 Cloud exhausted. VRAM load reduction sleep {seconds_to_wait}s until {wait_until.strftime('%H:%M:%S')}")
                    _publish_heartbeat()
                    time.sleep(seconds_to_wait + 2)
                    continue

            # SLOW mode
            if mode == "SLOW":
                time.sleep(30)

            # ── IN-MEMORY T0 GENERATION ──────────────────────────────────────
            scenario = _generate_single_memory_scenario(exchange)
            if not scenario:
                log.info("[BOOST] T0 Memory Generator choked (missing data/exchange error) -> waiting 20s")
                time.sleep(20)
                continue
                
            ticker = scenario.get("ticker", "UNK")
            date = scenario.get("date", "unknown")
            log.info(f"[BOOST] ✅ T0 successfully attached. Contest #{batch_count+1}: {ticker}/{date}")

            # Run blind contest in memory
            pair = run_blind_contest(scenario, nen_dict=scenario.get("nen_dict"))
            
            if pair:
                if isinstance(pair, dict) and pair.get("EXHAUSTED"):
                    log.error("[BOOST] 🛑 JUDGING PANEL EXHAUSTED! Saving state and waiting for reset (Will retry in 120s)")
                    matrix.set("SYSTEM", "a04:boost:exhausted_today", True, ttl=120)
                    continue
                    
                _save_dpo_pair(pair)
                pairs_generated += 1
                total_engrams += 1
                batch_count += 1
                
                # Update Dual Checkpoint
                matrix.set('SYSTEM', ckpt_key, total_engrams)
                disk_checkpoints[ckpt_key] = total_engrams
                try:
                    with open(checkpoint_file, 'w', encoding='utf-8') as f:
                        json.dump(disk_checkpoints, f, indent=2)
                except Exception as e:
                    pass
                
                log.info(f"[BOOST] 🎉 DPO pair saved successfully | Total: {total_engrams} (Session: {pairs_generated})")
            else:
                log.warning(f"[BOOST] Contest failed for {ticker}/{date}")

            _publish_metrics_to_matrix()

            # ── STEP-BY-STEP MODE (From Boss zcl:a04:boost:step_next) ─────
            if step_mode:
                log.info(f"[BOOST-STEP] ⏸️ Completed {ticker}/{date}. Waiting for NEXT command (zcl:a04:boost:step_next 1)...")
                matrix.set("SYSTEM", "boost:step_waiting", f"{ticker}@{date}", ttl=3600)
                matrix.delete("SYSTEM", "boost:step_next")
                
                while not _shutdown_requested:
                    if matrix.get("SYSTEM", "boost:step_next"):
                        log.info("[BOOST-STEP] ▶ NEXT command received. Continuing...")
                        matrix.delete("SYSTEM", "boost:step_waiting")
                        break
                    time.sleep(1)
            else:
                # 🔱 SOVEREIGN HEARTBEAT
                log.info(f"[BOOST] 💤 Resting {BOOST_HEARTBEAT_SEC}s (5 minutes) — Yielding Cerebras to A05 Deep Diagnosis...")
                time.sleep(BOOST_HEARTBEAT_SEC)

        except KeyboardInterrupt:
            _shutdown_requested = True
            break
        except Exception as e:
            log.error(f"[BOOST] Loop error: {e}")
            time.sleep(180)

    log.info("[BOOST] Graceful shutdown completed")
    matrix.set("A04", "boost:state", {
        "status": "STOPPED",
        "reason": "graceful_shutdown",
        "ts":     int(time.time()),
    }, ttl=300)

# ══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="A04 Boosting Mode — Eight Trigrams Furnace DPO (In-Memory)")
    parser.add_argument("--run", action="store_true", help="Run the BOOSTER stream continuously")
    parser.add_argument("--step", action="store_true", help="Run in step-by-step mode (Manual optimization)")
    parser.add_argument("--status", action="store_true", help="View quota status")
    args = parser.parse_args()

    if args.status:
        print("\n=== Cerebras Quota ===")
        for k, v in cerebras_tracker.get_status().items():
            print(f"  {k}: {v}")
    elif args.run:
        run_boost_loop(step_mode=args.step)
    else:
        parser.print_help()
