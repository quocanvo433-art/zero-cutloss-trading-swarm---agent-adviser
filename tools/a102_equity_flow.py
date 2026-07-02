"""
🧬 DNA: v1.0 (Sovereign Purity — Equity Flow Scanner) [DNA Header]
🏢 UNIT: EQUITY_FLOW_SCANNER (A102)
🛠️ ROLE: SUB-MODULE of A10 EMF_HARVESTER
📖 DESC: Scan full US Equity landscape: 11 GICS Sectors, Factor Rotation, Market Breadth,
         Divergence Detection. Data from yfinance (free) + Google Sheets (GOOGLEFINANCE).
🔗 CALLS: a10_signal_collector._build_signal()
📟 I/O: Redis: zcl:a10:equity_flow, zcl:a10:rs_matrix, zcl:a10:breadth_state
🛡️ INTEGRITY: Cache-1h, Batch-Download, Thread-Safe.
"""

import os
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs" / "emf_signals"

from imperial_state import matrix, setup_agent_logger

log = setup_agent_logger("A102", "EQUITY_FLOW")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

# 11 GICS Sector ETFs
SECTOR_ETFS = {
    "XLK":  "Technology",
    "XLF":  "Financial",
    "XLE":  "Energy",
    "XLI":  "Industrial",
    "XLV":  "Healthcare",
    "XLC":  "Communication",
    "XLY":  "Consumer_Disc",
    "XLP":  "Consumer_Staples",
    "XLU":  "Utilities",
    "XLRE": "Real_Estate",
    "XLB":  "Materials",
}

# Factor ETFs: used to measure Risk Appetite
FACTOR_ETFS = {
    "SPY":  "Benchmark_SP500",
    "RSP":  "EqualWeight_SP500",
    "QQQ":  "Nasdaq100",
    "DIA":  "Dow30",
    "IWM":  "SmallCap2000",
    "IWF":  "Growth_Factor",
    "IWD":  "Value_Factor",
    "EFA":  "Intl_Developed",
    "EEM":  "Emerging_Markets",
    "VXF":  "Extended_Market",
    "ARKK": "Innovation_Disrupt",
    "ITA":  "Defense_Pure",
}

# Sector representatives (Top holdings of each sector)
STOCK_REPS = {
    # Technology
    "NVDA": "Tech/AI_GPU", "AAPL": "Tech/Consumer", "MSFT": "Tech/Cloud",
    "AVGO": "Tech/Semiconductor", "AMD": "Tech/AI_GPU", "TSM": "Tech/Foundry",
    # Financial
    "JPM": "Bank/Major", "GS": "Bank/Investment", "BAC": "Bank/Consumer",
    "V": "Fintech/Payment",
    # Energy
    "XOM": "Oil/Major", "CVX": "Oil/Major", "SLB": "Oil/Services", "OXY": "Oil/Upstream",
    # Industrial + Defense
    "CAT": "Industrial/Heavy", "LMT": "Defense/Aerospace", "RTX": "Defense/Missile",
    "GE": "Industrial/Conglom", "BA": "Aerospace/Civil",
    # Healthcare
    "UNH": "Health/Insurance", "JNJ": "Pharma/Major", "LLY": "Pharma/Biotech",
    "PFE": "Pharma/Vaccine",
    # Communication
    "META": "Social/Ads", "GOOGL": "Search/Cloud", "NFLX": "Streaming", "DIS": "Media/Theme",
    # Consumer Discretionary
    "AMZN": "Ecommerce", "TSLA": "EV/Auto", "HD": "Retail/Home", "NKE": "Consumer/Brand",
    # Consumer Staples
    "PG": "Staples/Major", "KO": "Beverage", "WMT": "Retail/Discount", "COST": "Retail/Warehouse",
    # Utilities / Real Estate / Materials
    "NEE": "Utility/Renew", "SO": "Utility/Major",
    "AMT": "REIT/Tower",
    "FCX": "Mining/Copper", "NEM": "Mining/Gold",
}

# Defensive sectors: increase when fearing recession
DEFENSIVE_SECTORS = {"XLV", "XLU", "XLP"}
# Offensive sectors: increase during Risk-On
OFFENSIVE_SECTORS = {"XLK", "XLY", "XLC"}

# Cache
_eq_cache: dict = {}
_eq_cache_lock = threading.Lock()
EQ_CACHE_TTL = 3600  # 1h


