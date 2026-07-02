"""
🧬 DNA: v16.6 (Sovereign Purity & EMF Harvest) [DNA Header]
🏢 UNIT: SIGNAL_COLLECTOR (A10)
🛠️ ROLE: EMF_HARVESTER
📖 DESC: Smart money cash flow signal collection system (EMF). Harvesting data from SEC, CFTC, On-chain, and institutional macro indicators (FRED/EIA).
🔗 CALLS: tools/nlm_changelog.py, tools/imperial_state.py
📟 I/O: Redis: emf:signals:raw, emf:signals:scored, zcl:A10:heartbeat
🛡️ INTEGRITY: Data-Purity, Source-Verification, Real-time-EMF.

LLM (Gemini 3.1 Flash Lite) is used to normalize the schema and score narrative for raw signals.
"""

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))

import os
import json
import time
import uuid
import logging
import hashlib
import threading
import feedparser
import requests
from collections import deque
from datetime import datetime, timezone, timedelta
import yfinance as yf
from dotenv import load_dotenv
from typing import Optional

from imperial_state import matrix
import nlm_changelog
from llm_router import router_api_call, ALGO_CYCLE_INTERVAL_SEC
last_algo_time = 0
from imperial_brain import brain
from agent_session_logger import log_session as _log_agent_session, get_drift_context as _get_drift_context
import a102_equity_flow

load_dotenv(dotenv_path=BASE_DIR / 'config' / '.env')

# ── Config ───────────────────────────────────────────────────────────────────
# REDIS_URL deprecated in favor of Matrix
# Intelligence Routing (Unified Empire Router)
FRED_API_KEY       = os.getenv("FRED_API_KEY", "")
EIA_API_KEY        = os.getenv("EIA_API_KEY", "")
DUNE_API_KEY       = os.getenv("DUNE_API_KEY", "")
DUNE_QUERY_BTC_NETFLOW = os.getenv("DUNE_QUERY_BTC_NETFLOW", "")
DUNE_QUERY_BTC_WHALE   = os.getenv("DUNE_QUERY_BTC_WHALE", "")
DUNE_QUERY_ETH_FLOW    = os.getenv("DUNE_QUERY_ETH_FLOW", "")
WHALE_ALERT_API_KEY    = os.getenv("WHALE_ALERT_API_KEY", "")

EMF_LAB_DIR  = BASE_DIR / "emf_lab"
LOG_DIR      = BASE_DIR / "logs" / "emf_signals"
MEMORY_DIR   = EMF_LAB_DIR / "memory"
WEIGHTS_FILE = MEMORY_DIR / "weights.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

from dos_guardian import get_agent_instructions
from a09_immunity import sanitize_text_for_llm as a09_sanitize_text

from imperial_state import setup_agent_logger

log = setup_agent_logger("A10", "EMF_COLLECTOR")

# ── Default source weights (overridden by emf_lab/memory/weights.json from A11) ─
DEFAULT_WEIGHTS = {
    "sec_form4":         0.75,
    "cftc_cot":          0.70,
    "fred":              0.65,
    "dune_analytics":    0.85,
    "clankapp":          0.80,
    "eia_energy":        0.72,
    "fred_elite_macro":  0.70,
    "yfinance_elite":    0.68,
}

# Average lead time (hours) — how long each signal_type predicts the event beforehand
# This is a statistical reference, NOT a fixed formula (Elite creative)
LEAD_TIME_MAP = {
    # Equity
    "insider_trade":    72,    # SEC Form 4: ~3 days before
    "darkpool_print":   24,    # Dark Pool: ~1 day
    "options_unusual":  48,    # Unusual options: ~2 days
    # Crypto
    "smart_money_flow": 12,    # On-chain whale: ~12h
    "whale_wallet":     6,     # Dormant wallet wake: ~6h
    "stablecoin_flow":  4,     # Stablecoin move: ~4h
    "exchange_inflow":  8,     # Exchange net flow: ~8h
    "hodl_wave":        168,   # HODL wave shift: ~7 days
    # Commodity
    "cot_positioning":  168,   # CFTC COT: 1 week (delayed inherently)
    "physical_demand":  120,   # COMEX inventory: 5 days
    # Bond
    "reverse_repo_flow": 720,  # Reverse Repo: 30 days (macro slow)
    "yield_10y":        720,
    "yield_2y":         720,
    "yield_curve":      720,
    "hy_spread":        96,    # HY Spread: ~4 days
    # FX
    "usd_index":        36,
    "fx_skew":          36,
}

# Simple cache: source → (data, timestamp)
_cache: dict = {}
_cache_lock = threading.Lock()
CACHE_TTL_SEC = 3600  # 1 hour


# ══════════════════════════════════════════════════════════════════════════════
# REDIS HELPER
# ══════════════════════════════════════════════════════════════════════════════

# matrix is imported from imperial_state

def _get_dos_mode() -> str:
    return matrix.get("GUARDIAN", "system_mode") or "NORMAL"

def _get_position_state() -> str:
    return matrix.get("SYSTEM", "position_state") or "STATE_1_HUNTING"


# ══════════════════════════════════════════════════════════════════════════════
# WEIGHTS — read from emf_lab/memory/weights.json (updated by A11)
# ══════════════════════════════════════════════════════════════════════════════

