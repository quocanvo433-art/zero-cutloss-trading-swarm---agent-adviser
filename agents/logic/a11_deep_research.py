"""
🧬 DNA: v16.6 (Sovereign Purity) [DNA Header]
🏢 UNIT: A11
🛠️ ROLE: DEEP_ANALYST
📖 DESC: Deep Research analytical brain block (Tâm Mã)
"""
import json
import logging
import time
import sys
import os

# Set up separate log file for Deep Research
log = logging.getLogger("DeepResearch")
log.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log.addHandler(console_handler)

LOG_DIR = os.path.join("logs", "A11")
os.makedirs(LOG_DIR, exist_ok=True)
file_handler = logging.FileHandler(os.path.join(LOG_DIR, "deep_research.log"))
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log.addHandler(file_handler)


from imperial_brain import brain
from imperial_state import matrix

def generate_deep_research_report(generated_prompt: str):
    """
    CLAW 2: DEEP RESEARCH EXECUTION
    Receives prompt from Claw 1, uses Master AI to write a deep report,
    saves checkpoint if logs exceed 200k tokens.
    """
    log.info(f"=== ACTIVATING DEEP RESEARCH CLAW 2 (AI-Q) ===")
    try:
        log.info("[A11:3] Initiating Deep Analyst reasoning (Master Lattice)...")
        report_text = brain.think_as("A11_DEEP_ANALYST", generated_prompt, brain_mode="MASTER", est_tokens=2000)
        
        if report_text:
             clean_text = report_text.replace("```json", "").replace("```", "").strip()
             log.warning(f"🚨 [DEEP RESEARCH RESULT] 🚨\n{clean_text}")
             
             # 1. Send results to A05 and A12 via dedicated Redis Stream
             payload = {"source": "A11_AI-Q", "report": clean_text, "ts": int(time.time())}
             payload_str = json.dumps(payload, ensure_ascii=False)
             
             # Send to the unique stream reserved for Deep Research
             matrix.xadd("EMF", "deep_research_stream", {"event": "DEEP_RESEARCH", "data": payload_str}, maxlen=5)
             
             # Set TTL of 2 hours to self-destroy if not checked
             try:
                 stream_key = matrix._build_key("EMF", "deep_research_stream")
                 matrix.client.expire(stream_key, 7200)
             except: pass
             
             log.info("[A11:3] Broadcasted report to deep_research_stream (Maxlen 5, TTL 2h).")
             
             # 2. Session Logger Logic - Write to logs/A11_2/
             log_dir = os.path.join("logs", "A11_2")
             os.makedirs(log_dir, exist_ok=True)
             history_file = os.path.join(log_dir, "deep_history.txt")
             
             # Append with file locking
             import fcntl
             with open(history_file, "a", encoding="utf-8") as f:
                 fcntl.flock(f, fcntl.LOCK_EX)
                 f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n{clean_text}\n{'='*50}\n")
                 fcntl.flock(f, fcntl.LOCK_UN)
                 
             # Checkpoint if size exceeds 800k chars (~200k tokens)
             file_size = os.path.getsize(history_file)
             if file_size > 800 * 1024:
                 log.warning("[A11:3] Log size exceeds 200k tokens. Activating Checkpoint Summarization using high-end model!")
                 with open(history_file, "r", encoding="utf-8") as f:
                     full_history = f.read()
                 
                 checkpoint_prompt = f"Condense the following full history of deep research thinking into a single Core Checkpoint, linking the analytical flows:\n{full_history[:2000000]}"
                 checkpoint_text = brain.think_as("A11_CHECKPOINT", checkpoint_prompt, brain_mode="MASTER", est_tokens=4000)
                 
                 if checkpoint_text:
                     # Overwrite history with the checkpoint
                     temp_file = history_file + ".tmp"
                     with open(temp_file, "w", encoding="utf-8") as f:
                         f.write(f"--- GRAND CHECKPOINT ---\n{checkpoint_text}\n{'='*50}\n")
                     os.replace(temp_file, history_file)
                     # Publish Checkpoint to Stream as well
                     chk_payload = {"source": "A11_AI-Q", "report": f"[CHECKPOINT] {checkpoint_text}", "ts": int(time.time())}
                     matrix.xadd("EMF", "deep_research_stream", {"event": "DEEP_CHECKPOINT", "data": json.dumps(chk_payload, ensure_ascii=False)}, maxlen=5)
                     log.info("[A11:3] Checkpoint created successfully.")
                     
        else:
             log.error("[A11:3] Master AI reasoning failed.")
             
    except Exception as e:
        log.error(f"Deep Research Async Error: {e}")

if __name__ == "__main__":
    # Test file local trigger
    test_intent = '{"scenario": {"type": "CRISIS_INCOMING"}, "intent": {"composite_score": -45, "label": "STRONG_DISTRIBUTE"}}'
    generate_deep_research_report(test_intent)