# ══════════════════════════════════════════════════════════════════════════════
# CACHE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_eq_cache(key: str) -> Optional[any]:
    with _eq_cache_lock:
        entry = _eq_cache.get(key)
        if entry and (time.time() - entry["ts"]) < EQ_CACHE_TTL:
            return entry["data"]
    return None


def _set_eq_cache(key: str, data):
    with _eq_cache_lock:
        _eq_cache[key] = {"data": data, "ts": time.time()}


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS READER (Optional — fallback to yfinance if not configured)
# ══════════════════════════════════════════════════════════════════════════════

def _clean_float(val: any) -> Optional[float]:
    """Cleans string containing special characters before parsing to float."""
    if val is None:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None
    val_str = val_str.replace("$", "").replace("%", "").replace(",", "").strip()
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return None


def _read_google_sheets() -> Optional[dict]:
    """
    Reads data from Google Sheets if Service Account is configured.
    Returns dict: {ticker: {price, volume, change_pct, high52, low52}}
    Returns None if not configured or on error.
    """
    sa_key_path = os.getenv("GOOGLE_SA_KEY_PATH", "")
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")

    if not sa_key_path or not spreadsheet_id:
        return None

    key_path = Path(sa_key_path)
    if not key_path.exists():
        # Fallback: try from BASE_DIR
        key_path = BASE_DIR / "config" / "openclaw-key.json"
        if not key_path.exists():
            log.debug("[A102] Google SA key not found, skipping Sheets")
            return None

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_file(str(key_path), scopes=SCOPES)
        service = build("sheets", "v4", credentials=creds)

        result = {}

        # Sheet 1: Sector_ETF (A2:G12 — ignore header)
        for sheet_name, row_range in [
            ("Sector_ETF", "A2:G12"),
            ("Stock_Reps", "A2:E100"),
            ("Factor_Breadth", "A2:E15"),
        ]:
            try:
                resp = service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=f"{sheet_name}!{row_range}",
                ).execute()
                rows = resp.get("values", [])
                for row in rows:
                    if not row or not row[0]:
                        continue
                    ticker = str(row[0]).strip().upper()
                    entry = {"ticker": ticker}
                    
                    price = _clean_float(row[2]) if len(row) > 2 else None
                    volume = _clean_float(row[3]) if len(row) > 3 else None
                    change_pct = _clean_float(row[4]) if len(row) > 4 else None
                    
                    if price is not None:
                        entry["price"] = price
                    if volume is not None:
                        entry["volume"] = volume
                    if change_pct is not None:
                        entry["change_pct"] = change_pct
                        
                    result[ticker] = entry
            except Exception as e_sheet:
                log.debug(f"[A102] Sheet {sheet_name} read error: {e_sheet}")

        if result:
            log.info(f"[A102] Google Sheets: {len(result)} tickers loaded")
        return result if result else None

    except ImportError:
        log.info("[A102] google-api-python-client not installed — using yfinance fallback")
        return None
    except Exception as e:
        log.warning(f"[A102] Google Sheets error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# CORE FETCHERS
# ══════════════════════════════════════════════════════════════════════════════

def _batch_download_yf(tickers: list, period: str = "1mo") -> dict:
    """
    Batch download via yfinance — reduces API calls.
    Returns: {ticker: DataFrame of Close prices}
    """
    cache_key = f"yf_batch_{period}_{'_'.join(sorted(tickers[:5]))}"
    cached = _get_eq_cache(cache_key)
    if cached is not None:
        return cached

    try:
        data = yf.download(
            tickers, period=period, interval="1d",
            group_by="ticker", auto_adjust=True, progress=False,
            threads=True,
        )
        result = {}
        for t in tickers:
            try:
                if len(tickers) == 1:
                    hist = data["Close"].dropna()
                else:
                    hist = data[t]["Close"].dropna()
                if len(hist) >= 2:
                    result[t] = hist
            except (KeyError, TypeError):
                continue

        _set_eq_cache(cache_key, result)
        log.info(f"[A102] yfinance batch: {len(result)}/{len(tickers)} tickers OK ({period})")
        return result
    except Exception as e:
        log.warning(f"[A102] yfinance batch error: {e}")
        return _get_eq_cache(cache_key) or {}


def fetch_market_breadth() -> dict:
    """
    Market Breadth Indicators:
    1. RSP/SPY Ratio (Equal-weight vs Cap-weight divergence)
    2. % Sector ETFs advancing (5D)
    3. Sector Advance/Decline

    Output: {
        "rsp_spy_ratio": float,       # > 1.0 = Healthy, < 1.0 = Narrow
        "sectors_advancing": int,     # Number of sectors advancing (5D)
        "sectors_declining": int,
        "breadth_state": str,         # HEALTHY / NARROW / DIVERGENT / THRUST
        "breadth_score": float,       # 0.0 - 1.0
    }
    """
    cached = _get_eq_cache("market_breadth")
    if cached is not None:
        return cached

    all_tickers = list(SECTOR_ETFS.keys()) + ["SPY", "RSP"]
    prices = _batch_download_yf(all_tickers, period="1mo")

    if "SPY" not in prices or "RSP" not in prices:
        log.warning("[A102] SPY/RSP data unavailable for breadth calc")
        return {"breadth_state": "UNKNOWN", "breadth_score": 0.5}

    spy_hist = prices["SPY"]
    rsp_hist = prices["RSP"]

    # RSP/SPY Ratio: compare 5D returns
    spy_5d = (float(spy_hist.iloc[-1]) / float(spy_hist.iloc[-min(5, len(spy_hist))])) - 1
    rsp_5d = (float(rsp_hist.iloc[-1]) / float(rsp_hist.iloc[-min(5, len(rsp_hist))])) - 1

    rsp_spy_ratio = (1 + rsp_5d) / (1 + spy_5d) if (1 + spy_5d) != 0 else 1.0

    # Sector Advance/Decline
    advancing = 0
    declining = 0
    sector_returns = {}

    for etf, sector_name in SECTOR_ETFS.items():
        if etf in prices and len(prices[etf]) >= 5:
            hist = prices[etf]
            pct_5d = (float(hist.iloc[-1]) / float(hist.iloc[-min(5, len(hist))])) - 1
            sector_returns[etf] = pct_5d * 100
            if pct_5d > 0.001:
                advancing += 1
            elif pct_5d < -0.001:
                declining += 1

    total_sectors = advancing + declining
    breadth_pct = advancing / max(total_sectors, 1)

    # Determine state
    if breadth_pct >= 0.8:
        breadth_state = "THRUST"        # >80% sectors up = strong breakout
    elif breadth_pct >= 0.55 and rsp_spy_ratio >= 0.98:
        breadth_state = "HEALTHY"       # Broad participation
    elif rsp_spy_ratio < 0.96:
        breadth_state = "NARROW"        # SPY up but RSP lagging = narrow rally
    elif breadth_pct <= 0.3:
        breadth_state = "DIVERGENT"     # Most sectors declining
    else:
        breadth_state = "MIXED"

    breadth_score = round(breadth_pct * 0.6 + min(rsp_spy_ratio, 1.05) * 0.4, 3)

    result = {
        "rsp_spy_ratio": round(rsp_spy_ratio, 4),
        "spy_5d_pct": round(spy_5d * 100, 2),
        "rsp_5d_pct": round(rsp_5d * 100, 2),
        "sectors_advancing": advancing,
        "sectors_declining": declining,
        "sector_returns_5d": sector_returns,
        "breadth_state": breadth_state,
        "breadth_score": breadth_score,
    }

    _set_eq_cache("market_breadth", result)
    log.info(f"[A102] Breadth: {breadth_state} | RSP/SPY={rsp_spy_ratio:.3f} | Adv={advancing} Dec={declining}")
    return result


def fetch_factor_rotation() -> dict:
    """
    Factor Rotation: Growth vs Value, Large vs Small, US vs Intl.

    Output: {
        "growth_value_ratio": float,  # >1 = Growth leading, <1 = Value leading
        "large_small_ratio": float,   # >1 = Large Cap leading
        "us_intl_ratio": float,       # >1 = US outperforming
        "regime": str,                # RISK_ON / RISK_OFF / ROTATION / NEUTRAL
        "factor_signals": list,       # Formatted signals for LLM
    }
    """
    cached = _get_eq_cache("factor_rotation")
    if cached is not None:
        return cached

    factor_tickers = ["IWF", "IWD", "SPY", "IWM", "EFA", "EEM", "ARKK"]
    prices = _batch_download_yf(factor_tickers, period="1mo")

    def _calc_5d_return(ticker):
        if ticker not in prices or len(prices[ticker]) < 5:
            return 0.0
        h = prices[ticker]
        return (float(h.iloc[-1]) / float(h.iloc[-min(5, len(h))])) - 1

    gv_r = (1 + _calc_5d_return("IWF")) / max(1 + _calc_5d_return("IWD"), 0.001)
    ls_r = (1 + _calc_5d_return("SPY")) / max(1 + _calc_5d_return("IWM"), 0.001)
    us_intl = (1 + _calc_5d_return("SPY")) / max(1 + _calc_5d_return("EFA"), 0.001)

    # Determine regime
    signals = []
    if gv_r > 1.02:
        signals.append("Growth > Value (+Risk On)")
    elif gv_r < 0.98:
        signals.append("Value > Growth (+Defensive)")

    if ls_r > 1.02:
        signals.append("Large Cap > Small Cap (+Quality Flight)")
    elif ls_r < 0.98:
        signals.append("Small Cap > Large Cap (+Risk Appetite)")

    if us_intl > 1.02:
        signals.append("US > International (+Dollar Strength)")
    elif us_intl < 0.98:
        signals.append("International > US (+Capital Outflow)")

    arkk_ret = _calc_5d_return("ARKK") * 100
    if arkk_ret > 5:
        signals.append(f"ARKK {arkk_ret:+.1f}% (+Innovation Frenzy)")
    elif arkk_ret < -5:
        signals.append(f"ARKK {arkk_ret:+.1f}% (+Innovation Crash)")

    # Regime classification
    if gv_r > 1.01 and ls_r < 1.01:
        regime = "RISK_ON"
    elif gv_r < 0.99 and ls_r > 1.01:
        regime = "RISK_OFF"
    elif abs(gv_r - 1.0) > 0.02 or abs(ls_r - 1.0) > 0.02:
        regime = "ROTATION"
    else:
        regime = "NEUTRAL"

    result = {
        "growth_value_ratio": round(gv_r, 4),
        "large_small_ratio": round(ls_r, 4),
        "us_intl_ratio": round(us_intl, 4),
        "regime": regime,
        "factor_signals": signals,
        "arkk_5d_pct": round(arkk_ret, 2),
    }

    _set_eq_cache("factor_rotation", result)
    log.info(f"[A102] Factor: regime={regime} | G/V={gv_r:.3f} L/S={ls_r:.3f} US/Intl={us_intl:.3f}")
    return result


def fetch_rs_matrix() -> dict:
    """
    Relative Strength Matrix: rank 11 GICS sectors against SPY.
    RS = (Sector 5D return / SPY 5D return) * 100

    Output: {
        "rankings": [{"sector": str, "etf": str, "rs": float, "ret_5d": float}],
        "convergence_score": float,  # High = all sectors moving in the same direction = strong trend
        "top_3": list,
        "bottom_3": list,
    }
    """
    cached = _get_eq_cache("rs_matrix")
    if cached is not None:
        return cached

    all_tickers = list(SECTOR_ETFS.keys()) + ["SPY"]
    prices = _batch_download_yf(all_tickers, period="1mo")

    if "SPY" not in prices:
        return {"rankings": [], "convergence_score": 0.5}

    spy_hist = prices["SPY"]
    spy_5d = (float(spy_hist.iloc[-1]) / float(spy_hist.iloc[-min(5, len(spy_hist))])) - 1

    rankings = []
    returns_5d = []

    for etf, sector_name in SECTOR_ETFS.items():
        if etf in prices and len(prices[etf]) >= 5:
            hist = prices[etf]
            ret_5d = (float(hist.iloc[-1]) / float(hist.iloc[-min(5, len(hist))])) - 1
            rs = (ret_5d / spy_5d * 100) if spy_5d != 0 else 100.0
            rankings.append({
                "sector": sector_name,
                "etf": etf,
                "rs": round(rs, 1),
                "ret_5d_pct": round(ret_5d * 100, 2),
            })
            returns_5d.append(ret_5d)

    # Sort by RS descending
    rankings.sort(key=lambda x: x["rs"], reverse=True)

    # Convergence: low std dev of returns = all moving together
    if returns_5d:
        import statistics
        std_dev = statistics.stdev(returns_5d) if len(returns_5d) > 1 else 0
        mean_abs = sum(abs(r) for r in returns_5d) / len(returns_5d)
        convergence = max(0, 1 - (std_dev / max(mean_abs, 0.001)))
        convergence = round(min(convergence, 1.0), 3)
    else:
        convergence = 0.5

    result = {
        "rankings": rankings,
        "convergence_score": convergence,
        "top_3": [r["etf"] for r in rankings[:3]],
        "bottom_3": [r["etf"] for r in rankings[-3:]],
        "spy_5d_pct": round(spy_5d * 100, 2),
    }

    _set_eq_cache("rs_matrix", result)
    log.info(f"[A102] RS Matrix: Top={result['top_3']} Bot={result['bottom_3']} Conv={convergence:.2f}")
    return result


def fetch_stock_reps_summary() -> dict:
    """
    Fetches data from Google Sheets (prioritized) or yfinance for sector representative stocks.
    Returns summary: top gainers, losers, volume spikes.
    """
    cached = _get_eq_cache("stock_reps")
    if cached is not None:
        return cached

    # Prioritize Google Sheets if full data is available
    gs_data = _read_google_sheets()
    stock_data = {}

    if gs_data:
        for ticker in STOCK_REPS:
            # Ticker must have change_pct or price to receive data from Sheets
            if ticker in gs_data and ("change_pct" in gs_data[ticker] or "price" in gs_data[ticker]):
                stock_data[ticker] = gs_data[ticker]

    # Fallback to yfinance for missing symbols
    missing_tickers = [t for t in STOCK_REPS if t not in stock_data]
    if missing_tickers:
        prices = _batch_download_yf(missing_tickers, period="5d")
        for t in missing_tickers:
            if t in prices and len(prices[t]) >= 2:
                hist = prices[t]
                pct_1d = (float(hist.iloc[-1]) / float(hist.iloc[-2]) - 1) * 100
                stock_data[t] = {
                    "ticker": t,
                    "price": round(float(hist.iloc[-1]), 2),
                    "change_pct": round(pct_1d, 2),
                }

    # Rank
    ranked = sorted(stock_data.values(), key=lambda x: x.get("change_pct", 0), reverse=True)
    top_gainers = ranked[:5] if ranked else []
    top_losers = ranked[-5:] if len(ranked) >= 5 else []

    result = {
        "total_tracked": len(stock_data),
        "top_gainers": [
            f"{s['ticker']} ({STOCK_REPS.get(s['ticker'], '?')}) {s.get('change_pct', 0):+.1f}%"
            for s in top_gainers
        ],
        "top_losers": [
            f"{s['ticker']} ({STOCK_REPS.get(s['ticker'], '?')}) {s.get('change_pct', 0):+.1f}%"
            for s in top_losers
        ],
    }

    _set_eq_cache("stock_reps", result)
    log.info(f"[A102] Stock Reps: {result['total_tracked']} tracked | GS={'YES' if gs_data else 'NO'}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# DIVERGENCE DETECTOR — Core algorithm
# ══════════════════════════════════════════════════════════════════════════════

def detect_flow_divergence(breadth: dict, factors: dict, rs: dict) -> dict:
    """
    Detect 5 critical patterns:
    1. NARROW_RALLY: SPY ↑ but Breadth ↓ → Bull trap
    2. STEALTH_ROTATION: Sector X attracting capital, Y withdrawing → Capital rotating sectors
    3. RISK_APPETITE_SHIFT: Growth→Value or Large→Small → Regime change
    4. BREADTH_THRUST: >80% sectors rising strongly → Confirmed breakout
    5. DEFENSIVE_PIVOT: XLV+XLU+XLP attracting capital, XLK+XLY withdrawing → Fearing recession

    Output: {"patterns": list, "danger_level": str, "interpretation": str}
    """
    patterns = []
    danger_score = 0

    # 1. NARROW RALLY
    spy_5d = breadth.get("spy_5d_pct", 0)
    if spy_5d > 1.0 and breadth.get("breadth_state") in ("NARROW", "DIVERGENT"):
        total_sectors = breadth.get('sectors_advancing', 0) + breadth.get('sectors_declining', 0)
        patterns.append({
            "type": "NARROW_RALLY",
            "severity": "HIGH",
            "detail": f"SPY +{spy_5d:.1f}% but breadth={breadth.get('breadth_state')} "
                      f"(RSP/SPY={breadth.get('rsp_spy_ratio', 0):.3f}). "
                      f"Only {breadth.get('sectors_advancing', 0)}/{max(total_sectors, 1)} sectors advancing.",
        })
        danger_score += 3

    # 2. STEALTH ROTATION
    if rs.get("rankings"):
        top_rs = rs["rankings"][0].get("rs", 100)
        bot_rs = rs["rankings"][-1].get("rs", 100) if rs["rankings"] else 100
        if top_rs - bot_rs > 50:  # RS divergence > 50 points
            patterns.append({
                "type": "STEALTH_ROTATION",
                "severity": "MEDIUM",
                "detail": f"Capital rotating from {rs['bottom_3']} → {rs['top_3']}. "
                          f"RS gap: {top_rs:.0f} vs {bot_rs:.0f}",
            })
            danger_score += 2

    # 3. RISK APPETITE SHIFT
    if factors.get("regime") in ("RISK_OFF", "ROTATION"):
        patterns.append({
            "type": "RISK_APPETITE_SHIFT",
            "severity": "HIGH" if factors["regime"] == "RISK_OFF" else "MEDIUM",
            "detail": f"Regime: {factors['regime']}. "
                      f"G/V={factors.get('growth_value_ratio', 0):.3f} "
                      f"L/S={factors.get('large_small_ratio', 0):.3f} "
                      f"US/Intl={factors.get('us_intl_ratio', 0):.3f}. "
                      f"Signals: {', '.join(factors.get('factor_signals', []))}",
        })
        danger_score += 3 if factors["regime"] == "RISK_OFF" else 2

    # 4. BREADTH THRUST
    if breadth.get("breadth_state") == "THRUST":
        patterns.append({
            "type": "BREADTH_THRUST",
            "severity": "LOW",
            "detail": f">80% sectors rising 5D. Adv={breadth.get('sectors_advancing')}. "
                      f"Breakout confirmed — Strong trend.",
        })
        # Positive signal — reduces danger
        danger_score = max(danger_score - 2, 0)

    # 5. DEFENSIVE PIVOT
    sector_rets = breadth.get("sector_returns_5d", {})
    defensive_avg = sum(sector_rets.get(s, 0) for s in DEFENSIVE_SECTORS) / max(len(DEFENSIVE_SECTORS), 1)
    offensive_avg = sum(sector_rets.get(s, 0) for s in OFFENSIVE_SECTORS) / max(len(OFFENSIVE_SECTORS), 1)

    if defensive_avg > 1.0 and offensive_avg < -1.0:
        patterns.append({
            "type": "DEFENSIVE_PIVOT",
            "severity": "HIGH",
            "detail": f"Defensive (XLV/XLU/XLP) avg +{defensive_avg:.1f}%, "
                      f"Offensive (XLK/XLY/XLC) avg {offensive_avg:.1f}%. "
                      f"Market is in defensive mode — fearing recession.",
        })
        danger_score += 3

    # Danger level
    if danger_score >= 6:
        danger_level = "CRITICAL"
    elif danger_score >= 4:
        danger_level = "HIGH"
    elif danger_score >= 2:
        danger_level = "ELEVATED"
    elif patterns:
        danger_level = "WATCH"
    else:
        danger_level = "CALM"

    # Build interpretation
    if not patterns:
        interpretation = "No unusual divergence detected. US Equity market is synchronized."
    else:
        parts = [f"[{p['severity']}] {p['type']}: {p['detail']}" for p in patterns]
        interpretation = " | ".join(parts)

    return {
        "patterns": patterns,
        "danger_level": danger_level,
        "danger_score": danger_score,
        "interpretation": interpretation[:2000],
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY — Called from A10
# ══════════════════════════════════════════════════════════════════════════════

def run_equity_flow_scan() -> dict:
    """
    Main entry point — called from a10_signal_collector.py.
    Returns dict containing all A102 results to be merged into the A10 LLM prompt.
    """
    log.info("[A102] === STARTING US EQUITY FLOW SCAN ===")
    t0 = time.time()

    breadth = fetch_market_breadth()
    factors = fetch_factor_rotation()
    rs = fetch_rs_matrix()
    stocks = fetch_stock_reps_summary()
    divergence = detect_flow_divergence(breadth, factors, rs)

    elapsed = time.time() - t0

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "breadth": breadth,
        "factor_rotation": factors,
        "rs_matrix": rs,
        "stock_reps": stocks,
        "divergence": divergence,
        "elapsed_sec": round(elapsed, 1),
    }

    # Publish to Redis
    try:
        matrix.set("A10", "equity_flow", json.dumps(result, ensure_ascii=False, default=str), ttl=7200)
        matrix.set("A10", "breadth_state", breadth.get("breadth_state", "UNKNOWN"), ttl=7200)
        matrix.set("A10", "rs_matrix", json.dumps(rs, ensure_ascii=False), ttl=7200)
    except Exception as e:
        log.warning(f"[A102] Redis publish error: {e}")

    log.info(f"[A102] === COMPLETED ({elapsed:.1f}s) | "
             f"Breadth={breadth.get('breadth_state')} | "
             f"Regime={factors.get('regime')} | "
             f"Danger={divergence.get('danger_level')} ===")

    return result


def format_for_llm_prompt(result: dict) -> str:
    """
    Format A102 result into a text block for the A10 LLM prompt.
    """
    breadth = result.get("breadth", {})
    factors = result.get("factor_rotation", {})
    rs = result.get("rs_matrix", {})
    stocks = result.get("stock_reps", {})
    div = result.get("divergence", {})

    lines = [
        "=== A102: US EQUITY FLOW SCANNER ===",
        "",
        f"📊 MARKET BREADTH: {breadth.get('breadth_state', 'N/A')} "
        f"(Score: {breadth.get('breadth_score', 0):.2f})",
        f"   SPY 5D: {breadth.get('spy_5d_pct', 0):+.2f}% | "
        f"RSP 5D: {breadth.get('rsp_5d_pct', 0):+.2f}% | "
        f"RSP/SPY: {breadth.get('rsp_spy_ratio', 0):.3f}",
        f"   Advancing: {breadth.get('sectors_advancing', 0)} | "
        f"Declining: {breadth.get('sectors_declining', 0)}",
        "",
        f"🔄 FACTOR ROTATION: Regime = {factors.get('regime', 'N/A')}",
        f"   Growth/Value: {factors.get('growth_value_ratio', 0):.3f} | "
        f"Large/Small: {factors.get('large_small_ratio', 0):.3f} | "
        f"US/Intl: {factors.get('us_intl_ratio', 0):.3f}",
    ]

    if factors.get("factor_signals"):
        for sig in factors["factor_signals"]:
            lines.append(f"   ➤ {sig}")

    lines.append("")
    lines.append("📈 SECTOR RELATIVE STRENGTH (RS vs SPY):")
    lines.append("   | Sector | ETF | RS | 5D Return |")
    lines.append("   |---|---|---|---|")
    for r in rs.get("rankings", [])[:11]:
        emoji = "🔥" if r["rs"] > 120 else ("❄️" if r["rs"] < 80 else "⚡")
        lines.append(f"   | {r['sector']} | {r['etf']} | {r['rs']:.0f} | {r['ret_5d_pct']:+.1f}% | {emoji}")
    lines.append(f"   Convergence: {rs.get('convergence_score', 0):.2f} "
                 f"({'Synchronized' if rs.get('convergence_score', 0) > 0.7 else 'Divergent'})")

    lines.append("")
    lines.append(f"💰 STOCK REPS: {stocks.get('total_tracked', 0)} symbols tracked")
    if stocks.get("top_gainers"):
        lines.append(f"   Top Gainers: {', '.join(stocks['top_gainers'][:3])}")
    if stocks.get("top_losers"):
        lines.append(f"   Top Losers: {', '.join(stocks['top_losers'][:3])}")

    lines.append("")
    lines.append(f"⚠️ DIVERGENCE ALERT: {div.get('danger_level', 'N/A')} "
                 f"(Score: {div.get('danger_score', 0)})")
    for p in div.get("patterns", []):
        lines.append(f"   🚨 [{p['severity']}] {p['type']}: {p['detail']}")

    if not div.get("patterns"):
        lines.append("   ✅ No divergence detected. US Equity market is synchronized.")

    lines.append("")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing A102 Equity Flow Scanner...")
    result = run_equity_flow_scan()
    print(format_for_llm_prompt(result))
    print(f"\nDone in {result.get('elapsed_sec', 0)}s")
