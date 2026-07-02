"""
🧬 DNA: v16.7 (Sovereign Purity & VSA 2.0)
🏢 UNIT: MARKET_HOUND (A01)
🛠️ ROLE: MARKET_SCANNER_CLAW
📖 DESC: Real-time market data scanner (Binance/Bybit), spoofing detection, OI analysis, and price cross-validation via CoinGecko.
🔗 CALLS: tools/nlm_changelog.py, tools/imperial_state.py
📟 I/O: Redis: A01:raw, SYSTEM:tracker:latest, alerts:urgent
🛡️ INTEGRITY: Organic-Market-Pulse, Data-Cross-Validation, Anti-Spoof-Logic.
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))

import os
import json
import time
import asyncio
import logging
from datetime import datetime
from typing import Optional

import ccxt
import ccxt.async_support as ccxt_async
import requests
from dotenv import load_dotenv
import nlm_changelog
from imperial_state import matrix

# ── Load environment variables from config/.env ──────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../config/.env'))

BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
BYBIT_API_KEY      = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET_KEY   = os.getenv("BYBIT_SECRET_KEY", "")

# ── Logging ───────────────────────────────────────────────────────────────────
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'agent_execution.log')),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("01_BLOOD_CLAW")

# ── Spoofing detection thresholds (can be adjusted in orchestrator.yaml) ──────
SPOOF_THRESHOLD = float(os.getenv("SPOOF_THRESHOLD", "2.5"))  # 2.5x Ratio
OI_ALERT_PCT = float(os.getenv("OI_ALERT_PCT", "5.0"))     # OI Change > 5%

# Price cross-validation threshold vs CoinGecko — if exceeded, suspect price feed spoofing/tampering
PRICE_CROSSVAL_THRESHOLD_PCT = float(os.getenv("PRICE_CROSSVAL_THRESHOLD_PCT", "1.5"))

# Map Binance symbol → CoinGecko ID (add symbols as needed)
COINGECKO_ID_MAP = {
    "BTC/USDT": "bitcoin",
    "ETH/USDT": "ethereum",
    "SOL/USDT": "solana",
    "BNB/USDT": "binancecoin",
    "XRP/USDT": "ripple",
    "DOGE/USDT": "dogecoin",
    "ADA/USDT": "cardano",
    "AVAX/USDT": "avalanche-2",
    "DOT/USDT": "polkadot",
    "MATIC/USDT": "matic-network",
}


def cross_validate_price(symbol: str, binance_price: float) -> dict:
    """
    Cross-validate Binance price with CoinGecko (independent source, free API).

    If deviation > PRICE_CROSSVAL_THRESHOLD_PCT (default 1.5%) → flag PRICE_DEVIATION_WARNING.
    If deviation > 3x threshold → flag SUSPECTED_DATA_FEED (potential man-in-the-middle or fake API).

    Returns:
        dict with the following fields:
          coingecko_price:    retrieved price (0.0 if error)
          deviation_pct:         absolute deviation percentage
          status:             VALIDATION_OK | PRICE_DEVIATION_WARNING | SUSPECTED_DATA_FEED | ERROR_CANNOT_VALIDATE
          reason:             brief description
    """
    cg_id = COINGECKO_ID_MAP.get(symbol)
    if not cg_id:
        return {
            "coingecko_price": 0.0,
            "deviation_pct": 0.0,
            "status": "ERROR_CANNOT_VALIDATE",
            "reason": f"No CoinGecko ID mapped for {symbol}",
        }

    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": cg_id, "vs_currencies": "usd"},
            timeout=8,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        gia_cg = float(resp.json().get(cg_id, {}).get("usd", 0))
        if gia_cg <= 0:
            return {
                "coingecko_price": 0.0,
                "deviation_pct": 0.0,
                "status": "ERROR_CANNOT_VALIDATE",
                "reason": "CoinGecko returned price <= 0",
            }

        deviation_pct = abs(binance_price - gia_cg) / gia_cg * 100
        warning_threshold = PRICE_CROSSVAL_THRESHOLD_PCT
        suspicion_threshold = PRICE_CROSSVAL_THRESHOLD_PCT * 3

        if deviation_pct > suspicion_threshold:
            status = "SUSPECTED_DATA_FEED"
            reason = (f"Binance price ({binance_price}) deviates {deviation_pct:.2f}% from CoinGecko ({gia_cg:.4f}). "
                      f"Exceeds suspicion threshold {suspicion_threshold:.1f}% — feed may be spoofed.")
            log.warning(f"⚠️ DATA FEED ANOMALY {symbol}: {deviation_pct:.2f}% deviation vs CoinGecko")
        elif deviation_pct > warning_threshold:
            status = "PRICE_DEVIATION_WARNING"
            reason = (f"Binance price ({binance_price}) deviates {deviation_pct:.2f}% from CoinGecko ({gia_cg:.4f}). "
                      f"Within acceptable range but requires attention.")
            log.info(f"Cross-validate {symbol}: deviation {deviation_pct:.2f}% — accepted")
        else:
            status = "VALIDATION_OK"
            reason = f"Price matches within threshold {warning_threshold:.1f}% (deviation {deviation_pct:.2f}%)"

        return {
            "coingecko_price": round(gia_cg, 4),
            "deviation_pct": round(deviation_pct, 3),
            "status": status,
            "reason": reason,
        }

    except requests.exceptions.Timeout:
        log.warning(f"CoinGecko timeout when validating {symbol}")
        return {"coingecko_price": 0.0, "deviation_pct": 0.0,
                "status": "ERROR_CANNOT_VALIDATE", "reason": "CoinGecko timeout"}
    except Exception as e:
        log.warning(f"CoinGecko cross-validate {symbol}: {e}")
        return {"coingecko_price": 0.0, "deviation_pct": 0.0,
                "status": "ERROR_CANNOT_VALIDATE", "reason": str(e)}


def init_exchange(exchange_name: str) -> ccxt.Exchange:
    """Initialize exchange with API keys from environment"""
    name_upper = exchange_name.upper()
    if name_upper == "BINANCE":
        return ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_SECRET_KEY,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'},  # Use futures to retrieve OI
        })
    elif name_upper == "BYBIT":
        return ccxt.bybit({
            'apiKey': BYBIT_API_KEY,
            'secret': BYBIT_SECRET_KEY,
            'enableRateLimit': True,
        })
    else:
        raise ValueError(f"Exchange not supported: {exchange_name}")


def detect_whale_spoofing(total_buy: float, total_sell: float, current_price: float, prev_price: float) -> tuple[str, str]:
    """
    Detect Whale Spoofing (Orderbook manipulation):
    - Giant sell wall but price does NOT drop (or rises) -> fake selling to accumulate.
    - Giant buy wall but price does NOT rise (or drops) -> fake buying to distribute.
    """
    warning = "NORMAL"
    reason = ""

    price_change = current_price - prev_price if prev_price > 0 else 0

    if total_sell > total_buy * SPOOF_THRESHOLD and price_change >= 0:
        warning = "FAKE_BULL_TRAP"
        reason = (f"Sell wall {round(total_sell/total_buy, 1)}x buy wall "
                  f"but price {'rose' if price_change > 0 else 'held flat'}. "
                  f"Likely Whale fake selling to accumulate.")

    elif total_buy > total_sell * SPOOF_THRESHOLD and price_change <= 0:
        warning = "FAKE_BEAR_TRAP"
        reason = (f"Buy wall {round(total_buy/total_sell, 1)}x sell wall "
                  f"but price {'dropped' if price_change < 0 else 'held flat'}. "
                  f"Likely Whale fake buying to distribute.")

    return warning, reason


def analyze_oi(current_oi: float, prev_oi: float, price_change_pct: float) -> tuple[float, str]:
    """Analyze Open Interest and detect dangerous divergences"""
    if prev_oi <= 0:
        return 0.0, "NORMAL"

    oi_change_pct = ((current_oi - prev_oi) / prev_oi) * 100

    if abs(oi_change_pct) < OI_ALERT_PCT:
        return round(oi_change_pct, 2), "NORMAL"

    if oi_change_pct > 0 and price_change_pct > 0:
        return round(oi_change_pct, 2), "OI_INCREASE_PRICE_INCREASE"    # Strong trend
    elif oi_change_pct > 0 and price_change_pct < 0:
        return round(oi_change_pct, 2), "OI_INCREASE_PRICE_DECREASE"    # ⚠️ Dangerous divergence
    elif oi_change_pct < 0 and price_change_pct > 0:
        return round(oi_change_pct, 2), "OI_DECREASE_PRICE_INCREASE"    # Short covering / liquidation
    else:
        return round(oi_change_pct, 2), "OI_DECREASE_PRICE_DECREASE"    # Long liquidation


def determine_urgency(whale_warning: str, oi_warning: str, ls_ratio: float) -> str:
    """Determine urgency level for Agent 07 prioritizing reports"""
    if whale_warning != "NORMAL" and oi_warning in ("OI_INCREASE_PRICE_DECREASE", "OI_DECREASE_PRICE_INCREASE"):
        return "HIGH"     # Multiple anomalous signals simultaneously
    if whale_warning != "NORMAL" or oi_warning not in ("NORMAL", "OI_INCREASE_PRICE_INCREASE"):
        return "MEDIUM"
    if ls_ratio > 3.0 or ls_ratio < 0.33:
        return "MEDIUM"   # Oversaturated Longs/Shorts -> cascading liquidation risk
    return "LOW"


def scan_market_pulse(
    symbol: str = "BTC/USDT",
    exchange_name: str = "BINANCE",
    orderbook_depth: int = 100,
    prev_price: float = 0.0,
    prev_oi: float = 0.0,
) -> str:
    """
    Main Claw Scanner — Scans all market metrics.

    Args:
        symbol:             Trading pair (e.g. "BTC/USDT")
        exchange_name:      "BINANCE" or "BYBIT"
        orderbook_depth:    Number of levels to retrieve from Order Book
        prev_price:         Price from previous scan (for Spoofing divergence)
        prev_oi:            OI from previous scan (for OI velocity/divergence)

    Returns:
        JSON string conforming to 01_tracker_soul.md schema
    """
    timestamp_unix = int(time.time())
    log.info(f"Starting scan for {symbol} on {exchange_name}")

    try:
        exchange = init_exchange(exchange_name)

        # 1. Price and 24h Volume
        ticker = exchange.fetch_ticker(symbol)
        current_price    = float(ticker.get('last', 0))
        volume_24h_usdt = float(ticker.get('quoteVolume', 0))
        change_24h_pct   = float(ticker.get('percentage', 0) or 0)

        # 1b. Cross-validate Binance price with CoinGecko (independent source)
        #     Detects man-in-the-middle or spoofed price feed anomalies
        validated_price = cross_validate_price(symbol, current_price)
        if validated_price["status"] == "SUSPECTED_DATA_FEED":
            # Push urgent alert to Matrix
            matrix.publish("alerts:urgent", {
                "agent_id": "01_BLOOD_CLAW",
                "warning_type": "SUSPECTED_DATA_FEED",
                "symbol": symbol,
                "reason": validated_price["reason"],
                "timestamp_unix": timestamp_unix,
            })

        # 2. Order Book & Snapshots (VSA 2.0 Ready)
        order_book   = exchange.fetch_order_book(symbol, orderbook_depth)
        total_buy_depth = sum(order[1] for order in order_book['bids'])
        total_sell_depth = sum(order[1] for order in order_book['asks'])
        buy_sell_ratio = round(total_buy_depth / total_sell_depth, 2) if total_sell_depth > 0 else 0
        
        # DNA v16.7: Keep 20-level snapshot for Iceberg Hunter
        ob_snapshots = {
            "bids": order_book['bids'][:20],
            "asks": order_book['asks'][:20]
        }

        # 3. Open Interest (only available on Futures)
        current_oi   = 0.0
        oi_warning   = "NOT_AVAILABLE"
        oi_change_pct = 0.0
        try:
            oi_data = exchange.fetch_open_interest(symbol)
            current_oi = float(oi_data.get('openInterestAmount', 0))
            oi_change_pct, oi_warning = analyze_oi(current_oi, prev_oi, change_24h_pct)
        except Exception as oi_err:
            log.warning(f"Could not retrieve OI for {symbol}: {oi_err}")

        # 3b. DNA v16.7: Collect OFI Candles (Aggregated trades per timeframe)
        # Use fetch_ohlcv index 9/10 (taker buy volume) to estimate historical OFI
        ofi_candles = {}
        for tf in ["15m", "1h", "4h", "1d"]:
            try:
                klines = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=20)
                # OFI ~ (Taker Buy Vol) - (Taker Sell Vol)
                # Klines: [timestamp, open, high, low, close, volume, close_time, quote_vol, trades, taker_buy_base, taker_buy_quote]
                tf_ofi = []
                for k in klines:
                    v_buy = float(k[9])
                    v_sell = float(k[5]) - v_buy
                    tf_ofi.append({"ts": k[0], "buy": v_buy, "sell": v_sell, "ofi": v_buy - v_sell})
                ofi_candles[tf] = tf_ofi
            except: 
                ofi_candles[tf] = []

        # 3c. DNA v16.7: Recent Aggregated Trades (Tick intensity)
        agg_trades_recent = []
        try:
            trades = exchange.fetch_trades(symbol, limit=50)
            for t in trades:
                agg_trades_recent.append({
                    "ts": t['timestamp'], "price": t['price'], 
                    "amount": t['amount'], "side": t['side']
                })
            log.info(f"Retrieved {len(agg_trades_recent)} recent trades for {symbol}")
        except: 
            pass

        # 4. Long/Short Ratio
        long_pct, short_pct, ls_ratio = 50.0, 50.0, 1.0
        try:
            ls_data  = exchange.fetch_long_short_ratio(symbol, '1h')
            if ls_data and len(ls_data) > 0:
                long_pct = float(ls_data[0].get('longAccount', 50))
                short_pct = 100 - long_pct
                ls_ratio = round(long_pct / short_pct, 2) if short_pct > 0 else 0
        except Exception as ls_err:
            log.warning(f"Could not retrieve Long/Short Ratio: {ls_err}")

        # 5. Detect Spoofing
        whale_warning, reason = detect_whale_spoofing(
            total_buy_depth, total_sell_depth, current_price, prev_price
        )

        # 6. Urgency level
        urgency_level = determine_urgency(whale_warning, oi_warning, ls_ratio)

        # 7. Formulate standardized JSON
        result = {
            "agent_id":            "01_BLOOD_CLAW",
            "timestamp_unix":      timestamp_unix,
            "timestamp_readable":  datetime.utcfromtimestamp(timestamp_unix).strftime('%Y-%m-%d %H:%M:%S UTC'),
            "exchange":            exchange_name.upper(),
            "symbol":              symbol,
            "current_price":        round(current_price, 4),
            "change_24h_pct":      round(change_24h_pct, 2),
            "volume_24h_usdt":     round(volume_24h_usdt, 2),
            "orderbook": {
                "total_bid_depth": round(total_buy_depth, 4),
                "total_ask_depth": round(total_sell_depth, 4),
                "bid_ask_ratio":   buy_sell_ratio,
                "scan_depth":       orderbook_depth,
            },
            "open_interest": {
                "current_oi":       round(current_oi, 2),
                "oi_change_pct":   oi_change_pct,
                "oi_warning":       oi_warning,
            },
            "vsa2_0_metrics": {
                "ofi_candles": ofi_candles,
                "ob_snapshots": ob_snapshots,
                "agg_trades_recent": agg_trades_recent
            },
            "long_short_ratio": {
                "long_pct":  round(long_pct, 1),
                "short_pct": round(short_pct, 1),
                "ls_ratio":  ls_ratio,
            },
            "whale_warning":    whale_warning,
            "warning_reason":   reason,
            "urgency_level":    urgency_level,
            "price_validation": validated_price,
        }

        json_output = json.dumps(result, ensure_ascii=False)

        # 8. Publish to Matrix (Organic I/O)
        _publish_matrix(result, urgency_level)

        log.info(f"Finished scanning {symbol} | Warning: {whale_warning} | Urgency: {urgency_level}")
        matrix.publish_heartbeat("A01", "WATCHING", {
            "symbol": symbol, "price": current_price, "ob_ratio": buy_sell_ratio,
            "warning": whale_warning, "urgency": urgency_level,
        })
        return json_output

    except Exception as err:
        error_json = {
            "agent_id":       "01_BLOOD_CLAW",
            "timestamp_unix": timestamp_unix,
            "error":          str(err),
            "error_code":     type(err).__name__,
            "symbol":         symbol,
            "exchange":       exchange_name.upper(),
        }
        log.error(f"Error scanning {symbol}: {err}")
        matrix.publish("errors", error_json)
        matrix.publish_heartbeat("A01", "ERROR", {"error": str(err)})
        return json.dumps(error_json, ensure_ascii=False)


def _publish_matrix(data: dict, urgency_level: str):
    """Publish data to the appropriate Matrix channels"""
    # 0. Set static cache for other Agents (like A03)
    matrix.set("TRACKER", "latest", data)
    matrix.set("A01", "realtime", data)

    # 1. Push to t0_stream event stream for A05 XREAD
    matrix.xadd("A05", "t0_stream", {"source": "A01", "payload": data}, maxlen=30)

    # 3. Urgent Alert (Circuit Breaker pathway)
    if urgency_level == "HIGH":
        matrix.publish("alerts:urgent", data)
        log.warning(f"🚨 URGENT ALERT Matrix: {data['symbol']}")

    # 4. Hash Cache for sliding price history (A04 read)
    matrix.hset("SYSTEM", "latest_prices", data['symbol'], {
        "price":     data.get('current_price', 0),
        "timestamp": data.get('timestamp_unix', 0),
        "oi":        data.get('open_interest', {}).get('current_oi', 0),
    })


# ── Tool Definition for OpenClaw ──────────────────────────────────────────────
TOOL_DEFINITION = {
    "name": "scan_market_pulse",
    "description": (
        "Orderbook Analyzer — Retrieves live data from Binance/Bybit: "
        "price, volume, order book, Open Interest, Long/Short Ratio. "
        "Detects Whale Spoofing. Returns clean JSON."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Trading pair. Example: BTC/USDT, ETH/USDT",
            },
            "exchange_name": {
                "type": "string",
                "enum": ["BINANCE", "BYBIT"],
                "description": "Exchange to scan",
                "default": "BINANCE",
            },
            "orderbook_depth": {
                "type": "integer",
                "description": "Number of levels to retrieve from Order Book (default 100)",
                "default": 100,
            },
        },
        "required": ["symbol"],
    },
}

TOOL_BATCH_DEFINITION = {
    "name": "scan_multiple_symbols",
    "description": "Scans the entire list of symbols specified by the Master simultaneously.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol_list": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of symbols. Example: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']",
            },
            "exchange_name": {
                "type": "string",
                "enum": ["BINANCE", "BYBIT"],
                "default": "BINANCE",
            },
        },
        "required": ["symbol_list"],
    },
}


# ── Orchestration ───────────────────────────────────────────────────────────────
def _listen_for_realtime_requests():
    """Listens for A01_REALTIME_REQUEST to execute scan immediately."""
    log.info("[A01] Starting listener for A01_REALTIME_REQUEST...")
    pubsub = matrix.subscribe(["COMMANDER:events"])
    for message in pubsub.listen():
        if message['type'] != 'message':
            continue
        try:
            data = json.loads(message['data'])
            action_event = data.get("action") or data.get("event")
            is_match = action_event in ["A01_REALTIME_REQUEST", "SWARM_REALTIME_REQUEST"]
            
            if is_match:
                topic = data.get("symbol", data.get("topic", "BTC/USDT"))
                log.info(f"[A01] 🔔 Received Realtime Pulse command for {topic} from {data.get('requester')}")
                
                # DNA v16.4: Execute scan immediately
                scan_market_pulse(topic, "BINANCE")
                log.info(f"[A01] Completed Realtime scan for {topic}.")
                
        except Exception as e:
            log.error(f"[A01] Error processing Realtime Request: {e}")

if __name__ == "__main__":
    import argparse
    import threading
    parser = argparse.ArgumentParser(description="Agent 01 — Orderbook Analyzer (Hound)")
    parser.add_argument("--symbol", type=str, default="BTC/USDT", help="Trading pair for testing")
    parser.add_argument("--run",     action="store_true", help="Run the full service (Realtime Pulse Listener)")
    args = parser.parse_args()

    if args.run:
        print("Starting Hound Market Sampler (Pulse Listener)...")
        # Pulse listener thread
        t_pulse = threading.Thread(target=_listen_for_realtime_requests, daemon=True)
        t_pulse.start()
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(600)
                if not t_pulse.is_alive():
                    log.warning("[A01] Pulse thread died, restarting...")
                    t_pulse = threading.Thread(target=_listen_for_realtime_requests, daemon=True)
                    t_pulse.start()
        except KeyboardInterrupt:
            log.info("[A01] Stop signal received.")
            
    else:
        print("=== TEST Agent 01 — Orderbook Analyzer ===")
        result = scan_market_pulse(args.symbol, "BINANCE")
        parsed = json.loads(result)
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