def _load_weights() -> dict:
    try:
        if WEIGHTS_FILE.exists():
            with open(WEIGHTS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return DEFAULT_WEIGHTS.copy()


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA — UNIFIED_SIGNAL
# ══════════════════════════════════════════════════════════════════════════════

def _build_signal(source: str, asset_class: str, asset_ticker: str,
                  signal_type: str, raw_value: float, baseline_30d: float,
                  direction: str, elite_intent_raw: str,
                  freshness: str = "realtime") -> dict:
    """Create signal according to standard UNIFIED_SIGNAL schema."""
    weights = _load_weights()
    deviation = 0.0
    if baseline_30d and baseline_30d != 0:
        deviation = round((raw_value - baseline_30d) / abs(baseline_30d) * 100, 2)

    abs_dev_ratio = abs(raw_value / baseline_30d) if baseline_30d and baseline_30d != 0 else 1.0
    if abs_dev_ratio < 1.5:    magnitude = "low"
    elif abs_dev_ratio < 3.0:  magnitude = "medium"
    elif abs_dev_ratio < 5.0:  magnitude = "high"
    else:                      magnitude = "extreme"

    return {
        "signal_id":       str(uuid.uuid4()),
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "source":          source,
        "asset_class":     asset_class,
        "asset_ticker":    asset_ticker,
        "signal_type":     signal_type,
        "raw_value":       raw_value,
        "baseline_30d":    baseline_30d,
        "deviation_score": deviation,
        "lead_time_avg_hours": LEAD_TIME_MAP.get(signal_type, 48),
        "direction":       direction,
        "magnitude":       magnitude,
        "source_weight":   weights.get(source, 0.5),
        "data_freshness":  freshness,
        "elite_intent_raw": elite_intent_raw,
        "position_state_context": _get_position_state(),
    }

def _build_error_signal(source: str, error_msg: str) -> dict:
    """Create signal reporting signal loss error when API crashes/rate-limited. Flag as DATA_RECENTLY."""
    return _build_signal(
        source=source, asset_class="unknown", asset_ticker="UNKNOWN",
        signal_type="API_ERROR", raw_value=0, baseline_30d=0,
        direction="neutral", elite_intent_raw="DATA_RECENTLY",
        freshness="error"
    )


# ══════════════════════════════════════════════════════════════════════════════
# CACHE HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _get_cache(key: str, ttl_sec: Optional[int] = None) -> Optional[list]:
    with _cache_lock:
        entry = _cache.get(key)
        eff_ttl = ttl_sec if ttl_sec is not None else CACHE_TTL_SEC
        if entry and (time.time() - entry["ts"]) < eff_ttl:
            return entry["data"]
    return None


def _set_cache(key: str, data: list):
    with _cache_lock:
        _cache[key] = {"data": data, "ts": time.time()}


# ══════════════════════════════════════════════════════════════════════════════
# FETCHERS — FREE TIER
# ══════════════════════════════════════════════════════════════════════════════




def fetch_sec_form4() -> list:
    """
    Fetch SEC Form 4 insider trades via RSS.
    Schedule: every 2h (orchestrator.yaml → schedules.sec_form4)
    """
    dos_mode = _get_dos_mode()
    if dos_mode == "LOCKDOWN":
        return []

    cached = _get_cache("sec_form4")
    if cached is not None:
        return cached

    RSS_URL = ("https://www.sec.gov/cgi-bin/browse-edgar"
               "?action=getcurrent&type=4&dateb=&owner=include&count=40&search_text=&output=atom")

    try:
        feed = feedparser.parse(RSS_URL)
        log.info("SEC Form4: Successfully parsed XML/Atom feed.")
    except Exception as e:
        log.error(f"SEC Form4 RSS (XML/Atom) error: {e}")
        return _get_cache("sec_form4") or [_build_error_signal("sec_form4", str(e))]

    signals = []
    MIN_VALUE = 100_000  # Only get transactions > $100K

    for entry in feed.entries[:20]:
        try:
            title   = entry.get("title", "")
            summary = entry.get("summary", "")

            # Simple parse — production requires full SEC XML parser
            if "purchase" in title.lower() or "acquisition" in summary.lower():
                direction = "up"
                intent    = "accumulate"
            elif "sale" in title.lower() or "disposition" in summary.lower():
                direction = "down"
                intent    = "distribute"
            else:
                continue

            # Extract ticker if any
            ticker = "UNKNOWN"
            for part in title.split():
                if part.isupper() and 2 <= len(part) <= 5:
                    ticker = part
                    break

            signals.append(_build_signal(
                source="sec_form4", asset_class="equity", asset_ticker=ticker,
                signal_type="insider_trade", raw_value=MIN_VALUE, baseline_30d=MIN_VALUE,
                direction=direction, elite_intent_raw=intent,
                freshness="realtime",
            ))
        except Exception:
            continue

    _set_cache("sec_form4", signals)
    log.info(f"SEC Form4: {len(signals)} signals")
    return signals


def fetch_cftc_cot() -> list:
    """
    Fetch CFTC COT Report — Commercial vs. Speculative positioning.
    Schedule: Friday 17:30 UTC (orchestrator.yaml → schedules.cftc_cot)
    Parse real CSV from CFTC: commercial_net, noncommercial_net, extreme_positioning.
    """
    dos_mode = _get_dos_mode()
    if dos_mode == "LOCKDOWN":
        return []

    cached = _get_cache("cftc_cot")
    if cached is not None:
        return cached

    # CFTC Disaggregated Futures-only (updated every Friday)
    COT_CSV_URL = "https://www.cftc.gov/dea/newcot/f_disagg.txt"

    # Contract code → (asset_slug, asset_class, ticker)
    CONTRACT_MAP = {
        "CRUDE OIL":          ("commodity", "CRUDE_OIL"),
        "GOLD":               ("commodity", "GOLD"),
        "NATURAL GAS":        ("commodity", "NAT_GAS"),
        "E-MINI S&P 500":     ("equity",    "SPX"),
        "BITCOIN":            ("crypto",    "BTC"),
    }

    signals = []
    try:
        resp = requests.get(COT_CSV_URL, timeout=60)
        resp.raise_for_status()
        log.info("CFTC COT: Downloaded and preparing to parse report in text/CSV format.")
        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            log.warning("CFTC CSV empty")
            return _get_cache("cftc_cot") or [_build_error_signal("cftc_cot", "CSV empty")]

        # CSV headers at line 0, data from line 1
        # Format: Market_Name, As_of_Date, ..., Comm_Long, Comm_Short, ...,
        #         NonComm_Long, NonComm_Short, ...
        for line in lines[1:]:
            cols = [c.strip().strip('"') for c in line.split(",")]
            if len(cols) < 12:
                continue

            market_name = cols[0].upper()
            matched = None
            for key, (asset_class, ticker) in CONTRACT_MAP.items():
                if key in market_name:
                    matched = (asset_class, ticker)
                    break
            if not matched:
                continue

            asset_class, ticker = matched

            try:
                # CFTC Disaggregated format:
                # Col 11: Managed Money Long (Non-Comm), Col 12: Managed Money Short
                # Col 5: Producer/Merchant Long (Comm), Col 6: Producer/Merchant Short
                noncomm_long  = float(cols[11]) if len(cols) > 11 and cols[11] else 0
                noncomm_short = float(cols[12]) if len(cols) > 12 and cols[12] else 0
                comm_long     = float(cols[5]) if len(cols) > 5 and cols[5] else 0
                comm_short    = float(cols[6]) if len(cols) > 6 and cols[6] else 0
            except (ValueError, IndexError):
                continue

            comm_net    = comm_long - comm_short
            noncomm_net = noncomm_long - noncomm_short

            # Elite intent: Commercial (who actually know price) vs. Speculative (hedge funds)
            #   Commercial increase net long → they know price will go up → accumulate
            #   Commercial increase net short → hedging → hedge/distribute
            #   NonComm at extreme net long → retail/fund has gone all-in → reversal imminent
            if comm_net > 0:
                direction = "up"
                intent = "accumulate"  # Commercials are bullish
            elif comm_net < 0:
                direction = "down"
                intent = "hedge"       # Commercials are hedging
            else:
                direction = "neutral"
                intent = "unknown"

            # Extreme positioning: if noncomm net is too large relative to total OI
            total_oi = noncomm_long + noncomm_short + comm_long + comm_short
            extreme_pct = abs(noncomm_net) / max(total_oi, 1) * 100 if total_oi > 0 else 0

            # Baseline: use commercial net average = 0 (normal hedge position)
            signals.append(_build_signal(
                source="cftc_cot", asset_class=asset_class, asset_ticker=ticker,
                signal_type="cot_positioning",
                raw_value=comm_net,
                baseline_30d=0.0,  # Baseline = neutral commercial positioning
                direction=direction, elite_intent_raw=intent,
                freshness="delayed",  # COT data lag 3 days
            ))

            # If extreme positioning → add separate alert
            if extreme_pct > 60:  # NonComm is at extreme → contrarian signal
                contrarian_intent = "distribute" if noncomm_net > 0 else "accumulate"
                signals.append(_build_signal(
                    source="cftc_cot", asset_class=asset_class, asset_ticker=ticker,
                    signal_type="cot_positioning",
                    raw_value=extreme_pct,
                    baseline_30d=50.0,  # Baseline = 50% (average)
                    direction="down" if noncomm_net > 0 else "up",
                    elite_intent_raw=contrarian_intent,
                    freshness="delayed",
                ))
                log.warning(f"CFTC EXTREME: {ticker} noncomm_net={noncomm_net:.0f} "
                            f"extreme_pct={extreme_pct:.1f}% → contrarian {contrarian_intent}")

    except Exception as e:
        log.error(f"CFTC COT (CSV Parse) error: {e}")
        return _get_cache("cftc_cot") or [_build_error_signal("cftc_cot", str(e))]

    _set_cache("cftc_cot", signals)
    log.info(f"CFTC COT: {len(signals)} signals")
    return signals


# ══════════════════════════════════════════════════════════════════════════════
# FETCHERS — ON-CHAIN SOURCES (Dune Analytics & ClankApp)
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_dune_data(query_id: str, cycle: str = "SHORT") -> Optional[list]:
    """Fetch latest Dune Analytics query result"""
    if not DUNE_API_KEY or not query_id:
        return None
    try:
        limit_days = 7 if cycle == "SHORT" else 30
        resp = requests.get(
            f"https://api.dune.com/api/v1/query/{query_id}/results",
            headers={"X-Dune-API-Key": DUNE_API_KEY},
            params={"limit": limit_days},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("result", {}).get("rows", [])
    except Exception as e:
        log.warning(f"Dune query {query_id} error: {e}")
        return None


def fetch_dune_analytics(cycle: str = "SHORT") -> list:
    """
    Fetch Dune Analytics: BTC Netflow, BTC Whales, ETH Flow
    Schedule: every 1-2h (depending on orchestrator config)
    """
    if not DUNE_API_KEY:
        return []
    dos_mode = _get_dos_mode()
    if dos_mode in ("SURVIVAL", "LOCKDOWN"):
        return []

    cached = _get_cache(f"dune_analytics_{cycle}")
    if cached is not None:
        return cached

    signals = []

    # 1. BTC Netflow
    netflow_rows = _fetch_dune_data(DUNE_QUERY_BTC_NETFLOW, cycle)
    if netflow_rows:
        try:
            netflow_today = float(netflow_rows[0].get("netflow_btc", 0))
            # Negative netflow (outflow) = bullish (accumulate), positive netflow (inflow) = bearish (distribute)
            direction = "up" if netflow_today < 0 else "down"
            intent = "accumulate" if netflow_today < 0 else "distribute"
            baseline = sum(float(r.get("netflow_btc", 0)) for r in netflow_rows) / max(len(netflow_rows), 1)
            signals.append(_build_signal(
                source="dune_analytics", asset_class="crypto", asset_ticker="BTC",
                signal_type="exchange_inflow", raw_value=netflow_today, baseline_30d=baseline,
                direction=direction, elite_intent_raw=intent,
            ))
        except Exception as e:
            log.warning(f"Dune BTC Netflow parse error: {e}")

    # 2. BTC Whales (Smart Money)
    whale_rows = _fetch_dune_data(DUNE_QUERY_BTC_WHALE, cycle)
    if whale_rows:
        try:
            whale_tx_count  = float(whale_rows[0].get("so_outputs", 0))
            total_btc_whale = float(whale_rows[0].get("tong_btc", 0))
            baseline_tx = sum(float(r.get("so_outputs", 0)) for r in whale_rows) / max(len(whale_rows), 1)
            # High whale activity usually predicts large volatility (can be accumulation or distribution)
            direction = "up" if whale_tx_count > baseline_tx else "neutral"
            signals.append(_build_signal(
                source="dune_analytics", asset_class="crypto", asset_ticker="BTC",
                signal_type="whale_wallet", raw_value=whale_tx_count, baseline_30d=baseline_tx,
                direction=direction, elite_intent_raw="unknown",
            ))
        except Exception as e:
            log.warning(f"Dune BTC Whale parse error: {e}")

    # 3. ETH Smart Flow
    eth_rows = _fetch_dune_data(DUNE_QUERY_ETH_FLOW, cycle)
    if eth_rows:
        try:
            eth_netflow = float(eth_rows[0].get("netflow_eth", 0))
            direction = "up" if eth_netflow < 0 else "down"
            intent = "accumulate" if eth_netflow < 0 else "distribute"
            baseline = sum(float(r.get("netflow_eth", 0)) for r in eth_rows) / max(len(eth_rows), 1)
            signals.append(_build_signal(
                source="dune_analytics", asset_class="crypto", asset_ticker="ETH",
                signal_type="exchange_inflow", raw_value=eth_netflow, baseline_30d=baseline,
                direction=direction, elite_intent_raw=intent,
            ))
        except Exception as e:
            log.warning(f"Dune Analytics error: {e}")
            return _get_cache(f"dune_analytics_{cycle}") or [_build_error_signal("dune_analytics", str(e))]

    _set_cache(f"dune_analytics_{cycle}", signals)
    log.info(f"Dune Analytics ({cycle}): {len(signals)} signals")
    return signals


def fetch_clankapp() -> list:
    """
    Fetch Whale Transactions: Real-time large crypto moves.
    Primary: whale-alert.io public API (free, no key, 1000tx/day)
    Fallback: Blockchair large-transaction query (free)
    Frequency: 30 minutes - 1 hour
    """
    dos_mode = _get_dos_mode()
    if dos_mode in ("SURVIVAL", "LOCKDOWN"):
        return []

    cached = _get_cache("clankapp")
    if cached is not None:
        return cached

    signals = []
    btc_vol: float = 0.0
    eth_vol: float = 0.0

    # ── Primary: Whale Alert API ─────────────────────────────────────────────
    try:
        api_key = WHALE_ALERT_API_KEY or "live_free" # Fallback to live_free if not set
        resp = requests.get(
            "https://api.whale-alert.io/v1/transactions",
            params={"api_key": api_key, "min_value": "50000000", "currency": "btc,eth"},
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200:
            txs = resp.json().get("transactions", [])
            for tx in txs[:30]:
                sym   = tx.get("symbol", "").upper()
                amt_u = float(tx.get("amount_usd", 0))
                if sym == "BTC":  btc_vol += amt_u
                elif sym == "ETH": eth_vol += amt_u
        elif resp.status_code == 401:
            log.warning(f"Whale Alert API 401: Key '{api_key}' is invalid or expired.")
            raise ValueError(f"whale-alert HTTP 401")
        else:
            raise ValueError(f"whale-alert HTTP {resp.status_code}")
    except Exception as e_primary:
        log.warning(f"Whale Alert API error ({e_primary}) — trying Blockchair fallback")
        # ── Fallback: Blockchair BTC large transactions (public, no key) ─────
        try:
            # Use Blockchair API free tier (limit 1 req/sec)
            resp_b = requests.get(
                "https://api.blockchair.com/bitcoin/transactions",
                params={"q": "output_total_usd(50000000..)", "limit": "10", "s": "time(desc)"},
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp_b.status_code == 200:
                rows = resp_b.json().get("data", [])
                btc_vol = sum(float(r.get("output_total_usd", 0)) for r in rows[:10])
            elif resp_b.status_code == 430:
                 log.warning(f"Blockchair fallback HTTP 430: Rate limit hit. (API Key required)")
            else:
                log.warning(f"Blockchair BTC fallback HTTP {resp_b.status_code}")
        except Exception as e_fb:
            log.warning(f"Blockchair fallback error: {e_fb}")
            return _get_cache("clankapp") or [_build_error_signal("clankapp", str(e_fb))]

    if btc_vol > 0:
        signals.append(_build_signal(
            source="clankapp", asset_class="crypto", asset_ticker="BTC",
            signal_type="smart_money_flow", raw_value=btc_vol, baseline_30d=50000000,
            direction="up", elite_intent_raw="unknown", freshness="realtime"
        ))
    if eth_vol > 0:
        signals.append(_build_signal(
            source="clankapp", asset_class="crypto", asset_ticker="ETH",
            signal_type="smart_money_flow", raw_value=eth_vol, baseline_30d=50000000,
            direction="up", elite_intent_raw="unknown", freshness="realtime"
        ))

    if not signals:
        return _get_cache("clankapp") or [_build_error_signal("clankapp", "No whale tx above $50M")]

    _set_cache("clankapp", signals)
    log.info(f"Whale Monitor (ClankApp compat): {len(signals)} signals")
    return signals


# ══════════════════════════════════════════════════════════════════════════════
# FETCHERS — ELITE MACRO (EIA + FRED Macro + yfinance)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_verified_news_shifts() -> list:
    """
    Fetch verified news shifts via RSS from multiple sources for Elite assets:
    SPY, QQQ, DIA, TLT, HYG, GLD, USO, VXX.
    NEW mechanism: Strict Evaluation Pipeline (Filtering via keyword + LLM Crawler CRAWL_FREE).
    Only collects actual actions of Top Tier Elite.
    """
    dos_mode = _get_dos_mode()
    if dos_mode == "LOCKDOWN": return []

    cached = _get_cache("verified_news_shifts", ttl_sec=900) # Reduce Cache to 15 minutes to increase RSS update frequency
    if cached is not None: return cached

    import urllib.parse
    
    # Elite Standard Keyword Matrix (Global multi-language coverage)
    # Using unicode escapes to prevent Vietnamese literal characters in source code
    elite_keywords = [
        # English
        "acquire", "merger", "offload", "liquidate", "sell-off", "buyout", "insider", "institutional", "hedge fund", "sovereign", "dump", "accumulate", "stake", "hoard", "stockpile", "reserve",
        # Vietnamese
        "t\u00edch tr\u1eef", "\u0111\u1ea7u c\u01a1", "d\u1ef1 tr\u1eef", "thu gom", "b\u00e1n th\u00e1o",
        # Chinese
        "囤积", "储备", "抛售", "收购", "央行", "主权基金",
        # Russian
        "накопление", "резерв", "распродажа", "суверенный",
        # Spanish & Others
        "acumular", "reserva", "liquidación"
    ]
    
    # Global Asset List
    assets = '"gold" OR "oil" OR "copper" OR "bonds" OR "SPY" OR "QQQ" OR "DIA" OR "DBC" OR "DBA" OR "CPER" OR "KRBN" OR "LQD"'
    
    # Global Action List
    actions = '"hoard" OR "stockpile" OR "accumulate" OR "liquidate" OR "dump" OR "t\u00edch tr\u1eef" OR "d\u1ef1 tr\u1eef" OR "\u0111\u1ea7u c\u01a1" OR "囤积" OR "储备" OR "накопление"'
    
    # Use Yahoo RSS (new news) and Google News RSS (12m historical news)
    query_1y = f'({assets}) AND ({actions}) when:1y'
    google_rss = f"https://news.google.com/rss/search?q={urllib.parse.quote(query_1y)}&hl=en-US&gl=US&ceid=US:en"
    yahoo_rss = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GLD,USO,TLT,SPY,QQQ,DIA,BTC-USD,HYG,VXX,DBC,DBA,CPER,KRBN,LQD"
    
    sources = [yahoo_rss, google_rss]
    signals = []
    
    try:
        raw_news = []
        for rss_url in sources:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:50]: # Expand high-frequency scraping to 50 articles per source
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                full_text = f"{title} {summary}".lower()
                
                # Round 1: Multi-language Keyword Check
                if any(k in full_text for k in elite_keywords):
                    link = entry.get("link", "No_Link")
                    source_name = entry.get("source", {}).get("title", "News") if isinstance(entry.get("source"), dict) else "RSS"
                    raw_news.append(f"- [{source_name}] {title} (URL: {link})")
                
        if raw_news:
            # Round 2: LLM CRAWL_MODE Extract Tickers & Rotation with Link (Multilingual support)
            news_block = "\n".join(raw_news)
            prompt = f"""[ELITE ASSET ROTATION EXTRACTOR - GLOBAL COVERAGE]
The raw news below has passed the 12-month historical CRAWL filter. The news sources are displayed in hundreds of different languages (e.g. Chinese "囤积", Russian "резерв", US "hoard").
You (LLM) are encouraged to constantly change IPs/proxies if you have web browsing plugins to cross-scrape and verify the origin if needed.

Please distinguish clearly: What is the news that the Elite (Government/Sovereign, Intelligence Funds) is SPECULATING/HOARDING strategic assets before the event occurs.

--- RAW MULTILINGUAL NEWS ---
{news_block}
--- END ---

Task: Return a JSON array containing independent events for the system to generate high-frequency signals (absolutely no further explanation):
[
  {{
      "is_rotation": true,
      "tickers": ["Mã 1", "Mã 2"],
      "asset_rotation_desc": "Description of what assets the Elite (China, Russia, Elites...) are hoarding? What is the conspiracy? + CLEARLY specify the source URL Link."
  }}
]
"""
            llm_eval = router_api_call(prompt, agent_id="A10_CRAWL", brain_mode="CRAWL")
            try:
                import json
                cleaned = str(llm_eval).strip()
                if cleaned.startswith("```json"): cleaned = cleaned[7:]
                if cleaned.startswith("```"): cleaned = cleaned[3:]
                if cleaned.endswith("```"): cleaned = cleaned[:-3]
                
                resp_json = json.loads(cleaned.strip())
                items = resp_json if isinstance(resp_json, list) else [resp_json]
                
                for item in items:
                    if isinstance(item, dict) and item.get("is_rotation"):
                        tkrs = item.get("tickers", ["MACRO"])
                        if not tkrs: tkrs = ["MACRO"]
                        tkr_str = ",".join(tkrs)
                        signals.append(_build_signal(
                            source="strict_news_crawler", asset_class="macro_news", asset_ticker=tkr_str,
                            signal_type="verified_news_shift", raw_value=0.0, baseline_30d=0.0,
                            direction="neutral", elite_intent_raw=item.get("asset_rotation_desc", "Global Asset Rotation detected"), freshness="historical_12m"
                        ))
            except Exception as e_json:
                log.warning(f"[A10] Failed to parse JSON from Multilingual News LLM: {e_json} | Output: {llm_eval[:100]}")
                
    except Exception as e:
        log.warning(f"Error fetching verified news RSS: {e}")
        return _get_cache("verified_news_shifts") or []

    _set_cache("verified_news_shifts", signals)
    log.info(f"Verified Strict Global Elite News: {len(signals)} signals")
    return signals


def fetch_eia_energy() -> list:
    """
    Fetch EIA Open Data API v2: Weekly U.S. Ending Stocks of Crude Oil.
    Series: PET.WCESTUS1.W (Weekly U.S. Ending Stocks of Crude Oil)
    Logic: Inventories falling sharply compared to 4 weeks = Elite hoarding oil / supply tightening.
           Inventories rising sharply = weak demand / risk-off.
    Schedule: every 4h
    """
    if not EIA_API_KEY:
        return []
    dos_mode = _get_dos_mode()
    if dos_mode in ("SURVIVAL", "LOCKDOWN"):
        return []

    cached = _get_cache("eia_energy")
    if cached is not None:
        return cached

    signals = []

    # Weekly U.S. Crude Oil Stocks
    try:
        resp = requests.get(
            "https://api.eia.gov/v2/petroleum/stoc/wstk/data/",
            params={
                "api_key": EIA_API_KEY,
                "frequency": "weekly",
                "data[0]": "value",
                "facets[product][]": "EPC0",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
            "length": 5,
        },
        timeout=20,
    )
        resp.raise_for_status()
        log.info("EIA Energy: Received valid application/json API response.")
        rows = resp.json().get("response", {}).get("data", [])

        if rows and len(rows) >= 2:
            latest_val  = float(rows[0].get("value", 0))
            avg_4w      = sum(float(r.get("value", 0)) for r in rows[:4]) / 4
            pct_change  = ((latest_val - avg_4w) / avg_4w * 100) if avg_4w else 0

            # Decrease > 2% = supply tightening (bullish commodities)
            if pct_change < -2:
                direction, intent = "up", "accumulate"
            elif pct_change > 2:
                direction, intent = "down", "distribute"
            else:
                direction, intent = "neutral", "unknown"

            signals.append(_build_signal(
                source="eia_energy", asset_class="commodity", asset_ticker="CRUDE_OIL",
                signal_type="physical_demand", raw_value=latest_val, baseline_30d=avg_4w,
                direction=direction, elite_intent_raw=intent,
            ))
    except Exception as e:
        log.warning(f"EIA crude oil (JSON Parse) error: {e}")
        return _get_cache("eia_energy") or [_build_error_signal("eia_energy", str(e))]

    _set_cache("eia_energy", signals)
    log.info(f"EIA Energy: {len(signals)} signals")
    return signals


def fetch_fred_elite_macro(cycle: str = "SHORT") -> list:
    """
    Fetch FRED API: Hedged Elite Macro indicators.
    - BAMLH0A0HYM2: ICE BofA High Yield OAS Spread (Junk bond credit risk)
    - DTWEXBGS: Trade Weighted USD Index Broad (DXY proxy)
    - DEXJPUS: USD/JPY Exchange Rate (Carry Trade indicator)
    - GSCPI: Global Supply Chain Pressure Index
    Schedule: every 2h, offset 15 minutes
    """
    if not FRED_API_KEY:
        return []
    dos_mode = _get_dos_mode()
    if dos_mode in ("SURVIVAL", "LOCKDOWN"):
        return []

    cached = _get_cache(f"fred_elite_macro_{cycle}")
    if cached is not None:
        return cached

    signals = []

    SERIES_MAP = {
        "BAMLH0A0HYM2": {
            "ticker": "HY_SPREAD", "asset_class": "bond",
            "signal_type": "hy_spread",
            "threshold_high": 5.0, "threshold_low": 3.0,
            "desc": "HY OAS Spread — Spread > 5 = Elite hedging credit risk"
        },
        "DTWEXBGS": {
            "ticker": "DXY", "asset_class": "fx",
            "signal_type": "usd_index",
            "threshold_high": 115, "threshold_low": 100,
            "desc": "Trade Weighted USD — Strong DXY = global risk-off"
        },
        "DEXJPUS": {
            "ticker": "USD_JPY", "asset_class": "fx",
            "signal_type": "fx_skew",
            "threshold_high": 155, "threshold_low": 140,
            "desc": "USD/JPY — Weak JPY = carry trade running hot"
        },
        "PPIACO": {
            "ticker": "PPI_COMMODITY", "asset_class": "commodity",
            "signal_type": "physical_demand",
            "threshold_high": 220.0, "threshold_low": 170.0,
            "desc": "PPI All Commodities — supply-chain pressure proxy (GSCPI not on FRED)"
        },
    }

    for series_id, cfg in SERIES_MAP.items():
        try:
            limit_obs = 5 if cycle == "SHORT" else 20
            resp = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": FRED_API_KEY,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": limit_obs
                },
                timeout=15
            )
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
            valid_obs = [o for o in obs if o.get("value", ".") != "."]

            if valid_obs:
                latest = float(valid_obs[0]["value"])
                avg = sum(float(o["value"]) for o in valid_obs) / len(valid_obs)

                # Ensure latest is float before comparing
                val = float(latest)
                h_thresh = float(cfg["threshold_high"])
                l_thresh = float(cfg["threshold_low"])

                if val > h_thresh:
                    direction, intent = "down", "hedge"
                elif val < l_thresh:
                    direction, intent = "up", "accumulate"
                else:
                    direction, intent = "neutral", "unknown"

                signals.append(_build_signal(
                    source="fred_elite_macro",
                    asset_class=cfg["asset_class"],
                    asset_ticker=cfg["ticker"],
                    signal_type=cfg["signal_type"],
                    raw_value=latest,
                    baseline_30d=avg,
                    direction=direction,
                    elite_intent_raw=intent,
                ))
        except Exception as e:
            log.warning(f"FRED Elite error: {e}")
            return _get_cache(f"fred_elite_macro_{cycle}") or [_build_error_signal("fred_elite_macro", str(e))]

    _set_cache(f"fred_elite_macro_{cycle}", signals)
    log.info(f"FRED Elite Macro ({cycle}): {len(signals)} signals")
    return signals


# ══════════════════════════════════════════════════════════════════════════════
# BINANCE TIER 2: MOMENTUM / CTA SENSORS (NO API KEY REQUIRED)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_binance_tier2(symbol: str = "BTCUSDT") -> list:
    """
    Tier 2 (CTA / Momentum) Sensors: Open Interest, Funding Rate, Long/Short Ratio.
    Measure the fomo leverage level of the derivatives crowd.
    """
    cache_key = f"binance_tier2_{symbol}"
    signals = []
    try:
        import requests
        # 1. Open Interest (Open contracts volume - gambling intensity)
        r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}", timeout=5)
        if r_oi.status_code == 200:
            oi_val = float(r_oi.json().get("openInterest", 0))
            if oi_val > 0:
                signals.append(_build_signal(
                    source="binance_tier2", asset_class="crypto", asset_ticker=f"TIER2_OI_BTC",
                    signal_type="tier2_open_interest", raw_value=oi_val, baseline_30d=80000,
                    direction="neutral", elite_intent_raw="momentum_build"
                ))

        # 2. Funding Rate (Crowd bias direction)
        r_fr = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}", timeout=5)
        if r_fr.status_code == 200:
            fr_data = r_fr.json()
            if isinstance(fr_data, list): fr_data = fr_data[0]
            fr_val = float(fr_data.get("lastFundingRate", 0))
            fr_dir = "up" if fr_val > 0.0001 else "down"
            # Usually positive Funding drains liquidity -> market makers easily manipulate shorts (distribution trap)
            fr_intent = "distribute_trap" if fr_val > 0.00015 else ("accumulate_trap" if fr_val < -0.0001 else "neutral")
            signals.append(_build_signal(
                source="binance_tier2", asset_class="crypto", asset_ticker=f"TIER2_FUNDING",
                signal_type="tier2_funding_rate", raw_value=fr_val, baseline_30d=0.0001,
                direction=fr_dir, elite_intent_raw=fr_intent
            ))

        # 3. Global Long/Short Ratio
        r_ls = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=1h&limit=1", timeout=5)
        if r_ls.status_code == 200:
            ls_data = r_ls.json()
            if len(ls_data) > 0:
                ls_val = float(ls_data[0].get("longShortRatio", 1.0))
                ls_dir = "up" if ls_val > 1.0 else "down"
                ls_intent = "distribute_trap" if ls_val > 1.5 else ("accumulate_trap" if ls_val < 0.7 else "neutral")
                signals.append(_build_signal(
                    source="binance_tier2", asset_class="crypto", asset_ticker=f"TIER2_LS_RATIO",
                    signal_type="tier2_ls_ratio", raw_value=ls_val, baseline_30d=1.0,
                    direction=ls_dir, elite_intent_raw=ls_intent
                ))

    except Exception as e:
        log.warning(f"Binance Tier 2 fetch error: {e}")
        return _get_cache(cache_key) or [_build_error_signal("binance_tier2", str(e))]

    if signals:
        _set_cache(cache_key, signals)
    log.info(f"Binance Tier 2 ({symbol}): {len(signals)} signals")
    return signals


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR ETF ROTATION TRACKER — Determine which sector money flows into
# ══════════════════════════════════════════════════════════════════════════════

