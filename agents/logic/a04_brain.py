"""
🧬 DNA: v16.6 (Sovereign Purity) [DNA Header]
🏢 UNIT: THEORETICAL_BRAIN
🛠️ ROLE: A04_SCHOLAR_GENESIS
📖 DESC: German Engine - 4-tier history harvester (VSA 4.0 Kinematics).
"""

import os
import sys
import json
import time
import logging
import argparse
import statistics
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import ccxt
import redis
from dotenv import load_dotenv
from imperial_state import matrix

def _heartbeat_daemon(interval_sec: int = 15):
    """Background thread to keep A04 alive in A09's eyes."""
    if not isinstance(interval_sec, int) or interval_sec <= 0:
        interval_sec = 15
        
    while True:
        try:
            if matrix is None:
                log.error("[A04] Matrix is None, stopping heartbeat daemon")
                break
            matrix.publish_heartbeat("A04", status="ALIVE", metadata={"role": "BRAIN_SCHOLAR"})
            log.debug("Heartbeat sent")
        except redis.ConnectionError as e:
            log.error(f"Heartbeat Redis connection error: {e}")
        except Exception as e:
            log.error(f"Heartbeat error: {e}")
            
        try:
            time.sleep(interval_sec)
        except Exception:
            break

# ── EMPIRE INFRASTRUCTURE ─────────────────────────────────────────────────────
# Ensure tools/ path is valid
sys.path.append(os.path.join(os.path.dirname(__file__), '../../tools'))

from llm_router import router_api_call
import A04_BRAIN_HELPER as helper
from A04_BRAIN_HELPER import tinh_kinematics
from imperial_brain import brain
from imperial_state import matrix
from engram_helper import A04EngramHelper
from dos_guardian import check_chroma_write_allowed

# ── LOAD CONFIGURATION ────────────────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../config/.env'))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GENESIS_FILE = os.path.join(BASE_DIR, "memory/genesis_points.json")

# ── UNIVERSAL CONSTANTS ───────────────────────────────────────────
WYCKOFF_PHASES = {
    "PHASE_A_ACCUM": "Selling Climax — Panic bottom",
    "PHASE_B_ACCUM": "Horizontal accumulation — Base building",
    "PHASE_C_ACCUM": "Spring — Final shakeout, long lower wick",
    "PHASE_D_ACCUM": "SOS / LPS — Breakout point upwards",
    "PHASE_E_ACCUM": "Markup — Clear uptrend",
    "PHASE_A_DIST": "Buying Climax — FOMO peak",
    "PHASE_B_DIST": "Horizontal distribution — Top building",
    "PHASE_C_DIST": "UTAD — Bull trap, long upper wick",
    "PHASE_D_DIST": "SOW / LPSY — Support structure breakdown",
    "PHASE_E_DIST": "Markdown — Clear downtrend",
    "UNKNOWN": "Undetermined phase",
}

# VSA constants from the German Engine
VSA_LABEL = {
    "BUYING_CLIMAX": "Maximum buying effort but price does not rise - Sign of peak",
    "SELLING_CLIMAX": "Extreme panic selling - Sign of bottom",
    "SHAKEOUT": "Strong shakeout piercing support before bouncing back",
    "TEST_SUPPLY": "Testing supply - Low volume is a good sign",
    "NO_SUPPLY": "Exhausted supply - Preparing for Markup",
    "NO_DEMAND": "Exhausted demand - Preparing for Markdown",
    "UTAD_TRAP": "Price pierces resistance but wicks back to close below - Bull Trap",
    "SPRING_TRAP": "Price pierces support but wicks back to close above - Bear Trap",
    "SOW_BREAKDOWN": "Piercing strong support with long-bodied candle, high volume - Markdown start",
    "SOS_BREAKOUT": "Piercing strong resistance with long green candle, high volume - Markup start",
    "LPSY": "Weak recovery touching resistance, exhausted volume - Last point of supply",
    "LPS": "Minor drop touching support, exhausted volume - Last point of support",
}

# ── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(levelname)s %(message)s')
log = logging.getLogger("A04_GENESIS_ENGINE")

# ── REDIS ────────────────────────────────────────────────────────────────────
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except:
    redis_client = None

# ==============================================================================
# CORE FUNCTIONS — FETCH & PARSE (THE GERMAN ENGINE)
# ==============================================================================

_BINANCE_CLIENT = None

def get_binance_client():
    global _BINANCE_CLIENT
    if _BINANCE_CLIENT is None:
        import ccxt
        _BINANCE_CLIENT = ccxt.binance({'enableRateLimit': True})
    return _BINANCE_CLIENT

def lay_ohlcv(ma_coin: str, timeframe: str, so_nen: int = 300, since: Optional[int] = None) -> list:
    """Get OHLCV candle data from Binance (Legacy logic from tmp/)."""
    san = get_binance_client()
    nen = []
    since_ms = since
    batch = min(so_nen, 1000)

    try:
        while len(nen) < so_nen:
            data = san.fetch_ohlcv(ma_coin, timeframe, since=since_ms, limit=batch)
            if not data: break
            nen.extend(data)
            since_ms = data[-1][0] + 1
            if len(data) < batch: break
            time.sleep(0.1)
    except Exception as e:
        log.warning(f"OHLCV {ma_coin} {timeframe}: {e}")

    return nen[-so_nen:] if len(nen) > so_nen else nen

def _phan_tich_vsa_thong_minh(nen_list: list) -> dict:
    """VSA 4.0: Kinematics analysis + Symmetrical VSA (Accumulation vs Distribution)."""
    if not isinstance(nen_list, list) or len(nen_list) < 21:
        return {"score": 0, "label": "DATA_INSUFFICIENT", "kinematics": {}}

    valid_nen = [n for n in nen_list if isinstance(n, (list, tuple)) and len(n) >= 6]
    if len(valid_nen) < 21:
        return {"score": 0, "label": "DATA_INSUFFICIENT", "kinematics": {}}

    # VSA 4.0 Kinematics
    kin = tinh_kinematics(valid_nen, lookback=min(50, len(valid_nen)))
    if not isinstance(kin, dict):
        kin = {}

    # VSA 4.0 Symmetrical Logic
    vols = [n[5] for n in valid_nen]
    vol_avg = statistics.mean(vols[-21:-1]) # Avg vol of 20 preceding candles
    curr_vol = vols[-1]
    curr_open = valid_nen[-1][1]
    curr_close = valid_nen[-1][4]
    curr_high = valid_nen[-1][2]
    curr_low = valid_nen[-1][3]
    curr_spread = abs(curr_high - curr_low)
    body = abs(curr_close - curr_open)
    upper_wick = curr_high - max(curr_open, curr_close)
    lower_wick = min(curr_open, curr_close) - curr_low

    # Find local Support & Resistance (preceding 20 candles)
    recent_highs = [n[2] for n in valid_nen[-21:-1]]
    recent_lows = [n[3] for n in valid_nen[-21:-1]]
    local_resistance = max(recent_highs)
    local_support = min(recent_lows)

    label = kin.get("tier", "UNKNOWN")
    desc = kin.get("note", "No kinematics data")

    # Override Kinematics labels with absolute VSA price action (Bull/Bear Traps)
    # 1. UTAD_TRAP (Distribution Phase C)
    if curr_high > local_resistance and curr_close < local_resistance:
        if upper_wick > body * 1.5 and curr_vol > vol_avg * 1.2:
            label = "UTAD_TRAP"
            desc = "Bull Trap: Pierced resistance but rejected with strong distribution."
    # 2. SPRING_TRAP (Accumulation Phase C)
    elif curr_low < local_support and curr_close > local_support:
        if lower_wick > body * 1.5 and curr_vol > vol_avg * 1.2:
            label = "SPRING_TRAP"
            desc = "Bear Trap: Pierced support but rejected with strong accumulation."
    # 3. SOW_BREAKDOWN (Distribution Phase D)
    elif curr_close < local_support and curr_vol > vol_avg * 2.0 and upper_wick < body * 0.5:
        label = "SOW_BREAKDOWN"
        desc = "Sign of Weakness: Broke hard support with overwhelming volume."
    # 4. SOS_BREAKOUT (Accumulation Phase D)
    elif curr_close > local_resistance and curr_vol > vol_avg * 2.0 and lower_wick < body * 0.5:
        label = "SOS_BREAKOUT"
        desc = "Sign of Strength: Broke strong resistance with overwhelming demand."
    # 5. LPSY (Distribution Pullback)
    elif curr_high >= local_resistance * 0.99 and curr_close <= curr_open and curr_vol < vol_avg * 0.5:
        label = "LPSY"
        desc = "Tested peak but volume exhausted (No Demand) -> Easy dump."
    # 6. LPS (Accumulation Pullback)
    elif curr_low <= local_support * 1.01 and curr_close >= curr_open and curr_vol < vol_avg * 0.5:
        label = "LPS"
        desc = "Tested bottom but volume exhausted (No Supply) -> Easy pump."
    
    # Supplemental classic VSA labels if no traps detected
    if label in ["NEUTRAL", "UNKNOWN"]:
        if curr_vol < vol_avg * 0.4:
            label = "NO_SUPPLY" if curr_close > valid_nen[-2][4] else "NO_DEMAND"
            desc = "Extremely low volume — supply/demand exhaustion"
        elif curr_vol > vol_avg * 2.5:
            if upper_wick > body * 1.5:
                label = "BUYING_CLIMAX"
                desc = "Long upper wick + high volume (Peak reached)"
            elif lower_wick > body * 1.5:
                label = "SELLING_CLIMAX"
                desc = "Long lower wick + high volume (Bottom reached)"
            else:
                label = "NORMAL"
                desc = "Stable liquidity"

    return {"label": label, "desc": desc, "kinematics": kin}

