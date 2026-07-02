"""
🧬 DNA: v16.6 (Sovereign Purity & Butler Sandbox) [DNA Header]
🏢 UNIT: BUTLER_WRAPPER (A06)
🛠️ ROLE: COMM_SANDBOX_PROTECTOR
📖 DESC: Sandbox protection layer for Agent 06 (Telegram Butler), handling key injection from RAM and monitoring outbound communication flow via OpenShell.
🔗 CALLS: agents/logic/a06_butler.py, tools/imperial_state.py
📟 I/O: Telegram Bot API, Redis: zcl:A06:heartbeat
🛡️ INTEGRITY: In-Memory-Injection, Egress-Policy-Whitelist, Butler-Isolation.
"""

# Tasks:
# 1. Read keys (TELEGRAM, BINANCE, BYBIT) from .env
# 2. Store keys in internal memory (RAM).
# 3. SANITIZE (clear) keys from os.environ so the OS cannot spy on them.
# 4. Inject keys into the internal object of a06_butler.
# 5. Call `chay_telegram_listener()`.

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))

import os
import logging
from dotenv import load_dotenv

# Set up secure Logger
logging.basicConfig(level=logging.INFO, format='[OPENSHELL_A06] %(asctime)s %(message)s')
log = logging.getLogger("OPENSHELL_A06")

def main():
    log.info("Starting OpenShell V9 Shield for Agent 06...")
    
    # 1. Load keys from .env (can also load from a secure Vault)
    if not isinstance(BASE_DIR, Path) or not BASE_DIR.exists():
        log.error("Invalid BASE_DIR. Aborting startup.")
        sys.exit(1)
        
    env_path = BASE_DIR / "config" / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
    else:
        log.warning(f"Could not find .env file at {env_path}, running with OS env instead.")
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.getenv("TELEGRAM_CHAT_ID", "")
    chat_trade = os.getenv("TELEGRAM_CHAT_ID_TRADE")
    if not chat_trade and chat_id: chat_trade = chat_id
    chat_system = os.getenv("TELEGRAM_CHAT_ID_SYSTEM")
    if not chat_system and chat_id: chat_system = chat_id
    chat_alert = os.getenv("TELEGRAM_CHAT_ID_ALERT")
    if not chat_alert and chat_id: chat_alert = chat_id
    
    bin_api   = os.getenv("BINANCE_API_KEY", "")
    bin_sec   = os.getenv("BINANCE_SECRET_KEY", "")
    byb_api   = os.getenv("BYBIT_API_KEY", "")
    byb_sec   = os.getenv("BYBIT_SECRET_KEY", "")
    
    if not bot_token or len(bot_token) < 10:
        log.error("Missing valid TELEGRAM_BOT_TOKEN. Aborting startup.")
        sys.exit(1)
        
    if not chat_id:
        log.warning("Missing TELEGRAM_CHAT_ID. Some system alerts may not be delivered.")

    # 2. SANITIZE - Erase all footprint of keys on the operating system environment (OS Environment)
    sensitive_keys = [
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
        "TELEGRAM_CHAT_ID_TRADE", "TELEGRAM_CHAT_ID_SYSTEM", "TELEGRAM_CHAT_ID_ALERT",
        "BINANCE_API_KEY", "BINANCE_SECRET_KEY",
        "BYBIT_API_KEY", "BYBIT_SECRET_KEY"
    ]
    for key in sensitive_keys:
        if key in os.environ:
            del os.environ[key]
            
    log.info("OS env sanitized: Removed all traces of asset keys from the operating system.")
    
    # 3. Inject RAM and Import target logic (Physical Body)
    import a06_butler
    
    # Inject keys directly into the secure structure of a06_butler, fallback to module space
    a06_butler.TELEGRAM_BOT_TOKEN = bot_token
    a06_butler.TELEGRAM_CHAT_ID = chat_id
    a06_butler.TELEGRAM_CHAT_ID_TRADE = chat_trade
    a06_butler.TELEGRAM_CHAT_ID_SYSTEM = chat_system
    a06_butler.TELEGRAM_CHAT_ID_ALERT = chat_alert
    a06_butler.BINANCE_API_KEY = bin_api
    a06_butler.BINANCE_SECRET_KEY = bin_sec
    a06_butler.BYBIT_API_KEY = byb_api
    a06_butler.BYBIT_SECRET_KEY = byb_sec
    
    log.info("In-memory variables injected successfully into a06_butler.")
    
    log.info("Transferring control to Telegram Listener Core...")
    
    # 4. Activate Telegram Butler core logic
    try:
        a06_butler.chay_telegram_listener()
    except KeyboardInterrupt:
        log.info("Shutdown instruction received for OpenShell shield. Stopping...")
    except Exception as e:
        log.error(f"A06 Butler system error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
