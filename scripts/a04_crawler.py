import os
from datetime import datetime, timezone
"""
🧬 DNA: v17.0 (Sovereign Purity & Dynamic Streaming)
🏢 UNIT: CRAWLER_A04 (A04 STREAM)
🛠️ ROLE: EXTERNAL_METRICS_INGESTION
📖 DESC: Independent crawler that fetches OHLCV and calculates VSA, KAR, PEI to push into the stream for A04.
🔗 CALLS: tools/A04_BRAIN_HELPER.py, tools/imperial_state.py
📟 I/O: Redis: A04:kinematics_stream
🛡️ INTEGRITY: Persistent-Crawler
"""
import sys
import time
import json
import traceback
from pathlib import Path

PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(PROJECT_ROOT / "agents"))
sys.path.append(str(PROJECT_ROOT / "tools"))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "config" / ".env")

import ccxt
import redis
from tools.A04_BRAIN_HELPER import (
    lay_ohlcv, 
    _phan_tich_wyckoff_don_gian, 
    _phan_tich_elliott,
    _phan_tich_ob_snapshot,
    _phan_tich_micro_trades,
    fingerprint_composite_man,
)
from agents.logic.a04_brain import _phan_tich_vsa_thong_minh

redis_host = "redis" if os.getenv("WORKSPACE_DIR") else "localhost"
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', redis_host), 
    port=6379, 
    db=0, 
    password=os.getenv("REDIS_PASSWORD"), 
    decode_responses=True
)

exchange = ccxt.binance({"enableRateLimit": True})