def _mo_ta_ket_qua_tri_ly(gia_chot: float, nen_tuong_lai: list) -> str:
    """Label Ground Truth (future outcome) with high resolution."""
    if not nen_tuong_lai or not isinstance(nen_tuong_lai, list) or len(nen_tuong_lai) == 0:
        return "No outcome data available"
    if gia_chot == 0:
        return "Closing price error"
    
    valid_nen = [n for n in nen_tuong_lai if isinstance(n, (list, tuple)) and len(n) >= 5]
    if not valid_nen:
        return "Invalid future data"
        
    high_max = max(n[2] for n in valid_nen)
    low_min  = min(n[3] for n in valid_nen)
    gia_cuoi = valid_nen[-1][4]
    
    # Fluctuation range
    max_pump = ((high_max - gia_chot) / gia_chot) * 100
    max_dump = ((low_min - gia_chot) / gia_chot) * 100
    final_roi = ((gia_cuoi - gia_chot) / gia_chot) * 100
    
    # Classify scenarios
    if max_pump > 15 and final_roi > 5:
        return f"🚀 SUCCESSFUL BREAKOUT (+{max_pump:.1f}%)"
    if max_dump < -15:
        return f"💀 SEVERE TRAP/DUMP ({max_dump:.1f}%)"
    if abs(final_roi) < 3:
        return f"⚖️ SIDEWAYS (Awaiting trend) ({final_roi:+.1f}%)"
        
    return f"⚡ MODERATE VOLATILITY ({final_roi:+.1f}%)"

# ==============================================================================
# GENESIS ENGINE — 4H-SLIDING HARVESTER
# ==============================================================================

def load_genesis_metadata() -> dict:
    if os.path.exists(GENESIS_FILE):
        try:
            with open(GENESIS_FILE, 'r') as f: 
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            log.warning(f"Error loading genesis metadata: {e}")
    return {}

def save_genesis_metadata(metadata: dict):
    os.makedirs(os.path.dirname(GENESIS_FILE), exist_ok=True)
    try:
        with open(GENESIS_FILE, 'w') as f: json.dump(metadata, f, indent=2)
    except Exception as e: 
        log.warning(f"Error saving genesis metadata: {e}")

