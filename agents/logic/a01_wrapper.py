"""
🧬 DNA: v16.6 (Sovereign Purity & Scheduled Mode)
🏢 UNIT: HOUND_WRAPPER (A01)
🛠️ ROLE: STERILE_SANDBOX_PROTECTOR
📖 DESC: Scheduled Mode (300s): Automatically wakes up to scrape market data. Removes Pub/Sub.
🔗 CALLS: agents/logic/a01_hound.py, tools/imperial_state.py
📟 I/O: Redis: zcl:a05:t0_stream, heartbeat:A01
🛡️ INTEGRITY: Persistent-Schedule, Sterile-Sandbox.
"""
import sys
import os
import time
import yaml
import logging
import subprocess
from pathlib import Path
from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))

def load_keys():
    env_path = os.path.join(BASE_DIR, "config/.env")
    return dotenv_values(env_path) if os.path.exists(env_path) else {}

# Load environment before matrix imports
# [FIX] Only inject keys if they are NOT in os.environ — respects Docker Compose env injection
# Previously the code overrode REDIS_URL=127.0.0.1 (from local .env) on top of redis:6379 (from Docker)
env_keys = load_keys()
if env_keys:
    for k, v in env_keys.items():
        if v and k not in os.environ:
            os.environ[k] = v

from imperial_state import matrix

logging.basicConfig(level=logging.INFO, format='[A01_WRAPPER] %(asctime)s - %(message)s')
log = logging.getLogger("A01_Wrapper")

def create_env(keys):
    env = {k: v for k, v in os.environ.items()}
    # [FIX] Only inject keys from .env if env does NOT contain them (Docker Compose has higher priority than .env file)
    keys_needed = ["BINANCE_API_KEY", "BINANCE_SECRET_KEY", "BYBIT_API_KEY", "BYBIT_SECRET_KEY", "REDIS_URL", "REDIS_PASSWORD"]
    for k in keys_needed:
        if k in keys and k not in env:
            env[k] = keys[k]
    return env

def run_agent_in_sandbox():
    log.info("Executing Agent 01 (Blood Claw) in Sandbox...")
    keys = load_keys()
    env = create_env(keys)
    target = os.path.join(os.path.dirname(__file__), "a01_hound.py")
    try:
        process = subprocess.Popen([sys.executable, target], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout: 
            print(line.strip())
        process.wait()
    except Exception as e: 
        log.error(f"Sandbox error: {e}")

def main_loop():
    last_run = 0
    while True:
        interval = 300 # Keep 300s as requested by Scheduled Heartbeat

        now = time.time()
        if now - last_run >= interval:
            log.info("Scheduled Update Pulse: Running A01 Scan...")
            import threading
            threading.Thread(target=run_agent_in_sandbox, daemon=True).start()
            last_run = now
        
        try:
            matrix.publish_heartbeat("A01", status="WATCHING", metadata={"next_run_in": int(interval - (now - last_run))})
        except Exception as e:
            log.warning(f"Heartbeat publish error: {e}")
        time.sleep(10)

if __name__ == "__main__":
    main_loop()