_SECTOR_ETFS = {
    "XLK": "Technology/AI (NVDA, MSFT, AAPL)",
    "XLF": "Financial/Banks (JPM, GS, BAC)",
    "XLE": "Energy/Oil (XOM, CVX, SLB)",
    "XLI": "Industrial/Defense (Boeing, CAT, HON)",
    "ITA": "Defense Pure (LMT, RTX, NOC, GD)",
    "XLV": "Healthcare (JNJ, UNH, PFE)",
    "XLC": "Communication (META, GOOG, NFLX)",
    "ARKK": "Disruptive Innovation/AI Startups",
}


def fetch_sector_etf_rotation() -> str:
    """
    Fetch % change 1D, 5D, 1M for 8 Sector ETFs.
    Cache 1 hour. Returns formatted string for LLM prompt.
    """
    cache_key = "sector_etf_rotation"
    cached = _get_cache(cache_key, ttl_sec=3600)
    if cached is not None:
        return cached

    rows = []
    for ticker, desc in _SECTOR_ETFS.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1mo")
            if hist.empty or len(hist) < 2:
                rows.append(f"| {ticker} ({desc}) | N/A | N/A | N/A | ⚪ NO DATA |")
                continue

            close_now = hist['Close'].iloc[-1]
            pct_1d = ((close_now / hist['Close'].iloc[-2]) - 1) * 100 if len(hist) >= 2 else 0
            pct_5d = ((close_now / hist['Close'].iloc[-min(5, len(hist))]) - 1) * 100
            pct_1m = ((close_now / hist['Close'].iloc[0]) - 1) * 100

            if pct_5d > 3:
                note = "🔥 STRONG INFLOW"
            elif pct_5d > 1:
                note = "🔥 INFLOW"
            elif pct_5d < -3:
                note = "❄️ STRONG OUTFLOW"
            elif pct_5d < -1:
                note = "❄️ OUTFLOW"
            else:
                note = "⚡ AVERAGE"

            short_desc = desc.split('(')[0].strip()
            rows.append(
                f"| {ticker} ({short_desc}) "
                f"| {pct_1d:+.1f}% | {pct_5d:+.1f}% | {pct_1m:+.1f}% | {note} |"
            )
        except Exception as e:
            log.warning(f"Sector ETF {ticker} error: {e}")
            rows.append(f"| {ticker} | ERR | ERR | ERR | ⚪ ERROR |")

    header = (
        "=== SECTOR ROTATION TRACKER (MONEY FLOW BY SECTOR) ===\n"
        "| Sector | 1 Day | 5 Days | 1 Month | Comment |\n"
        "|---|---|---|---|---|"
    )
    result = header + "\n" + "\n".join(rows) + "\n\n"
    result += (
        "WHEN ANALYZING EQUITY INFLOW: MUST specify which sector is attracting money.\n"
        "- Defense + Oil strong → War Economy narrative?\n"
        "- Banks + XLF → Rate cut expectation?\n"
        "- ARKK + XLK → Risk-on Innovation/AI?\n"
        "- XLV strong → Defensive rotation (recession fear)?\n"
    )

    _set_cache(cache_key, result)
    log.info(f"Sector ETF Rotation: {len(rows)} sectors tracked")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

