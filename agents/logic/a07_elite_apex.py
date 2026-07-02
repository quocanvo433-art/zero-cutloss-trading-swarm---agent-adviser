"""
🧬 DNA: v16.7 - Sovereign Purity
🏢 UNIT: AGENTIC
🛠️ ROLE: Agent07Apex
📖 DESC: Elite financial analyst (Apex Strategist) logic engine.
"""
import sys

import os
import json
import time
import logging
import re
from pathlib import Path
from datetime import datetime, timezone

# Add parent paths so tools are accessible
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "tools"))
sys.path.insert(0, str(BASE_DIR / "agents/logic"))

from imperial_state import matrix, setup_agent_logger
from a09_immunity import sanitize_text_for_llm as a09_sanitize_text
from llm_router import router_api_call
from agent_session_logger import log_session, log_agent_snapshot, get_drift_context

log = setup_agent_logger("A07", "APEX_STRATEGIST")

class Agent07Apex:
    def __init__(self):
        log.info("[A07] Initializing Agent07Apex (The Apex Strategist)...")
        # Ensure soul file path is defined
        self.soul_file = BASE_DIR / "agents" / "07_queen_soul.md"
        self.soul_content = ""
        self._load_soul()

    def _load_soul(self):
        if self.soul_file.exists():
            try:
                self.soul_content = self.soul_file.read_text(encoding="utf-8")
                log.info(f"[A07] Loaded soul file from {self.soul_file}")
            except Exception as e:
                log.error(f"[A07] Failed to load soul file: {e}")
        else:
            log.warning(f"[A07] Soul file not found at {self.soul_file}")

    def run_pipeline(self):
        log.info("[A07] Starting Apex Strategist pipeline...")
        # Step 1: Pre-filtering
        latest_macro_narrative = ""
        macro_sensors = {}
        drift_context = ""
        
        try:
            latest_macro_narrative = matrix.get("A10", "latest_macro_narrative") or ""
        except Exception as e:
            log.error(f"[A07] Error fetching latest macro narrative: {e}")
            
        try:
            macro_sensors = matrix.get("MACRO", "sensors") or {}
        except Exception as e:
            log.error(f"[A07] Error fetching macro sensors: {e}")
            
        try:
            drift_context = get_drift_context("A07", "FULL") or ""
        except Exception as e:
            log.error(f"[A07] Error fetching drift context: {e}")
            
        # Format sensors as string
        if isinstance(macro_sensors, (dict, list)):
            macro_sensors_str = json.dumps(macro_sensors, ensure_ascii=False, indent=2)
        else:
            macro_sensors_str = str(macro_sensors)
            
        # Bio-vaccination (sanitization)
        # We pass a larger max_len to preserve detailed context
        clean_narrative = a09_sanitize_text(latest_macro_narrative, max_len=15000)
        clean_sensors = a09_sanitize_text(macro_sensors_str, max_len=15000)
        clean_drift = a09_sanitize_text(drift_context, max_len=20000)
        
        # Step 2: 3-Phase LLM Call Process
        # Phase 1: Calculations
        phase1_prompt = f"""{self.soul_content}

[PHASE 1: DATA PROCESSING & CALCULATIONS]
You are in Phase 1: Calculations.
Based on the following sanitized inputs, evaluate and calculate the 5 components of the ACDI formula:
1. W_shadow_liq (Shadow Liquidity Decay)
2. W_equity_bubble (Equity Bubble / Distribution)
3. W_labor_decay (Gig Labor Decay)
4. W_skilled_layoffs (Skilled/Tech Layoffs)
5. W_debt_default (SME & Personal Debt Defaults)

Calculate the final ACDI score using the formula:
ACDI = 0.25 * W_shadow_liq + 0.20 * W_equity_bubble + 0.20 * W_labor_decay + 0.15 * W_skilled_layoffs + 0.20 * W_debt_default

--- INPUT DATA ---
- Latest Macro Narrative from A10:
{clean_narrative}

- Macro Sensors:
{clean_sensors}

- Drift Context (History):
{clean_drift}

--- INSTRUCTIONS ---
Perform the calculation. Output a detailed breakdown of your calculated values for the 5 components and the final ACDI score. Also estimate the values for the other required metrics in the HingeEBM schema:
- dark_pool_absorption_ratio
- net_gex_status (e.g., POSITIVE_DEALER_WALL, NEGATIVE_GEX_EXPOSURE)
- shadow_qe_flow_usd
- stablecoin_tbills_backing
- buyback_force_index
- gig_decay_point
- high_skilled_layoffs_io
- sme_zombie_debt_billion
- personal_default_rate
- elite_cash_allocation_ratio

Provide your reasoning step-by-step.
"""
        log.info("[A07] Executing Phase 1 (Calculations)...")
        phase1_response = router_api_call(
            prompt=phase1_prompt,
            agent_id="A07_P1",
            brain_mode="A07_PHASE1",
            est_tokens=1000
        )
        log_agent_snapshot("A07_PHASE1", phase1_prompt, phase1_response, metadata={"step": "phase1"})

        # Phase 2: Narrative Analysis
        phase2_prompt = f"""{self.soul_content}

[PHASE 2: NARRATIVE BUILDING & CONTEXT MATCHING]
You are in Phase 2: Narrative Analysis.
Based on the Phase 1 calculations and analysis, construct the narrative lens for the Empire.

--- PHASE 1 CALCULATIONS & ANALYSIS ---
{phase1_response}

--- INSTRUCTIONS ---
Determine the current ACDI Phase:
- Phase 1: ACDI < 45.0
- Phase 2: ACDI 45.0 - 65.0
- Phase 3: ACDI 65.0 - 84.9
- Phase 4: ACDI >= 85.0

Analyze and write detailed analytical narratives for:
1. R > G Divergence Threat (nominal vs real growth divergence)
2. White-Collar Downward Mobility (high-skilled layoffs & AI replacement pressures)
3. Apex Exit Trap (elite asset allocation to cash/T-bills, stablecoin backing)
4. Strategic Advice for Commander A05.

Be cold, analytical, and highly structured.
"""
        log.info("[A07] Executing Phase 2 (Narratives)...")
        phase2_response = router_api_call(
            prompt=phase2_prompt,
            agent_id="A07_P2",
            brain_mode="A07_PHASE2",
            est_tokens=1200
        )
        log_agent_snapshot("A07_PHASE2", phase2_prompt, phase2_response, metadata={"step": "phase2"})

        # Phase 3: Consolidation
        phase3_prompt = f"""{self.soul_content}

[PHASE 3: HINGEEBM COMPLIANCE CONSOLIDATION]
You are in Phase 3: Consolidation.
Consolidate all previous calculations, findings, and narratives into a single, valid JSON block that strictly follows the HingeEBM compliance schema.

--- PHASE 1 CALCULATIONS ---
{phase1_response}

--- PHASE 2 NARRATIVES ---
{phase2_response}

--- SCHEMA SPECIFICATION ---
Must return a single JSON block, inside or outside ```json...``` tags (if using ```json, make sure to close the JSON block properly).
No additional greeting, explanation, or discussion text outside the JSON block.
Format JSON must be:
{{
  "algo_core": {{
    "apex_crisis_detonator_index": <calculated ACDI float 0-100>,
    "dark_pool_absorption_ratio": <float>,
    "net_gex_status": "POSITIVE_DEALER_WALL"|"NEGATIVE_GEX_EXPOSURE"|...,
    "shadow_qe_flow_usd": <float>,
    "stablecoin_tbills_backing": <float>,
    "buyback_force_index": <float>,
    "gig_decay_point": <float>,
    "high_skilled_layoffs_io": <float>,
    "sme_zombie_debt_billion": <float>,
    "personal_default_rate": <float>,
    "elite_cash_allocation_ratio": <float>
  }},
  "narrative_lens": {{
    "summary": "<ACDI at X | Component highlights>",
    "r_g_divergence_threat": "<nominal vs real growth divergence threat analysis>",
    "white_collar_downward_mobility": "<layoff and AI substitution narrative>",
    "apex_exit_trap": "<elite asset relocation and stablecoin backing narrative>",
    "strategic_advice": "<advisory for commander A05>"
  }}
}}
"""
        log.info("[A07] Executing Phase 3 (Consolidation)...")
        phase3_response = router_api_call(
            prompt=phase3_prompt,
            agent_id="A07_FINAL",
            brain_mode="A07_PHASE3",
            est_tokens=1500
        )
        log_agent_snapshot("A07", phase3_prompt, phase3_response, metadata={"step": "phase3"})

        # Step 3: Extraction and Publishing
        final_dict = self._extract_json_block(phase3_response)
        if not final_dict:
            log.error("[A07] Failed to parse HingeEBM JSON from Phase 3 response!")
            return

        # Publish to Redis
        try:
            # Save latest decision
            matrix.set("A07", "latest_decision", json.dumps(final_dict, ensure_ascii=False))
            log.info("[A07] Saved latest_decision to Redis.")
            
            # Send to A05 stream
            matrix.xadd("A05", "t0_stream", {"source": "A07", "payload": json.dumps(final_dict, ensure_ascii=False)}, maxlen=5)
            log.info("[A07] Pushed decision payload to Agent A05 stream.")
            
            # Publish event
            matrix.publish("A07:decision", final_dict)
            log.info("[A07] Published decision to Redis event channel.")
        except Exception as e:
            log.error(f"[A07] Redis write/publish error: {e}")

        # Telegram notification queue
        try:
            algo_core = final_dict.get("algo_core", {})
            narrative_lens = final_dict.get("narrative_lens", {})
            
            acdi = algo_core.get("apex_crisis_detonator_index", 0.0)
            summary = narrative_lens.get("summary", "Apex Strategist summary")
            advice = narrative_lens.get("strategic_advice", "No strategic advice provided.")
            
            # Extract additional metrics for detailed report
            dark_pool = algo_core.get("dark_pool_absorption_ratio", 0.0)
            net_gex = algo_core.get("net_gex_status", "UNKNOWN")
            shadow_qe = algo_core.get("shadow_qe_flow_usd", 0.0)
            stablecoin = algo_core.get("stablecoin_tbills_backing", 0.0)
            buyback = algo_core.get("buyback_force_index", 0.0)
            gig_decay = algo_core.get("gig_decay_point", 0.0)
            skilled_layoffs = algo_core.get("high_skilled_layoffs_io", 0.0)
            sme_debt = algo_core.get("sme_zombie_debt_billion", 0.0)
            personal_default = algo_core.get("personal_default_rate", 0.0)
            elite_cash = algo_core.get("elite_cash_allocation_ratio", 0.0)
            
            r_g = narrative_lens.get("r_g_divergence_threat", "N/A")
            white_collar = narrative_lens.get("white_collar_downward_mobility", "N/A")
            exit_trap = narrative_lens.get("apex_exit_trap", "N/A")

            # Select correct Phase name based on score
            if acdi < 45.0:
                phase_name = "Phase 1: Accumulation & Shakeout"
            elif acdi < 65.0:
                phase_name = "Phase 2: Yield Steepening"
            elif acdi < 85.0:
                phase_name = "Phase 3: Blow-off Top"
            else:
                phase_name = "Phase 4: Minsky Moment (DETONATION)"

            report_text = (
                f"📈 *Crisis Detonator Index (ACDI)*: `{acdi:.2f}` / 100.0\n"
                f"📊 *Macro Status*: *{phase_name}*\n\n"
                f"🧮 *Quantitative Parameters (algo_core)*:\n"
                f"• Dark Pool Abs Ratio: `{dark_pool}`\n"
                f"• Net GEX Status: `{net_gex}`\n"
                f"• Shadow QE Flow: `{shadow_qe}B USD`\n"
                f"• Stablecoin T-bills Backing: `{stablecoin}`\n"
                f"• Buyback Force Index: `{buyback}`\n"
                f"• Gig Labor Decay Point: `{gig_decay}`\n"
                f"• High-Skilled Layoffs (I/O): `{skilled_layoffs}`\n"
                f"• SME Zombie Debt: `{sme_debt}B USD`\n"
                f"• Personal Default Rate: `{personal_default}`\n"
                f"• Elite Cash Allocation: `{elite_cash}`\n\n"
                f"📝 *Summary*: {summary}\n\n"
                f"⚠️ *R > G Divergence*: {r_g}\n\n"
                f"💼 *White-Collar Layoffs*: {white_collar}\n\n"
                f"🏦 *Apex Exit Trap*: {exit_trap}\n\n"
                f"💡 *Commander Advice (A05)*:\n|_{advice}_|"
            )
            
            tele_payload = json.dumps({
                "type": "A07_TO_A06_REPORT",
                "cycle": int(time.time()),
                "report_text": report_text
            }, ensure_ascii=False)
            
            matrix.xadd("SYSTEM", "telegram:queue", {"payload": tele_payload}, maxlen=1000)
            log.info("[A07] Enqueued Telegram report.")
        except Exception as e:
            log.error(f"[A07] Error enqueuing Telegram report: {e}")

        # Log session snapshots
        try:
            log_session(
                agent_id="A07",
                redis_key="zcl:a07:latest_decision",
                summary=f"ACDI: {acdi:.1f} | {summary}",
                signals_count=5,
                confidence=1.0,
                expert_metrics=algo_core,
                extra=narrative_lens
            )
            log.info("[A07] Logged session data.")
        except Exception as e:
            log.error(f"[A07] Session logging error: {e}")

    def _extract_json_block(self, text: str) -> dict:
        if not text:
            return {}
        text_clean = text.strip()
        
        # Remove thinking tags
        if "<thinking>" in text_clean:
            text_clean = re.sub(r"<thinking>.*?</thinking>", "", text_clean, flags=re.DOTALL).strip()
            
        # Try finding json block
        json_match = re.search(r"({.*})", text_clean, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass
                
        # Try direct parsing
        try:
            return json.loads(text_clean)
        except Exception:
            pass
            
        return {}

def main_loop():
    agent = Agent07Apex()
    last_run = 0
    interval = 1800 # 30 minutes
    
    log.info("[A07] Starting Daemon Loop...")
    while True:
        try:
            now = time.time()
            if now - last_run >= interval:
                agent.run_pipeline()
                last_run = now
                
            # Publish heartbeat every 60 seconds
            next_run_in = int(max(0, interval - (time.time() - last_run)))
            payload = {
                "agent_id": "A07",
                "status": "ACTIVE",
                "timestamp": int(time.time()),
                "next_run_in": next_run_in
            }
            
            matrix.publish_heartbeat("A07", status="ACTIVE", metadata={"next_run_in": next_run_in})
            matrix.set("A07", "heartbeat", payload, ttl=600)
            
            time.sleep(60)
        except KeyboardInterrupt:
            log.info("[A07] Daemon Loop stopped by keyboard interrupt.")
            break
        except Exception as e:
            log.error(f"[A07] Exception in main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main_loop()
