"""
🧬 DNA: v17.0
🏢 UNIT: DIRECTOR (A06) - EXTENSION
🛠️ ROLE: Telegram Data Collector (Telethon Headless)
📖 DESC: Module to scrape data from public channels
"""
import os
import asyncio
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

try:
    from tools.imperial_state import matrix
except ImportError:
    from imperial_state import matrix

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../config/.env'))

TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID", "")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")

# Use shared DB of the Swarm
SESSION_FILE = os.path.join(os.path.dirname(__file__), '../config/a06_scraper.session')

log = logging.getLogger("TELEGRAM_SCRAPER")
if not log.handlers:
    log.setLevel(logging.INFO)
    log.addHandler(logging.StreamHandler())

WHITELIST_CHANNELS = [
    "cointelegraph",
    "binancekillers",
    "WhaleAlert",
    "CryptoMichNL",
    "cryptocompass",
    "bitcoinbulls"
]

def _run_scraper_loop():
    """Start isolated async thread for Scraper"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_telethon_scraper())
    except Exception as e:
        log.error(f"[SCRAPER] Crash: {e}")
    finally:
        loop.close()

async def run_telethon_scraper():
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH or not TELEGRAM_PHONE:
        log.warning("[SCRAPER] Missing API_ID / API_HASH / PHONE. Will not scrape Telegram.")
        return

    if not str(TELEGRAM_API_ID).isdigit():
        log.warning("[SCRAPER] TELEGRAM_API_ID invalid. Will not scrape Telegram.")
        return

    client = TelegramClient(SESSION_FILE, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
    
    await client.connect()
    if not await client.is_user_authorized():
        log.info(f"[SCRAPER] Requesting OTP code for number {TELEGRAM_PHONE}...")
        try:
            req = await client.send_code_request(TELEGRAM_PHONE)
            
            # Write OTP waiting status to matrix for A06 Butler to report to the Owner
            matrix.set("SYSTEM", "telegram_scraper:status", "WAITING_OTP", expire=3600)
            log.info("[SCRAPER] OTP sent. Waiting for the Owner to load OTP via '/otp <code>' command in A06.")
            
            phone_code = None
            for i in range(300): # Wait up to 50 minutes
                phone_code = matrix.get("SYSTEM", "telegram_otp")
                if phone_code:
                    log.info(f"[SCRAPER] Received OTP from Redis: {phone_code}. Logging in...")
                    matrix.delete("SYSTEM", "telegram_otp")
                    break
                await asyncio.sleep(10)
                
            if not phone_code:
                log.error("[SCRAPER] Timeout waiting for OTP. Disabling crawler.")
                return
                
            # Sign in
            try:
                await client.sign_in(TELEGRAM_PHONE, phone_code)
                matrix.set("SYSTEM", "telegram_scraper:status", "AUTHORIZED")
                log.info("[SCRAPER] Login successful!")
            except SessionPasswordNeededError:
                log.error("[SCRAPER] Account has 2FA Password. Must set 2FA directly in code if applicable.")
                return
        except Exception as e:
            log.error(f"[SCRAPER] Login error: {e}")
            return
            
    matrix.set("SYSTEM", "telegram_scraper:status", "AUTHORIZED")
    log.info("[SCRAPER] Authenticated, starting scrape loop...")
    
    # Scrape loop: runs periodically
    while True:
        try:
            aggregated_texts = []
            message_count = 0
            
            # Scan important channels
            for channel in WHITELIST_CHANNELS:
                try:
                    # Retrieve 100 most recent messages
                    messages = await client.get_messages(channel, limit=100)
                    for msg in messages:
                        if msg.text:
                            text_safe = msg.text[:600].replace('\n', ' ')
                            aggregated_texts.append(f"[{channel.upper()}] {text_safe}")
                            message_count += 1
                except Exception as ce:
                    log.warning(f"[SCRAPER] Error scraping channel {channel}: {ce}")
                    continue
            
            if message_count > 0:
                payload = {
                    "message_count": message_count,
                    "sample_texts": aggregated_texts,
                    "timestamp": time.time()
                }
                matrix.set("SYSTEM", "a06:telegram:latest", json.dumps(payload), expire=7200) # Keep for 2 hours
                log.info(f"[SCRAPER] Scraped {message_count} messages. Overwriting a06:telegram:latest")
                
            await asyncio.sleep(300) # sleep 5 minutes
            
        except Exception as loop_e:
            log.error(f"[SCRAPER] Loop error: {loop_e}")
            await asyncio.sleep(600)

def start_scraper_thread():
    """Called from a06_butler.py"""
    import threading
    t = threading.Thread(target=_run_scraper_loop, daemon=True, name="TelethonScraper")
    t.start()
    return t

if __name__ == "__main__":
    _run_scraper_loop()