ALL_SOURCES = ["sec_form4", "cftc_cot", "dune_analytics", "clankapp",
               "eia_energy", "fred_elite_macro", "yfinance_elite", "binance_tier2"]

def calculate_confidence(signals: list) -> dict:
    """
    Calculate confidence based on:
    1. Coverage penalty (how many sources have data)
    2. Alignment bonus (how many signals align)
    3. Weighted sum (uses weights from memory/weights.json)
    """
    weights = _load_weights()
    active_sources = list(set(s["source"] for s in signals))
    missing = [s for s in ALL_SOURCES if s not in active_sources]

    COVERAGE_PENALTY = {0: 1.00, 1: 0.85, 2: 0.65, 3: 0.40, 4: 0.25, 5: 0.15}
    coverage = COVERAGE_PENALTY.get(len(missing), 0.10)

    if not signals:
        return {
            "score": 0.0, "label": "VERY_LOW",
            "coverage_pct": 0.0, "alignment_score": 0.0,
            "missing_sources": ALL_SOURCES, "warning": "No signals",
        }

    # Weighted score
    total_weight = sum(weights.get(s["source"], 0.5) for s in signals)
    if total_weight == 0:
        weighted_sum = 0.5
    else:
        weighted_sum = sum(
            weights.get(s["source"], 0.5) * (1.0 if s["direction"] != "neutral" else 0.5)
            for s in signals
        ) / total_weight

    # Alignment bonus
    directions = [s["direction"] for s in signals if s["direction"] != "neutral"]
    if directions:
        dominant    = max(set(directions), key=directions.count)
        alignment   = directions.count(dominant) / len(directions)
        align_bonus = 1 + (alignment - 0.5) * 0.4
    else:
        alignment   = 0.5
        align_bonus = 1.0

    score = min(weighted_sum * coverage * align_bonus, 1.0)
    score = round(score, 3)

    if score >= 0.80:   label = "HIGH"
    elif score >= 0.60: label = "MEDIUM"
    elif score >= 0.40: label = "LOW"
    else:               label = "VERY_LOW"

    return {
        "score":          score,
        "label":          label,
        "coverage_pct":   round(coverage * 100, 1),
        "alignment_score": round(alignment, 3),
        "missing_sources": missing,
        "warning":        f"Missing: {missing}" if missing else None,
    }


def _calc_alert_level(signals: list, confidence: dict) -> str:
    if confidence["label"] == "HIGH" and len(signals) >= 5:
        return "CRITICAL"
    elif confidence["label"] in ("HIGH", "MEDIUM") and len(signals) >= 3:
        return "HIGH"
    elif signals:
        return "WATCH"
    return "NONE"


