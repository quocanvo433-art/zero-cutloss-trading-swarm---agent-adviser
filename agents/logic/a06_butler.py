"""
🧬 DNA: v16.6 (Sovereign Purity & Master Gateway) [DNA Header]
🏢 UNIT: TELEGRAM_BUTLER (A06)
🛠️ ROLE: MASTER_COMMUNICATOR
📖 DESC: Official communication system between Commander and Swarm via Telegram. Handles commands, status reports, and digital signature authentication (Auth).
🔗 CALLS: tools/telegram_auth.py, tools/imperial_state.py
📟 I/O: Telegram Bot API, Redis: zcl:A06:heartbeat
🛡️ INTEGRITY: Secure-Channel, Auth-Verified, Signal-Transparency.
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
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import ccxt
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from telegram_auth import parse_and_authenticate
from dos_guardian import check_telegram_rate_limit, get_agent_instructions
import nlm_changelog
import threading
from imperial_state import matrix

# ════════════════════════════════════════════════════════════════════
# SEMANTIC INTENT ENGINE — Cloud-Routed, On-Top Priority
# ════════════════════════════════════════════════════════════════════

# Standard command list
_STANDARD_COMMANDS_MAP = {
    "/mode status": "View current operating profile",
    "/mode safe": "Switch system to asset protection mode (LOCAL+CAUTION)",
    "/mode continuous": "Switch system to normal multi-layer operation (HYBRID)",
    "/mode smart": "Enable self-learning DPO (HYBRID+TRAIN)",
    "/mode max": "Maximize Cloud Gemini usage (CLOUD_BOOSTED)",
    "/mode cloud_off": "Turn off Cloud, run local only",
    "/mode freeze": "Freeze entire system (both Cloud and HW down)",
    "/mode cloud_detach": "Detach hardware for maintenance, Cloud takes over",
    "/mode recovery": "Step-by-step system recovery after Freeze",
    "/boost status": "View status of A04 blind contest DPO training (boosting, training results)",
    "/boost on": "Turn on DPO training at full speed",
    "/boost pause": "Temporarily pause DPO training",
    "/boost slow": "Run DPO training slowly (30s/contest)",
    "/boost off": "Turn off DPO training completely",
    "/boost gen": "Generate 14 new blind scenarios",
    "/cloud status": "View Cloud health status",
    "/cloud probe": "Probe Cloud health immediately",

    "/judge postmortem": "View the most recent 235B lesson",
    "/judge mistakes": "View the 5 most recent mistakes",
    "/judge riding": "View active riding errors being tracked",
    "protection status": "View DoS Guardian status",
    "reset guardian": "Reset DoS Guardian to NORMAL",
    "update": "Approve FIM Manifest update",
    "list": "View all monitored campaigns",
    "extend survival": "Extend Survival mode duration",
}

REDIS_PENDING_CONFIRM_PREFIX = "zcl:butler:pending_confirm"
REDIS_PENDING_INTENT_TS_PREFIX = "zcl:butler:pending_intent_ts"


def _call_llm_semantic_intent(user_text: str) -> str:
    """
    Call Cloud LLM to analyze semantics and map to standard commands.
    - Priority: urgency=1 (top priority)
    - Returns standard command syntax if confident, or empty string if UNKNOWN.
    """
    try:
        from llm_router import router_api_call
        from imperial_brain import brain
    except ImportError:
        log.warning("[A06 Intent] Failed to import llm_router or imperial_brain")
        return ""

    command_list_str = "\n".join(f"- {k}: {v}" for k, v in _STANDARD_COMMANDS_MAP.items())
    prompt = (
        f"You are the internal command classifier for the Zero Cutloss Empire system.\n"
        f"User input: '{user_text}'\n\n"
        f"List of valid commands:\n{command_list_str}\n\n"
        f"Identify if the user input matches any valid command in the list above.\n"
        f"If matched, return ONLY the exact command syntax (e.g., /mode safe) and nothing else.\n"
        f"If it does NOT match any command, return ONLY: UNKNOWN"
    )

    result = brain.think_as(
        "A06", 
        prompt,
        urgency_priority=1, 
        est_tokens=100
    )
    if not result or "ERROR" in result.upper():
        return ""

    result_upper = result.upper()
    if "UNKNOWN" in result_upper:
        return ""
        
    for cmd in sorted(_STANDARD_COMMANDS_MAP.keys(), key=len, reverse=True):
        if cmd.lower() in result.lower():
            return cmd
            
    return ""


async def _trigger_totp_challenge_now(chat_id: str):
    """Send TOTP challenge code immediately without warning."""
    from telegram_auth import generate_challenge, CHALLENGE_VALID_SECONDS
    matrix.delete("AUTH", "session")
    challenge = generate_challenge(chat_id)
    await _send_telegram(
        f"🔐 *SECURITY: RE-AUTHENTICATION REQUIRED*\n"
        f"Challenge code: `{challenge}`\n\n"
        f"Calculate: `HMAC('{challenge}', CHALLENGE_SECRET)[:8]`\n"
        f"Send: `!verify <8_chars>`\n"
        f"⏱️ Expires in {CHALLENGE_VALID_SECONDS} seconds."
    )

TELEGRAM_BOT_TOKEN  = ""
TELEGRAM_CHAT_ID    = ""
TELEGRAM_CHAT_ID_TRADE = ""
TELEGRAM_CHAT_ID_SYSTEM = ""
TELEGRAM_CHAT_ID_ALERT = ""
BINANCE_API_KEY     = ""
BINANCE_SECRET_KEY  = ""
BYBIT_API_KEY       = ""
BYBIT_SECRET_KEY    = ""

from imperial_state import setup_agent_logger
log = setup_agent_logger("A06", "06_OVERVIEW")

REDIS_CAMPAIGNS_KEY = "CAMPAIGNS"
REDIS_AGENT05_KEY   = "latest_recommendation"

bot: Optional[Bot] = None


# ════════════════════════════════════════════════════════════════════
# SECTION 1 — CAMPAIGN MANAGEMENT (Redis storage)
# ════════════════════════════════════════════════════════════════════

def _get_campaign_name(coin: str, signal: str = "Custom") -> str:
    """Format campaign name: {COIN}-{Signal}-{DDMM}-{HHMM}"""
    now = datetime.now(timezone.utc)
    return f"{coin.replace('/', '-')}-{signal}-{now.strftime('%d%m-%H%M')}"


def _save_campaign(name: str, data: dict):
    """Save campaign to Matrix CAMPAIGNS hash."""
    matrix.hset("CAMPAIGN", "ACTIVE", name, data)
    log.info(json.dumps({"event": "CAMPAIGN_OPENED", "name": name, "data": data}, ensure_ascii=False))


def _update_campaign(name: str, **kwargs):
    """Update fields of an active campaign."""
    data = matrix.hget("CAMPAIGN", "ACTIVE", name)
    if not data:
        return
    data.update(kwargs)
    matrix.hset("CAMPAIGN", "ACTIVE", name, data)


def _get_all_campaigns() -> dict:
    """Retrieve all campaigns from Matrix."""
    return matrix.hgetall("CAMPAIGN", "ACTIVE")


def _delete_campaign(name: str, reason: str):
    """Close campaign and log details."""
    matrix.hdel("CAMPAIGN", "ACTIVE", name)
    log.info(json.dumps({
        "event": "CAMPAIGN_CLOSED",
        "name": name,
        "reason": reason,
        "timestamp": int(time.time())
    }, ensure_ascii=False))


# ════════════════════════════════════════════════════════════════════
# SECTION 2 — EXCHANGE INITIALIZATION
# ════════════════════════════════════════════════════════════════════

def _init_exchange(exchange_name: str, market_type: str = "FUTURES") -> ccxt.Exchange:
    """Initialize CCXT exchange. market_type: SPOT or FUTURES"""
    mode = 'future' if market_type == "FUTURES" else 'spot'
    if exchange_name.upper() == "BINANCE":
        return ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_SECRET_KEY,
            'enableRateLimit': True,
            'options': {'defaultType': mode},
        })
    elif exchange_name.upper() == "BYBIT":
        return ccxt.bybit({
            'apiKey': BYBIT_API_KEY,
            'secret': BYBIT_SECRET_KEY,
            'enableRateLimit': True,
        })
    raise ValueError(f"Unsupported exchange: {exchange_name}")


# ════════════════════════════════════════════════════════════════════
# SECTION 3 — MONITOR EXCHANGE ORDER STATUS
# ════════════════════════════════════════════════════════════════════

def _check_exchange_order(campaign_name: str, data: dict) -> Optional[Dict[str, Any]]:
    """
    Call Binance/Bybit API to check actual order status.
    Returns dict containing event info if action is needed.
    """
    event = None
    try:
        exchange = _init_exchange(data['exchange'], data['market_type'])
        order = exchange.fetch_order(data['order_id_san'], data['coin'])

        exchange_status = order.get('status', 'unknown').upper()  # OPEN/FILLED/CANCELED/...
        actual_fill_price = order.get('average') or order.get('price')
        filled_quantity = order.get('filled', 0)

        previous_status = data.get('monitoring_status', 'AWAITING_FILL')

        # ── Case A: Order fully filled for the first time ──────────────────
        if exchange_status == "FILLED" and previous_status in ("AWAITING_FILL", "PARTIALLY_FILLED"):
            _update_campaign(campaign_name,
                monitoring_status="FULLY_FILLED",
                exchange_status="FILLED",
                actual_fill_price=float(actual_fill_price or data['order_price']),
                fill_time=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            )
            event = {
                "type": "ORDER_FILLED",
                "campaign_name": campaign_name,
                "fill_price": float(actual_fill_price or data['order_price']),
                "quantity": filled_quantity,
            }

        # ── Case B: Order partially filled ──────────────────────────────────
        elif exchange_status == "PARTIALLY_FILLED" and previous_status == "AWAITING_FILL":
            _update_campaign(campaign_name,
                monitoring_status="PARTIALLY_FILLED",
                exchange_status="PARTIALLY_FILLED",
                partially_filled_quantity=filled_quantity,
            )

        # ── Case C: Order cancelled on exchange ────────────────────────────
        elif exchange_status == "CANCELED" and previous_status not in ("EMERGENCY_CANCEL",):
            _delete_campaign(campaign_name, reason="CANCELLED_ON_EXCHANGE")

        # ── Case D: Position active — monitor targets and stop loss ──────────
        elif previous_status in ("FULLY_FILLED", "MONITORING_POSITION", "TARGET_1_REACHED"):
            current_price = _get_current_price(data['coin'], exchange)
            event = _check_targets_and_sl(campaign_name, data, current_price)
            if event:
                _update_campaign(campaign_name, monitoring_status="MONITORING_POSITION")

    except ccxt.NetworkError as e:
        log.error(f"Network error checking {campaign_name}: {e}")
    except ccxt.ExchangeError as e:
        log.error(f"Exchange error checking {campaign_name}: {e}")
    except Exception as e:
        log.error(f"Unknown error checking {campaign_name}: {e}")

    return event


def _get_current_price(coin: str, exchange: ccxt.Exchange) -> float:
    """Fetch current market price."""
    try:
        ticker = exchange.fetch_ticker(coin)
        return float(ticker.get('last', 0))
    except Exception:
        cache = matrix.hget("SYSTEM", "latest_prices", coin)
        if cache:
            return cache.get('price', 0.0)
        return 0.0


def _check_targets_and_sl(name: str, data: dict, current_price: float) -> Optional[dict]:
    """Check if price has reached Target 1/2 or Stop Loss."""
    rec = data.get('agent05_recommendation', {})
    target_1 = rec.get('target_1')
    target_2 = rec.get('target_2')
    stop_loss = rec.get('stop_loss')
    t1_reached = data.get('monitoring_status') == "TARGET_1_REACHED"

    if not current_price or current_price <= 0 or not data.get('actual_fill_price'):
        return None

    # Target 1 reached
    if target_1 and current_price >= target_1 and not t1_reached:
        profit_pct = round(float(((current_price - data['actual_fill_price']) / data['actual_fill_price']) * 100), 2)
        return {
            "type": "TARGET_1_REACHED",
            "campaign_name": name,
            "current_price": current_price,
            "target_1": target_1,
            "proposed_new_stop_loss": data['actual_fill_price'],  # Move SL to breakeven
            "profit_pct": profit_pct,
        }

    # Target 2 reached
    if target_2 and current_price >= target_2 and t1_reached:
        profit_pct = round(float(((current_price - data['actual_fill_price']) / data['actual_fill_price']) * 100), 2)
        return {
            "type": "TARGET_2_REACHED",
            "campaign_name": name,
            "current_price": current_price,
            "target_2": target_2,
            "profit_pct": profit_pct,
        }

    # Stop Loss triggered
    if stop_loss and current_price <= stop_loss:
        return {
            "type": "STOP_LOSS_TRIGGERED",
            "campaign_name": name,
            "current_price": current_price,
            "stop_loss": stop_loss,
        }

    return None


# ════════════════════════════════════════════════════════════════════
# SECTION 4 — TELEGRAM MESSAGE GENERATION
# ════════════════════════════════════════════════════════════════════

def _build_campaign_table() -> str:
    """Generate status table for all active campaigns."""
    campaigns = _get_all_campaigns()
    if not campaigns:
        return "_(No active campaigns)_"

    lines = []
    for name, data in campaigns.items():
        status = data.get('monitoring_status', '?')
        order_px = data.get('order_price', '?')
        fill_px = data.get('actual_fill_price')

        if status == "AWAITING_FILL":
            lines.append(f"⏳ `{name}` → AWAITING FILL @ {order_px:,.0f}")
        elif status == "PARTIALLY_FILLED":
            lines.append(f"🔶 `{name}` → PARTIALLY FILLED @ {order_px:,.0f}")
        elif status in ("FULLY_FILLED", "MONITORING_POSITION"):
            prices = matrix.hgetall("SYSTEM", "latest_prices")
            current_px_dict = prices.get(data.get('coin', ''), {})
            current_px = current_px_dict.get('price', 0)
            if fill_px and current_px:
                profit = round(((current_px - fill_px) / fill_px) * 100, 2)
                leverage = data.get('actual_leverage', 1)
                net_profit = profit * leverage
                icon = "📈" if net_profit >= 0 else "📉"
                
                liq_warn = ""
                extra = data.get("extra_data", {})
                liq_zone = extra.get("estimated_liquidation_zone", 0)
                if liq_zone > 0:
                    distance = abs(current_px - liq_zone) / current_px
                    if distance < 0.05: liq_warn = " ⚠️ LIQ RISK"
                    
                lines.append(f"{icon} `{name}` ({leverage}x) → FILLED @ {fill_px:,.0f} | {'+' if net_profit >= 0 else ''}{net_profit:.1f}%{liq_warn}")
        elif status == "TARGET_1_REACHED":
            lines.append(f"✅ `{name}` → TARGET 1 MET | Awaiting Target 2")
        else:
            lines.append(f"⚫ `{name}` → {status}")

    return "\n".join(lines)


def _format_order_filled_msg(event: dict, data: dict) -> str:
    rec = data.get('agent05_recommendation', {})
    extra = data.get('extra_data', {})
    table = _build_campaign_table()
    name = event['campaign_name']
    price = event['fill_price']
    sl = rec.get('stop_loss', '?')
    market_type = data.get('market_type', 'FUTURES')
    order_type = data.get('order_type', 'LIMIT')

    return (
        f"🩸 *ORDER FILLED*\n"
        f"`{name}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Exchange: {data.get('exchange', '?')} {market_type} | {order_type}\n"
        f"Fill Price: *{price:,.2f}* USDT\n"
        f"Quantity: {event.get('quantity', '?')} {data.get('coin', '').split('/')[0]}\n\n"
        f"📋 *Plan (Elliott {extra.get('hold_bias', 'UNKNOWN')}):*\n"
        f"• Capital Allocation: *{extra.get('capital_allocation_pct', 0)}%*\n"
        f"• Max Leverage: *{extra.get('leverage', 1)}x*\n"
        f"• Hard SL: {sl} (Est. Liquidation: {extra.get('estimated_liquidation_zone', '?')})\n"
        f"• Target 1: {extra.get('take_profit_plan', {}).get('T1', '?')}\n"
        f"• Target 2: {extra.get('take_profit_plan', {}).get('T2', '?')}\n"
        f"• Target 3: {extra.get('take_profit_plan', {}).get('T3', 'None')}\n\n"
        f"📊 *ACTIVE CAMPAIGNS*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{table}"
    )


def _format_target_msg(event: dict, data: dict) -> str:
    table = _build_campaign_table()
    name = event['campaign_name']
    price = event['current_price']
    event_type = event['type']

    if event_type == "TARGET_1_REACHED":
        return (
            f"💰 *ACTION REQUIRED*\n"
            f"`{name}`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Required: *TAKE 50% PROFIT AT TARGET 1*\n"
            f"Current Price: *{price:,.2f}* ✅\n"
            f"Profit: *+{event.get('profit_pct', 0)}%*\n\n"
            f"→ Take 50% profit manually\n"
            f"→ Move SL to breakeven: *{event.get('proposed_new_stop_loss', '?'):,.2f}*\n\n"
            f"📊 *ACTIVE CAMPAIGNS*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{table}"
        )
    elif event_type == "TARGET_2_REACHED":
        return (
            f"🏆 *FINAL TARGET MET*\n"
            f"`{name}`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Target 2: *{event.get('target_2', '?'):,.2f}* ✅\n"
            f"Current Price: *{price:,.2f}*\n"
            f"Profit: *+{event.get('profit_pct', 0)}%*\n\n"
            f"→ Close remaining 50% position\n\n"
            f"📊 *ACTIVE CAMPAIGNS*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{table}"
        )
    return ""


def _format_stop_loss_msg(event: dict) -> str:
    table = _build_campaign_table()
    name = event['campaign_name']
    price = event['current_price']
    sl = event['stop_loss']

    return (
        f"🚨 *EMERGENCY: STOP LOSS HIT*\n"
        f"`{name}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Current Price: *{price:,.2f}*\n"
        f"Stop Loss: *{sl:,.2f}* ⛔\n\n"
        f"→ EXIT position immediately\n\n"
        f"📊 *ACTIVE CAMPAIGNS*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{table}"
    )


def _escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown V1."""
    chars = ['_', '*', '`', '[']
    for char in chars:
        text = text.replace(char, f'\\{char}')
    return text