def genesis_scan(ma_coin: str, limit: Optional[int] = None, rollback_hours: int = 0):
    """
    History harvesting mode (The German Engine):
    - 1h continuous sliding window.
    - Multi-tier Input Configuration: 100w, 200d, 300h, 500m.
    - Multi-tier analysis adhering to Wyckoff & Elliott principles.
    """
    log.info(f"🔱 [GENESIS_HARVESTER] Launching German engine for: {ma_coin} (Limit: {limit if limit else 'None'})")
    
    metadata = load_genesis_metadata()
    coin_meta = metadata.get(ma_coin, {"last_scanned_ts": 0, "total_engrams": 0})
    
    if rollback_hours > 0:
        log.info(f"⏪ [ROLLBACK] Rewinding scan timestamp for {ma_coin} by {rollback_hours} hours to compensate for missing 40 pairs...")
        if coin_meta.get("last_scanned_ts", 0) > 0:
            coin_meta["last_scanned_ts"] -= rollback_hours * 3600 * 1000
            metadata[ma_coin] = coin_meta
            save_genesis_metadata(metadata)
            
    now_ts = int(time.time() * 1000)
    buoc_truot_1h = 3600 * 1000
    
    # 1. Find T0 (Genesis Point)
    current_ts = coin_meta.get("last_scanned_ts") or 0
    if current_ts != 0:
        # DNA v18.4: Advance +1h from the last checkpoint to avoid duplication (Commander's request)
        current_ts += buoc_truot_1h
    
    if current_ts == 0:
        import glob
        from pathlib import Path
        log.info(f"🔍 Searching for nearest T0 from In-Memory pairs for {ma_coin} (Sliding mode)...")
        latest_ts = 0
        try:
            base_dir = os.path.join(BASE_DIR, "dpo_lab/A04/genesis")
            pattern = os.path.join(base_dir, f"pairs_{ma_coin.replace('/', '_')}_*.jsonl")
            for f_path in glob.glob(pattern):
                with open(f_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                d = json.loads(line)
                                # Get ts_end_ms from genesis pair
                                ts = d.get("_meta", {}).get("ts", 0)
                                if not ts and "context" in d:
                                    ts = d["context"].get("timestamp_unix", 0)
                                # Convert ts to milliseconds if it is in seconds (10 digits)
                                if ts > 0 and ts < 20000000000:
                                    ts = ts * 1000
                                if ts > latest_ts:
                                    latest_ts = ts
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            log.warning(f"Error resolving timestamp from pairs: {e}")
            
        if latest_ts > 0:
            current_ts = latest_ts + buoc_truot_1h
            log.info(f"✅ Found latest T0: {datetime.utcfromtimestamp(latest_ts/1000).strftime('%Y-%m-%d %H:%M')} -> Advancing forward.")
        else:
            log.info(f"⚠️ No historical pairs found. Starting harvest from Feb 2018 (To filter out dirty/garbage data before 2018).")
            # 1517443200000 = 2018-02-01
            current_ts = 1517443200000
    
    if not current_ts:
        log.error(f"❌ Could not determine starting point for {ma_coin}. Exchange has not listed the pair long enough?")
        return

    # Leave 21 days in the future for Scholar to perform "Hindsight Analysis" (Ground Truth)
    deadline_ts = now_ts - (21 * 24 * 3600 * 1000)
    
    log.info(f"⚙️ Starting scan from: {datetime.utcfromtimestamp(current_ts/1000).strftime('%Y-%m-%d %H:%M')}")
    cnt = 0
    last_distill_check_ts = 0  # Cooldown tracker for Distill (As per command)

    def _auto_check_distill(coin):
        nonlocal last_distill_check_ts
        now = time.time()
        # Rate limit: 5 minutes (300s) cooldown per distill
        if last_distill_check_ts > 0 and now - last_distill_check_ts < 300:
            return
            
        try:
            if brain and brain.memory:
                active_file = brain.memory.get_active_genesis_file(coin)
                from engram_helper import A04EngramHelper
                engram_runner = A04EngramHelper()
                
                if active_file.exists():
                    with open(active_file, 'r', encoding='utf-8') as f:
                        sum_val = sum(1 for _ in f)
                    
                    ckpt_key = f"a04:genesis:checkpoint:{active_file.stem}"
                    checkpoint_val = int(matrix.get("SYSTEM", ckpt_key) or 0)
                    undistilled_count = sum_val - checkpoint_val
                    
                    log.info(f"📈 [GENESIS_PROGRESS] {coin}: {undistilled_count} undistilled ({sum_val} - {checkpoint_val})")
                    
                    # DNA v22.6: Rapid Catch-up Mode
                    # If backlog > 50, compress continuously (max 5 batches ~ 250 candles) to clear queue
                    batch_count = 0
                    while undistilled_count >= 10 and batch_count < 5:
                        log.info(f"🚀 [AUTO_DISTILL] Batch {batch_count+1}: Compressing 10 lessons (Backlog: {undistilled_count})...")
                        # Update timestamp so cooldown tracker knows we are working
                        last_distill_check_ts = time.time() 
                        
                        # 1. Distill 50 pairs
                        result_file = engram_runner.distill_genesis_pairs(active_file)
                        
                        # 2. DNA v17.0: Global Synthesis
                        if result_file:
                            new_cycle = int(matrix.get("SYSTEM", "a04:engram:cycle") or 0)
                            if new_cycle == 0:
                                log.info(f"🌌 [GLOBAL_SYNTHESIS] Cycle returned to 0. Crystallizing Master Lattice...")
                                engram_runner.synthesize_master_lattice()
                                
                            # Update backlog count to let while loop decide whether to continue
                            checkpoint_val = int(matrix.get("SYSTEM", ckpt_key) or 0)
                            undistilled_count = sum_val - checkpoint_val
                            batch_count += 1
                        else:
                            # If distill error (Timeout/API), break loop to avoid error spamming
                            break
        except Exception as e:
            log.warning(f"⚠️ [GENESIS_COUNTER_ERROR] Distill check error: {e}")

    try:
        # --- STARTUP CHECK ---
        _auto_check_distill(ma_coin)

        while current_ts < deadline_ts:
            if limit and cnt >= limit:
                log.info(f"🛑 Reached limit of --limit {limit}. Stopping scan.")
                break

            ts_str = datetime.utcfromtimestamp(current_ts/1000).strftime('%Y-%m-%d %H:%M')
            
            # A. Multi-tier Data Collection (Sovereign 4-Lane Input)
            nen_w = lay_ohlcv(ma_coin, "1w", so_nen=100, since=current_ts - (100 * 7 * 24 * 3600 * 1000))
            nen_d = lay_ohlcv(ma_coin, "1d", so_nen=200, since=current_ts - (200 * 24 * 3600 * 1000))
            nen_h1 = lay_ohlcv(ma_coin, "1h", so_nen=300, since=current_ts - (300 * 3600 * 1000))
            nen_m1 = lay_ohlcv(ma_coin, "1m", so_nen=500, since=current_ts - (500 * 60 * 1000))
            nen_gt = lay_ohlcv(ma_coin, "1d", so_nen=21, since=current_ts + buoc_truot_1h)
            
            if len(nen_w) < 80 or len(nen_d) < 160 or len(nen_h1) < 240 or len(nen_m1) < 400 or len(nen_gt) < 18:
                log.warning(f"⚠️ [VAL] Insufficient data at {ts_str}. Skipping this step to retrieve later... "
                            f"(W:{len(nen_w)}, D:{len(nen_d)}, H:{len(nen_h1)}, M:{len(nen_m1)}, GT:{len(nen_gt)})")
                current_ts += buoc_truot_1h
                continue
            
            phase_w = helper._phan_tich_wyckoff_don_gian(nen_w).get("phase", "UNKNOWN") if nen_w and helper else "UNKNOWN"
            phase_d = helper._phan_tich_wyckoff_don_gian(nen_d).get("phase", "UNKNOWN") if nen_d and helper else "UNKNOWN"
            elliott = helper._phan_tich_elliott(nen_d) if nen_d and helper else {"song_hien_tai": "UNKNOWN"}
            vsa_info = _phan_tich_vsa_thong_minh(nen_d)
            kin_info = vsa_info.get("kinematics", {})
            gt_result = _mo_ta_ket_qua_tri_ly(nen_d[-1][4] if nen_d else 0, nen_gt)

            # Keep breathing rate stable to protect API
            time.sleep(45) 
            scholar_engram = _generate_scholar_reasoning(ma_coin, ts_str, phase_w, phase_d, elliott, vsa_info, gt_result)

            score_val = scholar_engram.get("score", 0) if scholar_engram else 0
            if isinstance(score_val, list) and score_val: score_val = score_val[0]
            try: score_f = float(score_val)
            except: score_f = 0

            if scholar_engram and score_f >= 0.75:
                try:
                    from engram_helper import A04EngramHelper
                    engram = A04EngramHelper()
                    engram.store_a04_lesson(ma_coin, scholar_engram, mode="genesis")
                except Exception as e:
                    log.error(f"Error storing genesis engram: {e}")
                else:
                    cnt += 1
                    coin_meta["total_engrams"] += 1
                    log.info(f"✨ [ENGRAM_SECURED] {ts_str} | Score: {scholar_engram['score']} | {gt_result}")
            else:
                if scholar_engram:
                    log.debug(f"⏩ [SKIP] {ts_str} | Low score: {scholar_engram.get('score')}")

            # Advance current_ts NO MATTER WHAT
            current_ts += buoc_truot_1h
            coin_meta["last_scanned_ts"] = current_ts
            metadata = load_genesis_metadata()
            metadata[ma_coin] = coin_meta
            
            _auto_check_distill(ma_coin)

            if cnt % 5 == 0 and cnt > 0:
                save_genesis_metadata(metadata)
                log.info(f"📈 Harvesting progress: {cnt} high-quality engrams.")
    finally:
        metadata = load_genesis_metadata()
        metadata[ma_coin] = coin_meta
        save_genesis_metadata(metadata)
        log.info(f"✅ CHECKPOINT GENESIS SAVED (Up to: {datetime.utcfromtimestamp(current_ts/1000).strftime('%Y-%m-%d %H:%M')}). Total: {cnt} new lessons.")

def _generate_scholar_reasoning(coin: str, time_str: str, phase_w: str, phase_d: str, 
                               elliott: dict, vsa: dict, gt: str) -> Optional[dict]:
    """Use Teacher LLM to dissect 'Why' based on known outcomes (Hindsight)."""
    
    if brain is None:
        return None
    
    # None Safety validations
    coin = coin if coin is not None else "UNKNOWN"
    time_str = time_str if time_str is not None else "UNKNOWN"
    phase_w = phase_w if phase_w is not None else "UNKNOWN"
    phase_d = phase_d if phase_d is not None else "UNKNOWN"
    gt = gt if gt is not None else "UNKNOWN"
    elliott = elliott if elliott is not None else {}
    vsa = vsa if vsa is not None else {}
    kinematics = vsa.get('kinematics') if vsa.get('kinematics') is not None else {}

    prompt = f"""
[EMPIRE CONTEXT - GENESIS HARVESTER HIGH-FIDELITY]
You are "Scholar" A04. Mission: Analyze historical patterns that HAVE OCCURRED using the F3 NodeGraph method.

INPUT DATA (T0):
(Note: If some long-term timeframes like 100w are missing due to a newly listed coin, use the full set of the longest available historical data).
- Coin: {coin} | Timestamp: {time_str}
- Wyckoff (W/D): {phase_w} / {phase_d}
- Elliott (D): {elliott.get('song_hien_tai', 'UNKNOWN')}
- VSA 4.0 Tier: {vsa.get('label', 'UNKNOWN')} ({vsa.get('desc', 'UNKNOWN')})
- Kinematics Vector: KAR={kinematics.get('kar', 0)} | PEI={kinematics.get('pei', 0)} | MNR={kinematics.get('mnr', 0)} | CA={kinematics.get('ca', 0)}

=== KINEMATICS VECTOR DECODING ===
- KAR (Absorption Ratio): >3.0 = Tier 1 Apex Wall (Iceberg blocking price). <0.5 = Exhausted volume.
- PEI (Path Efficiency): >0.8 = Tier 2 bots controlling trend. <0.3 = Noise/Choppiness.
- MNR (Micro-Noise): >0.7 = Tier 3 garbage zone (Stop-hunt). STAND ASIDE.
- CA (Capitulation): >2.0 = Tier 4 FOMO/Panic. If CA is high + KAR is high = REVERSAL.

=== INPUT DATA (T0): ===

ACTUAL OUTCOME IN 21 DAYS: {gt}

=== BOUNDED RATIONALITY SETUP ===
Note: You are analyzing aggregated historical data (OFI Candles). You are completely BLIND to the Order Book and tick data at this T0 timestamp. You cannot see Iceberg or Spoofing orders directly.

Therefore, you MUST perform "Ghost Footprints" tracking:
1. Do not state absolute certainty about hidden orders. Use probabilities: "The asymmetry between OFI and Price Delta suggests a high probability of absorption (Absorption) at this candle wick zone."
2. Find the "Failure Context": If OFI is extremely large (Long dominance) but price does not breakout -> This is indirect evidence of an Elite Iceberg Ask wall.
3. Never trust appearances: A large green volume candle is not necessarily bullish if it is accompanied by an abnormally high AR (Absorption Ratio).

STEP 1: TECHNICAL DEPTH & MICROSTRUCTURE (40% WEIGHT)
- OFI Anatomy: Anomaly between net order flow (OFI) and price spread.
- Wyckoff Examination: Position in Accumulation / Distribution cycle.
- Elliott Fractal Cycle: Wave within wave and retracement levels.

STEP 2: ELITE / COMPOSITE MAN INTENT (40% WEIGHT)
- Reverse-engineer all technical data into ARTIFICIAL ACTIONS.
- Determine whether Elite is Absorbing or Trapping through "indirect footprints".

STEP 3: OUTCOME INJUNCTION (20% WEIGHT)
- Based on Elite intent, explain WHY the actual outcome was: {gt}. 
- Formulate "hard-won" lessons to recognize this pattern in the future.

RETURN ONLY THE JSON FORMAT:
{{
  "instruction": "F3 NodeGraph tracking for {coin} at {time_str}. Actual outcome: {gt}",
  "input": "Structural: {phase_d} | Intent: {vsa.get('label', 'UNKNOWN')} | Connection: {elliott.get('song_hien_tai', 'UNKNOWN')}",
  "output": "[Extremely deep High-Fidelity analysis, strictly following the 3 thinking steps above, using advanced Wyckoff/Elliott terminology]",
  "score": 0.85,
  "_meta": {{ "engine": "A04_VSA4_Kinematics", "logic": "4Tier_Behavioral_Fingerprint" }}
}}
"""
    try:
        # DNA v18.3: Pass currency pair into agent_id for transparent logging
        resp_raw = brain.think_as(f"A04_GENESIS:{coin}", prompt, est_tokens=1000)
        try:
            from tools.agent_session_logger import log_agent_snapshot
            log_agent_snapshot("A04", prompt, resp_raw)
        except Exception as e:
            log.warning(f"Failed to log snapshot: {e}")
        
        log.debug(f"🔍 [LLM_RAW_RESPONSE]:\n{resp_raw}")
        # Find JSON in response
        import re
        match = re.search(r'\{.*\}', str(resp_raw) if resp_raw else "", re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(), strict=False)
                return data
            except json.JSONDecodeError as decode_err:
                log.error(f"Scholar Reasoning JSON Decode Error: {decode_err} | Raw: {match.group()}")
    except Exception as e:
        log.error(f"Scholar Reasoning Error: {e}")
    return None

# ==============================================================================
# DERIVATIVES TRAJECTORY HELPERS (8h trend)
# ==============================================================================

def _fetch_derivatives_trajectory(clean_sym: str, log) -> dict:
    """Fetch 8-point derivatives trajectory for L/S, OI, Funding."""
    import requests
    result = {"ls_trajectory": [], "oi_trajectory": [], "funding_trajectory": [],
              "ls_top_trajectory": [], "ls_current": "N/A", "oi_current": "N/A", 
              "funding_current": "N/A", "oi_delta_pct": 0.0, "ls_trend": "FLAT"}
    try:
        # L/S Global (8 points, 1h each)
        r = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={clean_sym}&period=1h&limit=8", timeout=5)
        if r.status_code == 200 and r.json():
            data = r.json()
            result["ls_trajectory"] = [round(float(d.get('longShortRatio', 1.0)), 4) for d in data]
            result["ls_current"] = f"{result['ls_trajectory'][-1]:.4f}" if result["ls_trajectory"] else "N/A"
            if len(result["ls_trajectory"]) >= 2:
                delta = result["ls_trajectory"][-1] - result["ls_trajectory"][0]
                result["ls_trend"] = "LONGS_INCREASING" if delta > 0.05 else "SHORTS_CLOSING" if delta < -0.05 else "FLAT"
    except Exception as e:
        log.warning(f"[A04] L/S trajectory fetch failed: {e}")
    
    try:
        # Top Trader L/S (8 points)
        r = requests.get(f"https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol={clean_sym}&period=1h&limit=8", timeout=5)
        if r.status_code == 200 and r.json():
            result["ls_top_trajectory"] = [round(float(d.get('longShortRatio', 1.0)), 4) for d in r.json()]
    except Exception as e:
        log.warning(f"[A04] Top Trader L/S fetch failed: {e}")
    
    try:
        # OI History (8 points)
        r = requests.get(f"https://fapi.binance.com/futures/data/openInterestHist?symbol={clean_sym}&period=1h&limit=8", timeout=5)
        if r.status_code == 200 and r.json():
            data = r.json()
            result["oi_trajectory"] = [round(float(d.get('sumOpenInterest', 0)), 2) for d in data]
            if len(result["oi_trajectory"]) >= 2:
                result["oi_delta_pct"] = round((result["oi_trajectory"][-1] - result["oi_trajectory"][0]) / max(result["oi_trajectory"][0], 1) * 100, 2)
            result["oi_current"] = f"{result['oi_trajectory'][-1]:,.2f}" if result["oi_trajectory"] else "N/A"
    except Exception as e:
        log.warning(f"[A04] OI trajectory fetch failed: {e}")
    
    try:
        # Funding Rate History (8 points)
        r = requests.get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={clean_sym}&limit=8", timeout=5)
        if r.status_code == 200 and r.json():
            result["funding_trajectory"] = [round(float(d.get('fundingRate', 0)) * 100, 4) for d in r.json()]
            result["funding_current"] = f"{result['funding_trajectory'][-1]:.4f}%" if result["funding_trajectory"] else "N/A"
    except Exception as e:
        log.warning(f"[A04] Funding trajectory fetch failed: {e}")
    
    return result

def _format_derivatives_section(deriv: dict) -> str:
    """Format derivatives trajectory as structured table for LLM."""
    lines = ["=== DERIVATIVES MOMENTUM (TREND 8H — algo_core, DO NOT recalculate) ==="]
    
    # L/S Global
    ls = deriv.get('ls_trajectory', [])
    if ls:
        ls_str = ' → '.join([f"{v:.3f}" for v in ls])
        trend = deriv.get('ls_trend', 'FLAT')
        trend_emoji = '📈' if 'INCREASING' in trend else '📉' if 'CLOSING' in trend else '➡️'
        lines.append(f"L/S Global: [{ls_str}] {trend_emoji} {trend}")
    else:
        lines.append("L/S Global: [NO_DATA]")
    
    # L/S Top Trader
    ls_top = deriv.get('ls_top_trajectory', [])
    if ls_top:
        ls_top_str = ' → '.join([f"{v:.3f}" for v in ls_top])
        lines.append(f"L/S Top Trader: [{ls_top_str}]")
    
    # OI
    oi = deriv.get('oi_trajectory', [])
    if oi:
        oi_str = ' → '.join([f"{v:,.0f}" for v in oi])
        delta = deriv.get('oi_delta_pct', 0)
        delta_emoji = '📈' if delta > 3 else '📉' if delta < -3 else '➡️'
        lines.append(f"Open Interest: [{oi_str}] {delta_emoji} Δ{delta:+.1f}% (8h)")
    else:
        lines.append(f"Open Interest: {deriv.get('oi_current', 'N/A')} [NO_HISTORY]")
    
    # Funding
    fund = deriv.get('funding_trajectory', [])
    if fund:
        fund_str = ' → '.join([f"{v:.4f}%" for v in fund])
        extreme = '🚨 EXTREME' if any(abs(f) > 0.05 for f in fund) else ''
        lines.append(f"Funding Rate: [{fund_str}] {extreme}")
    else:
        lines.append(f"Funding Rate: {deriv.get('funding_current', 'N/A')} [NO_HISTORY]")
    
    # Velocity
    if oi and len(oi) >= 2:
        oi_velocity = round((oi[-1] - oi[-2]), 2)
        lines.append(f"OI Velocity: {oi_velocity:+,.2f}/h")
    
    return '\n'.join(lines)

# ==============================================================================
# REALTIME HARVESTER - A05 STREAM SUPPORT 
# ==============================================================================

def _listen_for_realtime_requests():
    """Listen for Realtime requests from A05 or Commander."""
    log.info("[A04_REALTIME] Starting Realtime listening engine...")
    pubsub = matrix.subscribe(["COMMANDER:events", "SWARM_REALTIME_REQUEST"])
    for message in pubsub.listen():
        if message['type'] != 'message':
            continue
        try:
            data = json.loads(message['data'])
            action_event = data.get("action") or data.get("event")
            if action_event in ["A04_REALTIME_REQUEST", "SWARM_REALTIME_REQUEST"]:
                ma_coin = data.get("topic", "BTC/USDT")
                log.info(f"🔔 [A04_REALTIME] Starting on-the-spot analysis for {ma_coin}")
                
                kinematics = {}
                latest_json = {}
                try:
                    # Pulling historical XRANGE of the last 1 hour from Stream
                    t_now = int(time.time() * 1000)
                    t_100h_ago = t_now - 100 * 3600 * 1000
                    stream_history = matrix.client.xrange("zcl:a04:kinematics_stream", min=t_100h_ago, max="+")
                    
                    if stream_history and len(stream_history) > 0:
                        latest_record_id, latest_data = stream_history[-1]
                        latest_payload_str = latest_data.get(b"payload", latest_data.get("payload", "{}"))
                        if isinstance(latest_payload_str, bytes):
                            latest_payload_str = latest_payload_str.decode("utf-8")
                        latest_json = json.loads(latest_payload_str)
                    else:
                        latest_json = {}
                        
                    kinematics = latest_json.get("kinematics", {})
                    # Backward compatibility support
                    if "spot" in kinematics:
                        spot_kin = kinematics["spot"]
                        futures_kin = kinematics.get("futures", {})
                    else:
                        spot_kin = kinematics
                        futures_kin = kinematics

                    # SPOT
                    spot_wyckoff_w_str = json.dumps(spot_kin.get("1w", {}).get("wyckoff", {}), ensure_ascii=False)
                    spot_wyckoff_d_str = json.dumps(spot_kin.get("1d", {}).get("wyckoff", {}), ensure_ascii=False)
                    spot_wyckoff_h_str = json.dumps(spot_kin.get("1h", {}).get("wyckoff", {}), ensure_ascii=False)
                    spot_wyckoff_m_str = json.dumps(spot_kin.get("15m", {}).get("wyckoff", {}), ensure_ascii=False)
                    spot_wyckoff_s_str = json.dumps(spot_kin.get("1s", {}).get("wyckoff", {}), ensure_ascii=False)
                    
                    spot_elliott_w_str = json.dumps(spot_kin.get("1w", {}).get("elliott", {}), ensure_ascii=False)
                    spot_elliott_d_str = json.dumps(spot_kin.get("1d", {}).get("elliott", {}), ensure_ascii=False)
                    spot_elliott_h_str = json.dumps(spot_kin.get("1h", {}).get("elliott", {}), ensure_ascii=False)
                    spot_elliott_m_str = json.dumps(spot_kin.get("15m", {}).get("elliott", {}), ensure_ascii=False)
                    spot_elliott_s_str = json.dumps(spot_kin.get("1s", {}).get("elliott", {}), ensure_ascii=False)
                    
                    spot_vsa_w_str = json.dumps(spot_kin.get("1w", {}).get("vsa", {}), ensure_ascii=False)
                    spot_vsa_d_str = json.dumps(spot_kin.get("1d", {}).get("vsa", {}), ensure_ascii=False)
                    spot_vsa_h_str = json.dumps(spot_kin.get("1h", {}).get("vsa", {}), ensure_ascii=False)
                    spot_vsa_m_str = json.dumps(spot_kin.get("15m", {}).get("vsa", {}), ensure_ascii=False)
                    spot_vsa_s_str = json.dumps(spot_kin.get("1s", {}).get("vsa", {}), ensure_ascii=False)

                    # FUTURES
                    fut_wyckoff_w_str = json.dumps(futures_kin.get("1w", {}).get("wyckoff", {}), ensure_ascii=False)
                    fut_wyckoff_d_str = json.dumps(futures_kin.get("1d", {}).get("wyckoff", {}), ensure_ascii=False)
                    fut_wyckoff_h_str = json.dumps(futures_kin.get("1h", {}).get("wyckoff", {}), ensure_ascii=False)
                    fut_wyckoff_m_str = json.dumps(futures_kin.get("15m", {}).get("wyckoff", {}), ensure_ascii=False)
                    fut_wyckoff_s_str = json.dumps(futures_kin.get("1s", {}).get("wyckoff", {}), ensure_ascii=False)
                    
                    fut_elliott_w_str = json.dumps(futures_kin.get("1w", {}).get("elliott", {}), ensure_ascii=False)
                    fut_elliott_d_str = json.dumps(futures_kin.get("1d", {}).get("elliott", {}), ensure_ascii=False)
                    fut_elliott_h_str = json.dumps(futures_kin.get("1h", {}).get("elliott", {}), ensure_ascii=False)
                    fut_elliott_m_str = json.dumps(futures_kin.get("15m", {}).get("elliott", {}), ensure_ascii=False)
                    fut_elliott_s_str = json.dumps(futures_kin.get("1s", {}).get("elliott", {}), ensure_ascii=False)
                    
                    fut_vsa_w_str = json.dumps(futures_kin.get("1w", {}).get("vsa", {}), ensure_ascii=False)
                    fut_vsa_d_str = json.dumps(futures_kin.get("1d", {}).get("vsa", {}), ensure_ascii=False)
                    fut_vsa_h_str = json.dumps(futures_kin.get("1h", {}).get("vsa", {}), ensure_ascii=False)
                    fut_vsa_m_str = json.dumps(futures_kin.get("15m", {}).get("vsa", {}), ensure_ascii=False)
                    fut_vsa_s_str = json.dumps(futures_kin.get("1s", {}).get("vsa", {}), ensure_ascii=False)
                    
                    # HFT & CM Fingerprint data arrays
                    ob_snapshot_str = json.dumps(latest_json.get("orderbook_snapshot", {}), ensure_ascii=False)
                    micro_trades_str = json.dumps(latest_json.get("micro_trades", {}), ensure_ascii=False)
                    cm_htf_str = json.dumps(latest_json.get("cm_fingerprint_htf", {}), ensure_ascii=False)
                    cm_ltf_str = json.dumps(latest_json.get("cm_fingerprint_ltf", {}), ensure_ascii=False)
                    
                except Exception as e:
                    log.error(f"Error reading zcl:a04:kinematics_stream: {e}")
                    spot_wyckoff_w_str = spot_wyckoff_d_str = spot_wyckoff_h_str = spot_wyckoff_m_str = spot_wyckoff_s_str = "{}"
                    spot_elliott_w_str = spot_elliott_d_str = spot_elliott_h_str = spot_elliott_m_str = spot_elliott_s_str = "{}"
                    spot_vsa_w_str = spot_vsa_d_str = spot_vsa_h_str = spot_vsa_m_str = spot_vsa_s_str = "{}"
                    fut_wyckoff_w_str = fut_wyckoff_d_str = fut_wyckoff_h_str = fut_wyckoff_m_str = fut_wyckoff_s_str = "{}"
                    fut_elliott_w_str = fut_elliott_d_str = fut_elliott_h_str = fut_elliott_m_str = fut_elliott_s_str = "{}"
                    fut_vsa_w_str = fut_vsa_d_str = fut_vsa_h_str = fut_vsa_m_str = fut_vsa_s_str = "{}"
                    ob_snapshot_str = micro_trades_str = cm_htf_str = cm_ltf_str = "{}"
                
                # ── FETCH DERIVATIVES TRAJECTORY (8h trend: L/S, OI, Funding) ──
                oi_val = "N/A"
                funding_val = "N/A"
                ls_ratio = "N/A"
                oi_raw = 0.0
                funding_raw = 0.0
                deriv_data = {}
                try:
                    import requests
                    clean_sym = ma_coin.replace("/", "")
                    # Fetch full 8h trajectory
                    deriv_data = _fetch_derivatives_trajectory(clean_sym, log)
                    
                    # Backward compatibility: populate single-point vars from trajectory
                    ls_ratio = deriv_data.get('ls_current', 'N/A')
                    funding_val = deriv_data.get('funding_current', 'N/A')
                    
                    # OI: still need current snapshot for oi_raw (used by Sufficiency model)
                    r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={clean_sym}", timeout=3)
                    if r_oi.status_code == 200:
                        oi_raw = float(r_oi.json().get('openInterest', 0))
                        oi_val = f"{oi_raw:,.2f}"
                    elif deriv_data.get('oi_current') != 'N/A':
                        oi_val = deriv_data['oi_current']
                    
                    # Funding raw for Sufficiency model
                    r_fr = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={clean_sym}", timeout=3)
                    if r_fr.status_code == 200:
                        fr_data = r_fr.json()
                        if isinstance(fr_data, list): fr_data = fr_data[0]
                        funding_raw = float(fr_data.get('lastFundingRate', 0))
                except Exception as e_deriv:
                    log.warning(f"Error fetching derivatives data directly: {e_deriv}")
                
                # Format derivatives section for prompt
                derivatives_section = _format_derivatives_section(deriv_data)

                # Get/Update Peak OI
                peak_oi = 0.0
                try:
                    peak_key = f"zcl:a04:peak_oi:{clean_sym}"
                    stored_peak = matrix.client.get(peak_key)
                    if stored_peak:
                        peak_oi = float(stored_peak)
                    if oi_raw > peak_oi:
                        peak_oi = oi_raw
                        matrix.client.set(peak_key, str(peak_oi))
                except Exception:
                    pass
                if peak_oi == 0.0:
                    peak_oi = oi_raw if oi_raw > 0 else 1.0

                # LIQUIDITY SUFFICIENCY CALCULATION
                sufficiency_report = latest_json.get("sufficiency_report", {})
                if not sufficiency_report:
                    try:
                        from tools.A04_BRAIN_HELPER import LiquiditySufficiencyModel
                        model = LiquiditySufficiencyModel()
                        # Get daily ohlcv for volume profile
                        ohlcv_d = lay_ohlcv(ma_coin, "1d", so_nen=30)
                        ob_snapshot_dict = latest_json.get("orderbook_snapshot", {})
                        micro_trades_dict = latest_json.get("micro_trades", {})
                        sufficiency_report = model.evaluate_maturity(
                            ohlcv_d, oi_raw, peak_oi, funding_raw, ob_snapshot_dict, micro_trades_dict, matrix.client
                        )
                    except Exception as e_suff:
                        log.error(f"Error calculating Liquidity Sufficiency: {e_suff}")
                        sufficiency_report = {}


                # ══ REALITY ANCHOR: Latest 1-minute candle ══
                try:
                    _latest = lay_ohlcv(ma_coin, "1m", so_nen=1)
                    if _latest and len(_latest) > 0:
                        _c = _latest[-1]
                        from datetime import datetime as _dt
                        _ts = _dt.utcfromtimestamp(_c[0]/1000).strftime('%Y-%m-%d %H:%M UTC')
                        ohlcv_reality = (
                            f"Timestamp: {_ts} | Open: ${_c[1]:,.2f} | "
                            f"High: ${_c[2]:,.2f} | Low: ${_c[3]:,.2f} | "
                            f"Close: ${_c[4]:,.2f} | Vol: {_c[5]:,.0f}"
                        )
                    else:
                        ohlcv_reality = "Failed to fetch the latest candle."
                except Exception as e_ohlcv:
                    ohlcv_reality = f"OHLCV Error: {e_ohlcv}"

                # ── SESSION MEMORY: Read 2 Matrix FIFO ──
                try:
                    _m100h = matrix.client.lrange("zcl:a04:matrix_100h", 0, -1)
                    matrix_100h_str = "\n".join(
                        [v.decode('utf-8') if isinstance(v, bytes) else v for v in _m100h]
                    ) if _m100h else "No 100h data available"
                    
                    _m70d = matrix.client.lrange("zcl:a04:matrix_70d", 0, -1)
                    matrix_70d_str = "\n".join(
                        [v.decode('utf-8') if isinstance(v, bytes) else v for v in _m70d]
                    ) if _m70d else "No 70d data available"
                except Exception:
                    matrix_100h_str = "No data available"
                    matrix_70d_str = "No data available"
                
                # ── GROUND TRUTH: Read historical verdicts from Snapshot Harvester ──
                try:
                    from tools.agent_session_logger import get_recent_verdicts
                    _verdicts = get_recent_verdicts("A04", n=6)
                    verdicts_str = json.dumps(_verdicts, ensure_ascii=False)[:8000]
                except Exception:
                    verdicts_str = "No historical verdicts available."
                    
                # ── CHROMADB ENGRAM RECALL (A04 Exception: Requires Historical Data) ──
                chroma_rag_data = "ChromaDB not loaded or has no recent lessons."
                try:
                    from tools.engram_helper import A04EngramHelper
                    _engram = A04EngramHelper()
                    chroma_rag_data = _engram.recall_knowledge_deep(f"Accumulation distribution context of {ma_coin}", ma_coin)
                    if not chroma_rag_data or len(chroma_rag_data) < 10:
                        chroma_rag_data = "Engram records not found."
                except Exception as e:
                    log.warning(f"Error pulling ChromaDB Engram: {e}")
                    
                # ── HINGE PROTOCOL CHRONICLE (Long-term HingeEBM data) ──
                longterm_flow = "No long-term mathematical report available."
                try:
                    longterm_path = os.path.join(BASE_DIR, "agentic/knowledge/a04_longterm_flow_analysis.md")
                    if os.path.exists(longterm_path):
                        with open(longterm_path, "r", encoding="utf-8") as f:
                            longterm_flow = f.read()
                except Exception as e:
                    log.warning(f"Error reading A04 Longterm Flow: {e}")
                
                # ── A01 INTEGRATION: OFI & SPOOFING ──
                try:
                    # Extract spoofing from latest a04 crawler record instead of a01
                    spoofing_warning = latest_json.get("spoofing_warning", "KHONG_CO_DATA")
                    
                    # Pull OFI from 100-hour history stream of A04 Crawler (1 sample per 10 minutes)
                    ofi_traj_items = []
                    step = max(1, len(stream_history) // 600)
                    for i in range(0, len(stream_history), step):
                        rid, rdata = stream_history[i]
                        r_payload_str = rdata.get(b"payload", rdata.get("payload", "{}"))
                        if isinstance(r_payload_str, bytes):
                            r_payload_str = r_payload_str.decode("utf-8")
                        try:
                            r_json = json.loads(r_payload_str)
                            r_ofi_15m = r_json.get("ofi_candles", {}).get("15m", [])
                            if r_ofi_15m:
                                ofi_val_candle = r_ofi_15m[-1].get("ofi", 0)
                                ofi_traj_items.append(f"[OFI:{ofi_val_candle:,.0f}]")
                        except Exception:
                            pass
                    
                    if ofi_traj_items:
                        ofi_chunks = [" -> ".join(ofi_traj_items[i:i+10]) for i in range(0, len(ofi_traj_items), 10)]
                        ofi_matrix_str = "OFI TRAJECTORY (10 MIN/SAMPLE) OVER THE PAST 100 HOURS:\n" + "\n".join(ofi_chunks)
                    else:
                        ofi_matrix_str = "No OFI data from Stream A04."
                    
                    a01_block = f"SPOOFING WARNING (From Order Book): {spoofing_warning}\n{ofi_matrix_str}"
                except Exception as e:
                    log.error(f"Error pulling OFI from Stream: {e}")
                    a01_block = "Failed to retrieve OFI data."
                
                # ── SENTIMENT & CROSS-MARKET INTEGRATION (From A03) ──
                try:
                    a03_raw = matrix.get("SENTIMENT", "latest") or {}
                    a03_raw = a03_raw.get("trinity", a03_raw)
                    sentiment_metadata = a03_raw.get("metadata", {})
                    a03_payload = a03_raw.get("payload", {}) if "payload" in a03_raw else a03_raw
                    # Include full A03 JSON to prevent loss of RAPR, Fear&Greed, Narrative
                    a03_block_str = json.dumps(a03_payload, ensure_ascii=False)
                    a03_block = f"FULL A03 INTEL JSON: {a03_block_str}"
                except Exception as e:
                    log.error(f"Error pulling A03 SENTIMENT: {e}")
                    a03_block = "Failed to retrieve Sentiment/Cross-market data from A03."

                # ── DIEN HONG MINUTES (Inject) ──
                def _get_council_minutes_a04():
                    try:
                        from dien_hong_council import load_council_history
                        return load_council_history("A04")
                    except Exception:
                        return ""

                # ── A08 INTEGRATION: LIQUIDATION MIGRATION MAP ──
                liq_map_str = "No liquidation map available from A08."
                try:
                    liq_map_raw = matrix.get("A08", "liquidation_migration_map")
                    if liq_map_raw:
                        if isinstance(liq_map_raw, bytes):
                            liq_map_raw = liq_map_raw.decode("utf-8")
                        liq_map = json.loads(liq_map_raw)
                        
                        long_clusters = liq_map.get("long_liq_clusters", {})
                        short_clusters = liq_map.get("short_liq_clusters", {})
                        
                        # Format the largest liquidation clusters
                        top_longs = sorted(long_clusters.items(), key=lambda x: x[1], reverse=True)[:5]
                        top_shorts = sorted(short_clusters.items(), key=lambda x: x[1], reverse=True)[:5]
                        
                        long_str = ", ".join([f"${price}: {weight:.2f}" for price, weight in top_longs]) if top_longs else "None"
                        short_str = ", ".join([f"${price}: {weight:.2f}" for price, weight in top_shorts]) if top_shorts else "None"
                        
                        liq_map_str = f"LARGEST LONG LIQUIDATION CLUSTER: {long_str}\nLARGEST SHORT LIQUIDATION CLUSTER: {short_str}"
                except Exception as e_liq:
                    log.warning(f"Error pulling Liquidation Migration Map: {e_liq}")

                sufficiency_str = ""
                if sufficiency_report:
                    sufficiency_str = (
                        f"- Bottom Maturity Score: {sufficiency_report.get('bottom_maturity_score', 0.0):.4f} (Requires >= 0.85 to confirm Spring)\n"
                        f"- Top Maturity Score: {sufficiency_report.get('top_maturity_score', 0.0):.4f} (Requires >= 0.85 to confirm UTAD)\n"
                        f"- Open Interest Flush Ratio (OI Flush Ratio): {sufficiency_report.get('oi_flush_ratio_pct', 100.0):.2f}%\n"
                        f"- Absorption Rate Bottom: {sufficiency_report.get('abs_rate_bottom', 0.0):.4f}\n"
                        f"- Absorption Rate Top: {sufficiency_report.get('abs_rate_top', 0.0):.4f}\n"
                        f"- POC Trapped Capital Zone (POC Price): ${sufficiency_report.get('poc_price', 0.0):,.2f}\n"
                        f"- Estimated trapped capital volume (V_trapped): {sufficiency_report.get('v_trapped', 0.0):,.2f} BTC\n"
                        f"- OI Velocity: {sufficiency_report.get('oi_velocity', 0.0):.6f} contracts/sec\n"
                        f"- Funding Velocity: {sufficiency_report.get('funding_velocity', 0.0):.8f}/sec\n"
                        f"- CVD Delta (Micro net buying/selling power): {sufficiency_report.get('cvd_delta', 0.0):.4f} BTC\n"
                        f"- Absorption Exhaustion State: {sufficiency_report.get('absorption_exhaustion', False)}\n"
                        f"- Short Liquidity Pool Coordinates ($Zone_{{Pool}}$ Short): {json.dumps(sufficiency_report.get('zone_pools_short', {}), ensure_ascii=False)}\n"
                        f"- Long Liquidity Pool Coordinates ($Zone_{{Pool}}$ Long): {json.dumps(sufficiency_report.get('zone_pools_long', {}), ensure_ascii=False)}\n"
                        f"- Estimated Liquidation Force (Short Vol/Long Vol): {json.dumps(sufficiency_report.get('estimated_liquidation_volume', {}), ensure_ascii=False)}\n"
                        f"- Bi-directional Kinematics State: {json.dumps(sufficiency_report.get('bi_directional_kinematics', {}), ensure_ascii=False)}\n"
                        f"- Spot-Futures CVD Divergence Difference: {sufficiency_report.get('cvd_spot_futures_divergence', 0.0):.4f}"
                    )
                else:
                    sufficiency_str = "No Liquidity Sufficiency quantitative report available."

                realtime_prompt = f"""You are Elder A04 (Price Behavior Cryptography Expert - Wyckoff & VSA).
Based on the T0 scan data of coin {ma_coin}:

=== MATHEMATICAL SOURCE CODE PROTOCOLS CURRENTLY IN USE ===
- Shark Trap (Spoofing): Orderbook scanning algorithm. Sell wall > 2.5x buy wall but price does not drop/rise = SHARKS PLACING FAKE SELLS TO ACCUMULATE. Conversely, PLACING FAKE BUYS TO DISTRIBUTE/DUMP.
- OFI (Order Flow Imbalance): Delta between Taker Buy and Taker Sell Volume (from Raw Binance Klines). Positive OFI = Aggressive buying dominates.
- Vector Kinematics:
  + KAR (Absorption Ratio): Ratio of Volume absorbed by Limit orders. KAR > 3.0 = Block Wall exists (Iceberg).
  + PEI (Path Efficiency): Smoothness of price. PEI > 0.8 = HFT Bot leading. PEI < 0.3 = Noise/Choppiness.
  + MNR (Micro-Noise): Micro-noise level. MNR > 0.7 = Stop-hunt zone (liquidity hunting), many wicks.
- VSA & Wyckoff Algorithm: Automatically matches Support/Resistance range from the preceding 20 candles. Evaluates volume exhaustion (Low Vol Test) or breakout/breakdown spike to label Spring (Accumulation) or UTAD (Distribution). UTMOST NEUTRALITY REQUIRED.

=== BI-DIRECTIONAL KINEMATICS ALGORITHM INTERPRETATION GUIDE (LLM ALIGNMENT) ===
1. Zone_Pool coordinates: Compute theoretical liquidation price P_liq for leverage L in [20, 10, 5] starting from position POC entry (P_entry) and maintenance margin MMR = 0.5%:
   - Short P_liq = P_entry * (1 + 1/L - MMR)
   - Long P_liq = P_entry * (1 - 1/L + MMR)
   The outer boundary of Zone_Pool is computed from Swing High/Low or VAH/VAL plus an overshoot error margin of 0.8%.
2. Estimated liquidation force: Divide the new open interest delta OI by the account Long/Short ratio to calculate the volume at risk.
3. Spot-Futures CVD Divergence: Difference between Futures CVD and Spot CVD. Futures CVD dropping sharply (retail closing/liquidated leverage) while Spot CVD is sideways/increasing indicates Elite is silently accumulating Spot (Shakeout).
4. Exhaustion Point criterion: When price hits Zone_Pool and Absorption Rate >= 0.90 (Market orders completely absorbed by hidden walls) with OI velocity approaching 0 (Squeeze fuel exhausted).

[FORECAST 1-48H] (Short-term future forecast):
Based on the separation of FLOW and CURRENT, outline action scenarios, Wyckoff inflection points, or expected liquidity traps arising within the next 1-48 hours.

The arbitrator for judgment is not just the W/D label but the % change in price, volume, and Kinematics vectors (KAR, MNR).
UTMOST NEUTRALITY is required. Do not bias towards Long (Spring) or Short (UTAD). Balance your perspective!

=== YOUR RECENT VERDICTS (GROUND TRUTH — 6 SESSIONS) ===
{verdicts_str}
=== LONG-TERM MACRO FLOW DATA ===
{longterm_flow}
=== CHROMADB ENGRAM RECALL - PAST LESSONS ===
{chroma_rag_data}
=== PREVIOUS SESSION DIEN HONG MINUTES ===
{_get_council_minutes_a04()}

[CURRENT] (Latest reality):
=== 🔴 LATEST PRICE REALITY (REALITY ANCHOR — 1-MINUTE CANDLE) ===
{ohlcv_reality}
=== 🔴 REALITY CHECK (MANDATORY) ===
COMPARE the actual Close price with the resistance/support levels identified in the previous session.
- If price BREAKS ABOVE previous resistance → classify: UTAD? BREAKOUT? FALSE_BREAKOUT?
- If price BREAKS BELOW previous support → SPRING? SELLING_CLIMAX? BREAKDOWN?
- NEVER hold onto old verdicts when REALITY HAS REFUTED THEM!

=== RAW ALGORITHMIC DATA - 5 TIMEFRAMES ===
[WEEKLY TIMEFRAME - MACRO]
- SPOT - WYCKOFF: {spot_wyckoff_w_str} | ELLIOTT: {spot_elliott_w_str} | VSA: {spot_vsa_w_str}
- FUTURES - WYCKOFF: {fut_wyckoff_w_str} | ELLIOTT: {fut_elliott_w_str} | VSA: {fut_vsa_w_str}

[DAILY TIMEFRAME - MAIN TREND]
- SPOT - WYCKOFF: {spot_wyckoff_d_str} | ELLIOTT: {spot_elliott_d_str} | VSA: {spot_vsa_d_str}
- FUTURES - WYCKOFF: {fut_wyckoff_d_str} | ELLIOTT: {fut_elliott_d_str} | VSA: {fut_vsa_d_str}

[HOURLY TIMEFRAME (1H) - TRADING]
- SPOT - WYCKOFF: {spot_wyckoff_h_str} | ELLIOTT: {spot_elliott_h_str} | VSA: {spot_vsa_h_str}
- FUTURES - WYCKOFF: {fut_wyckoff_h_str} | ELLIOTT: {fut_elliott_h_str} | VSA: {fut_vsa_h_str}

[MINUTE TIMEFRAME (15M) - MICRO/ENTRY]
- SPOT - WYCKOFF: {spot_wyckoff_m_str} | ELLIOTT: {spot_elliott_m_str} | VSA: {spot_vsa_m_str}
- FUTURES - WYCKOFF: {fut_wyckoff_m_str} | ELLIOTT: {fut_elliott_m_str} | VSA: {fut_vsa_m_str}

[SECOND TIMEFRAME (1S) - HIGH FREQUENCY/RETAIL HUNTING]
- SPOT - WYCKOFF: {spot_wyckoff_s_str} | ELLIOTT: {spot_elliott_s_str} | VSA: {spot_vsa_s_str}
- FUTURES - WYCKOFF: {fut_wyckoff_s_str} | ELLIOTT: {fut_elliott_s_str} | VSA: {fut_vsa_s_str}

{derivatives_section}

=== LIQUIDITY SUFFICIENCY STATUS ===
{sufficiency_str}

=== A08 DYNAMIC LIQUIDATION MIGRATION MAP ===
{liq_map_str}

=== ORDER CAROUSEL & ELITE FOOTPRINTS (HFT & CM FINGERPRINT) ===
[ORDERBOOK SNAPSHOT (Static order book)]: {ob_snapshot_str}
[MICRO-TRADES (Dynamic order tape)]: {micro_trades_str}
[COMPOSITE MAN FINGERPRINT - MACRO (1D-4H-15M)]: {cm_htf_str}
[COMPOSITE MAN FINGERPRINT - MICRO (4H-15M-1S)]: {cm_ltf_str}

=== HOURLY TRAJECTORY — MATRIX 100H (FIFO, 1h/sample, WITH OHLC PRICE) ===
{matrix_100h_str}

=== DAILY TRAJECTORY — MATRIX 70D (FIFO, 1d/sample, WITH OHLC PRICE) ===
{matrix_70d_str}

=== SENTIMENT & INTERMARKET INTELLIGENCE (From A03 Sentiment) ===
{a03_block}

=== REAL-TIME ORDER FLOW & SPOOFING (From A01 Hound) ===
{a01_block}

THINKING MANDATE (Emergent Abilities):
Before reaching a conclusion, you MUST open a <think> tag according to the Five Scholar sequence:
1. [WEEKLY SCHOLAR THINKING]: Look macro, forecast whether the Accumulation (Long window) or Distribution (Short window) is occurring.
2. [DAILY SCHOLAR THINKING]: Reverse engineer Elite intent: High absorption (large KAR) could be a Peak Sell Wall (UTAD) or a Bottom Buy Wall (Spring).
3. [HOURLY SCHOLAR THINKING]: Inspect Volume spike points. Is this a SOS_BREAKOUT (Pump) or SOW_BREAKDOWN (Dump)?
4. [MINUTE SCHOLAR THINKING]: Capture liquidity traps: Shakeout (Spring_Trap) or Bull Trap (UTAD_Trap)?
5. [SECOND SCHOLAR THINKING]: Capture HFT Bot high-frequency spikes, identify hidden money flow.
Chain the 70-day VSA trajectory to track the Distribution/Accumulation logic flow from macro to micro!

Rule: Deduce whether Elite is setting a Bull Trap (UTAD) or Bear Trap (Spring).
Analyze objectively, compare Wyckoff structure and VSA correlation between Spot and Futures across timeframes to find asymmetries.
Pay attention to sudden increases/decreases of Open Interest and extreme Funding Rates to detect Spring (Short liquidation sweep) and UTAD (Long liquidation sweep) traps.

MILESTONE TRAIL: Daily and Hourly Scholars MUST determine the sequential milestones traversed. Use ONLY the keywords: SOS_BREAKOUT, LPS, SPRING_TRAP, SOW_BREAKDOWN, LPSY, UTAD_TRAP, SOS, Spring, Bottom 1, Bottom 2, Peak 1, Peak 2, Phase A/B/C/D/E.

BEFORE RETURNING JSON, YOU MUST OPEN A <thinking> TAG AND PERFORM THE EXACT 5 INDEPENDENT THINKING STEPS FOR THE 5 SCHOLARS (WEEKLY, DAILY, HOURLY, MINUTE, SECOND):
- ABSOLUTELY NO shallow, superficial, or rushed thinking. Academic rigor is sacred!
- Each Scholar must have a thorough analysis section, respecting and dissecting every mathematical metric (OFI, KAR, PEI, MNR, Support/Resistance range) of their respective timeframe.

YOU MUST RETURN THE FOLLOWING JSON FORMAT (AFTER THINKING TAG, NO ADDITIONAL OUTSIDE TEXT):
{{
  "phan_tich_dien_hong": "<Analysis of Dien Hong council minutes and cross-referencing>",
  "reality_check": "<COMPARE actual Close price vs previous session resistance/support. Classify: UTAD/SPRING/BREAKOUT/FALSE_BREAKOUT if any>",
  "Hoc_Gia_Tuan": "<Weekly comments: Time window, VSA & Elliott distinct...>",
  "Hoc_Gia_Ngay": "<Daily comments...>",
  "Quy_Dao_Ngay": ["<Milestone 1>", "<Milestone 2>", "..."],
  "Hoc_Gia_Gio": "<Hourly comments...>",
  "Quy_Dao_Gio": ["<Milestone 1>", "<Milestone 2>", "..."],
  "Hoc_Gia_Phut": "<Minute comments...>",
  "Hoc_Gia_Giay": "<Second comments...>",
  "squeeze_kinematics_analysis": "<Analyze price distance to Zone_Pool liquidity and forecast Squeeze exhaustion point>",
  "shakeout_flow_analysis": "<Analyze Spot vs Futures CVD divergence to detect shakeout traps>",
  "pyramiding_reloads_zone": "<Estimate optimal coordinates P_reload to reload orders after Squeeze ends>",
  "du_bao_48h": "<Forecast market behavior over the next 1-48 hours>"
}}"""
                llm_out = brain.think_as("A04_REALTIME", realtime_prompt, est_tokens=600)
                try:
                    from tools.agent_session_logger import log_agent_snapshot
                    log_agent_snapshot("A04", realtime_prompt, llm_out)
                except Exception:
                    pass
                try:
                    import re
                    clean_out = re.sub(r'<(?:think|thinking)>.*?</(?:think|thinking)>', '', llm_out, flags=re.DOTALL)
                    start = clean_out.find("{")
                    end = clean_out.rfind("}") + 1
                    json_data = json.loads(clean_out[start:end], strict=False)
                except Exception as e:
                    import logging
                    log.error(f"[A04_REALTIME] JSON parsing error: {e} | Raw LLM: {llm_out}")
                    json_data = {
                        "Hoc_Gia_Tuan": "N/A",
                        "Hoc_Gia_Ngay": "N/A",
                        "Hoc_Gia_Gio": "N/A",
                        "Hoc_Gia_Phut": "N/A",
                        "Hoc_Gia_Giay": "N/A",
                        "Quy_Dao_Ngay": [],
                        "Quy_Dao_Gio": [],
                        "reality_check": "",
                        "squeeze_kinematics_analysis": "N/A",
                        "shakeout_flow_analysis": "N/A",
                        "pyramiding_reloads_zone": "N/A"
                    }
                    
                # ── COMPILED INSIGHT: LEGACY REMOVED — Replaced by Snapshot Harvester ──
                    
                # ── PHASE 4 GRAND SURGERY: VSA Trajectory Memory + Trinity Envelope ──
                vsa_label = spot_kin.get("1d", {}).get("vsa", {}).get("label", "UNKNOWN")
                phase_w = spot_kin.get("1w", {}).get("wyckoff", {}).get("phase", "UNKNOWN")
                phase_d = spot_kin.get("1d", {}).get("wyckoff", {}).get("phase", "UNKNOWN")
                elliott_d_song = spot_kin.get("1d", {}).get("elliott", {}).get("song_hien_tai", "UNKNOWN")
                kin_info = spot_kin.get("1d", {}).get("kinematics", {})
                vsa_desc_d = spot_kin.get("1d", {}).get("vsa", {}).get("desc", "UNKNOWN")
                
                vsa_trail = [vsa_label] # Added to prevent NameError
                # ── PHASE 4 GRAND SURGERY: HingeEBM Packet (A04_VSA_PACKET) ──
                is_fallback = (json_data.get("Hoc_Gia_Tuan", "") == "" or 
                               "N/A" in json_data.get("reality_check", "N/A"))
                
                algo_core_a04 = {
                    "ts": datetime.utcnow().isoformat(),
                    "symbol": str(ma_coin),
                    "wyckoff_phase": str(phase_d),
                    "vsa_label": str(vsa_label),
                    "expert_metrics": {
                        "is_fallback": is_fallback,
                        "wyckoff": f"W:{phase_w}|D:{phase_d}",
                        "vsa_trajectory": " → ".join(vsa_trail),
                        "elliott": elliott_d_song,
                        "kinematics": {
                            "KAR": kin_info.get('kar', 0),
                            "MNR": kin_info.get('mnr', 0),
                            "CA": kin_info.get('ca', 0),
                            "PEI": kin_info.get('pei', 0),
                        },
                        "sufficiency_report": sufficiency_report,
                        "milestone_ngay": " -> ".join(json_data.get("Quy_Dao_Ngay", [])),
                        "milestone_gio": " -> ".join(json_data.get("Quy_Dao_Gio", [])),
                        # Futures integration
                        "futures": {
                            "wyckoff_phase": str(futures_kin.get("1d", {}).get("wyckoff", {}).get("phase", "UNKNOWN")),
                            "vsa_label": str(futures_kin.get("1d", {}).get("vsa", {}).get("label", "UNKNOWN")),
                            "elliott": str(futures_kin.get("1d", {}).get("elliott", {}).get("song_hien_tai", "UNKNOWN")),
                            "open_interest": deriv_data.get('oi_current', oi_val),
                            "funding_rate": deriv_data.get('funding_current', funding_val),
                            "long_short_ratio": deriv_data.get('ls_current', ls_ratio),
                            "ls_trajectory": deriv_data.get('ls_trajectory', []),
                            "ls_top_trajectory": deriv_data.get('ls_top_trajectory', []),
                            "oi_trajectory": deriv_data.get('oi_trajectory', []),
                            "oi_delta_pct": deriv_data.get('oi_delta_pct', 0.0),
                            "ls_trend": deriv_data.get('ls_trend', 'FLAT'),
                            "funding_trajectory": deriv_data.get('funding_trajectory', []),
                        }
                    }
                }
                
                narrative_lens_a04 = {
                    "hoc_gia_tuan": str(json_data.get("Hoc_Gia_Tuan", "")),
                    "hoc_gia_ngay": str(json_data.get("Hoc_Gia_Ngay", "")),
                    "hoc_gia_gio": str(json_data.get("Hoc_Gia_Gio", "")),
                    "hoc_gia_phut": str(json_data.get("Hoc_Gia_Phut", "")),
                    "reality_check": str(json_data.get("reality_check", "Split into Five Scholars and added CM Fingerprint.")),
                    "a04_story": str(json_data.get("Hoc_Gia_Giay", "The A04 system has been upgraded to Five Scholars. Please resolve from the Scholar knowledge slots."))
                }
                
                hinge_packet_a04 = {
                    "algo_core": algo_core_a04,
                    "narrative_lens": narrative_lens_a04
                }
                
                try:
                    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
                    quy_dao_ngay_str = " -> ".join(json_data.get("Quy_Dao_Ngay", []))
                    if quy_dao_ngay_str: matrix.rpush("A04", "milestone_trail_ngay", f"[{now_str}] {quy_dao_ngay_str}", max_len=70)
                    
                    quy_dao_gio_str = " -> ".join(json_data.get("Quy_Dao_Gio", []))
                    if quy_dao_gio_str: matrix.rpush("A04", "milestone_trail_gio", f"[{now_str}] {quy_dao_gio_str}", max_len=70)
                except Exception as e:
                    log.warning(f"Error writing milestone trail: {e}")
                
                matrix.xadd("A05", "t0_stream", {"source": "A04", "payload": json.dumps(hinge_packet_a04, ensure_ascii=False)}, maxlen=30)
                matrix.set("A04", "latest", json.dumps(hinge_packet_a04, ensure_ascii=False), ttl=1800)
                
                # --- xadd SYSTEM telegram:queue Stream ---
                try:
                    report_text = (
                        f"📈 *Phase Wyckoff*: {phase_d} | *VSA Label*: {vsa_label}\n"
                        f"📊 *Elliott*: {elliott_d_song}\n\n"
                        f"🔍 *Reality Check*:\n|_{json_data.get('reality_check', 'N/A')}_|\n\n"
                        f"⚡ *Squeeze Kinematics*:\n|_{json_data.get('squeeze_kinematics_analysis', 'N/A')}_|\n\n"
                        f"🌊 *Shakeout Flow*:\n|_{json_data.get('shakeout_flow_analysis', 'N/A')}_|\n\n"
                        f"🔮 *Forecast 48h*:\n|_{json_data.get('du_bao_48h', 'N/A')}_|"
                    )
                    is_algo_plus = False
                    try:
                        is_algo_plus = (matrix.client.get("zcl:system:last_algo_mode:A04_REALTIME") == b"algo_plus" or 
                                        matrix.client.get("zcl:system:last_algo_mode:A04_REALTIME") == "algo_plus")
                    except Exception as e_chk:
                        log.warning(f"[A04] Could not check last_algo_mode: {e_chk}")
                        
                    if is_algo_plus:
                        matrix.xadd("SYSTEM", "telegram:queue", {
                            "payload": json.dumps({"type": "A04_TO_A06_REPORT", "chu_ky": int(time.time()), "report_text": report_text}, ensure_ascii=False)
                        }, maxlen=1000)
                    else:
                        log.info("[A04] Skip sending Telegram because not running in ALGO_PLUS mode")
                except Exception as e_tele:
                    log.error(f"[A04] Error pushing to Telegram queue: {e_tele}")

                log.info(f"✅ [A04_REALTIME] Analysis completed and pushed Trinity Envelope to A05:t0_stream! VSA Trail: {' → '.join(vsa_trail)}")
                
                # --- DNA v18.0: Session Logger ---
                try:
                    import agent_session_logger
                    _summary = f"W:{phase_w} | D:{phase_d} | E:{elliott_d_song} | VSA:{vsa_desc_d} (KAR={kin_info.get('kar', 0):.2f})"
                    agent_session_logger.log_session(
                        agent_id="A04",
                        redis_key="A05:t0_stream",
                        summary=_summary,
                        signals_count=1,
                        confidence=0.8,
                        extra={"Nhan_Xet": json_data.get("Nhan_Xet_Chuyen_Gia", "")}
                    )
                except Exception as ex_log:
                    log.error(f"[A04_LOGGER] Error writing session log: {ex_log}")
                
        except Exception as e:
            log.error(f"[A04_REALTIME] Error handling command: {e}")

# ==============================================================================
# CLI HANDLER
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A04 Genesis Harvester - Sovereign v16.6")
    parser.add_argument("--genesis", action="store_true", help="Activate Genesis Engine")
    parser.add_argument("--realtime", action="store_true", help="Activate Realtime Engine")
    parser.add_argument("--ma-coin", type=str, help="Coin symbol (BTC/USDT, ETH/USDT, ...)")
    
    parser.add_argument("--limit", type=int, help="Limit on the number of scanned candles")
    parser.add_argument("--rollback-hours", type=int, default=0, help="Rewind the scan starting point by N hours to retrieve lost data")
    
    args = parser.parse_args()
    
    if args.realtime:
        # Start background heartbeat
        threading.Thread(target=_heartbeat_daemon, daemon=True).start()
        
        # 🏛️ Dien Hong Council — 4h daemon
        try:
            from dien_hong_council import start_council_daemon
            start_council_daemon("A04")
        except Exception as e_dh:
            log.warning(f"[A04] Dien Hong daemon failed to start: {e_dh}")
        
        try:
            _listen_for_realtime_requests()
        except KeyboardInterrupt:
            log.warning("\n⚠️ Stopped by user.")
    elif args.genesis and args.ma_coin:
        try:
            genesis_scan(args.ma_coin, limit=args.limit, rollback_hours=args.rollback_hours)
        except KeyboardInterrupt:
            log.warning("\n⚠️ Stopped by user. Saving state...")
            from agents.logic.a04_brain import load_genesis_metadata, save_genesis_metadata, GENESIS_FILE
            # Re - load just to be safe if the loop didn't save
            md = load_genesis_metadata() 
            pass
    else:
        print("\n" + "="*50)
        print("🏛️ ZERO-CUTLOSS EMPIRE - AGENT 04 (SCHOLAR)")
        print("="*50)
        print("💡 Genesis Mode: python3 a04_brain.py --genesis --ma-coin BTC/USDT")
        print("💡 Realtime Mode: python3 a04_brain.py --realtime")
        print("="*50 + "\n")

# [BRAIN SNIPPET — ARCHIVE]
# The 4-Scholar Framework Algorithm:
# - Weekly Scholar: Macro anchor, counter-trend major swings.
# - Daily Scholar: Differentiate Wyckoff Phase B/C.
# - M15 Scholar: Hunt liquidity traps (Wicks).
# - 1-Second Scholar: Find Zero Volume points.