# ══════════════════════════════════════════════════════════════════════════════
# TIMELINE SENSORS (1M, 6M, 12M)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_real_timeline_macro_1_to_12() -> str:
    """
    Fetch historical growth data 1M, 6M, 12M for key Macro assets.
    Include Elite shadow market assets (Commodities, Carbon Credits, CDS Proxy).
    Assets: SPY, QQQ, DIA, TLT, GLD, USO, BTC-USD, DBC, DBA, CPER, KRBN, LQD, HYG.
    """
    tickers = ["SPY", "QQQ", "DIA", "TLT", "GLD", "USO", "BTC-USD", "DBC", "DBA", "CPER", "KRBN", "LQD", "HYG"]
    timeline_str = "=== SHADOW ORBIT CASH FLOW HISTORY ===\n"
    timeline_str += "Asset | 1 Month | 6 Months | 12 Months |\n"
    timeline_str += "---|---|---|---|\n"
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        
        # Use yfinance download once to be faster than calling individually
        today = datetime.now()
        start_date = today - timedelta(days=370)
        data = yf.download(tickers, start=start_date.strftime("%Y-%m-%d"), interval="1d", group_by="ticker", auto_adjust=True, progress=False)
        
        def get_price_ago(h, days_ago):
            target_date = h.index[-1] - timedelta(days=days_ago)
            valid_idx = h.index[h.index <= target_date]
            if len(valid_idx) == 0: return float(h.iloc[0])
            return float(h[valid_idx[-1]])

        for t in tickers:
            try:
                hist = data[t]['Close'].dropna() if len(tickers) > 1 else data['Close'].dropna()
                if len(hist) < 20: 
                    timeline_str += f"{t} | N/A | N/A | N/A |\n"
                    continue
                
                curr_price = float(hist.iloc[-1])
                
                price_1m = get_price_ago(hist, 30)
                price_6m = get_price_ago(hist, 180)
                price_12m = get_price_ago(hist, 360)
                
                pct_1m = ((curr_price - price_1m) / price_1m) * 100
                pct_6m = ((curr_price - price_6m) / price_6m) * 100
                pct_12m = ((curr_price - price_12m) / price_12m) * 100
                
                timeline_str += f"{t} | {pct_1m:+.1f}% | {pct_6m:+.1f}% | {pct_12m:+.1f}% |\n"
            except Exception:
                timeline_str += f"{t} | Data Error | Data Error | Data Error |\n"
    except Exception as e:
        timeline_str += f"Data pull error: {e}"
        
    return timeline_str

# ══════════════════════════════════════════════════════════════════════════════
# STRUCTURED SIGNAL DIGEST — HingeEBM Phase 3
# ══════════════════════════════════════════════════════════════════════════════

