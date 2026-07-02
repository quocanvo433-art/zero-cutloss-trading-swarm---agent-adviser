"""
🧬 DNA: v17.0 (Sovereign Purity) [DNA Header] | Unified Macro Radar - 16D Tensor
🏢 UNIT: MACRO_FLOW_SENSOR (A10 Extension)
🛠️ ROLE: GEOPOLITICAL_RADAR & MEGA_TENSOR
📖 DESC: Unified 13 Macro Sensors (GEO, OFI, GLS, REP, SHD, CRA, YC, INV, CFV, SDD, IRD, MRD, BCDT).
"""

import sys, os, time, json, logging
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import yfinance as yf
except ImportError:
    yf = None

from tools.imperial_state import matrix
from tools.megafeed_engine import MEGAFEED_RSS, ELITE_KEYWORDS, fetch_feed, VELOCITY_BASELINE

log = logging.getLogger("MACRO_RADAR")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

_CACHE = {}
_CACHE_TTL = 1800

# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Fetch & Compute
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_prices(ticker: str, period: str = "3mo", interval: str = "1d"):
    cache_key = f"{ticker}_{period}_{interval}"
    now = time.time()
    if cache_key in _CACHE:
        data, ts = _CACHE[cache_key]
        if now - ts < _CACHE_TTL: return data
    if yf is None: return None
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty: return None
        closes = df["Close"].values.astype(float).flatten()
        _CACHE[cache_key] = (closes, now)
        return closes
    except Exception as e:
        log.warning(f"[MACRO] fetch error for {ticker}: {e}")
        return None

def _fetch_vwap(ticker: str, period: str = "3mo"):
    cache_key = f"{ticker}_vwap_{period}"
    now = time.time()
    if cache_key in _CACHE:
        data, ts = _CACHE[cache_key]
        if now - ts < _CACHE_TTL: return data
    if yf is None: return None
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df.empty or 'Volume' not in df.columns: return None
        close = df["Close"].values.astype(float).flatten()
        vol = df["Volume"].values.astype(float).flatten()
        if np.sum(vol) == 0: return None
        vwap = np.sum(close * vol) / np.sum(vol)
        _CACHE[cache_key] = (float(vwap), now)
        return float(vwap)
    except: return None

def _roc(prices: np.ndarray, period: int = 14) -> np.ndarray:
    if len(prices) < period + 1: return np.array([0.0])
    return (prices[period:] - prices[:-period]) / prices[:-period] * 100

def _z_score(series: np.ndarray) -> float:
    if len(series) < 5: return 0.0
    mean, std = np.mean(series), np.std(series)
    return float((series[-1] - mean) / std) if std >= 1e-10 else 0.0

def _sma(prices: np.ndarray, period: int = 20) -> float:
    if len(prices) < period: return float(prices[-1]) if len(prices) > 0 else 0.0
    return float(np.mean(prices[-period:]))

def _pearson_rolling(series_a: np.ndarray, series_b: np.ndarray, window: int = 14) -> float:
    min_len = min(len(series_a), len(series_b))
    if min_len < window: return 0.0
    a, b = series_a[-window:], series_b[-window:]
    a_diff, b_diff = a - np.mean(a), b - np.mean(b)
    denom = np.sqrt(np.sum(a_diff**2) * np.sum(b_diff**2))
    return float(np.sum(a_diff * b_diff) / denom) if denom >= 1e-10 else 0.0

# ══════════════════════════════════════════════════════════════════════════════
# OLD SENSORS: GEO & OFI
# ══════════════════════════════════════════════════════════════════════════════