async def _send_telegram(content: str, jitter: bool = False, channel: str = "SYSTEM"):
    if not content:
        return
    if jitter:
        import random
        delay = random.uniform(30, 120)
        log.info(f"Jitter delay of {delay:.0f}s before sending message")
        await asyncio.sleep(delay)
    if not bot:
        log.error("Error: Telegram bot not initialized.")
        return

    target_id = TELEGRAM_CHAT_ID
    if channel == "TRADE" and TELEGRAM_CHAT_ID_TRADE:
        target_id = TELEGRAM_CHAT_ID_TRADE
    elif channel == "ALERT" and TELEGRAM_CHAT_ID_ALERT:
        target_id = TELEGRAM_CHAT_ID_ALERT
    elif channel == "SYSTEM" and TELEGRAM_CHAT_ID_SYSTEM:
        target_id = TELEGRAM_CHAT_ID_SYSTEM
    elif channel == "COMMON":
        from telegram_auth import TELEGRAM_GROUP_ID_COMMON
        if TELEGRAM_GROUP_ID_COMMON:
            target_id = TELEGRAM_GROUP_ID_COMMON
    elif channel == "ELITE":
        from telegram_auth import TELEGRAM_GROUP_ID_ELITE
        if TELEGRAM_GROUP_ID_ELITE:
            target_id = TELEGRAM_GROUP_ID_ELITE

    chunk_size = 4000
    chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]
    
    for idx, chunk in enumerate(chunks):
        try:
            await bot.send_message(
                chat_id=target_id,
                text=chunk,
                parse_mode=ParseMode.MARKDOWN
            )
            if len(chunks) > 1 and idx < len(chunks) - 1:
                await asyncio.sleep(1)
        except Exception as e:
            if "parse entities" in str(e).lower() or "can't find end" in str(e).lower():
                try:
                    await bot.send_message(
                        chat_id=target_id,
                        text=chunk,
                    )
                    log.warning(f"Fallback plain-text message sent successfully for chunk {idx+1}/{len(chunks)}")
                except Exception as e2:
                    log.error(f"Error sending plain-text fallback chunk {idx+1}/{len(chunks)}: {e2}")
            else:
                log.error(f"Error sending chunk {idx+1}/{len(chunks)}: {e}")

    log.info(json.dumps({
        "event": "TELEGRAM_SENT",
        "channel": channel,
        "timestamp": int(time.time()),
        "length": len(content),
        "chunks": len(chunks)
    }, ensure_ascii=False))


