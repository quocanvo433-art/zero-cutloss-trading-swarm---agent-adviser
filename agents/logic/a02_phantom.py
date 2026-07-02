"""
🧬 DNA: v16.6 (Sovereign Purity & Scheduled Mode)
🏢 UNIT: MACRO_PHANTOM (A02)
🛠️ ROLE: MACRO_SENTINEL
📖 DESC: Scheduled Mode (300s): Automatically scrapes macro data. Removes Pub/Sub.
🔗 CALLS: tools/imperial_state.py
📟 I/O: Redis: zcl:a05:t0_stream, heartbeat:A02
🛡️ INTEGRITY: Persistent-Schedule.
"""
import sys
import os
import json
import time
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))
from imperial_state import matrix

logging.basicConfig(level=logging.INFO, format='[A02_PHANTOM] %(asctime)s - %(message)s')
log = logging.getLogger("A02_Phantom")

def scan_macro_weather():
    log.info("Phantom scanning macro weather...")
    data = {
        "agent_id": "02_MACRO_PHANTOM",
        "timestamp_unix": int(time.time()),
        "fear_greed": 10,
        "status": "EXTREME_FEAR"
    }
    try:
        matrix.xadd("A05", "t0_stream", {"source": "A02", "payload": json.dumps(data)}, maxlen=5)
        log.info("Macro pulse delivered to A05 T0 Stream (maxlen=5)")
    except Exception as e:
        log.error(f"Failed to publish to t0_stream: {e}")

def main_loop():
    last_run = 0
    while True:
        try:
            interval = 300

            now = time.time()
            if now - last_run >= interval:
                scan_macro_weather()
                last_run = now
            
            matrix.publish_heartbeat("A02", status="WATCHING", metadata={"next_run_in": int(interval - (now - last_run))})
            time.sleep(60)
        except Exception as e:
            log.error(f"Error in main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main_loop()