def cawl_and_stream():
    ma_coin = "BTC/USDT"
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Activating A04 Streamer Crawler: {ma_coin}...")
    
    # 1. FETCH OHLCV CANDLES
    khung_time = {
        "1w": 100,
        "1d": 200,
        "4h": 200,
        "1h": 200,
        "15m": 200,
        "1s": 300
    }
    
    ohlcv_spot = {}
    ohlcv_future = {}
    for k, so_nen in khung_time.items():
        try:
            ohlcv_spot[k] = lay_ohlcv(ma_coin, k, so_nen=so_nen, default_type='spot')
        except Exception as e:
            print(f"Error fetching Spot candles {k}: {e}")
            ohlcv_spot[k] = []
            
        try:
            # For 1s, Future might not be supported or restricted, handle safely
            ohlcv_future[k] = lay_ohlcv(ma_coin, k, so_nen=so_nen, default_type='future')
        except Exception as e:
            print(f"Error fetching Future candles {k}: {e}")
            ohlcv_future[k] = []
            
    # Support backward compatibility for components using ohlcv_data
    ohlcv_data = ohlcv_spot
            
    # 2. CALCULATE STANDARD KINEMATICS
    kinematics_results = {
        "spot": {},
        "futures": {}
    }
    
    # Calculate Spot
    for k, data in ohlcv_spot.items():
        if not data or len(data) == 0:
            continue
        try:
            w = _phan_tich_wyckoff_don_gian(data)
            e = _phan_tich_elliott(data)
            v = _phan_tich_vsa_thong_minh(data)
            if "kinematics_history" in v:
                del v["kinematics_history"] # Reduce size
            kinematics_results["spot"][k] = {
                "wyckoff": w,
                "elliott": e,
                "vsa": v
            }
        except Exception as e:
            print(f"Error analyzing Spot mathematics for timeframe {k}: {e}")
            
    # Calculate Futures
    for k, data in ohlcv_future.items():
        if not data or len(data) == 0:
            continue
        try:
            w = _phan_tich_wyckoff_don_gian(data)
            e = _phan_tich_elliott(data)
            v = _phan_tich_vsa_thong_minh(data)
            if "kinematics_history" in v:
                del v["kinematics_history"] # Reduce size
            kinematics_results["futures"][k] = {
                "wyckoff": w,
                "elliott": e,
                "vsa": v
            }
        except Exception as e:
            print(f"Error analyzing Futures mathematics for timeframe {k}: {e}")

    # 3. FETCH ORDERBOOK & TRADES FROM CCXT
    try:
        ob = exchange.fetch_order_book(ma_coin, limit=50)
        ob_res = _phan_tich_ob_snapshot({"orderbook": ob})
    except Exception as e:
        print(f"Error analyzing Orderbook: {e}")
        ob_res = {"status": "ERROR", "details": str(e)}
        
    try:
        raw_trades = exchange.fetch_trades(ma_coin.replace("/", ""), limit=500)
        trades_list = [{"price": t["price"], "amount": t["amount"], "side": t["side"], "timestamp": t["timestamp"]} for t in raw_trades]
        trades_res = _phan_tich_micro_trades({"recent_trades": trades_list}, ma_coin)
    except Exception as e:
        print(f"Error analyzing Micro-Trades: {e}")
        trades_res = {"status": "ERROR", "details": str(e)}

    # 4. CALCULATE CM FINGERPRINT: 2 VERSIONS (HTF & LTF)
    cm_htf = {}
    for k in ["1d", "4h", "15m"]:
        if ohlcv_data.get(k):
            try:
                cm_htf[k] = fingerprint_composite_man(ohlcv_data[k], n_recent=20)
            except: pass

    cm_ltf = {}
    for k in ["4h", "15m", "1s"]:
        if ohlcv_data.get(k):
            try:
                cm_ltf[k] = fingerprint_composite_man(ohlcv_data[k], n_recent=20)
            except: pass

    # 4.5 FETCH OFI CANDLES (Use Raw Binance API to get Taker Buy Vol)
    import requests
    ofi_candles = {}
    for tf in ["15m", "1h", "4h", "1d"]:
        try:
            url = "https://fapi.binance.com/fapi/v1/klines"
            params = {"symbol": ma_coin.replace("/", ""), "interval": tf, "limit": 20}
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                klines = resp.json()
                tf_ofi = []
                for k in klines:
                    v_buy = float(k[9])  # Taker buy base asset volume
                    v_sell = float(k[5]) - v_buy # Total volume - Taker buy volume
                    tf_ofi.append({"ts": k[0], "buy": v_buy, "sell": v_sell, "ofi": v_buy - v_sell})
                ofi_candles[tf] = tf_ofi
            else:
                ofi_candles[tf] = []
        except Exception as e:
            print(f"Error fetching OFI {tf}: {e}")
            ofi_candles[tf] = []

    # 4.6 DETECT SPOOFING (Moved from A01)
    spoofing_warning = "NORMAL"
    try:
        if ohlcv_data.get("1m") and len(ohlcv_data["1m"]) >= 2:
            current_price = ohlcv_data["1m"][-1][4]
            previous_price = ohlcv_data["1m"][-2][4]
            price_change = current_price - previous_price
            
            total_bid = ob_res.get("total_bid_qty", 0)
            total_ask = ob_res.get("total_ask_qty", 0)
            
            SPOOF_THRESHOLD_PRICE = float(os.getenv("SPOOF_THRESHOLD", "2.5"))
            
            if total_ask > total_bid * SPOOF_THRESHOLD_PRICE and price_change >= 0:
                spoofing_warning = "FAKE_BULLISH_TRAP"
            elif total_bid > total_ask * SPOOF_THRESHOLD_PRICE and price_change <= 0:
                spoofing_warning = "FAKE_BEARISH_TRAP"
    except Exception as e:
        print(f"Error calculating Spoofing: {e}")

    # 4.7 CALCULATE LIQUIDITY SUFFICIENCY
    sufficiency_report = {}
    try:
        import requests
        clean_sym = ma_coin.replace("/", "")
        oi_raw = 0.0
        funding_raw = 0.0
        
        # Open Interest
        r_oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={clean_sym}", timeout=3)
        if r_oi.status_code == 200:
            oi_raw = float(r_oi.json().get('openInterest', 0))
            
        # Funding Rate
        r_fr = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={clean_sym}", timeout=3)
        if r_fr.status_code == 200:
            fr_data = r_fr.json()
            if isinstance(fr_data, list): fr_data = fr_data[0]
            funding_raw = float(fr_data.get('lastFundingRate', 0))

        # Get/Update Peak OI
        peak_oi = 0.0
        try:
            peak_key = f"zcl:a04:peak_oi:{clean_sym}"
            stored_peak = redis_client.get(peak_key)
            if stored_peak:
                peak_oi = float(stored_peak)
            if oi_raw > peak_oi:
                peak_oi = oi_raw
                redis_client.set(peak_key, str(peak_oi))
        except Exception:
            pass
        if peak_oi == 0.0:
            peak_oi = oi_raw if oi_raw > 0 else 1.0

        from tools.A04_BRAIN_HELPER import LiquiditySufficiencyModel
        model = LiquiditySufficiencyModel()
        sufficiency_report = model.evaluate_maturity(
            ohlcv_spot.get("1d", []), oi_raw, peak_oi, funding_raw, ob_res, trades_res, redis_client
        )
    except Exception as e:
        print(f"Error calculating Liquidity Sufficiency: {e}")

    # 5. PACKAGE AND SEND TO REDIS STREAM
    payload = {
        "timestamp": int(time.time()),
        "kinematics": kinematics_results,
        "orderbook_snapshot": ob_res,
        "micro_trades": trades_res,
        "cm_fingerprint_htf": cm_htf, # 1d, 4h, 15m
        "cm_fingerprint_ltf": cm_ltf, # 4h, 15m, 1s
        "ofi_candles": ofi_candles,
        "spoofing_warning": spoofing_warning,
        "sufficiency_report": sufficiency_report,
        "oi_raw": oi_raw,
        "funding_raw": funding_raw
    }
    
    # XADD into stream
    try:
        stream_key = "zcl:a04:kinematics_stream"
        payload_str = json.dumps(payload, ensure_ascii=False)
        redis_client.xadd(stream_key, {"payload": payload_str}, maxlen=1440) # Keep max 1440 minutes (24h)
        print(f"[{time.strftime('%H:%M:%S')}] Successfully ingested Kinematics ecosystem (Bytes: {len(payload_str)}) into {stream_key}")
    except Exception as e:
        print(f"Error pushing to Redis Stream: {e}")

    # ══════════════════════════════════════════════════════════════
    # MATRIX FIFO: 2 Redis LISTs accumulating for A04 LLM Prompt
    # ══════════════════════════════════════════════════════════════

    # --- MATRIX 100H (1 entry/hour, FIFO max 100) ---
    try:
        candles_h = ohlcv_data.get("1h", [])
        if candles_h and len(candles_h) > 0:
            last_h = candles_h[-1]
            ts_ms, c, h, l = last_h[0], last_h[4], last_h[2], last_h[3]
            
            kin_1h = kinematics_results.get("spot", {}).get("1h", {})
            vsa_1h = kin_1h.get("vsa", {})
            wy_1h = kin_1h.get("wyckoff", {})
            ell_1h = kin_1h.get("elliott", {})
            kin_vec = vsa_1h.get("kinematics", {})
            
            now_hour = time.strftime('%m-%d %H')
            entry_100h = (
                f"[{time.strftime('%m-%d %H:%M')}] ${c:,.0f}"
                f"|H:{h:,.0f}|L:{l:,.0f}"
                f"|VSA:{vsa_1h.get('label', '?')}"
                f"|KAR:{kin_vec.get('kar', 0):.1f}"
                f"|MNR:{kin_vec.get('mnr', 0):.1f}"
                f"|PEI:{kin_vec.get('pei', 0):.1f}"
                f"|W:{wy_1h.get('phase', '?')}"
                f"|E:{ell_1h.get('current_wave', '?')}"
            )
            
            # Dedup: same hour -> update (rpop + rpush). New hour -> pure rpush.
            last_entry = redis_client.lindex("zcl:a04:matrix_100h", -1)
            if last_entry and now_hour in last_entry[:11]:
                redis_client.rpop("zcl:a04:matrix_100h")
            
            redis_client.rpush("zcl:a04:matrix_100h", entry_100h)
            redis_client.ltrim("zcl:a04:matrix_100h", -100, -1)
    except Exception as e:
        print(f"Error writing matrix_100h: {e}")

    # --- MATRIX 70D (1 entry/day, FIFO max 70) ---
    try:
        candles_d = ohlcv_data.get("1d", [])
        if candles_d and len(candles_d) > 0:
            last_d = candles_d[-1]
            ts_ms, c, h, l = last_d[0], last_d[4], last_d[2], last_d[3]
            
            kin_1d = kinematics_results.get("spot", {}).get("1d", {})
            vsa_1d = kin_1d.get("vsa", {})
            wy_1d = kin_1d.get("wyckoff", {})
            wy_1w = kinematics_results.get("spot", {}).get("1w", {}).get("wyckoff", {})
            ell_1d = kin_1d.get("elliott", {})
            kin_vec = vsa_1d.get("kinematics", {})
            
            today_str = time.strftime('%Y-%m-%d')
            entry_70d = (
                f"[{today_str}] C:${c:,.0f}|H:${h:,.0f}|L:${l:,.0f}"
                f"|VSA:{vsa_1d.get('label', '?')}"
                f"|KAR:{kin_vec.get('kar', 0):.2f}"
                f"|W:{wy_1w.get('phase', '?')}|D:{wy_1d.get('phase', '?')}"
                f"|E:{ell_1d.get('current_wave', '?')}"
            )
            
            # Dedup: same day -> update. New day -> push.
            last_entry = redis_client.lindex("zcl:a04:matrix_70d", -1)
            if last_entry and today_str in last_entry[:12]:
                redis_client.rpop("zcl:a04:matrix_70d")
            
            redis_client.rpush("zcl:a04:matrix_70d", entry_70d)
            redis_client.ltrim("zcl:a04:matrix_70d", -70, -1)
    except Exception as e:
        print(f"Error writing matrix_70d: {e}")

if __name__ == "__main__":
    print("Starting A04 Kinematics Crawler Daemon...")
    while True:
        start_t = time.time()
        try:
            # Legacy: xay_dung_quy_dao_tu_a05 has been replaced by FIFO matrix_100h/70d
            cawl_and_stream()
        except Exception as e:
            print("Entire process collapsed:", e)
            traceback.print_exc()
        
        # Ensure each loop takes exactly 1 minute
        elapsed = time.time() - start_t
        sleep_time = max(10, 60 - elapsed)
        time.sleep(sleep_time)