def compute_geopolitical_risk() -> dict:
    geo_sources = MEGAFEED_RSS.get("geopolitical", {})
    all_entries, futures = [], []
    with ThreadPoolExecutor(max_workers=5) as executor:
        for src_name, feed_info in geo_sources.items():
            futures.append(executor.submit(fetch_feed, "geopolitical", src_name, feed_info))
        for future in as_completed(futures):
            try:
                all_entries.extend(future.result() or [])
            except Exception as e:
                log.error(f"Feed error: {e}")
    keywords = ELITE_KEYWORDS.get("geopolitical", []) + ELITE_KEYWORDS.get("policy", [])
    hits, detected = 0, {}
    for entry in all_entries:
        text = entry["title"].lower()
        hit_words = [kw for kw in keywords if kw.lower() in text]
        if hit_words:
            hits += 1
            for w in hit_words: detected[w] = detected.get(w, 0) + 1
    baseline = VELOCITY_BASELINE.get("geopolitical", 5.0)
    velocity = hits / baseline if baseline > 0 else 0
    geo_score = min(10.0, velocity * 2.0)
    alert = "GEO_CRITICAL" if geo_score > 8.0 else ("GEO_CAUTION" if geo_score > 6.0 else "NEUTRAL")
    return {
        "geo_score": float(round(geo_score, 2)), "velocity": float(round(velocity, 2)),
        "top_topics": [str(t[0]) for t in sorted(detected.items(), key=lambda x: x[1], reverse=True)[:3]],
        "alert": alert, "hits": int(hits)
    }

def compute_options_flow() -> dict:
    total_put, total_call = 0, 0
    try:
        for t in ["SPY", "QQQ"]:
            tk = yf.Ticker(t)
            if not tk.options: continue
            opt = tk.option_chain(tk.options[0])
            total_call += opt.calls['volume'].sum() if 'volume' in opt.calls else 0
            total_put += opt.puts['volume'].sum() if 'volume' in opt.puts else 0
        pc_ratio = total_put / total_call if total_call > 0 else 1.0
        ofi_score = min(10.0, max(0.0, (pc_ratio - 0.8) * 10.0))
        alert = "EXTREME_HEDGING" if pc_ratio > 2.0 else ("HEAVY_HEDGING" if pc_ratio > 1.5 else "NORMAL")
        return {
            "ofi_score": float(round(ofi_score, 2)), "put_call_ratio": float(round(pc_ratio, 2)),
            "unusual_volume": bool(pc_ratio > 1.5), "alert": alert
        }
    except: return {"ofi_score": 0.0, "put_call_ratio": 1.0, "unusual_volume": False, "alert": "ERROR"}

# ══════════════════════════════════════════════════════════════════════════════
# OLD SENSORS: GLS, REP, SHD, CRA, YC, INV
# ══════════════════════════════════════════════════════════════════════════════

def compute_gls() -> dict:
    dxy = _fetch_prices("DX-Y.NYB")
    if dxy is None:
        dxy = _fetch_prices("UUP")
    us10y = _fetch_prices("^TNX")
    if dxy is None or us10y is None: return {"gls": 0.0, "alert": "NO_DATA"}
    z_dxy, z_us10y = _z_score(_roc(dxy, 14)), _z_score(_roc(us10y, 14))
    gls = z_dxy + z_us10y
    if gls > 2.0: alert = "LIQUIDITY_SQUEEZE"
    elif gls > 1.0: alert = "ELEVATED"
    elif gls < -2.0: alert = "LIQUIDITY_FLUSH"
    elif gls < -1.0: alert = "FAVORABLE"
    else: alert = "NEUTRAL"
    return {"gls": round(gls, 4), "z_dxy": round(z_dxy, 4), "z_us10y": round(z_us10y, 4), "alert": alert}

def compute_rep() -> dict:
    copper, gold = _fetch_prices("HG=F"), _fetch_prices("GC=F")
    if copper is None or gold is None: return {"rep": 0.0, "alert": "NO_DATA"}
    sma_copper, sma_gold = _sma(copper, 20), _sma(gold, 20)
    if sma_gold < 1e-10: return {"rep": 0.0, "alert": "NO_DATA"}
    rep = sma_copper / sma_gold
    rep_trend = 0.0
    if len(copper) >= 35 and len(gold) >= 35:
        rep_series = [np.mean(copper[max(0, i-20):i]) / np.mean(gold[max(0, i-20):i]) for i in range(20, min(len(copper), len(gold)))]
        rep_roc = _roc(np.array(rep_series), 14)
        rep_trend = float(rep_roc[-1]) if len(rep_roc) > 0 else 0.0
    alert = "REAL_ECONOMY_DECLINE" if rep_trend < -5 else ("SOFTENING" if rep_trend < -2 else ("EXPANSION" if rep_trend > 5 else "NEUTRAL"))
    return {"rep": round(rep, 6), "rep_trend": round(rep_trend, 4), "alert": alert}

