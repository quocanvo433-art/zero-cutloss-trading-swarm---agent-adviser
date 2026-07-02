"""
🧬 DNA: v16.6 (Sovereign Purity & Knowledge)
🏢 UNIT: CHROMA_INGEST
🛠️ ROLE: KNOWLEDGE_GOMER
📖 DESC: Vector knowledge ingestion system, embedding Wyckoff/Elliott theories, Binance historical data, and DPO pairs into ChromaDB for RAG.
🔗 CALLS: chromadb, tools/elliott_wyckoff_brain.py
📟 I/O: ChromaDB: wyckoff_patterns, dpo_lab/pairs/*.jsonl
🛡️ INTEGRITY: RAG-Consistency, Theory-Integrity, Pattern-Deduplication.
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests
from dotenv import load_dotenv

# Ensure tools/ is in path for centralized logic
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../config/.env'))

CHROMA_URL        = os.getenv("CHROMA_URL", "http://localhost:8001")
BINANCE_API_KEY   = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET    = os.getenv("BINANCE_SECRET_KEY", "")
REDIS_URL         = os.getenv("REDIS_URL", "redis://localhost:6379")

# Centralized Wyckoff logic will be lazy-loaded in functions that use it

BASE_DIR       = Path(__file__).parent.parent
CONFIG_DIR     = BASE_DIR / "config"
DPO_DIR        = BASE_DIR / "dpo_lab"
CHOSEN_FILE    = DPO_DIR / "pairs" / "chosen.jsonl"
REJECTED_FILE  = DPO_DIR / "pairs" / "rejected.jsonl"

log = logging.getLogger("CHROMA_INGEST")
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s',
                    handlers=[logging.FileHandler(str(BASE_DIR / "logs" / "agent_execution.log")),
                              logging.StreamHandler()])

COLLECTION_NAME = "wyckoff_patterns"

def normalize_keys(d: dict) -> dict:
    if not isinstance(d, dict):
        return d
    mapping = {
        "volume_can_kiet": "volume_exhaustion",
        "gia_thay_doi_pct": "price_change_pct",
        "song_hien_tai": "current_wave"
    }
    return {mapping.get(k, k): v for k, v in d.items()}

def normalize_dpo_keys(d: dict) -> dict:
    if not isinstance(d, dict):
        return d
    # Mapping for top-level keys
    top_mapping = {
        "boi_canh_thi_truong": "market_context",
        "ket_qua": "result",
        "muc_do_tu_tin": "confidence_level",
        "bai_hoc": "lessons",
        "ly_do_rejected": "rejection_reason"
    }
    normalized = {top_mapping.get(k, k): v for k, v in d.items()}
    
    # Mapping for market_context keys
    if "market_context" in normalized and isinstance(normalized["market_context"], dict):
        mc_mapping = {
            "wyckoff_phase": "wyckoff_phase",
            "elliott_song": "elliott_wave",
            "composite_man": "composite_man",
            "tam_ly_dam_dong": "crowd_sentiment",
            "dong_thuan_4_tang": "4_tier_alignment"
        }
        normalized["market_context"] = {mc_mapping.get(k, k): v for k, v in normalized["market_context"].items()}
        
    # Mapping for result keys
    if "result" in normalized and isinstance(normalized["result"], dict):
        res_mapping = {
            "loi_nhuan_pct": "profit_pct",
            "drawdown_max_pct": "max_drawdown_pct"
        }
        normalized["result"] = {res_mapping.get(k, k): v for k, v in normalized["result"].items()}
        
    return normalized

# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — CHROMADB CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def _get_chroma_collection():
    """Connect to ChromaDB and return the wyckoff_patterns collection"""
    try:
        import chromadb
        host = CHROMA_URL.replace("http://", "").replace("https://", "").split(":")[0]
        port = int(CHROMA_URL.split(":")[-1]) if ":" in CHROMA_URL else 8001
        client = chromadb.HttpClient(host=host, port=port)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        log.info(f"ChromaDB connected — collection '{COLLECTION_NAME}' has {collection.count()} documents")
        return collection
    except Exception as e:
        log.error(f"ChromaDB connection error: {e}")
        log.error("Ensure ChromaDB is running: docker compose up chroma -d")
        raise


# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — WYCKOFF THEORY KNOWLEDGE (hardcoded, independent of API)
# ══════════════════════════════════════════════════════════════════════════════

WYCKOFF_THEORY_DOCS = [
    # Phase A — Stopping downtrend
    {
        "id": "theory_phase_A_PSY",
        "text": "Wyckoff Phase A - Preliminary Support (PSY): After a long decline, the first buying force appears to slow the decline. Volume increases, price rebounds temporarily but the trend has not changed. This is the first signal that the downtrend may be weakening. DO NOT enter buy orders here — Phase A is only an early warning.",
        "meta": {"phase": "PHASE_A", "pattern": "PSY", "action": "STAND_ASIDE", "confidence": 30}
    },
    {
        "id": "theory_phase_A_SC",
        "text": "Wyckoff Phase A - Selling Climax (SC): Peak panic selling — extremely high volume, price drops sharply then bounces immediately. This is when Smart Money begins to absorb supply from panicking retail traders. Do not buy even if the price looks cheap — SC is usually retested. Results after 3 weeks: 60% sideways, 30% retest, 10% continued decline.",
        "meta": {"phase": "PHASE_A", "pattern": "SC", "action": "STAND_ASIDE", "confidence": 40}
    },
    {
        "id": "theory_phase_A_AR",
        "text": "Wyckoff Phase A - Automatic Rally (AR): Strong bounce after SC due to lack of supply. Volume is lower than SC. Price rises to resistance, creating a Trading Range. The peak of AR will be the upper boundary of Phase B. Absolutely do not buy the rally — AR usually ends with a Secondary Test. Zero-Cutloss: STAND_ASIDE.",
        "meta": {"phase": "PHASE_A", "pattern": "AR", "action": "STAND_ASIDE", "confidence": 35}
    },
    # Phase B — Accumulation
    {
        "id": "theory_phase_B_main",
        "text": "Wyckoff Phase B - Accumulation: The longest accumulation phase, usually lasting 2-8 weeks. Smart Money continues to accumulate assets from impatient retail traders. Price fluctuates within a Trading Range. Many 'traps' appear: fake breakouts to the upside and downside to shake out retail. THIS IS THE DEATH ZONE — Zero-Cutloss absolutely bans entering orders during Phase B because sideways action wastes time and transaction fees.",
        "meta": {"phase": "PHASE_B", "pattern": "ACCUMULATION", "action": "ABSOLUTELY_FORBIDDEN", "confidence": 20}
    },
    {
        "id": "theory_phase_B_ST",
        "text": "Wyckoff Phase B - Secondary Test (ST) in Phase B: Price retests the SC area to check if selling pressure remains. Lower volume than SC is a good sign — selling pressure is drying up. However, Phase B has many STs and every ST looks similar. It is impossible to distinguish whether this is an ST of Phase B or a Phase C setup while in it. Zero-Cutloss: STAND_ASIDE.",
        "meta": {"phase": "PHASE_B", "pattern": "ST_PHASE_B", "action": "STAND_ASIDE", "confidence": 25}
    },
    # Phase C — Entry opportunity (Highest quality)
    {
        "id": "theory_phase_C_spring",
        "text": "Wyckoff Phase C - Spring (MOST IMPORTANT): Price is pushed below the Trading Range low to sweep stop losses of retail long positions. This is the final trap before the real increase. Valid Spring signs: (1) Volume drops sharply at the new low — Smart Money is not selling more, (2) Price quickly recovers back into the Trading Range within 1-3 candles, (3) Climactic volume or a No Supply bar at the Spring low. Historical results: 78% of genuine Spring cases have a subsequent markup of 15-30% in 2-4 weeks. THIS IS THE BEST ENTRY POINT according to Zero-Cutloss.",
        "meta": {"phase": "PHASE_C", "pattern": "SPRING", "action": "LIMIT_ORDER_ENTRY", "confidence": 85}
    },
    {
        "id": "theory_phase_C_spring_test",
        "text": "Wyckoff Phase C - Spring Test (Secondary Test of Spring): After a Spring, price usually retests the Spring low area with lower volume. This is a second entry opportunity that is better than the first Spring because it provides further confirmation. Successful Spring Test: lower volume than the Spring, price does not breach the Spring low. This is the highest quality entry point in the Zero-Cutloss system — minimal drawdown because SL is placed right below the Spring low.",
        "meta": {"phase": "PHASE_C", "pattern": "SPRING_TEST", "action": "HIGH_QUALITY_LIMIT_ENTRY", "confidence": 88}
    },
    {
        "id": "theory_phase_C_upthrust",
        "text": "Wyckoff Phase C - Upthrust (Distribution): Opposite of a Spring, price is pushed above the Trading Range high to sweep stop losses of retail shorts. Smart Money is distributing assets to retail traders who FOMO at the top. Signs: (1) High volume at the new peak, (2) Price cannot hold above resistance and returns inside the range, (3) Close near the candle low — clear rejection. Upthrust confirmed -> distribution is happening -> downtrend is about to start. Zero-Cutloss: CAN CONSIDER SHORT if there is a clear signal.",
        "meta": {"phase": "PHASE_C", "pattern": "UPTHRUST", "action": "CONSIDER_SHORT", "confidence": 82}
    },
    {
        "id": "theory_phase_C_UTAD",
        "text": "Wyckoff Phase C - Upthrust After Distribution (UTAD): The final push up in the distribution process, after which the price completely collapses. UTAD differs from a normal Upthrust: VERY HIGH volume at the new peak, retail FOMO rushing in, Smart Money dumps all inventory in 1-3 candles. After UTAD is Phase D — a strong markdown trend. DANGEROUS to mistake UTAD for a real breakout. Signs: volume climax + close near the candle low at historical resistance.",
        "meta": {"phase": "PHASE_C", "pattern": "UTAD", "action": "AVOID_LONG_CONSIDER_SHORT", "confidence": 75}
    },
    # Phase D/E — Markup
    {
        "id": "theory_phase_D_SOS",
        "text": "Wyckoff Phase D - Sign of Strength (SOS): After a Spring, price rises sharply on high volume, breaking above the Trading Range high. This is confirmation that Smart Money has finished accumulating and is starting to markup. SOS usually has volume 2-3x the average. Last Point of Support (LPS) after SOS is the final entry opportunity before the price takes off. Zero-Cutloss: entry at LPS is still possible with low drawdown.",
        "meta": {"phase": "PHASE_D", "pattern": "SOS", "action": "LPS_ENTRY", "confidence": 80}
    },
    {
        "id": "theory_phase_E_markup",
        "text": "Wyckoff Phase E - Markup: A clear and strong uptrend. Smart Money distributes inventory to retail gradually. Price rises step-by-step, with pullbacks serving as accumulation opportunities. Phase E usually ends in Distribution — restarting the cycle. Do not chase buy orders when price is up 20%+ — that is late Phase E, near the top. Zero-Cutloss: DO NOT ENTER NEW POSITIONS in late Phase E.",
        "meta": {"phase": "PHASE_E", "pattern": "MARKUP", "action": "NO_LATE_ENTRY", "confidence": 60}
    },
    # Zero-Cutloss rules
    {
        "id": "zero_cutloss_rule_1",
        "text": "Zero-Cutloss Rule 1 - Only trade Phase C: Spring, Spring Test, Upthrust, UTAD, Secondary Test Phase C. Absolutely do not enter trades during Phase A or Phase B. Reason: Phase C is the best risk/reward point — close SL (Spring low or Upthrust high), far Target (15-30% markup). Maximum acceptable drawdown: 2%. If drawdown > 2% after entry = incorrect setup, exit immediately.",
        "meta": {"phase": "ZERO_CUTLOSS", "pattern": "RULE", "action": "ONLY_TRADE_PHASE_C", "confidence": 100}
    },
    {
        "id": "zero_cutloss_rule_2",
        "text": "Zero-Cutloss Rule 2 - 4-tier alignment: Wyckoff Phase C MUST align across all 4 timeframes (Weekly, Daily/H4, M15/M5, 1s). Weekly Wyckoff provides the big picture, Daily/H4 confirms Phase C, M15/M5 locates the exact entry, and 1s confirms Volume exhaustion at the Spring low. Missing 1 tier of alignment = reduces confidence by 25%. Missing 2 tiers = DO NOT ENTER.",
        "meta": {"phase": "ZERO_CUTLOSS", "pattern": "RULE", "action": "TIMEFRAME_ALIGNMENT", "confidence": 100}
    },
    {
        "id": "zero_cutloss_rule_3",
        "text": "Zero-Cutloss Rule 3 - Limit Orders Only: No market orders, no chasing price. Distribute limit orders in a ladder format: 40% at the expected Spring low, 35% at H4 support, 25% at the Volume exhaustion level. A total of 3 limit orders -> if the market moves according to thesis, at least 1 order fills with near-zero drawdown. Cancel all orders if M5 breaks below the SL level and stays there for 2 consecutive candles.",
        "meta": {"phase": "ZERO_CUTLOSS", "pattern": "RULE", "action": "LIMIT_LADDER", "confidence": 100}
    },
    # Elliott Wave
    {
        "id": "elliott_wave_impulse",
        "text": "Elliott Wave - Impulse Wave (Impulse Wave 1-2-3-4-5): Wave 3 is usually the longest and strongest, never the shortest. Wave 2 retracement does not cross the bottom of wave 1. Wave 4 does not cross the peak of wave 1. Combining with Wyckoff: Spring usually occurs at the end of wave 2 or wave 4. Entering at a Spring = entering at the start of wave 3 or wave 5 — strongest bullish momentum. Fibonacci target for wave 3: 161.8% or 261.8% of wave 1 length.",
        "meta": {"phase": "ELLIOTT", "pattern": "IMPULSE", "action": "ENTER_START_OF_WAVE_3", "confidence": 75}
    },
    {
        "id": "elliott_wave_correction",
        "text": "Elliott Wave - Corrective Wave (ABC Correction): Wave A is typically Wyckoff Phase A, Wave B is Phase B (sideways), and Wave C is Phase C ending with a Spring. Fibonacci retracement of Wave C usually reaches 0.618 or 0.786 of the preceding impulse wave. This is the expected Spring region. Volume exhaustion at Fibonacci levels = strong confirmation for the Spring thesis.",
        "meta": {"phase": "ELLIOTT", "pattern": "CORRECTION_ABC", "action": "FIND_SPRING_VIA_FIBONACCI", "confidence": 78}
    },
    # Composite Man
    {
        "id": "composite_man_accumulation",
        "text": "Composite Man - Accumulation in noise: The Composite Man (market makers, whales) accumulates assets while retail is selling in panic. Signs: negative exchange netflow (withdrawing BTC from exchanges), increasing ETF inflows, but price does not rise. Composite Man uses bearish media to induce fear; retail sells, Composite Man buys. Combined with Agent 03 MM Fingerprint Score > 70 + Phase C Spring = extremely high-quality setup.",
        "meta": {"phase": "COMPOSITE_MAN", "pattern": "ACCUMULATION", "action": "HIGH_CONVICTION_LONG", "confidence": 90}
    },
    {
        "id": "composite_man_distribution",
        "text": "Composite Man - Distribution in euphoria: The Composite Man distributes assets when retail is buying at the peak due to FOMO. Signs: positive exchange netflow (depositing BTC to exchanges), extreme bullish media (>70% bullish articles), Fear & Greed > 80, TikTok viral posts about crypto. Composite Man uses minor pumps to trigger FOMO, then dumps. Upthrust/UTAD + MM Fingerprint distribution = extremely dangerous if holding long.",
        "meta": {"phase": "COMPOSITE_MAN", "pattern": "DISTRIBUTION", "action": "EXIT_LONG_CONSIDER_SHORT", "confidence": 88}
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — HISTORICAL PATTERNS FROM BINANCE
# ══════════════════════════════════════════════════════════════════════════════

def _phan_tich_wyckoff_don_gian_lazy(nen_list: list) -> dict:
    """Lazy load centralized Wyckoff brain logic"""
    try:
        from tools.elliott_wyckoff_brain import _phan_tich_wyckoff_don_gian
        return _phan_tich_wyckoff_don_gian(nen_list)
    except ImportError:
        # Fallback pathing for scripts/ running alongside tools/
        import sys as _sys
        import os as _os
        _parent = _os.path.join(_os.path.dirname(__file__), '..')
        if _parent not in _sys.path:
            _sys.path.append(_parent)
        try:
            from tools.elliott_wyckoff_brain import _phan_tich_wyckoff_don_gian
            return _phan_tich_wyckoff_don_gian(nen_list)
        except ImportError:
            # Last resort fallback if tools is not findable
            log.error("CRITICAL: Cannot import tools.elliott_wyckoff_brain. Falling back to UNKNOWN.")
            return {"phase": "UNKNOWN", "volume_trend": "UNKNOWN", "gia_thay_doi_pct": 0,
                    "volume_can_kiet": False, "spring_detected": False}


def _lay_ohlcv_binance(ma_coin: str, timeframe: str, so_nen: int = 500) -> list:
    """Fetch OHLCV from Binance (public endpoints, no auth required)"""
    try:
        import ccxt
        san = ccxt.binance({"enableRateLimit": True,
                            "apiKey": BINANCE_API_KEY, "secret": BINANCE_SECRET})
        nen = san.fetch_ohlcv(ma_coin, timeframe, limit=so_nen)
        log.info(f"Binance {ma_coin} {timeframe}: {len(nen)} candles")
        return nen
    except Exception as e:
        log.warning(f"Binance {ma_coin} {timeframe}: {e}")
        return []


def _mo_ta_ket_qua(nen_truoc: list, nen_sau: list) -> str:
    if not nen_sau:
        return "No subsequent data"
    gia_bat_dau  = nen_truoc[4]
    gia_ket_thuc = nen_sau[-1][4]
    thay_doi     = round(((gia_ket_thuc - gia_bat_dau) / gia_bat_dau) * 100, 1) if gia_bat_dau > 0 else 0
    xu_huong = "Up" if thay_doi > 3 else "Down" if thay_doi < -3 else "Sideways"
    return f"{xu_huong} {abs(thay_doi)}% after {len(nen_sau)} candles"


def ingest_lich_su_binance(collection, ma_coin: str, timeframe: str = "1w",
                           so_nen: int = 300, window: int = 50) -> int:
    """
    Fetch OHLCV history from Binance, run sliding window, embed patterns into ChromaDB.
    """
    nen_list = _lay_ohlcv_binance(ma_coin, timeframe, so_nen)
    if len(nen_list) < window + 20:
        log.warning(f"{ma_coin} {timeframe}: only has {len(nen_list)} candles, needs at least {window+20}")
        return 0

    so_nhu = 0
    for i in range(0, len(nen_list) - window - 20, 10):
        cua_so       = nen_list[i:i + window]
        ket_qua_thuc = nen_list[i + window:i + window + 20]
        
        phan_tich    = normalize_keys(_phan_tich_wyckoff_don_gian_lazy(cua_so))
        ket_qua_mo_ta = _mo_ta_ket_qua(cua_so[-1], ket_qua_thuc)
        ngay_str     = datetime.utcfromtimestamp(cua_so[-1][0] / 1000).strftime('%Y-%m-%d')
        doc_id  = f"{ma_coin.replace('/','-')}_{timeframe}_{cua_so[-1][0]}"
        doc_text = (
            f"Coin: {ma_coin} | Timeframe: {timeframe} | Date: {ngay_str} | "
            f"Wyckoff: {phan_tich.get('phase')} | Volume trend: {phan_tich.get('volume_trend')} | "
            f"Volume exhaustion: {phan_tich.get('volume_exhaustion')} | "
            f"Price change: {phan_tich.get('price_change_pct')}% | "
            f"Spring detected: {phan_tich.get('spring_detected')} | "
            f"Result 20 candles after: {ket_qua_mo_ta}"
        )
        try:
            collection.upsert(
                ids=[doc_id],
                documents=[doc_text],
                metadatas=[{
                    "ma_coin":          ma_coin,
                    "timeframe":        timeframe,
                    "timestamp":        cua_so[-1][0],
                    "date":             ngay_str,
                    "wyckoff_phase":    phan_tich.get("phase"),
                    "volume_exhaustion": str(phan_tich.get("volume_exhaustion")),
                    "spring_detected":  str(phan_tich.get("spring_detected")),
                    "actual_result":    ket_qua_mo_ta,
                    "price_change_pct": phan_tich.get("price_change_pct"),
                    "doc_type":         "binance_history",
                }]
            )
            so_nhu += 1
        except Exception as e:
            log.warning(f"Upsert error {doc_id}: {e}")
            
    log.info(f"{ma_coin} {timeframe}: embedded {so_nhu} patterns into ChromaDB")
    return so_nhu


# ══════════════════════════════════════════════════════════════════════════════
# PART 4 — EMBED EXISTING DPO PAIRS
# ══════════════════════════════════════════════════════════════════════════════

def ingest_dpo_pairs(collection) -> tuple[int, int]:
    """
    Embed existing DPO pairs into ChromaDB.
    Tells A04: "this setup occurred, result was CHOSEN/REJECTED".
    This is system-generated real-world experience, more valuable than textbook theory.
    """
    chosen_count = rejected_count = 0

    def _xu_ly_file(filepath: Path, label: str) -> int:
        count = 0
        if not filepath.exists():
            log.warning(f"File does not exist: {filepath}")
            return 0
        with open(filepath, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = normalize_dpo_keys(json.loads(line))
                    snap_id = rec.get("snapshot_id", f"pair_{i}")
                    # Get critical context
                    market_context = rec.get("market_context", {})
                    result = rec.get("result", {})
                    doc_text = (
                        f"DPO {label} | Snapshot: {snap_id} | "
                        f"Wyckoff: {market_context.get('wyckoff_phase', '?')} | "
                        f"Elliott: {market_context.get('elliott_wave', '?')} | "
                        f"Composite Man: {market_context.get('composite_man', '?')} | "
                        f"Sentiment: {market_context.get('crowd_sentiment', '?')} | "
                        f"Alignment: {market_context.get('4_tier_alignment', '?')} tiers | "
                        f"Confidence: {rec.get('confidence_level', '?')}% | "
                        f"Result: {label} | "
                        f"Profit: {result.get('profit_pct', '?')}% | "
                        f"Max Drawdown: {result.get('max_drawdown_pct', '?')}% | "
                        f"Lesson: {rec.get('lessons', '') or rec.get('rejection_reason', '')}"
                    )
                    collection.upsert(
                        ids=[f"dpo_{label}_{snap_id}"],
                        documents=[doc_text],
                        metadatas=[{
                            "doc_type":         f"dpo_{label}",
                            "snap_id":          snap_id,
                            "wyckoff_phase":    market_context.get("wyckoff_phase", "UNKNOWN"),
                            "composite_man":    market_context.get("composite_man", "UNKNOWN"),
                            "dpo_classification": label.upper(),
                            "confidence_pct":   str(rec.get("confidence_level", 0)),
                            "profit_pct":       str(result.get("profit_pct", 0)),
                        }]
                    )
                    count += 1
                except Exception as e:
                    log.warning(f"DPO {label} line {i}: {e}")
        return count

    chosen_count   = _xu_ly_file(CHOSEN_FILE, "chosen")
    rejected_count = _xu_ly_file(REJECTED_FILE, "rejected")
    log.info(f"DPO pairs embedded: {chosen_count} chosen + {rejected_count} rejected")
    return chosen_count, rejected_count


# ══════════════════════════════════════════════════════════════════════════════
# PART 5 — MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def init_full(skip_binance: bool = False):
    """
    Run first time initialization: load all theory + historical data.
    Takes about 15-30 minutes depending on network speed.
    """
    log.info("=== CHROMA INGEST: FULL INITIALIZATION ===")
    collection = _get_chroma_collection()

    # 1. Wyckoff/Elliott theory (instant)
    log.info("Loading Wyckoff/Elliott/Zero-Cutloss theories...")
    theo_ids = [d["id"] for d in WYCKOFF_THEORY_DOCS]
    theo_txts = [d["text"] for d in WYCKOFF_THEORY_DOCS]
    theo_metas = [d["meta"] | {"doc_type": "theory"} for d in WYCKOFF_THEORY_DOCS]
    collection.upsert(ids=theo_ids, documents=theo_txts, metadatas=theo_metas)
    log.info(f"Theories: {len(WYCKOFF_THEORY_DOCS)} documents embedded successfully")

    # 2. Binance history — BTC and ETH
    total_pattern = 0
    if not skip_binance:
        coins_timeframes = [
            ("BTC/USDT", "1w",  300),
            ("BTC/USDT", "1d",  500),
            ("BTC/USDT", "4h",  500),
            ("ETH/USDT", "1w",  250),
            ("ETH/USDT", "1d",  500),
        ]
        for ma, tf, n in coins_timeframes:
            try:
                cnt = ingest_lich_su_binance(collection, ma, tf, n)
                total_pattern += cnt
                time.sleep(0.5)  # Rate limit
            except Exception as e:
                log.warning(f"{ma} {tf}: {e}")
    else:
        log.info("Skipped Binance history (--skip-binance)")

    # 3. DPO pairs (if exist)
    c_cnt, r_cnt = ingest_dpo_pairs(collection)

    total = collection.count()
    log.info(f"=== INITIALIZATION COMPLETED ===")
    log.info(f"Theories: {len(WYCKOFF_THEORY_DOCS)} | Binance patterns: {total_pattern} | DPO: {c_cnt+r_cnt} | Total: {total}")
    return {"total_documents": total, "theory": len(WYCKOFF_THEORY_DOCS),
            "binance_patterns": total_pattern, "dpo_pairs": c_cnt + r_cnt}


def update_pairs_only():
    """Fast update of DPO pairs only — run after Agent 08 injects new pairs"""
    log.info("=== CHROMA INGEST: UPDATE DPO PAIRS ===")
    collection = _get_chroma_collection()
    c, r = ingest_dpo_pairs(collection)
    log.info(f"Update completed: +{c} chosen, +{r} rejected | Total: {collection.count()}")
    return {"chosen_added": c, "rejected_added": r, "total_collection": collection.count()}


def kiem_tra_suc_khoe() -> dict:
    """Check if ChromaDB has sufficient data — called by A04 on startup"""
    try:
        collection = _get_chroma_collection()
        total = collection.count()
        # Query a pattern to verify RAG is working
        test = collection.query(query_texts=["BTC Phase C Spring Volume exhaustion"],
                                n_results=3)
        so_ket_qua = len(test["documents"][0]) if test["documents"] else 0
        status = "GOOD" if total >= 20 else ("MISSING_THEORY" if total < 10 else "READY_TO_RUN")
        return {
            "total_documents":  total,
            "test_query_result": so_ket_qua,
            "status":           status,
            "notes": "Run: python scripts/chroma_ingest.py --init" if total < 20 else "OK",
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e),
                "notes": "ChromaDB is not running or not initialized"}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChromaDB Ingestion — Zero-Cutloss Knowledge Base")
    parser.add_argument("--init",          action="store_true", help="Full initialization (first time)")
    parser.add_argument("--update-pairs",  action="store_true", help="Update new DPO pairs")
    parser.add_argument("--status",        action="store_true", help="Check status")
    parser.add_argument("--skip-binance",  action="store_true", help="Skip Binance data (use when offline)")
    parser.add_argument("--coin",          type=str, default="",  help="Ingest a specific coin")
    args = parser.parse_args()

    if args.status:
        result = kiem_tra_suc_khoe()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.init:
        print("=== INITIALIZING CHROMADB — Zero-Cutloss Knowledge Base ===")
        print("Loading: Wyckoff/Elliott theory + Binance history + DPO pairs")
        print("Estimated time: 15-30 minutes\n")
        result = init_full(skip_binance=args.skip_binance)
        print(f"\nCompleted: {result}")

    elif args.update_pairs:
        result = update_pairs_only()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.coin:
        collection = _get_chroma_collection()
        for tf in ["1w", "1d"]:
            ingest_lich_su_binance(collection, args.coin, tf)
        print(f"Ingested {args.coin} successfully. Total: {collection.count()} documents")

    else:
        parser.print_help()
        print("\nQuick start:")
        print("  python scripts/chroma_ingest.py --status       # Check")
        print("  python scripts/chroma_ingest.py --init          # First time")
        print("  python scripts/chroma_ingest.py --update-pairs  # After new DPO is available")