# ════════════════════════════════════════════════════════════════════
# SECTION 5 — USER COMMAND PARSING
# ════════════════════════════════════════════════════════════════════

import re

def _parse_leverage_from_msg(text: str) -> tuple[int, str]:
    """Parse leverage (e.g., 5x, x10) and market type (Spot/Futures)."""
    text = text.upper()
    leverage = 1
    market_type = "SPOT" if "SPOT" in text else "FUTURES"
    
    match = re.search(r"(\d+)X|X(\d+)", text)
    if match:
        leverage = int(match.group(1) or match.group(2))
        market_type = "FUTURES"
    return leverage, market_type


def _parse_order_entry_msg(text: str) -> Optional[dict]:
    """Parse messages regarding placing orders."""
    text = text.strip()

    try:
        data = json.loads(text)
        if 'coin' in data or 'ma_tien_ao' in data:
            market_type = data.get('loai', 'FUTURES').upper()
            lev = data.get('don_bay', data.get('doi_bay_thuc_te', 1))
            return {
                "coin": data.get('coin') or data.get('ma_tien_ao', 'BTC/USDT'),
                "order_price": float(data.get('gia', 0)),
                "quantity": float(data.get('so_luong', 0)),
                "order_type": data.get('loai_lenh', 'LIMIT').upper(),
                "market_type": market_type,
                "actual_leverage": int(lev),
                "exchange": data.get('san', 'BINANCE').upper(),
                "order_id_san": data.get('order_id', ''),
                "signal": data.get('tin_hieu', 'Custom'),
            }
    except (json.JSONDecodeError, ValueError):
        pass

    trigger_words = ["place order", "rải lệnh", "rai lenh", "vào lệnh", "đặt lệnh", "dat lenh"]
    if not any(w in text.lower() for w in trigger_words):
        return None

    text_clean = re.sub(r'\b(SPOT|FUTURES|LIMIT|MARKET)\b', '', text.upper())
    coin_match = re.search(r'\b([A-Z]{2,10})\b', text_clean)
    if not coin_match:
        return None
    price_match = re.search(r'\b(\d{3,6}(?:\.\d+)?)\b', text)
    qty_match = re.search(r'\b(0\.\d+|\d+)\s*(?:coin|[a-z]{2,10})?\b', text.lower())
    leverage, market_type = _parse_leverage_from_msg(text)

    return {
        "coin": f"{coin_match.group(1)}/USDT",
        "order_price": float(price_match.group(1)) if price_match else 0,
        "quantity": float(qty_match.group(1)) if qty_match else 0,
        "order_type": "LIMIT",
        "market_type": market_type,
        "actual_leverage": leverage,
        "exchange": "BINANCE",
        "order_id_san": "",
        "signal": "Custom",
    }