def compute_shd() -> dict:
    spy, vix = _fetch_prices("SPY"), _fetch_prices("^VIX")
    if spy is None or vix is None: return {"shd": 0.0, "alert": "NO_DATA"}
    shd = _pearson_rolling(_roc(spy, 14), _roc(vix, 14), 14)
    alert = "SHADOW_HEDGE_DETECTED" if shd > 0.3 else ("SUSPICIOUS" if shd > 0 else "NORMAL")
    return {"shd": round(shd, 4), "vix_current": float(vix[-1]) if len(vix)>0 else 0, "alert": alert}

def compute_cra() -> dict:
    hyg, tlt = _fetch_prices("HYG"), _fetch_prices("TLT")
    if hyg is None or tlt is None: return {"cra": 0.0, "alert": "NO_DATA"}
    cra_current = float(hyg[-1]) / float(tlt[-1]) if float(tlt[-1]) > 0 else 0
    min_len = min(len(hyg), len(tlt))
    cra_roc = _roc(hyg[-min_len:] / tlt[-min_len:], 14)
    cra_z = _z_score(cra_roc) if len(cra_roc) >= 5 else 0.0
    alert = "CREDIT_COLLAPSE" if cra_z < -2.0 else ("CREDIT_WEAKENING" if cra_z < -1.0 else ("CREDIT_EUPHORIA" if cra_z > 2.0 else "NEUTRAL"))
    return {"cra": round(cra_current, 6), "cra_z": round(cra_z, 4), "alert": alert}

def compute_yield_curve() -> dict:
    us10y, us30y, us02y = _fetch_prices("^TNX", period="1mo"), _fetch_prices("^TYX", period="1mo"), _fetch_prices("^IRX", period="1mo")
    if us10y is None or us30y is None or us02y is None: return {"alert": "NO_DATA", "veto_long": False}
    val_10y, val_02y = float(us10y[-1]), float(us02y[-1])
    spread = val_10y - val_02y
    veto_long, agg_long_signal, alert = False, False, "NEUTRAL"
    if val_10y > 4.5 and val_02y > 5.0: alert, veto_long = "YIELD_SHOCK", True
    elif spread < 0 and _roc(us10y, 5)[-1] > 2: alert, veto_long = "LIQUIDATION_CASCADE", True
    elif val_10y < 3.8 and _roc(us10y, 5)[-1] < -3: alert, agg_long_signal = "YIELD_BREAKDOWN", True
    return {"us10y": val_10y, "us02y": val_02y, "spread": spread, "alert": alert, "veto_long": veto_long, "agg_long_signal": agg_long_signal}

def compute_macro_inventory() -> dict:
    gold, gold_vwap = _fetch_prices("GC=F", period="1mo"), _fetch_vwap("GC=F", period="3mo")
    if gold is None or gold_vwap is None: return {"alert": "NO_DATA"}
    gold_price = float(gold[-1])
    dist = (gold_price - gold_vwap) / gold_vwap * 100
    distribution, liq_cascade, alert = False, False, "NEUTRAL"
    if dist > 10 and _roc(gold, 5)[-1] > 2: alert, distribution = "FAKE_NARRATIVE_DISTRIBUTION", True
    elif dist < 0 and _roc(gold, 5)[-1] < -3: alert, liq_cascade = "HEDGE_LIQUIDATION", True
    return {"gold_price": gold_price, "alert": alert, "distribution_divergence": distribution, "liquidity_cascade": liq_cascade}

# ══════════════════════════════════════════════════════════════════════════════
# NEW SENSORS (CFV, SDD, IRD, MRD, BCDT)
# ══════════════════════════════════════════════════════════════════════════════

