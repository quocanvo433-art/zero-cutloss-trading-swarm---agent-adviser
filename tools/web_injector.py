"""
🧬 DNA: v17.0 (Sovereign Reporting Pipeline)
🏢 UNIT: HANDS (A07)
🛠️ ROLE: Snapshot Aggregator & Telegram Injector
📖 DESC: Scan Redis to get Block 2 LLM outputs from A03-A12, chunk, and push to Telegram Queue.
"""

import sys
import os
import json
import time
import logging
import re
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))

try:
    from tools.imperial_state import matrix
except ImportError:
    from imperial_state import matrix
from chunking_engine import chunk_text

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
log = logging.getLogger("A07_INJECTOR")

SPACING_MIN_GIAY = 1800  # 30 minutes

def _strip_thinking_block(text: str) -> str:
    """Completely remove the <think>...</think> tag pair and its inner content"""
    if not text:
        return ""
    # Delete <think>...</think> (re.DOTALL to delete newlines as well)
    clean_text = re.sub(r'<think>.*?(?:</think>|$)', '', text, flags=re.DOTALL | re.IGNORECASE)
    return clean_text.strip()

def run_report_cycle(custom_trigger: bool = False, trigger: str = "CYCLE_30_MINUTES") -> str:
    log.info(f"🚀 [A07] Triggered report cycle (Trigger: {trigger})")
    
    agents = ["03", "04", "05", "06", "08", "09", "10", "11", "12"]
    tong_hop = []
    
    for aid in agents:
        raw_text = matrix.get("SYSTEM", f"snapshot_llm:a{aid}")
        if raw_text:
            clean_text = _strip_thinking_block(raw_text)
            if clean_text:
                tong_hop.append(f"--- AGENT A{aid} ---\n{clean_text}\n")
    
    if not tong_hop:
        log.info("⚠️ [A07] No snapshot data found in Redis.")
        return '{"status": "NO_DATA"}'
        
    full_report = "\n".join(tong_hop)
    
    # Chunk the report
    chunks = chunk_text(full_report, chunk_size_tokens=1000)
    log.info(f"✂️ [A07] Split report into {len(chunks)} chunks.")
    
    for idx, chunk in enumerate(chunks):
        payload = {
            "type": "A07_TO_A06_REPORT",
            "report_text": f"[ZCL_AGENT_REPORT] (Part {idx+1}/{len(chunks)})\n\n{chunk}"
        }
        matrix.rpush("SYSTEM", "telegram:queue", json.dumps(payload, ensure_ascii=False))
        
    log.info("✅ [A07] Pushed all chunks to telegram:queue.")
    return '{"status": "SUCCESS", "chunks": ' + str(len(chunks)) + '}'

def daemon_loop():
    log.info("🔥 Agent 07 DAEMON started — Queen's Hands new version.")
    
    last_run = 0
    while True:
        try:
            # Heartbeat every 60s
            matrix.publish_heartbeat("A07", {"status": "INJECTING", "target": "Telegram_Queue"})
        except Exception:
            pass

        now = time.time()
        if now - last_run >= SPACING_MIN_GIAY:
            try:
                run_report_cycle(trigger="DAEMON_TICK")
                last_run = now
            except Exception as e:
                log.error(f"[DAEMON] Error: {e}")
            
        time.sleep(60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Agent 07 — Queen's Hands")
    parser.add_argument("--daemon", action="store_true", help="Run in Daemon mode")
    args = parser.parse_args()

    if args.daemon:
        daemon_loop()
    else:
        run_report_cycle(custom_trigger=True, trigger="MANUAL_TEST")