# ════════════════════════════════════════════════════════════════════
# SECTION 6 — TELEGRAM EVENT HANDLERS
# ════════════════════════════════════════════════════════════════════

async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for all incoming Telegram messages."""
    incoming_chat_id = str(update.effective_chat.id)
    incoming_user_id = str(update.effective_user.id) if update.effective_user else None
    text = update.message.text or ""

    allowed, rl_reason = check_telegram_rate_limit(incoming_chat_id)
    if not allowed:
        return

    # SECURITY LAYER 1: Authenticate user
    auth = parse_and_authenticate(text, incoming_chat_id, incoming_user_id)

    if not auth["authenticated"]:
        if auth.get("level") == "AUTH_FLOW":
            return
        if auth.get("reason", "").startswith("Chat ID"):
            return
        return

    log.info(json.dumps({
        "event": "MESSAGE_RECEIVED",
        "timestamp": int(time.time()),
        "content": text[:100],
        "auth_level": auth.get("level", "READ"),
        "session_remaining": auth.get("session_remaining", 0),
    }))

    _YES_WORDS = {"yes", "y", "ok", "confirm", "accurate"}
    if text.lower().strip() in _YES_WORDS:
        pending_cmd = matrix.get("A06", f"pending_confirm:{incoming_chat_id}")
        if pending_cmd:
            matrix.delete("A06", f"pending_confirm:{incoming_chat_id}")
            matrix.delete("A06", f"pending_intent_ts:{incoming_chat_id}")
            await _send_telegram(f"✅ Executing: `{pending_cmd}`")
            text = pending_cmd
            auth = parse_and_authenticate(text, incoming_chat_id, incoming_user_id)
        else:
            return

    order_data = _parse_order_entry_msg(text)
    if order_data:
        coin_code = order_data['coin'].replace('/', '-')
        signal = order_data.get('signal', 'Custom')
        campaign_name = _get_campaign_name(coin_code, signal)

        campaign = {
            **order_data,
            "campaign_name": campaign_name,
            "monitoring_status": "AWAITING_FILL",
            "exchange_status": "OPEN",
            "actual_fill_price": None,
            "order_time": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            "fill_time": None,
            "agent05_recommendation": _get_agent05_recommendation(order_data['coin']),
        }
        _save_campaign(campaign_name, campaign)

        table = _build_campaign_table()
        confirmation = (
            f"✅ *Order Recorded*\n"
            f"Campaign: `{campaign_name}`\n"
            f"Exchange: {order_data['exchange']} {order_data['market_type']}\n"
            f"Order Price: {order_data['order_price']:,.2f}\n\n"
            f"📊 *ACTIVE CAMPAIGNS*\n━━━━━━━━━━━━━━━\n{table}"
        )
        await _send_telegram(confirmation, channel="TRADE")
        return

    cmd = auth.get("command", "")
    log.info(f"Butler command: cmd='{cmd}' args={auth.get('args')}")

    if cmd == "protection status":
        from dos_guardian import get_system_status
        await _send_telegram(get_system_status())
        return

    elif cmd == "status":
        from dos_guardian import get_operational_profile
        profile = get_operational_profile()
        sec = profile["security_mode"]
        inf = profile["infra_mode"]
        ic_sec = {"NORMAL": "🟢", "CAUTION": "🟡", "SURVIVAL": "🟠", "LOCKDOWN": "🔴"}.get(sec, "⚪")
        ic_inf = {"LOCAL_ONLY": "💾", "HYBRID": "🔀", "CLOUD_ONLY": "☁️", "CLOUD_BOOSTED": "⚡☁️"}.get(inf, "⚪")
        
        q_info = "Status OK"
            
        await _send_telegram(
            f"👑 *ZERO-CUTLOSS EMPIRE OVERVIEW*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🛡️ Security: `{sec}` {ic_sec}\n"
            f"⚙️ Infrastructure: `{inf}` {ic_inf}\n\n"
            f"🤖 *Active Systems:*\n"
            f"• A04 DPO: `/boost status`\n"
            f"• API Bandwidth: {q_info}\n\n"
            f"ℹ️ _To place orders: rải lệnh BTC 64800_\n"
            f"ℹ️ _To configure mode: /mode_\n"
            f"ℹ️ _To manage campaigns: /list_"
        )
        return

    elif cmd == "reset guardian":
        from dos_guardian import reset_guardian
        reset_guardian()
        await _send_telegram("✅ DoS Guardian has been reset to NORMAL.\nAll circuit breakers have been opened.")
        return

    elif cmd == "safe mode":
        args = auth.get("args")
        if args:
            new_mode = args[0].upper()
            from dos_guardian import set_system_mode
            if set_system_mode(new_mode):
                await _send_telegram(f"⚔️ System mode switched to: `{new_mode}`")
            else:
                await _send_telegram("❌ Invalid system mode (Normal/Caution/Survival/Lockdown)")
        else:
            await _send_telegram("⚠️ Missing mode parameter (Normal/Caution/Survival/Lockdown)")
        return

    elif cmd == "extend survival":
        args = auth.get("args")
        minutes = int(args[0]) if args and args[0].isdigit() else 30
        from dos_guardian import extend_survival_mode
        total_extend_mins = extend_survival_mode(minutes)
        await _send_telegram(
            f"🛡️ SURVIVAL MODE EXTENDED\n"
            f"Added {minutes} minutes of survival duration.\n"
            f"Total extended time: {total_extend_mins} minutes."
        )
        return

    elif cmd == "decrypt archive":
        from vault_guardian import decrypt_file_to_memory
        args = auth.get("args")
        if args:
            filename = args[0]
            content = decrypt_file_to_memory(filename)
            if content.startswith("ERROR") or content.startswith("CRITICAL"):
                await _send_telegram(f"❌ {content}")
            else:
                await _send_telegram(f"📖 *DECRYPTED ARCHIVE: {filename}*\n\n{content}")
        else:
            await _send_telegram("⚠️ Missing filename to decrypt.")
        return

    elif cmd == "update":
        from immunity_core import fim_authorize_via_telegram, FIM_PENDING_FILE
        if not FIM_PENDING_FILE.exists():
            await _send_telegram("ℹ️ No file changes awaiting authorization.")
            return

        pending = json.loads(FIM_PENDING_FILE.read_text())
        files = [v["file"] for v in pending.get("violations", [])]

        if fim_authorize_via_telegram():
            await _send_telegram(
                f"✅ Authorized {len(files)} file(s):\n"
                + "\n".join(f"• {f}" for f in files)
                + "\n\nManifest will update in 30 seconds."
            )
        else:
            await _send_telegram("❌ Authorization failed - Redis error.")
        return

    if "list" in text.lower() or "campaign" in text.lower() or "status" in text.lower():
        table = _build_campaign_table()
        await _send_telegram(f"📊 *ACTIVE CAMPAIGNS*\n━━━━━━━━━━━━━━━\n{table}")

    # ── Command /mode — Operating Profile configuration ──────────────────
    elif text.lower().startswith("/mode"):
        parts = text.lower().split()
        sub = parts[1] if len(parts) > 1 else "status"

        from dos_guardian import (get_operational_profile, set_system_mode,
                                   set_infrastructure_mode)

        if sub == "status":
            profile = get_operational_profile()
            icon_sec = {"NORMAL": "🟢", "CAUTION": "🟡", "SURVIVAL": "🟠", "LOCKDOWN": "🔴"
                       }.get(profile["security_mode"], "⚪")
            icon_inf = {"LOCAL_ONLY": "💾", "HYBRID": "🔀", "CLOUD_ONLY": "☁️", "CLOUD_BOOSTED": "⚡☁️"
                       }.get(profile["infra_mode"], "⚪")
            await _send_telegram(
                f"⚙️ *Operational Profile*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"Profile: `{profile['profile']}`\n"
                f"{icon_sec} Security: `{profile['security_mode']}`\n"
                f"{icon_inf} Infrastructure: `{profile['infra_mode']}`\n"
                f"☁️ Compute Level: `{profile['compute_level']}`\n\n"
                f"• Allow Recommendations: {'✅' if profile['allow_new_recs'] else '❌'}\n"
                f"• A03 Weight: `{profile['a03_weight']}`\n\n"
                f"_Commands: /mode safe | continuous | smart | max | cloud_off_"
            )

        elif sub == "safe":
            set_infrastructure_mode("LOCAL_ONLY", "User Action: ASSET PROTECTION")
            set_system_mode("CAUTION", "User Action: ASSET PROTECTION")
            await _send_telegram(
                "🛡️ *SAFE MODE — SURVIVAL*\n"
                "• Infra: LOCAL_ONLY (No cloud)\n"
                "• Security: CAUTION\n"
                "• A04/A05: Local Qwen3 Only"
            )

        elif sub == "continuous":
            set_infrastructure_mode("HYBRID", "User Action: CONTINUOUS OPERATION")
            set_system_mode("NORMAL", "User Action: CONTINUOUS OPERATION")
            await _send_telegram(
                "🔀 *CONTINUOUS OPERATION MODE*\n"
                "• Infra: HYBRID\n"
                "• Security: NORMAL\n"
                "• A04/A05: Local + Cloud"
            )

        elif sub == "smart":
            set_infrastructure_mode("HYBRID", "User Action: SMART OPERATION")
            set_system_mode("NORMAL", "User Action: SELF STUDY")
            await _send_telegram(
                "🧠 *SMART MODE — SELF LEARNING*\n"
                "• Infra: HYBRID\n"
                "• Security: NORMAL\n"
                "• A09 AEO Hunter: ACTIVE"
            )

        elif sub == "max":
            set_infrastructure_mode("CLOUD_BOOSTED", "User Action: MAX POWER")
            set_system_mode("NORMAL", "User Action: MAX POWER")
            await _send_telegram(
                "⚡ *MAX POWER MODE — CLOUD BOOSTED*\n"
                "• Infra: CLOUD_BOOSTED\n"
                "• Security: NORMAL\n"
                "• Priority: Flash + Pro API"
            )

        elif sub in ("cloud_off", "cloud-off"):
            set_infrastructure_mode("LOCAL_ONLY", "User Action: Turn off Cloud")
            await _send_telegram(
                "💾 *CLOUD OFF — LOCAL ONLY*\n"
                "• A04/A05: Local model only"
            )

        elif sub == "freeze":
            from dos_guardian import freeze_system
            freeze_system("User Action: FREEZE SYSTEM")
            await _send_telegram(
                "❄️ *FROZEN MODE*\n"
                "• Cloud: ❌ NOT AVAILABLE\n"
                "• Hardware/GPU: ❌ NOT AVAILABLE\n"
                "• Security: SURVIVAL (Automatic)"
            )

        elif sub in ("cloud_detach", "cloud-detach", "detach"):
            from dos_guardian import detach_to_cloud
            detach_to_cloud("User Action: DETACH HARDWARE")
            await _send_telegram(
                "☁️🔒 *DETACH HARDWARE — CLOUD ONLY*\n"
                "• GPU/HW: 🔌 OFFLINE\n"
                "• Cloud: ✅ ACTIVE"
            )

        elif sub == "recovery":
            from dos_guardian import advance_recovery_step, get_frozen_status
            frozen = get_frozen_status()
            if not frozen.get("frozen") and not frozen.get("in_recovery"):
                await _send_telegram(
                    "ℹ️ System is not frozen or in recovery.\n"
                    "No recovery needed."
                )
            else:
                result = advance_recovery_step()
                step = result.get("step", "?")
                total = result.get("total", 4)
                desc = result.get("desc", "?")
                await _send_telegram(
                    f"🌱 *RECOVERY STEP {step}/{total}*\n"
                    f"• {desc}\n\n"
                    f"Next step: /mode recovery"
                )

        else:
            await _send_telegram(
                "⚙️ *Mode Commands /mode*\n"
                "• `/mode status`      — View current profile\n"
                "• `/mode safe`        — Safe Mode\n"
                "• `/mode continuous`  — Continuous Operation\n"
                "• `/mode smart`       — Smart Mode\n"
                "• `/mode max`         — Max Power Mode\n"
                "• `/mode cloud_off`   — Cloud Off\n"
                "─────────────────────\n"
                "• `/mode freeze`      — Freeze System\n"
                "• `/mode cloud_detach`— Cloud Detach\n"
                "• `/mode recovery`    — Step-by-step Recovery"
            )

    elif text.lower().startswith("/cloud"):
        await _send_telegram("ℹ️ Cloud Health Prober function has been deprecated.")

    # ── Command /boost — A04 Boosting Mode control ─────────────────────
    elif text.lower().startswith("/boost"):
        parts = text.lower().split()
        sub = parts[1] if len(parts) > 1 else "status"

        def _boost_set(mode: str) -> bool:
            try:
                matrix.set("SYSTEM", "boost_mode", mode)
                return True
            except Exception:
                return False

        def _boost_get_status() -> str:
            mode = matrix.get("SYSTEM", "boost_mode") or "ON"
            hb = matrix.get("SYSTEM", "boost_heartbeat")
            icon = {"ON": "🟢", "PAUSE": "⏸️", "SLOW": "🐢", "OFF": "🔴"}.get(mode, "⚪")

            groq_info = ""
            cerebras_info = ""
            pairs_today = "?"
            if hb:
                try:
                    pairs_today = hb.get("pairs_today", "?")
                    groq = hb.get("groq", {})
                    cer  = hb.get("cerebras", {})
                    groq_info = "  ".join(
                        f"Key{i}: RPM {v.get('rpm_used',0)}/60 TPD {v.get('tpd_used',0):,}"
                        for i, v in groq.items()
                    )
                    cerebras_info = "  ".join(
                        f"Key{i}: RPM {v.get('rpm_used',0)}/30 TPD {v.get('tpd_used',0):,}"
                        for i, v in cer.items()
                    )
                except Exception:
                    pass

            from pathlib import Path as _P
            boost_file = _P(__file__).parent.parent / "dpo_lab" / "a04" / "boost" / "boost_pairs.jsonl"
            total_pairs = 0
            if boost_file.exists():
                with open(boost_file) as bf:
                    total_pairs = sum(1 for _ in bf)

            return (
                f"🏭 *A04 Boosting Mode*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"{icon} Mode: `{mode}`\n"
                f"📦 Pairs Today: `{pairs_today}` | Total: `{total_pairs}`\n\n"
                f"🔹 *Groq (32B)*:\n_{groq_info or 'No heartbeat yet'}_\n\n"
                f"🔸 *Cerebras (235B)*:\n_{cerebras_info or 'No heartbeat yet'}_\n\n"
                f"_Commands: /boost on | pause | slow | off | gen_"
            )

        if sub == "status":
            await _send_telegram(_boost_get_status())

        elif sub == "on":
            if _boost_set("ON"):
                await _send_telegram("🟢 *A04 BOOSTING — ON*")
            else:
                await _send_telegram("❌ Failed to set Redis")

        elif sub == "pause":
            if _boost_set("PAUSE"):
                await _send_telegram("⏸️ *A04 BOOSTING — PAUSED*")
            else:
                await _send_telegram("❌ Failed to set Redis")

        elif sub == "slow":
            if _boost_set("SLOW"):
                await _send_telegram("🐢 *A04 BOOSTING — SLOW*")
            else:
                await _send_telegram("❌ Failed to set Redis")

        elif sub == "off":
            if _boost_set("OFF"):
                await _send_telegram("🔴 *A04 BOOSTING — OFF*")
            else:
                await _send_telegram("❌ Failed to set Redis")

        elif sub == "gen":
            import subprocess, threading
            def _run_gen():
                try:
                    from pathlib import Path as _P2
                    script = str(_P2(__file__).parent / "boost_scenario_gen.py")
                    subprocess.run(["python", script, "--generate", "--batch-size", "14"],
                                   timeout=300, capture_output=True)
                except Exception as e:
                    log.error(f"Gen scenario error: {e}")
            threading.Thread(target=_run_gen, daemon=True).start()
            await _send_telegram("🏭 *Generating 14 blind scenarios*")

        else:
            await _send_telegram(
                "🏭 *Boost Commands /boost*\n"
                "━━━━━━━━━━━━━━━\n"
                "• `/boost status` — View status and statistics\n"
                "• `/boost on`     — Turn on boosting\n"
                "• `/boost pause`  — Pause boosting\n"
                "• `/boost slow`   — Slow down boosting\n"
                "• `/boost off`    — Turn off boosting\n"
                "• `/boost gen`    — Generate new scenarios"
            )

    else:
        # ── FALLBACK: Semantic Intent Engine ──
        pending_key = f"{REDIS_PENDING_CONFIRM_PREFIX}:{incoming_chat_id}"
        ts_key      = f"{REDIS_PENDING_INTENT_TS_PREFIX}:{incoming_chat_id}"
        fail_key    = f"zcl:butler:semantic_fail:{incoming_chat_id}"

        existing_ts = matrix.get("A06", f"pending_intent_ts:{incoming_chat_id}")
        fail_count = matrix.incr("A06", f"semantic_fail:{incoming_chat_id}")
        if fail_count == 1:
            matrix.expire("A06", f"semantic_fail:{incoming_chat_id}", 120)

        should_challenge = False
        if fail_count >= 5:
            should_challenge = True
        elif existing_ts:
            age_seconds = time.time() - float(existing_ts)
            if age_seconds >= 120:
                should_challenge = True

        if should_challenge:
            matrix.delete("A06", f"pending_confirm:{incoming_chat_id}")
            matrix.delete("A06", f"pending_intent_ts:{incoming_chat_id}")
            matrix.delete("A06", f"semantic_fail:{incoming_chat_id}")
            await _trigger_totp_challenge_now(incoming_chat_id)
            return

        async def _xu_ly_semantic():
            proposed_cmd = await asyncio.get_event_loop().run_in_executor(
                None, _call_llm_semantic_intent, text
            )
            if proposed_cmd:
                matrix.set("A06", f"pending_confirm:{incoming_chat_id}", proposed_cmd, expire=300)
                matrix.set("A06", f"pending_intent_ts:{incoming_chat_id}", str(time.time()), expire=300)
                await _send_telegram(
                    f"🤔 *System could not recognize the command format.*\n"
                    f"Did you mean to run:\n\n"
                    f"`{proposed_cmd}`\n\n"
                    f"Type `yes` to confirm, or copy the command above and send it."
                )

        asyncio.create_task(_xu_ly_semantic())


def _get_agent05_recommendation(coin: str) -> dict:
    """Retrieve the latest recommendation from Agent 05."""
    data = matrix.get("A05", REDIS_AGENT05_KEY)
    if data:
        try:
            if data.get('coin') == coin or data.get('ma_tien_ao') == coin or data.get('tu_khoa_quet') == coin.split('/')[0]:
                plan  = data.get('ke_hoach_vao_lenh', {})
                qlt   = data.get('quan_ly_lenh', {})
                ep    = data.get('khuyen_nghi', {}).get('elliott_params', {})
                return {
                    "stop_loss":              qlt.get('stop_loss_cung') or qlt.get('stop_loss'),
                    "target_1":               qlt.get('target_1'),
                    "target_2":               qlt.get('target_2'),
                    "trailing_stop":          qlt.get('trailing_stop'),
                    "leverage":               ep.get('don_bay', 1),
                    "estimated_liquidation_zone": ep.get('vung_thanh_ly_du_kien'),
                    "take_profit_plan":       ep.get('take_profit_plan', []),
                    "hold_bias":              ep.get('hold_bias', 'UNKNOWN'),
                    "capital_allocation_pct": ep.get('phan_bo_von_pct', 0),
                }
        except Exception:
            pass
    return {}


def _tin_nhan_riding_alert(event: dict) -> str:
    """Format position riding alerts from Agent 05."""
    coin = event.get("coin", "?")
    leverage = event.get("leverage", 1)
    profit = event.get("leveraged_profit_pct", 0)
    alerts = event.get("alerts", [])
    snapshot_id = event.get("snapshot_id", "")
    table = _build_campaign_table()

    if not alerts:
        return ""

    first = alerts[0].upper()
    if "EMERGENCY_EXIT" in first or "THOAT_KHAN_CAP" in first or "KHAN_CAP_THANH_LY" in first:
        icon = "🚨🚨🚨"
        header = "EMERGENCY — EXIT POSITION IMMEDIATELY"
    elif "REDUCE_LEVERAGE" in first or "GIAM_DON_BAY" in first or "START_EXIT" in first:
        icon = "⚠️⚠️"
        header = "WARNING — Reduce leverage / Exit partially"
    else:
        icon = "⚠️"
        header = "Attention — Distribution signal"

    alert_lines = "\n".join(f"• {a}" for a in alerts[:4])

    return (
        f"{icon} *{header}*\n"
        f"`{coin}` ({leverage}x)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Current Profit: *+{profit:.1f}%*\n\n"
        f"📊 *Agent 05 Signal:*\n"
        f"{alert_lines}\n\n"
        f"🔹 Snap: `{snapshot_id}`\n\n"
        f"📊 *ACTIVE CAMPAIGNS*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{table}"
    )


# ════════════════════════════════════════════════════════════════════
# SECTION 7 — MAIN MONITORING LOOP
# ════════════════════════════════════════════════════════════════════

def quet_tat_ca_chien_dich() -> str:
    """
    Scan all active campaigns periodically.
    Trigger Telegram alerts ONLY on critical status changes.
    """
    timestamp_unix = int(time.time())
    campaigns = _get_all_campaigns()

    results: Dict[str, Any] = {
        "agent_id": "06_OVERVIEW",
        "timestamp_unix": timestamp_unix,
        "timestamp_readable": datetime.utcfromtimestamp(timestamp_unix).strftime('%Y-%m-%d %H:%M:%S UTC'),
        "active_campaign_count": len(campaigns),
        "recent_event": None,
        "telegram_notification": None,
        "next_action": "STANDBY",
    }

    if not campaigns:
        log.info(json.dumps({"event": "SCAN_COMPLETE", "result": "NO_ACTIVE_CAMPAIGNS", **results}))
        return json.dumps(results, ensure_ascii=False)

    for name, data in campaigns.items():
        status = data.get('monitoring_status', '')

        if status in ("COMPLETED", "EMERGENCY_CANCEL", "CANCELLED_BY_USER"):
            continue

        coin = data.get('coin', '')
        snap_id = data.get('snapshot_id_a05', '')
        if snap_id:
            riding_data = matrix.get("A05", f"riding_alert:{snap_id}")
            if riding_data:
                try:
                    alerts = riding_data.get("alerts", [])
                    if alerts:
                        alerts_hash = str(sorted(alerts))[:50]
                        if matrix.get("A06", f"riding_sent:{snap_id}") != alerts_hash:
                            event_riding = {
                                "type": "RIDING_ALERT",
                                "coin": riding_data.get("coin", coin),
                                "leverage": riding_data.get("leverage", data.get("actual_leverage", 1)),
                                "leveraged_profit_pct": riding_data.get("leveraged_profit_pct", 0),
                                "alerts": alerts,
                                "snapshot_id": snap_id,
                            }
                            riding_msg = _tin_nhan_riding_alert(event_riding)
                            if riding_msg:
                                asyncio.run(_send_telegram(riding_msg))
                                matrix.set("A06", f"riding_sent:{snap_id}", alerts_hash, expire=600)
                                results["recent_event"]  = event_riding
                                results["telegram_notification"]  = riding_msg[:200]
                                results["next_action"] = "REPORTED_RIDING_ALERT"
                except Exception as e:
                    log.warning(f"Riding alert parse error: {e}")

        event = _check_exchange_order(name, data)
        if not event:
            continue

        event_type = event['type']
        msg = None

        if event_type == "ORDER_FILLED":
            msg = _format_order_filled_msg(event, data)
            _update_campaign(name, monitoring_status="MONITORING_POSITION")

        elif event_type in ("TARGET_1_REACHED", "TARGET_2_REACHED"):
            msg = _format_target_msg(event, data)
            if event_type == "TARGET_1_REACHED":
                _update_campaign(name, monitoring_status="TARGET_1_REACHED")
            else:
                _delete_campaign(name, reason="TARGET_2_MET_COMPLETED")

        elif event_type == "STOP_LOSS_TRIGGERED":
            msg = _format_stop_loss_msg(event)
            _update_campaign(name, monitoring_status="MONITORING_POSITION")

        if msg:
            use_jitter = (event_type == "ORDER_FILLED")
            asyncio.run(_send_telegram(msg, jitter=use_jitter))
            results["recent_event"] = event
            results["telegram_notification"] = msg[:200]
            results["next_action"] = "REPORTED_STATUS_CHANGE"

    log.info(json.dumps({"event": "SCAN_COMPLETE", **results}))
    return json.dumps(results, ensure_ascii=False)


# ════════════════════════════════════════════════════════════════════
# SECTION 8 — TELEGRAM CONSUMER & LISTENER INITIALIZATION
# ════════════════════════════════════════════════════════════════════

_TELE_QUEUE_GROUP = "butler_consumers"
_TELE_QUEUE_CONSUMER = "a06_butler"
_tele_queue_initialized = False

def _ensure_telegram_queue_group():
    """Idempotently initialize Redis Stream consumer group."""
    global _tele_queue_initialized
    if _tele_queue_initialized:
        return
    try:
        matrix.xgroup_create("SYSTEM", "telegram:queue", _TELE_QUEUE_GROUP, id="0", mkstream=True)
        log.info("[BUTLER] Consumer group 'butler_consumers' initialized on telegram:queue.")
    except Exception:
        pass
    _tele_queue_initialized = True


async def _check_telegram_queue(context: ContextTypes.DEFAULT_TYPE):
    """Read queue stream via consumer group. XACK only after successful delivery."""
    _ensure_telegram_queue_group()
    
    for _ in range(10):
        try:
            stream_entries = matrix.xreadgroup(
                "SYSTEM", "telegram:queue",
                _TELE_QUEUE_GROUP, _TELE_QUEUE_CONSUMER,
                count=5, block=10
            )
            if not stream_entries:
                break

            for _stream_key, messages in stream_entries:
                for msg_id, fields in messages:
                    raw_payload = fields.get(b"payload") or fields.get("payload", "{}")
                    if isinstance(raw_payload, bytes):
                        raw_payload = raw_payload.decode("utf-8")
                    try:
                        data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                    except Exception:
                        data = {}

                    msg_type = data.get("type", "")
                    text = data.get("report_text", "")
                    cycle = data.get("cycle", "?")
                    sent_ok = False

                    try:
                        if msg_type == "A07_TO_A06_REPORT" and text:
                            header = f"📡 *A07 APEX STRATEGIST REPORT (Cycle #{cycle})*\n━━━━━━━━━━━━━━━\n"
                            await _send_telegram(header + text, channel="COMMON")
                            sent_ok = True

                        elif msg_type == "A05_TO_A06_REPORT" and text:
                            header = f"⚡ *A05 DECISION VERDICT REPORT (Cycle #{cycle})*\n━━━━━━━━━━━━━━━\n"
                            await _send_telegram(header + text, channel="ELITE")
                            sent_ok = True

                        elif msg_type == "A03_TO_A06_REPORT" and text:
                            header = f"📊 *A03 CROWD PSYCHOLOGY REPORT (Cycle #{cycle})*\n━━━━━━━━━━━━━━━\n"
                            await _send_telegram(header + text, channel="COMMON")
                            sent_ok = True

                        elif msg_type == "A04_TO_A06_REPORT" and text:
                            header = f"📈 *A04 PRICE ACTION REPORT (Cycle #{cycle})*\n━━━━━━━━━━━━━━━\n"
                            await _send_telegram(header + text, channel="COMMON")
                            sent_ok = True

                        elif msg_type == "A08_TO_A06_REPORT" and text:
                            header = f"👥 *A08 SWARM ORACLE REPORT (Cycle #{cycle})*\n━━━━━━━━━━━━━━━\n"
                            await _send_telegram(header + text, channel="COMMON")
                            sent_ok = True

                        elif msg_type == "A10_TO_A06_REPORT" and text:
                            header = f"💼 *A10 ELITE FLOW REPORT (Cycle #{cycle})*\n━━━━━━━━━━━━━━━\n"
                            await _send_telegram(header + text, channel="COMMON")
                            sent_ok = True

                        elif msg_type == "A11_TO_A06_REPORT" and text:
                            header = f"🧠 *A11 STRATEGIC INTENT REPORT (Cycle #{cycle})*\n━━━━━━━━━━━━━━━\n"
                            await _send_telegram(header + text, channel="COMMON")
                            sent_ok = True

                        elif msg_type == "A12_TO_A06_REPORT" and text:
                            header = f"🔍 *A12 MANIPULATION DETECT REPORT (Cycle #{cycle})*\n━━━━━━━━━━━━━━━\n"
                            await _send_telegram(header + text, channel="COMMON")
                            sent_ok = True

                        elif msg_type == "ELITE_ALERT" and text:
                            header = f"🚨 *BREAKING GEOPOLITICAL ALERT*\n━━━━━━━━━━━━━━━\n"
                            await _send_telegram(header + text, channel="SYSTEM")
                            sent_ok = True

                        elif msg_type in ("A09_ALERT", "ROUTER_TIMEOUT", "ALERT", "IMMUNITY_ALERT") and text:
                            await _send_telegram(text)
                            sent_ok = True

                        else:
                            sent_ok = True

                    except Exception as send_err:
                        log.error(f"[BUTLER] Telegram delivery error (msg {msg_id}): {send_err}")
                        sent_ok = False

                    if sent_ok:
                        try:
                            matrix.xack("SYSTEM", "telegram:queue", _TELE_QUEUE_GROUP, msg_id)
                        except Exception as ack_err:
                            log.warning(f"[BUTLER] XACK failed for {msg_id}: {ack_err}")

        except Exception as e:
            log.error(f"Error reading telegram queue stream: {e}")
            break

def chay_telegram_listener():
    """Start the Telegram bot event listener loop (blocking)."""
    global bot
    if not TELEGRAM_BOT_TOKEN:
        log.error("Fatal Error: TELEGRAM_BOT_TOKEN is missing!")
        return
        
    if not bot:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT | filters.COMMAND, _handle_message))

    async def _organic_heartbeat(context):
        try:
            matrix.publish_heartbeat("A06", {"status": "BUTLER_ALIVE", "vibe": "TELEGRAM_JOB"})
            await _check_telegram_queue(context)
        except Exception as e:
            log.warning(f"Heartbeat error: {e}")
    app.job_queue.run_repeating(_organic_heartbeat, interval=60, first=5)

    from telegram.ext import CommandHandler as _CmdHandler
    app.add_handler(_CmdHandler("judge", _xu_ly_judge))
    app.add_handler(_CmdHandler("extend_survival", _xu_ly_gia_han))
    app.add_handler(_CmdHandler("otp", _xu_ly_otp))

    log.info("Agent 06 — Telegram listener activated. Listening for commands...")
    
    try:
        import sys, os
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
        from tools.telegram_scraper import start_scraper_thread
        start_scraper_thread()
        log.info("Agent 06 — Telegram Scraper thread activated.")
    except Exception as e:
        log.error(f"Error starting Telegram Scraper: {e}")

    app.run_polling(drop_pending_updates=True)


async def _xu_ly_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /otp <code>
    Save OTP code to Redis for Telethon Scraper authentication.
    """
    incoming_chat_id = str(update.effective_chat.id)
    if incoming_chat_id != str(TELEGRAM_CHAT_ID):
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("❌ Missing code. Format: /otp <6_digit_code>")
        return
        
    code = str(args[0]).strip()
    try:
        matrix.set("SYSTEM", "telegram_otp", code, expire=300)
        await update.message.reply_text(f"✅ OTP [{code}] uploaded to pipeline. Scraper will log in shortly.")
    except Exception as e:
        await update.message.reply_text(f"❌ Redis write error: {e}")