def _build_signal_digest(signals: list) -> str:
    """Build structured digest of signals grouped by elite_intent_raw.
    Replaces raw JSON dump with human-readable summary for LLM prompt."""
    if not signals:
        return "=== MACRO SIGNAL DIGEST (0 signals) ===\nNo signals."

    n = len(signals)
    conf_vals = [s.get('confidence', 0) for s in signals if isinstance(s.get('confidence'), (int, float))]
    avg_conf = sum(conf_vals) / len(conf_vals) if conf_vals else 0.0

    acc_signals = [s for s in signals if s.get('elite_intent_raw') == 'accumulate']
    dis_signals = [s for s in signals if s.get('elite_intent_raw') == 'distribute']
    hedge_signals = [s for s in signals if s.get('elite_intent_raw') == 'hedge']
    neutral_signals = [s for s in signals if s.get('elite_intent_raw') not in ('accumulate', 'distribute', 'hedge')]

    def _top3_summary(sigs):
        """Return top 3 signals summary sorted by abs(deviation_score)."""
        ranked = sorted(sigs, key=lambda s: abs(s.get('deviation_score', 0)), reverse=True)[:3]
        parts = []
        for s in ranked:
            ticker = s.get('asset_ticker', '?')
            src = s.get('source', '?')
            dev = s.get('deviation_score', 0)
            parts.append(f"{ticker}({src}|dev={dev:.2f})")
        return ", ".join(parts) if parts else "N/A"

    lines = [
        f"=== MACRO SIGNAL DIGEST ({n} signals, confidence={avg_conf:.2f}) ===",
        f"📊 ACCUMULATE ({len(acc_signals)}): {_top3_summary(acc_signals)}",
        f"📊 DISTRIBUTE ({len(dis_signals)}): {_top3_summary(dis_signals)}",
        f"📊 HEDGE ({len(hedge_signals)}): {_top3_summary(hedge_signals)}",
        f"📊 NEUTRAL ({len(neutral_signals)}): {len(neutral_signals)} signals",
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLISH TO REDIS
# ══════════════════════════════════════════════════════════════════════════════

def _phan_tich_emf_3_phase_llm(signals: list, cycle: str, force_algo: bool = False) -> str:
    global last_algo_time
    is_main_cycle = False
    if (time.time() - last_algo_time >= ALGO_CYCLE_INTERVAL_SEC) or force_algo:
        is_main_cycle = True
        last_algo_time = time.time()
        
    if not is_main_cycle:
        last_narrative = matrix.get("A10", "latest_macro_narrative") or {}
        if isinstance(last_narrative, str):
            try:
                last_narrative = json.loads(last_narrative)
            except Exception:
                last_narrative = {}
        
        if "narrative_lens" in last_narrative:
            narr_lens = last_narrative.get("narrative_lens", {})
            compat_obj = {
                "money_flow_orbit": narr_lens.get("summary", ""),
                "theoretical_interpretation": narr_lens.get("a10_story", ""),
                "manipulation_footprint": narr_lens.get("elite_action", ""),
                "untracked_assets": []
            }
            log.info(f"[{ALGO_CYCLE_INTERVAL_SEC}s THROTTLE] Reusing old A10_FINAL (Hinge).")
            return json.dumps(compat_obj, ensure_ascii=False)
        else:
            trinity_part = last_narrative.get("trinity", last_narrative)
            if trinity_part:
                log.info(f"[{ALGO_CYCLE_INTERVAL_SEC}s THROTTLE] Reusing old A10_FINAL (Trinity).")
                if isinstance(trinity_part, str):
                    return trinity_part
                return json.dumps(trinity_part, ensure_ascii=False)
            else:
                log.info(f"[{ALGO_CYCLE_INTERVAL_SEC}s THROTTLE] Skipping A10_FINAL, returning Neutral.")
                return json.dumps({
                    "money_flow_orbit": "Maintained previous momentum from the prior cash flow orbit as no new data is available.",
                    "theoretical_interpretation": "No unusual macro fluctuations. Continue observing.",
                    "untracked_assets": []
                }, ensure_ascii=False)
    """
    Activate 3-Phase Analysis for EMF:
    Phase 1: Filter noise -> Phase 2: Filter surface -> Phase 3: Filter deep -> Phase 4: Post-audit compilation (JSON)
    """
    valid_signals = [s for s in signals if s.get("elite_intent_raw") != "DATA_RECENTLY" and s.get("signal_type") != "API_ERROR"]

    if not valid_signals:
        # A10 NETWORK CONGESTION: Restore using Session Logger!
        try:
            from agent_session_logger import get_recent_sessions
            recent = get_recent_sessions("A10", n=1)
            if recent:
                recent_summary = recent[0].get("summary", "No summary")
                return json.dumps({
                    "money_flow_orbit": "DATA_RECENTLY (A10 network congestion - 10% Confidence deducted)",
                    "theoretical_interpretation": recent_summary,
                    "untracked_assets": []
                }, ensure_ascii=False)
        except Exception as e:
            log.warning(f"[A10] DATA RECENTLY recovery error: {e}")
        
        return json.dumps({
            "money_flow_orbit": "No Macro EMF data.",
            "theoretical_interpretation": "Cannot analyze when lacking baseline data & empty Logger.",
            "untracked_assets": []
        }, ensure_ascii=False)
        
    try:
        from datetime import datetime as _dt
        _rl_16d_key = f"quota:16d:A10_FINAL:{_dt.now().strftime('%Y%m%d_%H')}"
        _16d_used = int(matrix.get("SYSTEM", _rl_16d_key) or 0)
        is_algo_plus = is_main_cycle and (_16d_used < 1)
        
        if is_algo_plus:
            max_len_data = 800000
            max_len_timeline = 50000
            max_len_session = 10
        else:
            max_len_data = 150000    # Prioritize keeping new data
            max_len_timeline = 2000  # Truncate timeline
            max_len_session = 2      # Truncate agent session logger

        # [GRAND SURGERY] Unleash Max Think! No more cutting data into 3000-character blocks.
        raw_text_str = json.dumps(signals, ensure_ascii=False)[:max_len_data]
        raw_text = a09_sanitize_text(raw_text_str, max_len=max_len_data)
        # [HingeEBM Phase 3] Structured signal digest — prepend before raw data
        signal_digest = _build_signal_digest(signals)
        drift_text = _get_drift_context("A10", "FULL")
        
        # ── SESSION MEMORY: GEO delta + alert history + LỊCH SỬ PHIÊN ──
        try:
            from tools.agent_session_logger import get_recent_sessions
            recent = get_recent_sessions("A10", n=max_len_session)
            hist_str = "\n".join([f"- [{r.get('ts','')[:16]}] {r.get('summary','')}" for r in recent]) if recent else "No session history yet."
            
            geo_delta_val = matrix.get("A10", "geo_delta") or "0"
            geo_prev_val = matrix.get("A10", "geo_prev") or "N/A"
            geo_alert_latest = ""
            try:
                alert_raw = matrix.stream_latest("A10", "geo_alerts")
                if alert_raw and isinstance(alert_raw, dict):
                    geo_alert_latest = f"⚠️ GEO Alert: {alert_raw.get('alert', alert_raw.get('message', ''))}"
            except Exception:
                pass
            session_memory = f"""
=== PAST HISTORY (SESSION MEMORY OF SHADOW FLOW ANALYSIS) ===
- Previous GEO Score: {geo_prev_val} | Delta: {geo_delta_val}
{geo_alert_latest}

=== PAST HISTORY ({max_len_session} RECENT STORIES TOLD) ===
{hist_str}
"""
        except Exception:
            session_memory = ""
            
        # ── GROUND TRUTH: Đọc nhận định cũ từ Snapshot Harvester ──
        try:
            from tools.agent_session_logger import get_recent_verdicts
            _verdicts = get_recent_verdicts("A10", n=6)
            verdicts_str = json.dumps(_verdicts, ensure_ascii=False)[:12000]
        except Exception:
            verdicts_str = "No previous verdicts."

        # ── Sector Rotation & Equity Flow ──
        try:
            sector_rotation_str = fetch_sector_etf_rotation()
            
            # Read A102 from Redis
            eq_flow = matrix.get("A10", "equity_flow")
            if eq_flow:
                if isinstance(eq_flow, str):
                    eq_flow_obj = json.loads(eq_flow)
                else:
                    eq_flow_obj = eq_flow
                
                # Render LLM str
                import a102_equity_flow
                a102_str = a102_equity_flow.format_for_llm_prompt(eq_flow_obj)
                sector_rotation_str += "\n\n" + a102_str
        except Exception as e_eq:
            sector_rotation_str = f"Could not fetch Sector ETF / Equity Flow data: {e_eq}"
            
        # ── TIMELINE MEMORY: Dữ liệu Lịch sử 1-12 tháng ──
        try:
            timeline_memory = fetch_real_timeline_macro_1_to_12()
            if not is_algo_plus:
                timeline_memory = timeline_memory[:max_len_timeline] + "... (truncated due to ALGO_FREE)"
        except Exception as e:
            timeline_memory = f"=== SHADOW ORBIT CASH FLOW HISTORY ===\nError: {e}\n"
            
        # ── MACRO SENSORS: 13 Cảm Biến Siêu Việt ──
        try:
            macro_sensors_raw = matrix.get("MACRO", "sensors")
            if macro_sensors_raw:
                if isinstance(macro_sensors_raw, str):
                    macro_sensors_raw = json.loads(macro_sensors_raw)
                macro_sensor_str = json.dumps(macro_sensors_raw, ensure_ascii=False, indent=2)
            else:
                macro_sensor_str = "Radar system has not updated all 13 macro sensors (GEO, OFI, GLS...)."
        except Exception as e:
            macro_sensor_str = f"MACRO:sensors retrieval error: {e}"
        
        # 🏛️ Diên Hồng Council Minutes → inject into prompt
        def _get_council_minutes_a10():
            try:
                from dien_hong_council import load_council_history
                return load_council_history("A10")
            except Exception:
                return ""

        try:
            with open("/home/newuser/Zero_Cutloss_Empire/agentic/knowledge/a10_macro_flow_anchor.md", "r", encoding="utf-8") as f:
                macro_flow_anchor = f.read()
        except Exception:
            macro_flow_anchor = ""

        # Phase 4 (Final): Call Qwen 3.5 Plus directly, bypass free tiers
        final_prompt = f"""[MACRO MAPPING DICTIONARY & ALLIED MATRIX ARCHITECTURE (ZERO-CUTLOSS EMPIRE)]
- A01 (Market Scanner): Scans market overview, records Order Book, whale buy/sell orders.
- A02 (News Scraper & Onchain): Updates raw news and On-chain flows (Whale alerts).
- A03 (Social Crawler / Market Sentiment): Dissects Vulture Sentiment, surface media. Reads Fear & Greed.
- A04 (Wyckoff/Elliott Analyzer): Analyzes Chart Structure (Phase A-E, Spring, Squeeze). Technical piece.
- A05 (The Judge / RAG Validator): Supreme Judge, makes Trade Decisions/Feasibility.
- A06 (Execution): Automated execution bot.
- A07 (Web Injector): Injects data into Frontend GUI.
- A08 (Trend Forecast): Forecasts time series trend based on statistical models.
- A09 (Risk Manager): Monitors PnL, risk structure deviation.
- A10 (Macro Flow / Signal Collector): Macro Engineer, Shadow Flow Sensors (Onchain, FED, Geo, Interest Rate Structure). Strategic assistant.
- A11 (Intent Analyzer): Director of Criminal Staff, dissects background manipulation plots from Elite. Double agent, Max Think reasoning.
- A12 (Narrative & State Engine): Narrative Governor, maintains cycle inheritance. Distinguishes Manufactured news.
- Core Algorithms/Metrics: PDI (Layout Deviation), CFV (Cash-Flow Velocity), SDD (Supply-Demand Deviation), GLS (Global Liquidity Squeeze), CRA (Credit Risk Appetite), OFI (Order Flow Imbalance), REP (Real Economy Proxy).
- Elite / Smart Money / Composite Man: Forces of professional financial market manipulation, creating the game. The house.

You are the Macro Expert & Core Cash Flow Analyst (A10 Macro Flow).
Equipped with 13 advanced sensors: GEO, OFI, GLS, REP, SHD, CRA, YIELD_CURVE, MACRO_INVENTORY, CFV, SDD, IRD, MRD, BCDT.
Along with A102 US Equity Flow Scanner to illuminate sector divergence and Factor Rotation.

<flow_context>
=== MACRO FLOW ANCHOR (MANDATORY MACRO ORIENTATION) ===
{macro_flow_anchor}
======================================================
=== DATA REPORT BY TIME LAYER (16D COORDINATE SYSTEM) ===
{drift_text}
========================================================================
=== PAST HISTORY (SESSION MEMORY OF SHADOW FLOW ANALYSIS) ===
{session_memory}
{timeline_memory}
=== YOUR RECENT VERDICTS (GROUND TRUTH — LAST 6 SESSIONS) ===
{verdicts_str}
[DIEN HONG COUNCIL CONTEXT - CONCENTRATED WISDOM FROM LAST SESSION]
{_get_council_minutes_a10()}
</flow_context>

<current_context>
[ALGO_CORE — STRUCTURED SIGNAL SUMMARY]
{signal_digest}

[RAW_SIGNALS — REFERENCE DATA]
From the following manipulation reports: {raw_text}
=== LIVE RADAR SENSORS (13 MACRO SENSORS MAP) ===
{macro_sensor_str}
=== CURRENT FACTOR ROTATION & SECTOR ALLOCATION ===
{sector_rotation_str}
</current_context>

<forecast_context>
=== SHORT-TERM FORECAST ORIENTATION (FORECAST 1-48H) ===
- Task: Sketch the short-term trajectory, macro inflection points, and Elite capital rotation in the next 1-48h.
</forecast_context>

THINKING DIRECTIVE:
Before outputting conclusions, you MUST open a <think> tag. In this tag, perform reasoning through these steps:
1. Assess whether the current cycle is early, middle, or late Macro cycle based on <flow_context> and compare with the latest reality in <current_context>.
2. From raw data (Netflow, Whale, etc.), sketch the "Shadow Profile" of the Elite (are they distributing in secret or pumping gas?).
3. IDENTIFY ACCUMULATION/DISTRIBUTION TIMELINE: When did the Elite start ACCUMULATING this asset (1, 6, or 12 months ago)? Are they currently DISTRIBUTING or continuing to ACCUMULATE?
4. FIND FOOTPRINTS: Identify the Elite's manipulation "manner" and "footprint" left on the market. Pay special attention to "key footprints": hidden stablecoin inflow + DeFi withdrawals.
5. Compare previous verdicts (Ground Truth) vs Current to recognize your own mistakes.
6. Project exact trend and volatility in the next 1-48h.
After completing <think>, you may output the result.

Strictly adhere to JSON rules. Return ONLY JSON, DO NOT ADD ANY TEXT OUTSIDE:
{{
  "dien_hong_analysis": "<Analyze the meeting minutes of the Dien Hong council and cross-reference>",
  "money_flow_orbit": "<Definitive answer: Specific timeline (1-12 months) Elite started collecting/distributing assets? What silent flow goes contrary to retail? Draw a story of elite moving before event X.>",
  "theoretical_interpretation": "<Interpret whether Elite is pumping gas or dumping goods through credit and on-chain systems?>",
  "manipulation_footprint": "<Clearly specify the 'manner' and 'footprint' of Elite manipulation (e.g. using media to blind, suppressing prices to accumulate, wash trading) to store in memory!>",
  "sector_analysis": "<When CFV shows sector rotation: Which sector has the strongest inflow? AI/Defense/Oil/Bank? Strategic meaning?>",
  "untracked_assets": ["Asset type 1", "Financial event 2"],
  "forecast_48h": "<Detailed forecast in the next 1-48h of how the market will look based on Flow vs Current analysis>"
}}"""
        aid_target = "A10_FINAL" if is_main_cycle else "A10_LITE"
        final_text = brain.think_as(aid_target, final_prompt, est_tokens=600)
        try:
            from tools.agent_session_logger import log_agent_snapshot
            log_agent_snapshot("A10", final_prompt, final_text)
        except Exception:
            pass

        if not final_text or "ERROR" in final_text:
            return json.dumps({
                "money_flow_orbit": "LLM A10 Analysis error.",
                "theoretical_interpretation": "Cannot analyze shadow flow due to API error.",
                "untracked_assets": []
            }, ensure_ascii=False)
            
        start = final_text.find("{")
        end   = final_text.rfind("}") + 1
        if start != -1 and end != 0:
            result_json = final_text[start:end]
            
            try:
                matrix.set("A10", "latest_macro_narrative", result_json, ttl=ALGO_CYCLE_INTERVAL_SEC*3)
            except Exception as e_redis:
                log.warning(f"[A10] Failed to cache latest narrative: {e_redis}")
            return result_json
        return final_text
    except Exception as e:
        log.error(f"Error 3-Phase EMF: {e}")
        return json.dumps({
            "money_flow_orbit": f"Error: {str(e)[:50]}",
            "theoretical_interpretation": "A10 system crashed.",
            "untracked_assets": []
        }, ensure_ascii=False)

def publish_to_redis(signals: list, cycle: str = "SHORT", force_algo: bool = False):
    """
    Publish to 2 channels:
    - emf:signals:raw   → Agent 11 consume (stream)
    - emf:signals:scored → A04 + A07 read (stream)
    """
    if not signals:
        return


    confidence = calculate_confidence(signals)
    top_signals = sorted(signals, key=lambda s: abs(s["deviation_score"]), reverse=True)[:5]

    # Stream 1: raw signals for A11 (A09 can Read from this stream to Audit)
    matrix.xadd("EMF", "signals:raw", {
        "source":    "A10",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signals":   json.dumps(signals),
        "count":     len(signals),
    }, maxlen=10000)

    # Run 3-phase algorithm
    macro_narrative = _phan_tich_emf_3_phase_llm(signals, cycle, force_algo)

    # ── PHASE 3 GRAND SURGERY: HingeEBM Packet (A10_SHADOW_FLOW_PACKET) ────────────
    narr_obj = {}
    try:
        if isinstance(macro_narrative, str) and macro_narrative.strip().startswith("{"):
            narr_obj = json.loads(macro_narrative)
    except (json.JSONDecodeError, ValueError):
        pass

    is_fallback = ("Error" in narr_obj.get("money_flow_orbit", "") or 
                   "DATA_RECENTLY" in narr_obj.get("money_flow_orbit", "") or
                   ("ERROR" in macro_narrative.upper() if isinstance(macro_narrative, str) else False))

    alert_lvl = _calc_alert_level(signals, confidence)
    alert_lvl_int = 0
    if alert_lvl == "WATCH": alert_lvl_int = 1
    elif alert_lvl == "HIGH": alert_lvl_int = 3
    elif alert_lvl == "CRITICAL": alert_lvl_int = 5
    
    sm_flow = sum(float(s.get("raw_value", 0)) for s in signals if "inflow" in str(s.get("signal_type", "")).lower() or "whale" in str(s.get("signal_type", "")).lower())

    # ── [HingeEBM FIX 1] OFI: Compute from accumulate/distribute signal balance ──
    _acc_signals = [s for s in signals if s.get('elite_intent_raw') == 'accumulate']
    _dis_signals = [s for s in signals if s.get('elite_intent_raw') == 'distribute']
    _ofi_computed = round((len(_acc_signals) - len(_dis_signals)) / max(len(signals), 1) * 100, 2)

    # ── [HingeEBM FIX 2] wyckoff_phase: Read from A04 Redis packet ──
    try:
        _a04_raw = matrix.get("A04", "latest")
        if _a04_raw:
            _a04_data = json.loads(_a04_raw) if isinstance(_a04_raw, str) else _a04_raw
            _wyckoff = _a04_data.get("algo_core", {}).get("wyckoff_phase", "SIDEWAYS_DRIFT")
        else:
            _wyckoff = "SIDEWAYS_DRIFT"
    except Exception:
        _wyckoff = "SIDEWAYS_DRIFT"

    # ── [HingeEBM FIX 3] cftc_concentration: Extract from CFTC signals ──
    _cftc_val = None
    for s in signals:
        if 'cftc' in s.get('source', '').lower():
            _cftc_val = s.get('raw_value', s.get('confidence', 0.5))
            break

    algo_core = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "symbol": "BTC",
        "smart_money_flow": float(sm_flow),
        "ofi": _ofi_computed,
        "kar": float(confidence.get("score", 0.5)),
        "wyckoff_phase": _wyckoff,
        "alert_level": alert_lvl_int,
        "cftc_concentration": _cftc_val,
        "expert_metrics": {
            "is_fallback": is_fallback,
            "cycle_id": cycle,
            "signals_count": len(signals),
            "missing_sources": confidence.get("missing_sources", [])
        }
    }
    
    narrative_lens = {
        "summary": str(narr_obj.get("money_flow_orbit", f"EMF:{confidence['label']} | {len(signals)} signals"))[:200],
        "elite_action": str(narr_obj.get("manipulation_footprint", "Unknown"))[:100],
        "a10_story": str(narr_obj.get("theoretical_interpretation", "Monitoring macro money flow."))[:1500]
    }
    
    hinge_packet = {
        "algo_core": algo_core,
        "narrative_lens": narrative_lens
    }

    # Stream 2: scored summary for A04/A07 (wraps HingeEBM Packet)
    active_tickers = list(set(s["asset_ticker"] for s in signals))
    matrix.xadd("EMF", "signals:scored", {
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "payload":         json.dumps(hinge_packet, ensure_ascii=False),
        "signals_count":   len(signals),
        "confidence":      json.dumps(confidence),
        "top_signals":     json.dumps(top_signals[:5]),
        "assets_active":   json.dumps(active_tickers),
        "alert_level":     alert_lvl,
        "macro_narrative": json.dumps(macro_narrative, ensure_ascii=False),
        "cycle":           cycle,
    }, maxlen=5000)
    
    # ── Write session log to give A10 history of previous stories ──
    try:
        from tools.agent_session_logger import log_session
        summary_log = narrative_lens["summary"][:480] + "..." if len(narrative_lens["summary"]) > 480 else narrative_lens["summary"]
        log_session("A10", "emf:signals:scored", summary=summary_log, signals_count=len(signals), confidence=float(confidence["score"]))
    except Exception as e:
        log.warning(f"[A10] Session logging error: {e}")
    
    # Save Packet into KV (A05/A12 read directly)
    try:
        matrix.set("A10", "latest_macro_narrative", json.dumps(hinge_packet, ensure_ascii=False), ttl=ALGO_CYCLE_INTERVAL_SEC*3)
    except Exception as e_redis:
        log.warning(f"[A10] Failed to cache latest narrative: {e_redis}")

    # --- xadd SYSTEM telegram:queue Stream ---
    is_algo_plus = False
    try:
        is_algo_plus = (matrix.client.get("zcl:system:last_algo_mode:A10_FINAL") == b"algo_plus" or 
                        matrix.client.get("zcl:system:last_algo_mode:A10_FINAL") == "algo_plus")
    except Exception as e_chk:
        log.warning(f"[A10] Failed to check last_algo_mode: {e_chk}")
        
    if is_algo_plus:
        try:
            report_text = (
                f"💼 *Money Flow Orbit*: {narrative_lens['summary']}\n"
                f"🎯 *Elite Footprint*: {narrative_lens['elite_action']}\n\n"
                f"🧠 *Macro Interpretation*:\n|_{narrative_lens['a10_story']}_|"
            )
            matrix.xadd("SYSTEM", "telegram:queue", {
                "payload": json.dumps({"type": "A10_TO_A06_REPORT", "cycle": int(time.time()), "report_text": report_text}, ensure_ascii=False)
            }, maxlen=1000)
        except Exception as e_tele:
            log.error(f"[A10] Error pushing to Telegram queue: {e_tele}")
    else:
        log.info("[A10] Skip sending Telegram since not running in ALGO_PLUS mode")

    # ── PHASE 8 GRAND SURGERY: GEO Velocity Delta (§3.3 CONTEXT.md) ──────
    # Calculate GEO delta between sessions. Alert when |delta| > 1.0
    try:
        # Get current GEO score from macro_radar sensors
        macro_sensors = matrix.get("MACRO", "sensors")
        if isinstance(macro_sensors, str):
            macro_sensors = json.loads(macro_sensors)
        if isinstance(macro_sensors, dict):
            sensors_data = macro_sensors.get("sensors", macro_sensors)
            geo_data = sensors_data.get("GEO", {})
            curr_geo = float(geo_data.get("geo_score", 0)) if isinstance(geo_data, dict) else 0
            
            if curr_geo > 0:
                prev_geo_raw = matrix.get("A10", "geo_prev")
                prev_geo = float(prev_geo_raw) if prev_geo_raw else 0
                delta_geo = curr_geo - prev_geo
                
                matrix.set("A10", "geo_prev", str(curr_geo), ttl=86400)
                matrix.set("A10", "geo_delta", str(round(delta_geo, 2)), ttl=86400)
                
                if abs(delta_geo) > 1.0 and prev_geo > 0:
                    alert_msg = f"🔴 GEO_SPIKE: {prev_geo:.1f}→{curr_geo:.1f} (Δ{delta_geo:+.1f})"
                    log.warning(f"[A10] {alert_msg}")
                    matrix.xadd("EMF", "geo_alerts", {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "alert": alert_msg,
                        "prev": str(prev_geo),
                        "curr": str(curr_geo),
                        "delta": str(round(delta_geo, 2)),
                    }, maxlen=50)
                elif prev_geo > 0:
                    log.info(f"[A10] GEO Delta: {prev_geo:.1f}→{curr_geo:.1f} (Δ{delta_geo:+.1f}) — Normal")
    except Exception as e_geo:
        log.debug(f"[A10] GEO Delta calc error (non-critical): {e_geo}")

    # ── SESSION LOG: Write condensed session for long-term drift analysis ──
    try:
        # Integrate actual data for 16D EMF Metrics instead of returning 0
        # GLS (Liquidity Squeeze) = DXY (Strong USD Index drains liquidity)
        gls_val = next((s.get("deviation_score", 0) for s in signals if s.get("asset_ticker") == "DXY"), 0.0)
        
        # CRA (Credit Risk Appetite) = Inverse of HY_SPREAD (Wide spread -> Credit risk -> Appetite decreases)
        hy_dev = next((s.get("deviation_score", 0) for s in signals if s.get("asset_ticker") == "HY_SPREAD"), 0.0)
        cra_val = -hy_dev if hy_dev else 0.0
        
        # SHD = VIX level (raw_value / 100) -> VIX 30 = 0.3
        vix_raw = next((s.get("raw_value", 0) for s in signals if s.get("asset_ticker") == "VIX"), 0.0)
        shd_val = vix_raw / 100.0 if vix_raw else 0.0
        
        # REP (Real Economy) = COPPER future deviation
        rep_val = next((s.get("deviation_score", 0) for s in signals if s.get("asset_ticker") == "COPPER"), 0.0)
        
        tensor_16d = {
            "GLS": gls_val,
            "CRA": cra_val,
            "ETF": next((s.get("raw_value", 0) for s in signals if s.get("signal_type", "") == "exchange_inflow" and s.get("asset_ticker") == "BTC"), 0.0),
            "MMX": next((s.get("raw_value", 0) for s in signals if s.get("signal_type", "") == "whale_alert"), 0.0)
        }
        
        # Add MACRO:sensors data into A10 tensor for clear visibility to LLM
        try:
            macro_sensors_raw = matrix.get("MACRO", "sensors")
            if isinstance(macro_sensors_raw, str):
                macro_sensors_raw = json.loads(macro_sensors_raw)
            if isinstance(macro_sensors_raw, dict):
                mac_dict = macro_sensors_raw.get("sensors", macro_sensors_raw)
                for k, v in mac_dict.items():
                    if isinstance(v, dict):
                        val = v.get("geo_score", v.get("score", v.get("raw_value", 0)))
                        tensor_16d[k] = val
        except:
            pass
            
        # Summary for A05
        narr_obj = json.loads(macro_narrative) if isinstance(macro_narrative, str) and macro_narrative.startswith("{") else {}
        expert_comment = narr_obj.get("expert_comment", "N/A")
        summary = f"EMF:{confidence['label']} | Count:{len(signals)} | {expert_comment}"
        
        # Ghi câu chuyện Dòng chảy ngầm + Timeline + Dấu chân thao túng!
        a10_story = f"Orbit/Timeline: {narr_obj.get('money_flow_orbit', 'N/A')} | Elite Footprint: {narr_obj.get('manipulation_footprint', 'N/A')} | Interpretation: {narr_obj.get('theoretical_interpretation', 'N/A')}"
        
        from tools.agent_session_logger import log_session
        log_session(
            agent_id="A10", redis_key="zcl:emf:latest",
            summary=summary, signals_count=len(signals),
            confidence=float(confidence["score"]),
            expert_metrics=tensor_16d,
            extra={"cycle": cycle, "alert_level": _calc_alert_level(signals, confidence), "a10_story": a10_story}
        )
    except Exception as e:
        log.warning(f"[A10] Session logging skipped: {e}")
    log.info(f"Published {len(signals)} signals | confidence={confidence['score']} ({confidence['label']})")


