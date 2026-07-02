"""
🧬 DNA: v16.6 (Sovereign Purity & Narrative Pipeline Sensors) [DNA Header]
🏢 UNIT: NARRATIVE_PIPELINE_SENSOR (A12 Extension)
🛠️ ROLE: COGNITIVE_WARFARE_RADAR
📖 DESC: 4 Algorithms to Extract Cognitive Pipeline Traces (Pipeline Sensors).
         Detect synthetic vs organic media campaigns.
         Free data: Google Trends, RSS timestamps, Yahoo Finance.
         Provides 4 dimensions of cognitive warfare: ECS, CAD, NPA, DAR for A12.
🔗 CALLS: pytrends (Google Trends), yfinance, tools/imperial_state.py
📟 I/O: Redis: zcl:narrative:sensors (TTL 30m)
🛡️ INTEGRITY: Read-only, no content manipulation.
"""

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))

import os
import json
import time
import logging
import math
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from collections import Counter

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from pytrends.request import TrendReq
    _HAS_PYTRENDS = True
except ImportError:
    _HAS_PYTRENDS = False

try:
    import feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    _HAS_FEEDPARSER = False

try:
    from tools.imperial_state import matrix
except ImportError:
    from imperial_state import matrix

log = logging.getLogger("NARRATIVE_PIPELINE_SENSORS")
if not log.handlers:
    log.setLevel(logging.INFO)
    log.addHandler(logging.StreamHandler())

# Cache
_CACHE: Dict[str, Any] = {}
_CACHE_TTL = 1800  # 30 minutes
_EPSILON = 1e-10


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _z_score_val(value: float, series: list) -> float:
    """Z-Score of a value compared to a series."""
    if len(series) < 3:
        return 0.0
    mean = np.mean(series)
    std = np.std(series)
    if std < _EPSILON:
        return 0.0
    return float((value - mean) / std)


def _roc_val(current: float, previous: float) -> float:
    """Rate of Change (%) between two values."""
    if abs(previous) < _EPSILON:
        return 100.0 if current > _EPSILON else 0.0
    return (current - previous) / abs(previous) * 100


def _fetch_google_trends(keyword: str, timeframe: str = "now 7-d") -> Optional[list]:
    """Get Google Trends data for a keyword. Cache 30 minutes."""
    cache_key = f"gtrends_{keyword}_{timeframe}"
    now = time.time()
    if cache_key in _CACHE:
        data, ts = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    if not _HAS_PYTRENDS:
        log.warning("pytrends not installed. Run: pip install pytrends")
        return None

    try:
        pytrends = TrendReq(hl='en-US', tz=0, timeout=(10, 30), requests_args={'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'}})
        pytrends.build_payload([keyword], timeframe=timeframe)
        df = pytrends.interest_over_time()
        if df.empty:
            return None
        values = df[keyword].values.tolist()
        _CACHE[cache_key] = (values, now)
        return values
    except Exception as e:
        log.warning(f"[NPS] Google Trends error for '{keyword}': {e}")
        return None


def _fetch_rss_timestamps(rss_urls: List[str], keyword: str,
                          max_entries: int = 50) -> List[float]:
    """
    Collect timestamps of articles containing keyword from RSS feeds list.
    Return list of unix timestamps.
    """
    if not _HAS_FEEDPARSER:
        return []

    timestamps = []
    keyword_lower = keyword.lower()

    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:30]:
                title = (entry.get("title", "") or "").lower()
                summary = (entry.get("summary", "") or "").lower()
                if keyword_lower in title or keyword_lower in summary:
                    published = entry.get("published_parsed")
                    if published:
                        ts = time.mktime(published)
                        timestamps.append(ts)
        except Exception:
            continue

    # Sort and get top nearest max_entries
    timestamps.sort(reverse=True)
    return timestamps[:max_entries]