def compute_cross_asset_flow_velocity() -> dict:
    assets = {"EQUITY": "SPY", "BOND": "TLT", "COMMODITY": "GLD", "CRYPTO": "BTC-USD"}
    prices = {n: _fetch_prices(t, "3mo") for n, t in assets.items() if _fetch_prices(t, "3mo") is not None}
    if len(prices) < 3: return {"alert": "INSUFFICIENT_DATA"}
    roc_short = {n: _roc(p, 5)[-1] if len(p)>=6 else 0 for n, p in prices.items()}
    roc_long = {n: _roc(p, 20)[-1] if len(p)>=21 else 0 for n, p in prices.items()}
    flow_matrix, inflow_score = {}, {n: 0.0 for n in prices.keys()}
    for i, a in enumerate(prices.keys()):
        for j, b in enumerate(prices.keys()):
            if i >= j: continue
            ds, dl = roc_short[b] - roc_short[a], roc_long[b] - roc_long[a]
            accel = ds - dl
            flow_matrix[f"{a}_to_{b}"] = {"delta_5d": round(ds, 3), "acceleration": round(accel, 3)}
            if ds > 0: inflow_score[b] += abs(ds); inflow_score[a] -= abs(ds)
            else: inflow_score[a] += abs(ds); inflow_score[b] -= abs(ds)
    high_accel = [k for k, v in flow_matrix.items() if abs(v["acceleration"]) > 2.0]
    rotation = len(high_accel) >= 2
    return {
        "rotation_detected": rotation, "alert": "ROTATION_EVENT" if rotation else "STABLE",
        "capital_destination": max(inflow_score, key=inflow_score.get),
        "capital_source": min(inflow_score, key=inflow_score.get)
    }

def compute_stablecoin_dominance() -> dict:
    try:
        r_st = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={"vs_currency": "usd", "ids": "tether,usd-coin,dai", "order": "market_cap_desc"}, timeout=15)
        r_btc = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={"vs_currency": "usd", "ids": "bitcoin"}, timeout=15)
        if r_st.status_code != 200 or r_btc.status_code != 200: return {"alert": "API_ERROR"}
        stables, btc = r_st.json(), r_btc.json()[0]
        stable_mc_change_24h = sum(c.get("market_cap_change_percentage_24h", 0) or 0 for c in stables) / max(len(stables), 1)
        btc_change_24h = btc.get("price_change_percentage_24h", 0) or 0
        phase = "NEUTRAL"
        if stable_mc_change_24h > 0.5 and btc_change_24h < -2: phase = "ACCUMULATION"
        elif stable_mc_change_24h < -0.5 and btc_change_24h > 2: phase = "DEPLOYMENT"
        elif stable_mc_change_24h < -0.5 and btc_change_24h < -2: phase = "EXIT"
        elif stable_mc_change_24h > 1.0 and btc_change_24h > 2: phase = "INFLOW"
        return {"phase": phase, "alert": phase, "stable_mc_change": round(stable_mc_change_24h, 2), "btc_change": round(btc_change_24h, 2)}
    except Exception as e: return {"alert": "ERROR", "error": str(e)}

def compute_institutional_rebalance() -> dict:
    tickers = {"SPY": "equity", "TLT": "bond", "GLD": "commodity", "BTC-USD": "crypto"}
    signals = []
    for t, cls in tickers.items():
        try:
            df = yf.download(t, period="3mo", interval="1d", progress=False)
            if df.empty or len(df) < 30: continue
            close, vol = df["Close"].values.astype(float).flatten(), df["Volume"].values.astype(float).flatten()
            vol_mean, vol_std, vol_recent = np.mean(vol), np.std(vol), np.mean(vol[-5:])
            vol_z = (vol_recent - vol_mean) / vol_std if vol_std > 0 else 0
            price_change = (close[-1] - close[-5]) / close[-5] * 100 if close[-5] > 0 else 0
            if vol_z > 1.5 and abs(price_change) < 1.5:
                signals.append({"asset": t, "class": cls, "direction": "OUTFLOW" if vol_z > 2 else "INFLOW"})
        except: continue
    return {"rebalance_signals": signals, "alert": "INSTITUTIONAL_REBALANCE" if len(signals) >= 2 else "NORMAL"}

def compute_monetary_regime() -> dict:
    dxy, us10y, gold = _fetch_prices("DX-Y.NYB", "1mo"), _fetch_prices("^TNX", "1mo"), _fetch_prices("GC=F", "1mo")
    if dxy is None or us10y is None or gold is None: return {"regime": "UNKNOWN", "alert": "NO_DATA"}
    roc_dxy, roc_yield, roc_gold = _roc(dxy, 10)[-1] if len(dxy)>10 else 0, _roc(us10y, 10)[-1] if len(us10y)>10 else 0, _roc(gold, 10)[-1] if len(gold)>10 else 0
    if roc_dxy > 1 and roc_yield > 1 and roc_gold < -1: regime = "TIGHTENING"
    elif roc_dxy < -1 and roc_yield < -1 and roc_gold > 1: regime = "EASING"
    elif roc_dxy > 1 and roc_yield < -1 and roc_gold > 1: regime = "CRISIS"
    elif roc_dxy < -1 and roc_yield > 1 and roc_gold < -1: regime = "EUPHORIA"
    else: regime = "TRANSITIONAL"
    return {"regime": regime, "alert": regime}