def publish_heartbeat_a10():
    """Publish heartbeat every 60s — Agent 11 checks if alive.
    Kèm last_data_ts + last_publish_ts to let A11 know data freshness."""
    # Count signals in the last 1h
    try:
        recent = matrix.xrevrange("EMF", "signals:raw", count=100)
        cutoff = time.time() - 3600
        count_1h = sum(1 for msg_id, _ in recent
                       if float(msg_id.split("-")[0]) / 1000 > cutoff)
    except Exception:
        count_1h = 0

    # Get timestamp of the last data publish
    last_data_ts = matrix.get("SYSTEM", "a10:last_realtime_ts") or "0"
    
    matrix.set("A10", "heartbeat", {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ALIVE",
        "signals_last_hour": count_1h,
        "last_data_ts": str(last_data_ts),
    }, ttl=300)  # TTL 5 minutes = 5x check interval (60s/time)


def publish_degraded(reason: str):
    """Publish when paid sources are lost — A11 adjusts confidence."""
    matrix.publish("agent10:degraded", {
        "ts": int(time.time()),
        "reason": reason,
        "active_sources": ["fred", "sec_form4", "cftc_cot"],
    })


# ══════════════════════════════════════════════════════════════════════════════
# LLM NORMALIZATION — optional
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def _log_signals(signals: list, source: str):
    """Log raw signals to emf_lab/logs/signals/YYYY-MM-DD/raw_{source}.json"""
    try:
        today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_dir = LOG_DIR / today
        day_dir.mkdir(exist_ok=True, parents=True)
        path    = day_dir / f"raw_{source}_{datetime.now(timezone.utc).strftime('%H')}.json"
        with open(path, "w") as f:
            json.dump({"ts": datetime.now(timezone.utc).isoformat(), "signals": signals},
                      f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"Could not log signal {source}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER — called by APScheduler according to orchestrator.yaml
# ══════════════════════════════════════════════════════════════════════════════


def _publish_all_from_matrix(force_algo: bool = False):
    data_map = {}
    missing = []
    # 4 mandatory algorithm components
    for src in ["sec_form4", "cftc_cot", "onchain", "elite_macro"]:
        val = matrix.hget("A10", "cache", src)
        if val is not None:
            if isinstance(val, (str, bytes)):
                try:
                    val = json.loads(val)
                except Exception:
                    pass
            data_map[src] = val if isinstance(val, list) else [val]
        else:
            missing.append(src)

    if missing:
        log.warning(f"🚨 [A10] LLM CALL REJECTED: Missing data from algorithms: {', '.join(missing)}")
        return

    all_sig = []
    for sigs in data_map.values():
        if isinstance(sigs, list):
            all_sig.extend(sigs)
            
    if all_sig:
        log.info(f"[A10] All 4 algorithmic streams present. Total {len(all_sig)} signals. Sending to QWEN 3.5 PLUS for analysis.")
        publish_to_redis(all_sig, cycle="SHORT", force_algo=force_algo)

def run_fetch_sec(publish: bool = True):
    dos_mode = _get_dos_mode()
    if dos_mode == "LOCKDOWN": return
    signals = fetch_sec_form4()
    if signals is not None:
        _log_signals(signals, "sec_form4")
        matrix.hset("A10", "cache", "sec_form4", json.dumps(signals, ensure_ascii=False))
        if publish: _publish_all_from_matrix()

def run_fetch_cftc(publish: bool = True):
    dos_mode = _get_dos_mode()
    if dos_mode == "LOCKDOWN": return
    signals = fetch_cftc_cot()
    if signals is not None:
        _log_signals(signals, "cftc_cot")
        matrix.hset("A10", "cache", "cftc_cot", json.dumps(signals, ensure_ascii=False))
        if publish: _publish_all_from_matrix()

def run_fetch_onchain_sources(publish: bool = True):
    dos_mode = _get_dos_mode()
    if dos_mode in ("SURVIVAL", "LOCKDOWN"): return
    all_signals = []
    s_clank = fetch_clankapp()
    if s_clank: all_signals.extend(s_clank)
    if DUNE_API_KEY:
        s_dune = fetch_dune_analytics()
        if s_dune: all_signals.extend(s_dune)
    else:
        publish_degraded("Dune Analytics API Key is missing")
        
    s_binance = fetch_binance_tier2()
    if s_binance: all_signals.extend(s_binance)
        
    _log_signals(all_signals, "onchain_batch")
    matrix.hset("A10", "cache", "onchain", json.dumps(all_signals, ensure_ascii=False))
    if publish: _publish_all_from_matrix()

def run_fetch_elite_macro(publish: bool = True, force_algo: bool = False):
    dos_mode = _get_dos_mode()
    if dos_mode in ("SURVIVAL", "LOCKDOWN"): return
    all_signals = []
    
    s_news = fetch_verified_news_shifts()
    if s_news: all_signals.extend(s_news)
    
    s_eia = fetch_eia_energy()
    if s_eia: all_signals.extend(s_eia)
    s_fred = fetch_fred_elite_macro()
    if s_fred: all_signals.extend(s_fred)
    
    # ── A102: US EQUITY FLOW SCANNER ──
    try:
        a102_result = a102_equity_flow.run_equity_flow_scan()
        if a102_result:
            # We don't add signals to all_signals because they are not in standard UNIFIED_SIGNAL format
            # A102 sets values in Redis which will be injected into LLM prompt directly
            pass
    except Exception as e_102:
        log.warning(f"[A10] Lỗi khi chạy A102 Equity Flow: {e_102}")
    
    _log_signals(all_signals, "elite_macro_batch")
    matrix.hset("A10", "cache", "elite_macro", json.dumps(all_signals, ensure_ascii=False))
    if publish: _publish_all_from_matrix(force_algo)


def run_heartbeat_daemon():
    """Background thread: publish heartbeat every 60s."""
    while True:
        try:
            publish_heartbeat_a10()
            # NLM Heartbeat
            nlm_changelog.log_heartbeat("A10", {"status": "ALIVE", "mode": "DAEMON"})
        except Exception as e:
            log.error(f"Heartbeat error: {e}")
        time.sleep(60)  # publish every 60s (TTL=300s)


def run_fetch_macro_radar(publish: bool = True):
    """Fetch 13 Macro Sensors (GEO, OFI, GLS, REP, SHD, CRA, YC, INV, CFV, SDD, IRD, MRD, BCDT)."""
    try:
        from tools.macro_radar import compute_macro_matrix
        macro_state = compute_macro_matrix()
        log.info(f"Macro Radar: verdict={macro_state.get('macro_verdict')} "
                 f"GEO={macro_state['sensors']['GEO'].get('geo_score',0):.1f}")
        # Session log
        _log_agent_session(
            agent_id="A10",
            redis_key="zcl:macro:sensors",
            summary=f"MACRO_RADAR | verdict:{macro_state.get('macro_verdict')} | red:{macro_state.get('red_count',0)}",
            signals_count=13,
            confidence=0.9,
            expert_metrics={
                "GEO": macro_state["sensors"]["GEO"].get("geo_score", 0),
                "OFI": macro_state["sensors"]["OFI"].get("ofi_score", 0),
                "CFV": 1 if macro_state["sensors"]["CFV"].get("rotation_detected") else 0,
            },
        )
    except Exception as e:
        log.error(f"Macro Radar error: {e}")

# Auto Saga Pulse interval (seconds)
_SAGA_PULSE_INTERVAL = 2 * 3600  # Every 2h send Saga Pulse to A05+A11

def run_scheduler_daemon():
    """Auto scheduler to fetch data periodically."""
    fetch_funcs = [
        (run_fetch_onchain_sources, 1 * 3600), # Every 1h
        (run_fetch_sec, 2 * 3600),             # Every 2h
        (run_fetch_elite_macro, 4 * 3600),     # Every 4h
        (run_fetch_cftc, 6 * 3600),            # Every 6h
        (run_fetch_macro_radar, 600),          # Every 10 min
    ]
    last_run = {func: time.time() for func, _ in fetch_funcs} # Initial run is done outside
    last_saga_pulse = time.time()  # Track last Saga Pulse
    
    while True:
        now = time.time()
        published = False
        for func, interval in fetch_funcs:
            if now - last_run[func] >= interval:
                try:
                    log.info(f"Running scheduled task: {func.__name__}")
                    func(publish=False)
                    published = True
                except Exception as e:
                    log.error(f"Error {func.__name__}: {e}")
                finally:
                    last_run[func] = time.time()
        
        if published:
            _publish_all_from_matrix()
        
        # Auto Saga Pulse: Every 2h send SWARM_REALTIME_REQUEST to let A05+A11 read new data
        if now - last_saga_pulse >= _SAGA_PULSE_INTERVAL:
            try:
                matrix.publish("COMMANDER:events", {
                    "event": "SWARM_REALTIME_REQUEST",
                    "source": "A10_AUTO_PULSE",
                    "agent_ids": [],  # Broadcast to all
                    "reason": "A10 Auto Saga Pulse — data refreshed"
                })
                matrix.set("SYSTEM", "a10:last_saga_pulse", now, ttl=_SAGA_PULSE_INTERVAL * 2)
                log.info(f"[A10] 🔔 AUTO SAGA PULSE sent successfully — A05+A11 will receive new data")
                last_saga_pulse = now
            except Exception as e:
                log.error(f"[A10] Saga Pulse error: {e}")
            
        time.sleep(300)  # Decreased from 600 to 300s to be more responsive

def _listen_for_realtime_requests():
    """Background thread to listen for A10_REALTIME_REQUEST via Matrix PubSub."""
    pubsub = matrix.subscribe(["COMMANDER:events", "SWARM_REALTIME_REQUEST"])
    if not pubsub: return
    log.info("A10 starting to listen for A10_REALTIME_REQUEST via Matrix PubSub...")
    
    last_processed_time = 0
    
    for msg in pubsub.listen():
        if msg["type"] == "message":
            try:
                data = json.loads(msg["data"])
                action_event = data.get("action") or data.get("event")
                is_swarm = action_event == "SWARM_REALTIME_REQUEST" and ("A10" in data.get("agent_ids", []) or not data.get("agent_ids"))
                is_direct = action_event == "A10_REALTIME_REQUEST"
                if is_direct or is_swarm:
                    now = time.time()
                    last_processed_time = float(matrix.get("SYSTEM", "a10:last_realtime_ts") or 0)
                    
                    if now - last_processed_time < 600:
                        log.info(f"Skipped A10_REALTIME_REQUEST because it ran {int(now - last_processed_time)}s ago (< 10 minutes).")
                        continue
                        
                    matrix.set("SYSTEM", "a10:last_realtime_ts", now, ttl=650)
                    log.info("Received A10_REALTIME_REQUEST. Fetching all data (Cache preferred)...")
                    run_fetch_sec(publish=False)
                    run_fetch_cftc(publish=False)
                    run_fetch_onchain_sources(publish=False)
                    run_fetch_macro_radar(publish=False)
                    run_fetch_elite_macro(publish=True, force_algo=True)
                    # Respond back to Commander to report ready status
                    matrix.publish("COMMANDER:events", {"event": "A10_DATA_READY"})
            except Exception as e:
                log.error(f"A10 listen error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT — run directly (development / test)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EMF Signal Collector — Agent 10")
    parser.add_argument("--test",     action="store_true", help="Fetch all sources and print out")
    parser.add_argument("--sec",      action="store_true", help="Fetch SEC Form4 only")
    parser.add_argument("--heartbeat",action="store_true", help="Publish 1 heartbeat")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.heartbeat:
        publish_heartbeat_a10()
        print("Heartbeat published")
    elif args.test:
        print("=== SEC ===")
        run_fetch_sec(publish=False)
        print("=== CFTC ===")
        run_fetch_cftc(publish=False)
        print("=== On-Chain ===")
        run_fetch_onchain_sources(publish=False)
        print("=== Macro Radar (13 Algos) ===")
        run_fetch_macro_radar(publish=False)
        print("=== Elite Macro ===")
        run_fetch_elite_macro(publish=False)
        _publish_all_from_matrix()
        print("Done. Check Redis: redis-cli XLEN emf:signals:raw")
    else:
        # Daemon mode
        print("Agent 10 starting — heartbeat daemon + listener + scheduler loop")
        threading.Thread(target=run_heartbeat_daemon, daemon=True).start()
        threading.Thread(target=_listen_for_realtime_requests, daemon=True).start()
        
        # Diên Hồng Council minutes daemon
        try:
            from dien_hong_council import start_council_daemon
            start_council_daemon("A10")
        except Exception as e_dh:
            log.warning(f"[A10] Diên Hồng daemon failed to start: {e_dh}")
        
        print("Running initial fetch (all APIs)...")
        run_fetch_sec(publish=False)
        run_fetch_cftc(publish=False)
        run_fetch_onchain_sources(publish=False)
        run_fetch_macro_radar(publish=False)
        run_fetch_elite_macro(publish=True)
        
        print("Initial fetch done. Starting daemon loop.")
        run_scheduler_daemon()