async def _xu_ly_gia_han(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /extend_survival
    Add 30 minutes survival extension to avoid entering Lockdown/Defense Mode.
    """
    incoming_chat_id = str(update.effective_chat.id)
    if incoming_chat_id != str(TELEGRAM_CHAT_ID):
        return
        
    current_ext = int(matrix.get("SYSTEM", "survival_extension") or 0)
    new_ext = current_ext + 1800
    matrix.set("SYSTEM", "survival_extension", new_ext)
    
    matrix.delete("SYSTEM", "defense_mode")
    try:
        from dos_guardian import set_defense_mode
        set_defense_mode(False, "USER_EXTENDED_SURVIVAL")
    except Exception: pass
    
    await update.message.reply_text(
        f"✅ *SURVIVAL MODE EXTENDED*\n"
        f"Added 30 minutes (Total: {new_ext // 60} minutes).\n"
        f"Defense mode temporarily disabled.",
        parse_mode=ParseMode.MARKDOWN
    )


async def _xu_ly_judge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /judge [sub_command]
    Query post-mortem data from Agent 05.
    """
    incoming_chat_id = str(update.effective_chat.id)
    if incoming_chat_id != str(TELEGRAM_CHAT_ID):
        return

    args = context.args or []
    sub = args[0].lower() if args else "postmortem"

    try:
        from dpo_report import (
            format_postmortem_for_telegram,
            get_recent_postmortems,
            get_riding_errors_active,
        )
    except ImportError as e:
        await update.message.reply_text(f"⚠️ Import error: {e}")
        return

    if sub == "postmortem":
        record = matrix.get("A05", "postmortem:latest")
        if not record:
            await update.message.reply_text("📭 No post-mortem records available yet.")
            return
        try:
            msg = format_postmortem_for_telegram(record)
        except Exception as e:
            msg = f"⚠️ Error reading post-mortem: {e}"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    elif sub == "mistakes":
        items = get_recent_postmortems(n=5)
        if not items:
            await update.message.reply_text("📭 No mistake records found in Redis.")
            return
        lines = ["🔴 *5 MOST RECENT MISTAKES — A05 POST-MORTEM*", "━━━━━━━━━━━━━━"]
        for i, item in enumerate(items, 1):
            ts   = datetime.fromtimestamp(item.get("ts", 0), tz=timezone.utc).strftime("%d/%m %H:%M")
            mode = item.get("mode", "?")
            snap = item.get("snapshot_id", "?")[:12]
            lesson = item.get("lesson", "N/A")[:120]
            icon = "🎯" if mode == "HUNTING" else "🏇"
            lines.append(f"{i}. {icon} `{snap}` [{ts}]")
            lines.append(f"   _{lesson}_")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    elif sub == "riding":
        items = get_riding_errors_active()
        if not items:
            await update.message.reply_text("✅ No active riding errors being tracked.")
            return
        lines = ["🏇 *ACTIVE RIDING ERRORS BEING TRACKED*", "━━━━━━━━━━━━━━"]
        ERR_ICON = {
            "LEVERAGE_WICKED":    "⚡",
            "EXIT_TOO_EARLY_PENNY": "💎",
            "EXIT_TOO_LATE_MAJOR":  "🐘",
            "OVER_LEVERAGE_IMPULSE": "🚀",
        }
        for item in items[:8]:
            coin   = item.get("coin", "?")
            alerts = item.get("alerts", [])
            ts     = item.get("ts", 0)
            age    = int((time.time() - ts) / 60)
            for a in alerts[:1]:
                for key, icon in ERR_ICON.items():
                    if key in a:
                        lines.append(f"{icon} *{coin}* — {key} ({age}m ago)")
                        break
                else:
                    lines.append(f"⚠️ *{coin}* — {str(a)[:50]}")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    else:
        await update.message.reply_text(
            "📋 *Command /judge:*\n"
            "`/judge postmortem` — View recent post-mortem\n"
            "`/judge mistakes`   — View recent mistakes\n"
            "`/judge riding`     — View active riding errors",
            parse_mode=ParseMode.MARKDOWN
        )


# ── Tool Definitions for OpenClaw ─────────────────────────────────────────────
TOOL_DEFINITION = {
    "name": "quet_tat_ca_chien_dich",
    "description": (
        "Main Monitoring Scan — Checks all tracked exchange orders by calling live exchange APIs. "
        "Sends Telegram updates when orders are filled, targets hit, or stop loss is reached."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_KHAN_CAP_DEFINITION = {
    "name": "xu_ly_lenh_khan_cap_tu_agent04",
    "description": "Receive emergency cancel instructions from Agent 04 and broadcast via Telegram.",
    "parameters": {
        "type": "object",
        "properties": {
            "campaign_name": {
                "type": "string",
                "description": "Campaign name to cancel immediately",
            },
            "reason": {
                "type": "string",
                "description": "Reason for cancellation",
            },
        },
        "required": ["campaign_name", "reason"],
    },
}


if __name__ == "__main__":
    print("=== TEST Agent 06 — Telegram Butler ===")
    print("Running check cycle...")
    print(json.dumps(json.loads(quet_tat_ca_chien_dich()), indent=2, ensure_ascii=False))
    print("\nStarting Telegram listener (Ctrl+C to stop)...")
    chay_telegram_listener()