def compute_bond_crypto_lead_lag() -> dict:
    tlt, btc = _fetch_prices("TLT", "6mo", "1d"), _fetch_prices("BTC-USD", "6mo", "1d")
    if tlt is None or btc is None: return {"alert": "NO_DATA"}
    min_len = min(len(tlt), len(btc))
    tlt, btc = tlt[-min_len:], btc[-min_len:]
    tlt_ret, btc_ret = np.diff(tlt)/tlt[:-1], np.diff(btc)/btc[:-1]
    correlations = {}
    for lag in range(0, 31):
        if lag >= len(tlt_ret) - 10: break
        a, b = (tlt_ret, btc_ret) if lag == 0 else (tlt_ret[:-lag], btc_ret[lag:])
        ml = min(len(a), len(b))
        if ml >= 10: correlations[lag] = round(np.corrcoef(a[-ml:], b[-ml:])[0,1], 4)
    if not correlations: return {"alert": "INSUFFICIENT_DATA"}
    opt_lag = max(correlations, key=lambda k: abs(correlations[k]))
    opt_corr = correlations[opt_lag]
    tlt_mom = (tlt[-1] - tlt[-5])/tlt[-5]*100 if len(tlt)>=5 else 0
    forecast = "NEUTRAL"
    if opt_corr > 0.3:
        if tlt_mom > 1: forecast = "BTC_BULLISH"
        elif tlt_mom < -1: forecast = "BTC_BEARISH"
    else: forecast = "DECOUPLED"
    return {"optimal_lag_days": int(opt_lag), "optimal_correlation": float(opt_corr), "forecast": forecast, "alert": forecast}

# ══════════════════════════════════════════════════════════════════════════════
# COMPOSITE & PUBLISH
# ══════════════════════════════════════════════════════════════════════════════

def compute_macro_matrix() -> dict:
    log.info("[MACRO_RADAR] Computing 13 Macro Sensors...")
    sensors = {
        "GEO": compute_geopolitical_risk(),
        "OFI": compute_options_flow(),
        "GLS": compute_gls(),
        "REP": compute_rep(),
        "SHD": compute_shd(),
        "CRA": compute_cra(),
        "YIELD_CURVE": compute_yield_curve(),
        "MACRO_INVENTORY": compute_macro_inventory(),
        "CFV": compute_cross_asset_flow_velocity(),
        "SDD": compute_stablecoin_dominance(),
        "IRD": compute_institutional_rebalance(),
        "MRD": compute_monetary_regime(),
        "BCDT": compute_bond_crypto_lead_lag(),
    }
    
    # Simple VETO logic based on critical components
    veto_long = sensors["YIELD_CURVE"].get("veto_long", False) or sensors["GLS"].get("alert") == "LIQUIDITY_SQUEEZE"
    
    red_alerts = [k for k, v in sensors.items() if "CRITICAL" in str(v.get("alert", "")) or "SQUEEZE" in str(v.get("alert", "")) or "COLLAPSE" in str(v.get("alert", ""))]
    
    macro_verdict = "NEUTRAL"
    if veto_long: macro_verdict = "MACRO_VETO_LONG"
    elif len(red_alerts) >= 2: macro_verdict = "MACRO_CRISIS_IMMINENT"
    elif sensors["YIELD_CURVE"].get("agg_long_signal"): macro_verdict = "MACRO_AGGRESSIVE_LONG"

    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sensors": sensors,
        "macro_verdict": macro_verdict,
        "red_count": len(red_alerts),
        "red_alerts": red_alerts
    }
    
    try:
        matrix.set("MACRO", "sensors", state, ttl=1800)
        log.info(f"[MACRO_RADAR] Published macro:sensors | Verdict: {macro_verdict} | Algo: 13")
    except Exception as e:
        log.error(f"Redis Publish Error: {e}")
        
    return state

if __name__ == "__main__":
    if "--once" in sys.argv:
        print(json.dumps(compute_macro_matrix(), indent=2, ensure_ascii=False))