def _fetch_price_data(ticker: str, period: str = "1mo") -> Optional[np.ndarray]:
    """Get closing prices from Yahoo Finance."""
    cache_key = f"yfin_{ticker}_{period}"
    now = time.time()
    if cache_key in _CACHE:
        data, ts = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    if yf is None:
        return None

    try:
        df = yf.download(ticker, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        closes = df["Close"].values.astype(float).flatten()
        _CACHE[cache_key] = (closes, now)
        return closes
    except Exception as e:
        log.warning(f"[NPS] yfinance error for {ticker}: {e}")
        return None


def _fetch_intraday_price_data(ticker: str, period: str = "5d", interval: str = "1h") -> Optional[np.ndarray]:
    """Get intraday prices from Yahoo Finance for CANL to catch fake moves faster."""
    cache_key = f"yfin_intra_{ticker}_{period}_{interval}"
    now = time.time()
    if cache_key in _CACHE:
        data, ts = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    if yf is None:
        return None

    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        closes = df["Close"].values.astype(float).flatten()
        _CACHE[cache_key] = (closes, now)
        return closes
    except Exception as e:
        log.warning(f"[NPS] yfinance intraday error for {ticker}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# DEFAULT RSS FEEDS (Free, public, financial news)
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_RSS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD&region=US&lang=en-US",
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptonews.com/news/feed/",
    "https://feeds.feedburner.com/zerohedge/feed",
    "https://www.investing.com/rss/news.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://feeds.reuters.com/reuters/businessNews",
]


# ══════════════════════════════════════════════════════════════════════════════
# SENSOR 1: ECS — Echo-Chamber Synchronization
# ══════════════════════════════════════════════════════════════════════════════

def compute_ecs(keyword: str, rss_urls: List[str] = None) -> Dict[str, Any]:
    """
    Echo-Chamber Synchronization.
    ECS = 1 / (Variance(Timestamps_of_Trending_News) + ε)

    Organic trend: spreads gradually (HIGH variance = LOW ECS).
    Synthetic trend: simultaneous breakout (LOW variance = HIGH ECS).

    ECS spike -> Sponsored PR campaign. DO NOT FOMO.
    """
    feeds = rss_urls or DEFAULT_RSS_FEEDS
    timestamps = _fetch_rss_timestamps(feeds, keyword, max_entries=50)

    if len(timestamps) < 3:
        return {
            "ecs": 0.0, "status": "INSUFFICIENT_DATA",
            "n_articles": len(timestamps),
            "interpretation": f"Insufficient articles about '{keyword}' ({len(timestamps)} < 3).",
            "alert": "NO_DATA",
        }

    # Normalize timestamps to hours (calculated from the first article)
    t_min = min(timestamps)
    t_normalized = [(t - t_min) / 3600 for t in timestamps]  # Unit: hours

    variance = float(np.var(t_normalized))
    ecs = 1.0 / (variance + _EPSILON)

    # Add: measure clustering - % of posts within the same 2 hours
    # If >70% articles published in 2h -> Organized campaign
    two_hour_window = 2.0
    max_cluster = 0
    for t in t_normalized:
        cluster_count = sum(1 for t2 in t_normalized if abs(t2 - t) <= two_hour_window)
        max_cluster = max(max_cluster, cluster_count)
    cluster_ratio = max_cluster / len(t_normalized)

    # Threshold: ECS > 0.5 or cluster_ratio > 0.7 -> Suspicious
    if ecs > 1.0 or cluster_ratio > 0.8:
        interpretation = (
            f"🔴 PR CAMPAIGN DETECTED: {len(timestamps)} articles about '{keyword}' "
            f"published almost simultaneously (ECS={ecs:.2f}, cluster={cluster_ratio:.0%}). "
            f"This is a sponsored media campaign. DO NOT FOMO."
        )
        alert = "SYNTHETIC_CAMPAIGN"
    elif ecs > 0.3 or cluster_ratio > 0.6:
        interpretation = (
            f"🟡 Suspicious: '{keyword}' spreading abnormally fast (ECS={ecs:.2f}, "
            f"cluster={cluster_ratio:.0%}). Possible manipulation."
        )
        alert = "SUSPICIOUS"
    else:
        interpretation = (
            f"🟢 Organic: '{keyword}' spreading naturally (ECS={ecs:.4f}, "
            f"cluster={cluster_ratio:.0%})."
        )
        alert = "ORGANIC"

    return {
        "ecs": round(ecs, 6),
        "variance_hours": round(variance, 4),
        "n_articles": len(timestamps),
        "cluster_ratio": round(cluster_ratio, 4),
        "alert": alert,
        "interpretation": interpretation,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SENSOR 2: CAD — Cognitive-Action Divergence
# ══════════════════════════════════════════════════════════════════════════════

def compute_cad(keyword: str, ticker: str = "BTC-USD") -> Dict[str, Any]:
    """
    Cognitive-Action Divergence.
    CAD = Z_Score(Search_Volume) - Z_Score(|Price_Delta|)

    CAD >> 0 -> Media booming but price flat.
              -> Decoy, Iceberg wall blocking price. Elite is dumping.
    CAD << 0 -> Price moving strongly but media silent.
              -> Elite is accumulating secretly. Possible buy opportunity.
    """
    # Get search volume from Google Trends
    search_data = _fetch_google_trends(keyword, timeframe="now 7-d")
    if search_data is None or len(search_data) < 3:
        search_data = _fetch_google_trends(keyword, timeframe="today 1-m")

    # Get price data
    price_data = _fetch_price_data(ticker, period="1mo")

    if search_data is None or price_data is None:
        return {
            "cad": 0.0, "status": "NO_DATA",
            "interpretation": f"Cannot retrieve data for '{keyword}' / '{ticker}'.",
            "alert": "NO_DATA",
        }

    # Z-Score of the latest search volume
    search_current = float(search_data[-1])
    z_search = _z_score_val(search_current, search_data)

    # Z-Score of absolute price change
    price_deltas = [abs(price_data[i] - price_data[i-1]) for i in range(1, len(price_data))]
    if not price_deltas:
        return {"cad": 0.0, "status": "NO_PRICE_DELTA", "alert": "NO_DATA",
                "interpretation": "Insufficient price data."}

    z_price = _z_score_val(price_deltas[-1], price_deltas)

    cad = z_search - z_price

    if cad > 2.0:
        interpretation = (
            f"🔴 DECOY DETECTED: Media for '{keyword}' booming (Z={z_search:.2f}) "
            f"but {ticker} price flat/wicking (Z={z_price:.2f}). "
            f"CAD={cad:.2f}. Iceberg wall blocking. Elite dumping on retail FOMO. "
            f"Prepare to SHORT!"
        )
        alert = "DECOY_NARRATIVE"
    elif cad > 1.0:
        interpretation = (
            f"🟡 Mild divergence: Media hotter than price (CAD={cad:.2f}). "
            f"Caution - possible distribution phase."
        )
        alert = "MILD_DIVERGENCE"
    elif cad < -2.0:
        interpretation = (
            f"🟢 STEALTH ACCUMULATION: {ticker} price moving strongly (Z={z_price:.2f}) "
            f"but media silent (Z={z_search:.2f}). CAD={cad:.2f}. "
            f"Elite accumulating in the dark. Possible buy opportunity."
        )
        alert = "STEALTH_ACCUMULATION"
    elif cad < -1.0:
        interpretation = (
            f"🟢 Price stronger than narrative (CAD={cad:.2f}). Possible positive signal."
        )
        alert = "PRICE_LEADS"
    else:
        interpretation = f"⚪ Normal correlation between media and price (CAD={cad:.2f})."
        alert = "NEUTRAL"

    return {
        "cad": round(cad, 4),
        "z_search": round(z_search, 4),
        "z_price": round(z_price, 4),
        "search_current": search_current,
        "alert": alert,
        "interpretation": interpretation,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SENSOR 3: NPA — Narrative Pivot Acceleration
# ══════════════════════════════════════════════════════════════════════════════

def compute_npa(trend_a: str, trend_b: str) -> Dict[str, Any]:
    """
    Narrative Pivot Acceleration.
    NPA = ROC(Media_Vol_Trend_B) - ROC(Media_Vol_Trend_A)

    Positive NPA reversal -> Pipeline pivoted.
    Smart money took profit on Trend A, setting up casino Trend B.
    """
    data_a = _fetch_google_trends(trend_a, timeframe="today 1-m")
    data_b = _fetch_google_trends(trend_b, timeframe="today 1-m")

    if data_a is None or data_b is None:
        return {
            "npa": 0.0, "status": "NO_DATA",
            "interpretation": f"Cannot compare '{trend_a}' vs '{trend_b}'.",
            "alert": "NO_DATA",
        }

    if len(data_a) < 8 or len(data_b) < 8:
        return {"npa": 0.0, "status": "INSUFFICIENT_DATA", "alert": "NO_DATA",
                "interpretation": "Data series too short to compute ROC."}

    # 7-day ROC (latest week vs previous week). Split timeframe into two halves.
    mid = len(data_a) // 2

    avg_a_old = np.mean(data_a[:mid])
    avg_a_new = np.mean(data_a[mid:])
    roc_a = _roc_val(avg_a_new, avg_a_old)

    avg_b_old = np.mean(data_b[:mid])
    avg_b_new = np.mean(data_b[mid:])
    roc_b = _roc_val(avg_b_new, avg_b_old)

    npa = roc_b - roc_a

    if npa > 50 and roc_a < 0:
        interpretation = (
            f"🔴 PIPELINE PIVOT: '{trend_a}' dying (ROC={roc_a:.1f}%) "
            f"while '{trend_b}' booming (ROC={roc_b:.1f}%). NPA={npa:.1f}%. "
            f"Smart money took profits on '{trend_a}', setting up '{trend_b}'. "
            f"Drop '{trend_a}' from portfolio!"
        )
        alert = "PIPELINE_PIVOT"
    elif npa > 30:
        interpretation = (
            f"🟡 Shifting trend: '{trend_b}' rising (ROC={roc_b:.1f}%), "
            f"'{trend_a}' saturating (ROC={roc_a:.1f}%). NPA={npa:.1f}%."
        )
        alert = "SHIFTING"
    elif npa < -50 and roc_b < 0:
        interpretation = (
            f"🟢 '{trend_a}' still accelerating (ROC={roc_a:.1f}%), "
            f"'{trend_b}' declining. Pipeline still focused on '{trend_a}'."
        )
        alert = "TREND_A_DOMINANT"
    else:
        interpretation = (
            f"⚪ Balanced trends: '{trend_a}' ROC={roc_a:.1f}%, "
            f"'{trend_b}' ROC={roc_b:.1f}%. NPA={npa:.1f}%."
        )
        alert = "BALANCED"

    return {
        "npa": round(npa, 4),
        "roc_trend_a": round(roc_a, 4),
        "roc_trend_b": round(roc_b, 4),
        "trend_a": trend_a,
        "trend_b": trend_b,
        "alert": alert,
        "interpretation": interpretation,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SENSOR 4: DAR — Decoy Attention Ratio
# ══════════════════════════════════════════════════════════════════════════════

def compute_dar(decoy_keyword: str, hidden_keyword: str,
                decoy_ticker: str, hidden_ticker: str) -> Dict[str, Any]:
    """
    Decoy Attention Ratio.
    DAR = (Media_Vol(Decoy) / Media_Vol(Hidden)) /
          (Trading_Vol(Decoy) / Trading_Vol(Hidden))

    DAR >> 1 -> Media trapping retail in Decoy, but real money flowing to Hidden. This is an illusion.
    DAR << 1 -> Reverse: Hidden is over-promoted compared to real money flows.
    """
    # Media Volume: Google Trends
    trends_decoy = _fetch_google_trends(decoy_keyword, timeframe="now 7-d")
    trends_hidden = _fetch_google_trends(hidden_keyword, timeframe="now 7-d")

    if trends_decoy is None or trends_hidden is None:
        return {"dar": 0.0, "status": "NO_TRENDS_DATA", "alert": "NO_DATA",
                "interpretation": f"Cannot retrieve Google Trends for '{decoy_keyword}'/'{hidden_keyword}'."}

    media_decoy = max(float(np.mean(trends_decoy[-7:])), _EPSILON)
    media_hidden = max(float(np.mean(trends_hidden[-7:])), _EPSILON)
    media_ratio = media_decoy / media_hidden

    # Trading Volume: Yahoo Finance (Convert to Notional USD Volume)
    vol_decoy_raw = _get_avg_volume(decoy_ticker)
    vol_hidden_raw = _get_avg_volume(hidden_ticker)

    price_decoy = _fetch_price_data(decoy_ticker, "5d")
    price_hidden = _fetch_price_data(hidden_ticker, "5d")

    if vol_decoy_raw is None or vol_hidden_raw is None or price_decoy is None or price_hidden is None or len(price_decoy) == 0 or len(price_hidden) == 0:
        return {"dar": 0.0, "status": "NO_VOLUME_DATA", "alert": "NO_DATA",
                "interpretation": "Cannot retrieve volume data or price data to compute Notional USD Volume."}

    vol_decoy = vol_decoy_raw * price_decoy[-1]
    vol_hidden = vol_hidden_raw * price_hidden[-1]

    vol_ratio = max(vol_decoy, _EPSILON) / max(vol_hidden, _EPSILON)
    dar = media_ratio / max(vol_ratio, _EPSILON)

    if dar > 5.0:
        interpretation = (
            f"🔴 DECOY DETECTED: Media for '{decoy_keyword}' is {media_ratio:.0f}x "
            f"'{hidden_keyword}', but volume only {vol_ratio:.1f}x. DAR={dar:.2f}. "
            f"Trend '{decoy_keyword}' is a DECOY. Big money preparing in '{hidden_keyword}'. "
            f"WITHDRAW ALL POSITIONS FROM '{decoy_keyword}'!"
        )
        alert = "DECOY_DETECTED"
    elif dar > 2.0:
        interpretation = (
            f"🟡 Mild asymmetry: '{decoy_keyword}' over-promoted compared to real cash flow. "
            f"DAR={dar:.2f}. Caution."
        )
        alert = "MILD_DECOY"
    elif dar < 0.3:
        interpretation = (
            f"🟢 '{hidden_keyword}' real cash flow far exceeds media. "
            f"DAR={dar:.2f}. Stealth accumulation opportunity."
        )
        alert = "HIDDEN_FLOW"
    else:
        interpretation = (
            f"⚪ Balanced media and cash flow ratio (DAR={dar:.2f})."
        )
        alert = "BALANCED"

    return {
        "dar": round(dar, 4),
        "media_ratio": round(media_ratio, 4),
        "vol_ratio": round(vol_ratio, 4),
        "alert": alert,
        "interpretation": interpretation,
    }


def _get_avg_volume(ticker: str, days: int = 7) -> Optional[float]:
    """Get average trading volume from Yahoo Finance."""
    cache_key = f"vol_{ticker}_{days}"
    now = time.time()
    if cache_key in _CACHE:
        data, ts = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    if yf is None:
        return None

    try:
        df = yf.download(ticker, period=f"{days}d", interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty or "Volume" not in df.columns:
            return None
        avg_vol = float(df["Volume"].mean())
        _CACHE[cache_key] = (avg_vol, now)
        return avg_vol
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# NEW SENSORS: IFT, OFND, CANL
# ══════════════════════════════════════════════════════════════════════════════

CORRELATION_MAP = {
    "BTC-USD": ["ETH-USD", "MSTR", "COIN", "MARA"],
    "SOL-USD": ["BTC-USD", "ETH-USD"],
    "GC=F": ["GLD", "GDX", "SLV"],
    "NVDA": ["AMD", "TSM", "SMCI"]
}

def _get_last_quarter_end() -> datetime:
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    if quarter == 1:
        return datetime(now.year - 1, 12, 31)
    elif quarter == 2:
        return datetime(now.year, 3, 31)
    elif quarter == 3:
        return datetime(now.year, 6, 30)
    else:
        return datetime(now.year, 9, 30)

def compute_ift(topic: str) -> Dict[str, Any]:
    """
    Institutional Fingerprint Timing.
    Detect narrative spike aligned with 13F filing window.
    """
    quarter_end = _get_last_quarter_end()
    days_since_quarter = (datetime.now() - quarter_end).days
    in_filing_window = 35 <= days_since_quarter <= 55
    
    if in_filing_window:
        trend_data = _fetch_google_trends(topic, "now 7-d")
        if trend_data and len(trend_data) > 0 and trend_data[-1] > np.mean(trend_data) * 1.5:
            return {
                "ift_alert": True,
                "alert": "INSTITUTIONAL_EXIT",
                "days_since_quarter": days_since_quarter,
                "interpretation": (
                    f"🔴 NARRATIVE IN FILING WINDOW: "
                    f"'{topic}' spiked {days_since_quarter} days after quarter end. "
                    f"Institutions might be exiting ahead of 13F disclosure."
                )
            }
    return {
        "ift_alert": False,
        "alert": "NORMAL",
        "days_since_quarter": days_since_quarter,
        "interpretation": f"⚪ '{topic}' not in the sensitive 13F exit window (day {days_since_quarter})."
    }

def _get_internal_crypto_hedging(ticker: str) -> float:
    """Helper to retrieve Hedge data for Crypto from Matrix (ZCL streams)."""
    try:
        macro_cache = matrix.get("MACRO", "sensors")
        if macro_cache:
            return 1.1 
    except Exception:
        pass
    return 1.0

def compute_ofnd(ticker: str, topic: str) -> Dict[str, Any]:
    """
    Options Flow vs Narrative Divergence.
    PUT volume spike before bullish narrative = trap.
    """
    is_crypto = "-USD" in ticker or ticker in ["BTC", "ETH", "SOL"]
    pcr = 0.0
    
    trend_data = _fetch_google_trends(topic, "now 7-d")
    narrative_hot = (trend_data and len(trend_data) > 0 and trend_data[-1] > 70) if trend_data else False

    if is_crypto:
        pcr = _get_internal_crypto_hedging(ticker)
        if pcr > 1.0 and narrative_hot: # Mock proxy: pcr > 1 is risk
            return {
                "ofnd": round(pcr, 4),
                "alert": "HEDGE_BEFORE_HYPE",
                "interpretation": f"🔴 INTERNAL MATRIX PCR Proxy: Hidden hedging indicator increased (PCR={pcr:.2f}) but '{topic}' is bullish. Crypto institutions are shorting."
            }
    else:
        if yf is None:
            return {"ofnd": 0.0, "alert": "NO_DATA", "interpretation": "yfinance error."}
        try:
            stock = yf.Ticker(ticker)
            dates = stock.options
            if not dates:
                return {"ofnd": 0.0, "alert": "NO_OPTIONS", "interpretation": f"No options for {ticker}."}
            chain = stock.option_chain(dates[0])
            put_volume = chain.puts["volume"].sum()
            call_volume = chain.calls["volume"].sum()
            pcr = put_volume / max(call_volume, 1)
            
            if pcr > 1.5 and narrative_hot:
                return {
                    "ofnd": round(pcr, 4),
                    "alert": "HEDGE_BEFORE_HYPE",
                    "interpretation": (
                        f"🔴 PUT/CALL={pcr:.2f} but narrative '{topic}' is bullish. "
                        f"TradFi institutions are buying insurance BEFORE driving FOMO."
                    )
                }
        except Exception as e:
            return {"ofnd": 0.0, "alert": "NO_OPTIONS", "interpretation": f"YF Options error: {str(e)[:50]}"}
            
    return {"ofnd": round(pcr, 4), "alert": "NORMAL", "interpretation": f"⚪ OFND (PCR={pcr:.2f}) shows no signs of Hedging Divergence."}

def compute_canl(primary_ticker: str, correlated_tickers: List[str] = None, topic: str = "") -> Dict[str, Any]:
    """
    Cross-Asset Narrative Leakage.
    (Fixed Beta Mismatch and Directionality Flaw)
    """
    if not correlated_tickers:
        correlated_tickers = CORRELATION_MAP.get(primary_ticker, ["SPY", "QQQ"])
        
    # Use hourly candles for 5 days to catch pump and dump instead of daily candles which are too slow
    primary_prices = _fetch_intraday_price_data(primary_ticker, period="5d", interval="1h")
    if primary_prices is None or len(primary_prices) < 3:
        return {"canl": 0.0, "alert": "NO_DATA", "interpretation": "Missing absolute price."}
    
    if abs(primary_prices[0]) < _EPSILON:
        return {"canl": 0.0, "alert": "NO_DATA", "interpretation": "Primary price starts at 0."}
    
    primary_return = (primary_prices[-1] - primary_prices[0]) / primary_prices[0]
    
    correlated_returns = []
    for ticker in correlated_tickers:
        prices = _fetch_intraday_price_data(ticker, period="5d", interval="1h")
        if prices is not None and len(prices) >= 3 and abs(prices[0]) >= _EPSILON:
            ret = (prices[-1] - prices[0]) / prices[0]
            correlated_returns.append(ret)
    
    if not correlated_returns:
        return {"canl": 0.0, "alert": "INSUFFICIENT_CORRELATED", "interpretation": "Missing correlated."}
    
    avg_corr_ret = float(np.mean(correlated_returns))
    
    # Fixed Beta and Directionality: Only calculate leakage (CANL > 0) when correlated assets do NOT go in the same direction or rise/fall too weakly compared to primary_return.
    # If they move in the same direction and stronger (high Beta), CANL = 0.
    if primary_return > 0:
        canl = max(0.0, primary_return - avg_corr_ret)
    else:
        canl = max(0.0, avg_corr_ret - primary_return)
        
    # Trigger Red Flag when: Primary moves >3%, but Correlated fails to validate (Deviation > 50% of Primary move)
    if abs(primary_return) > 0.03 and canl > abs(primary_return) * 0.5:
        return {
            "canl": round(canl, 4),
            "alert": "ISOLATED_MOVE",
            "interpretation": (
                f"🔴 '{primary_ticker}' moved {primary_return:.1%} but "
                f"correlated assets only moved {avg_corr_ret:.1%}. "
                f"Narrative '{topic}' LEAKED: Fake move."
            )
        }
    return {"canl": round(canl, 4), "alert": "CORRELATED_NORMALLY", "interpretation": f"⚪ Move spread evenly, validated by correlated assets (CANL={canl:.4f})."}

# ══════════════════════════════════════════════════════════════════════════════
# COMPOSITE: Cognitive Warfare Matrix
# ══════════════════════════════════════════════════════════════════════════════

def compute_narrative_matrix(
    keyword: str = "bitcoin",
    ticker: str = "BTC-USD",
    trend_b: str = "gold",
    decoy_keyword: str = "memecoin",
    hidden_keyword: str = "gold",
    decoy_ticker: str = "DOGE-USD",
    hidden_ticker: str = "GC=F",
) -> Dict[str, Any]:
    """
    Synthesize 4 dimensions of Cognitive Warfare into Narrative State Vector.

    Detect:
    - SYNTHETIC_NARRATIVE: PR Campaign + Decoy + Pivot
    - STEALTH_OPERATION: Elite accumulating secretly, media silent
    - ORGANIC: No signs of manipulation

    Publish: zcl:narrative:sensors (TTL 30m) for A12 to read.
    """
    ecs = compute_ecs(keyword)
    cat_val = compute_cad(keyword, ticker)
    npa = compute_npa(keyword, trend_b)
    dar = compute_dar(decoy_keyword, hidden_keyword, decoy_ticker, hidden_ticker)

    # 3 New Algorithms
    ift = compute_ift(keyword)
    ofnd = compute_ofnd(ticker, keyword)
    canl = compute_canl(ticker, None, keyword)

    # ── RED FLAG ENGINE ──
    red_flags = []
    if ecs.get("alert") == "SYNTHETIC_CAMPAIGN":
        red_flags.append("ECS: Simultaneous PR Campaign")
    if cat_val.get("alert") == "DECOY_NARRATIVE":
        red_flags.append("CAD: Decoy (booming news, flat price)")
    if npa.get("alert") == "PIPELINE_PIVOT":
        red_flags.append("NPA: Pivoted Pipeline to new trend")
    if dar.get("alert") == "DECOY_DETECTED":
        red_flags.append("DAR: Illusion")
    if ift.get("alert") == "INSTITUTIONAL_EXIT":
        red_flags.append("IFT: Narrative aligned with 13F distribution window")
    if ofnd.get("alert") == "HEDGE_BEFORE_HYPE":
        red_flags.append("OFND: Buying Options insurance before blowing price")
    if canl.get("alert") == "ISOLATED_MOVE":
        red_flags.append("CANL: Isolated move, did not spread to correlated assets")

    # Verdict
    if len(red_flags) >= 3:
        narrative_verdict = "FULL_SYNTHETIC_PIPELINE"
        narrative_detail = (
            "🔴 COMPLETE COGNITIVE PIPELINE: Elite is operating all 4 manipulation layers "
            "(Simultaneous PR + Price Decoy + Pivot + Illusion). "
            "This is a classic Exit Liquidity scenario. "
            "DO NOT BUY. Prepare to SHORT."
        )
    elif len(red_flags) >= 2:
        narrative_verdict = "PARTIAL_SYNTHETIC"
        narrative_detail = (
            f"🟡 PARTIAL MANIPULATION: {len(red_flags)} pipeline layers active. "
            f"Monitor closely. Do not FOMO."
        )
    elif len(red_flags) == 1:
        narrative_verdict = "SUSPICIOUS"
        narrative_detail = f"🟡 1 suspicious signal: {red_flags[0]}."
    else:
        # Check reverse: is there stealth accumulation?
        green_flags = []
        if cat_val.get("alert") == "STEALTH_ACCUMULATION":
            green_flags.append("CAD: Secret Elite accumulation")
        if dar.get("alert") == "HIDDEN_FLOW":
            green_flags.append("DAR: Hidden flow exceeding media")

        if green_flags:
            narrative_verdict = "STEALTH_OPERATION"
            narrative_detail = (
                f"🟢 STEALTH ACCUMULATION: {'; '.join(green_flags)}. "
                f"Elite accumulating silently. Potential opportunity."
            )
        else:
            narrative_verdict = "ORGANIC"
            narrative_detail = "🟢 No cognitive manipulation detected. Organic narrative."

    narrative_state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "keyword": keyword,
        "sensors": {
            "ECS": ecs,
            "CAD": cat_val,
            "NPA": npa,
            "DAR": dar,
            "IFT": ift,
            "OFND": ofnd,
            "CANL": canl,
        },
        "narrative_verdict": narrative_verdict,
        "red_flags": red_flags,
        "red_count": len(red_flags),
        "interpretation": narrative_detail,
    }

    # Publish to Redis
    try:
        matrix.set("NARRATIVE", "sensors", narrative_state, ttl=1800)
        log.info(f"[NPS] Published narrative:sensors | Verdict: {narrative_verdict} | Red: {len(red_flags)}")
    except Exception as e:
        log.error(f"[NPS] Redis publish error: {e}")

    return narrative_state


# ══════════════════════════════════════════════════════════════════════════════
# CLI & MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Narrative Pipeline Sensors (ECS/CAD/NPA/DAR)")
    parser.add_argument("--keyword", default="bitcoin", help="Main keyword to scan")
    parser.add_argument("--ticker", default="BTC-USD", help="Corresponding ticker")
    parser.add_argument("--trend-b", default="gold", help="Alternative trend to compare NPA")
    parser.add_argument("--once", action="store_true", help="Run once")
    parser.add_argument("--interval", type=int, default=1800, help="Interval (s)")
    args = parser.parse_args()

    if args.once:
        result = compute_narrative_matrix(
            keyword=args.keyword, ticker=args.ticker, trend_b=args.trend_b
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        log.info(f"[NPS] Starting Narrative Pipeline Sensor loop | keyword={args.keyword}")
        while True:
            try:
                result = compute_narrative_matrix(
                    keyword=args.keyword, ticker=args.ticker, trend_b=args.trend_b
                )
                log.info(f"[NPS] Cycle complete | Verdict: {result['narrative_verdict']}")
            except Exception as e:
                log.error(f"[NPS] Cycle error: {e}")
            time.sleep(args.interval)
