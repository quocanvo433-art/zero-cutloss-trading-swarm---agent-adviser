"""
🧬 DNA: v1.0 (Sovereign Purity — Swarm Interview Port)
🏢 UNIT: SWARM_DIAGNOSTIC (A08 Port)
🛠️ ROLE: IPC_INTERVIEWER
📖 DESC: Exclusive interview port for Lao Cong and IDE Agent.
         OTP validation and strict authorization check before querying agent inner state.
🔗 CALLS: tools/llm_router.py, agents/logic/a08_market_agents.py
📟 I/O: File IPC: tmp/a08_interview_cmd.json -> tmp/a08_interview_res.json
🛡️ INTEGRITY: OTP-Shielded, Role-Fenced, Isolated-Execution
"""

import os
import sys
import json
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))
sys.path.insert(0, str(BASE_DIR / "agents" / "logic"))

try:
    from llm_router import _call_algo
    from imperial_state import matrix
except ImportError:
    def _call_algo(prompt: str, agent_id: str, label: str, temp: float, tier: str = "ALGO") -> str:
        return "LLM_ROUTER_NOT_LOADED"
    class MockMatrix:
        def get(self, ns, key): return "{}"
    matrix = MockMatrix()

from a08_market_agents import LLM_PERSONAS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("A08_INTERVIEW")

CMD_FILE = BASE_DIR / "tmp" / "a08_interview_cmd.json"
RES_FILE = BASE_DIR / "tmp" / "a08_interview_res.json"

def run_interview():
    log.info("Listening for interview command...")
    
    if not CMD_FILE.exists():
        log.debug("No command file found.")
        return

    try:
        with open(CMD_FILE, "r", encoding="utf-8") as f:
            cmd = json.load(f)
    except Exception as e:
        log.error(f"Failed to read command file: {e}")
        return

    # 1. Verify Permissions and OTP
    requester = cmd.get("requester", "")
    otp = cmd.get("otp", "")
    
    # Only allow IDE_AGENT and LAO_CONG
    if requester not in ("IDE_AGENT", "LAO_CONG"):
        _write_error("UNAUTHORIZED_ROLE", f"Role '{requester}' is not allowed to access agent inner state.")
        return

    # Verify OTP
    env_otp = os.getenv("ZCL_OTP", "").strip()
    if not env_otp:
        # Fallback: read from config/.env if not present in process env
        from dotenv import load_dotenv
        load_dotenv(str(BASE_DIR / "config" / ".env"))
        env_otp = os.getenv("ZCL_OTP", "").strip()

    if not otp or otp != env_otp:
        _write_error("INVALID_OTP", "Authentication failed. Secure OTP code mismatch.")
        return

    # 2. Find Persona to interview
    persona_id = cmd.get("persona_id", "")
    persona = next((p for p in LLM_PERSONAS if p["id"] == persona_id), None)
    
    if not persona:
        _write_error("PERSONA_NOT_FOUND", f"Persona '{persona_id}' does not exist in LLM_PERSONAS.")
        return

    # 3. Read current market state from Redis as context
    try:
        a08_pred = matrix.get("A08", "swarm_prediction")
        market_state = json.loads(a08_pred) if a08_pred else {}
    except Exception:
        market_state = {}

    question = cmd.get("question", "What is your current view on the market?")
    
    # 4. Build custom interview prompt
    interview_prompt = (
        f"[SYSTEM] {persona['system_prompt']}\n\n"
        f"You are being interviewed by the system administrator.\n"
        f"Current Market Simulated State:\n"
        f"  Net Pressure: {market_state.get('net_pressure', 0.0):+.4f}\n"
        f"  Crowd Sentiment: {market_state.get('crowd_sentiment', 'NEUTRAL')}\n"
        f"  Divergence: {market_state.get('divergence_flag', 'MIXED')}\n\n"
        f"[INTERVIEW QUESTION]\n"
        f"\"{question}\"\n\n"
        f"Answer honestly, reflecting your persona's biases and psychological trauma state. Max 150 words."
    )

    log.info(f"Calling LLM for agent interview ({persona_id})...")
    try:
        response = _call_algo(
            prompt=interview_prompt,
            agent_id=f"A08_INTERVIEW_{persona_id}",
            label="SWARM_INTERVIEW",
            temp=0.7,
            tier="SWARM"
        )
    except Exception as e:
        response = f"LLM_CALL_FAILED: {e}"

    # 5. Write results
    result = {
        "status": "SUCCESS",
        "persona_id": persona_id,
        "question": question,
        "answer": response
    }
    
    try:
        with open(RES_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        log.info(f"Successfully interviewed {persona_id}. Response written.")
        # Clean up command file
        CMD_FILE.unlink(missing_ok=True)
    except Exception as e:
        log.error(f"Failed to write response file: {e}")

def _write_error(code: str, message: str):
    log.warning(f"Error [{code}]: {message}")
    result = {
        "status": "ERROR",
        "error_code": code,
        "message": message
    }
    try:
        with open(RES_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        CMD_FILE.unlink(missing_ok=True)
    except Exception as e:
        log.error(f"Failed to write error response: {e}")

if __name__ == "__main__":
    run_interview()
