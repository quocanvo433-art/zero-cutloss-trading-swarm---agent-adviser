"""
🧬 DNA: v16.6 (Sovereign Purity & Logic Audit)
🏢 UNIT: DEEP_DIAGNOSTICIAN (A05)
🛠️ ROLE: LOGIC_POSTMORTEM_WATCH
📖 DESC: Deep Post-mortem diagnostic system, dissecting model reasoning errors and recommending logic calibration plans for the entire Empire.
🔗 CALLS: tools/llm_router.py, tools/imperial_state.py
📟 I/O: Redis: zcl:A05:*, dpo_lab/postmortem/
🛡️ INTEGRITY: Post-Mortem-Precision, Logic-Drift-Detection, Holistic-Audit.
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))

import os
import sys
import json
import time
import glob
import logging
import argparse
from datetime import datetime, timezone
from typing import Optional

from llm_router import router_api_call
from imperial_state import matrix
from imperial_brain import brain
DIAG_MAX_TOKENS   = 4096   # Output token cap for diagnostics

# ── Constants & I/O ───────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DPO_LAB         = os.path.join(BASE_DIR, "dpo_lab")
ENGRAMS_DIR     = os.path.join(DPO_LAB, "engrams", "A05")
A05_DIR         = os.path.join(DPO_LAB, "A05")
REJECTED_DIR    = os.path.join(A05_DIR, "rejected")
JUDGE_DIR       = os.path.join(A05_DIR, "judge")
EVALUATIONS_DIR = os.path.join(A05_DIR, "reports") # For deep analysis reports

for d in [REJECTED_DIR, JUDGE_DIR, ENGRAMS_DIR, EVALUATIONS_DIR]:
    os.makedirs(d, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
from imperial_state import setup_agent_logger
log = setup_agent_logger("A05", "05_DEEP_DIAGNOSIS")

# redis_client deprecated — use matrix


# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — PACKAGING WORKSPACE SNAPSHOT
# ══════════════════════════════════════════════════════════════════════════════

# Legacy JSONL reader removed.


def _doc_n_evaluations_moi_nhat(n: int = 5) -> list[dict]:
    """Read the N most recent evaluation files"""
    files = sorted(glob.glob(os.path.join(EVALUATIONS_DIR, "*.json")), reverse=True)[:n]
    evals = []
    for fp in files:
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                evals.append(json.load(f))
        except Exception:
            continue
    return evals


# Legacy Master Rules reader removed (handled by prompt directly or bypassed).


def _lay_dpo_report_moi_nhat() -> Optional[dict]:
    """Get the latest 24h DPO report from Redis"""
    raw = matrix.get("JUDGE", "report")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return None


def dong_goi_workspace() -> dict:
    """
    Minimal context packaging from Engrams (ImperialBrain).
    """
    log.info("Packaging workspace snapshot from Engrams...")
    evals = _doc_n_evaluations_moi_nhat(5)
    report = _lay_dpo_report_moi_nhat()

    dpo_data = {
        "tong_chosen": len(glob.glob(os.path.join(JUDGE_DIR, "*.json"))),
        "tong_rejected": len(glob.glob(os.path.join(REJECTED_DIR, "*.json"))),
        "chosen_20_gan_nhat": [],
        "rejected_20_gan_nhat": []
    }

    workspace = {
        "meta": {
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "purpose":        "Deep diagnosis — finding improvement points for Auditor pipeline",
            "workspace_path": "dpo_lab/engrams/A05",
        },
        "dpo_report_24h": report,
        "evaluations_gan_nhat": evals,
        "dpo_data": dpo_data,
    }

    log.info(f"Workspace size: {len(json.dumps(workspace))} bytes")
    return workspace


# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — PROMPT BUILDING (Qwen Anchor: Zero-Cutloss + Wyckoff + Elliott)
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are the Judgment Eye — A05 of Zero-Cutloss Empire.  /no_think
Immutable Thinking Anchors:
  1. ZERO-CUTLOSS: Orders are CHOSEN only if Drawdown < 2% AND Target 1 is reached. No compromise.
  2. WYCKOFF PHASE C ONLY: Action only at Spring/UTAD/ST — absolutely forbidden in Phase A/B.
  3. ELLIOTT WAVE CONTEXT: Every analysis must be mapped to where the Elliott wave currently is.
  4. QWEN MINDSET: You reason based on verified historical patterns — do not listen to Narratives.

You receive the system workspace snapshot and MUST:
- Determine EXACTLY which error pattern is repeating (Wrong phase? Fake volume? Elliott miscount?)
- Analyze root causes — do not describe symptoms
- Recommendations must be SPECIFIC, ACTIONABLE (not abstract)
- Prioritize by actual impact for fixing first

OUTPUT MUST BE PURE JSON:
{
  "tom_tat_tinh_huong": "1-2 sentences summarizing the general situation",
  "diem_manh": ["..."],
  "van_de_chinh": [
    {
      "thu_tu_uu_tien": 1,
      "ten_van_de": "...",
      "nguyen_nhan_goc_re": "...",
      "bang_chung_wyckoff_elliott": "...",
      "huong_giai_quyet_cu_the": "...",
      "uoc_tinh_impact": "..."
    }
  ],
  "cai_thien_nhanh": ["..."],
  "canh_bao_nguy_hiem": "...",
  "chuoi_han_dong_uu_tien": ["Step 1: ...", "Step 2: ...", "Step 3: ..."]
}"""


def xay_dung_prompt(workspace: dict, van_de_cu_the: Optional[str] = None) -> str:
    """
    Build the complete prompt for Qwen. Anchor: Zero-Cutloss + Wyckoff + Elliott.

    Args:
        workspace:      Packaged workspace
        van_de_cu_the:  If special focus on a specific issue is requested
    """
    # Quick summary to avoid consuming too many input tokens
    report = workspace.get("dpo_report_24h") or {}
    alerts = report.get("alerts", [])
    cao_alerts = [a for a in alerts if a["muc_do"] == "CAO"]

    focus_section = ""
    if van_de_cu_the:
        focus_section = f"\n\nSpecial focus requested on: {van_de_cu_the}\n"
    elif cao_alerts:
        focus_section = f"\n\nHigh priority alerts to analyze:\n" + "\n".join(
            f"- {a['nhan']}: {a['mo_ta']}" for a in cao_alerts
        )

    prompt = f"""This is the workspace snapshot of Zero-Cutloss Trading AI Empire.
Please perform a deep analysis and find improvement points.
{focus_section}

=== ZERO-CUTLOSS CONSTITUTION (MASTER_RULES) ===
{workspace.get('master_rules', '')[:2000]}

=== DPO REPORT 24H ===
{json.dumps(report, ensure_ascii=False, indent=2)[:4000]}

=== DPO DATA (20 most recent pairs) ===
CHOSEN (win):
{json.dumps(workspace['dpo_data']['chosen_20_gan_nhat'][:10], ensure_ascii=False, indent=2)[:2000]}

REJECTED (loss/sideways):
{json.dumps(workspace['dpo_data']['rejected_20_gan_nhat'][:10], ensure_ascii=False, indent=2)[:2000]}

=== MOST RECENT EVALUATIONS ===
{json.dumps(workspace.get('evaluations_gan_nhat', [])[:3], ensure_ascii=False, indent=2)[:2000]}

=== CURRENT CHECKPOINT ===
{json.dumps(workspace.get('checkpoint_hien_tai'), ensure_ascii=False, indent=2)[:500]}

=== A04 BLIND LEARNING HEALTH (learning from history — separate from real trade) ===
{json.dumps(workspace.get('blind_learning_health', {}), ensure_ascii=False, indent=2)[:1500]}

{"=== CUSTOM SNAPSHOTS ===" + chr(10) + json.dumps(workspace.get('custom_snapshots'), ensure_ascii=False, indent=2)[:2000] if workspace.get('custom_snapshots') else ""}

Please analyze comprehensively and return JSON recommendations according to the given schema.
Pay special attention: compare "weak_songs" of A04 with "diem_yeu_can_cai_thien" of Wyckoff —
if they are in the same phase, that is a system weakness that must be prioritized.
Priority: immediately actionable insights > insights that take a long time to implement."""

    return prompt


# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — QWEN DIAGNOSIS ROUTER (Groq 32B → Cerebras 235B)
# ══════════════════════════════════════════════════════════════════════════════

def _parse_qwen_response(text: str) -> dict:
    """Extract JSON from response, handle markdown blocks and garbage text."""
    if text is None:
        return {"parse_error": True}
    text = text.strip()
    import re
    
    # 1. Prioritize markdown block as it is the safest
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if blocks:
        for block in blocks:
            try:
                return json.loads(block)
            except Exception:
                pass
                
    # 2. Scan for the outermost JSON block
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end+1]
        try:
            return json.loads(json_str)
        except Exception:
            pass
            
    return {"tom_tat": text[:300], "parse_error": True}

def goi_qwen_chan_doan(prompt: str) -> dict:
    """
    QwenDiagnosisRouter — Call llm_router with A05_PURITY mode.
    Route: Groq 32B -> Cerebras 235B.
    """
    t0 = time.time()
    text = brain.think_as("A05", prompt, brain_mode="A05_PURITY", est_tokens=DIAG_MAX_TOKENS)
    t_diff = time.time() - t0
    elapsed = float(int(t_diff * 10) / 10.0)
    
    # Parse result
    parsed = _parse_qwen_response(text)
    
    return {
        "ket_qua":        parsed,
        "thoi_gian_giay": elapsed,
        "token_usage":    {"total_tokens": len(text) // 4}, # Estimated tokens
        "model":          "qwen_hybrid_purity",
        "tier":           "ROUTER_V3_QWEN",
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART 4 — MAIN FUNCTION (Qwen-Based)
# ══════════════════════════════════════════════════════════════════════════════

def chay_deep_diagnosis(
    workspace_path: Optional[str] = None,
    van_de_cu_the: Optional[str] = None,
    auto_trigger: bool = False,
) -> str:
    """
    Main function — runs deep diagnosis using Qwen (QWEN PURITY DOCTRINE).
    Order: Groq Qwen3-32B → Cerebras Qwen3-235B

    Args:
        workspace_path: Custom snapshot folder path (None = realtime)
        van_de_cu_the:  Focus on a specific issue
        auto_trigger:   True = A05 auto-triggers when there is a HIGH alert
    Returns:
        JSON string of analysis results from Qwen
    """
    timestamp_unix = int(time.time())
    log.info(f"=== DEEP DIAGNOSIS START (QWEN) === auto={auto_trigger} | path={workspace_path}")

    # Publish heartbeat
    matrix.set("A05", "diag:heartbeat", {"ts": timestamp_unix, "status": "RUNNING", "auto": auto_trigger}, ttl=3600)

    # Pack workspace
    workspace = dong_goi_workspace()

    # Check if there is enough data
    tong_pairs = workspace["dpo_data"]["tong_chosen"] + workspace["dpo_data"]["tong_rejected"]
    if tong_pairs < 20:
        result = {
            "agent_id":       "05_NHAN_THAN_DEEP_DIAGNOSIS",
            "timestamp_unix": timestamp_unix,
            "canh_bao":       "INSUFFICIENT_DATA",
            "chi_tiet":       f"Requires at least 20 DPO pairs, currently have {tong_pairs}. Continuing to accumulate.",
        }
        return json.dumps(result, ensure_ascii=False)

    # Build prompt
    prompt = xay_dung_prompt(workspace, van_de_cu_the)
    log.info(f"Prompt length: {len(prompt)} chars")

    # Call Qwen Router (Groq 32B → Cerebras 235B)
    qwen_result = goi_qwen_chan_doan(prompt)

    # Package result
    output = {
        "agent_id":             "05_NHAN_THAN_DEEP_DIAGNOSIS",
        "loai_bao_cao":         "DEEP_DIAGNOSIS",
        "timestamp_unix":       timestamp_unix,
        "timestamp_readable":   datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        "auto_trigger":         auto_trigger,
        "workspace_path":       workspace_path or "realtime",
        "van_de_focus":         van_de_cu_the,
        "tong_pairs_phan_tich": tong_pairs,

        "phan_tich_qwen":       qwen_result.get("ket_qua", {}),
        "thoi_gian_phan_tich":  qwen_result.get("thoi_gian_giay"),
        "token_usage":          qwen_result.get("token_usage"),
        "model_su_dung":        qwen_result.get("model", "qwen_unknown"),
        "model_tier":           qwen_result.get("tier", "UNKNOWN"),
        "ghi_chu_model":        qwen_result.get("ghi_chu", ""),

        "loi_neu_co":           qwen_result.get("loi"),
    }

    # Save results
    os.makedirs(EVALUATIONS_DIR, exist_ok=True)
    output_file = os.path.join(
        EVALUATIONS_DIR,
        f"deep_diagnosis_{timestamp_unix}.json"
    )
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info(f"Deep diagnosis saved to: {output_file} | model={output['model_tier']}")

    # Push to Matrix → A07 pumps into Gemini Web immediately
    matrix.set("JUDGE", "deep_diagnosis", output, ttl=86400)

    # Notify A07 to pump immediately
    matrix.publish("alerts:urgent", {
        "loai":     "DEEP_DIAGNOSIS_READY",
        "trigger":  "BUOC_VAO_GEMINI_WEB_NGAY",
        "file":     output_file,
        "model":    output["model_tier"],
    })

    # Update heartbeat
    matrix.set("A05", "diag:heartbeat", {"ts": int(time.time()), "status": "DONE",
                    "model": output["model_tier"], "auto": auto_trigger}, ttl=3600)

    log.info(f"=== DEEP DIAGNOSIS DONE === model={output['model_tier']} "
             f"time={qwen_result.get('thoi_gian_phan_tich')}s")
    return json.dumps(output, ensure_ascii=False)


# ── Tool Definition for OpenClaw ──────────────────────────────────────────────
TOOL_DEFINITION = {
    "name": "chay_deep_diagnosis",
    "description": (
        "On-demand: Package workspace DPO snapshot and call Qwen (Groq 32B → Cerebras 235B) "
        "to deeply analyze pipeline weaknesses. "
        "QWEN PURITY: No Gemini — ensure pure Qwen reasoning for DPO. "
        "Automatically triggered when A05 report has a HIGH alert. "
        "Results pushed to Redis → A07 pumps into Gemini Web immediately."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workspace_path": {
                "type": "string",
                "description": "Custom snapshot folder path. Leave blank = use realtime data.",
                "default": "",
            },
            "van_de_cu_the": {
                "type": "string",
                "description": (
                    "Focus on a specific issue. Example:\n"
                    "  'UTAD accuracy only 41% — need to find the cause'\n"
                    "  'Win rate decreased by 15% in the last 7 days'\n"
                    "  'Model is overconfident in 90%+ bin'\n"
                    "Leave blank = comprehensive analysis."
                ),
                "default": "",
            },
            "auto_trigger": {
                "type": "boolean",
                "description": "True = allowed to be auto-triggered by A05 when there is a HIGH alert",
                "default": False,
            },
        },
        "required": [],
    },
}


# ── Run from command line ─────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DPO Deep Diagnosis — Qwen3 Router (32B Groq → 235B Cerebras)"
    )
    parser.add_argument("--workspace", type=str, default="",
                        help="Path to custom snapshot folder")
    parser.add_argument("--focus",     type=str, default="",
                        help="Specific issue to focus on")
    parser.add_argument("--tier",      type=str, default="auto",
                        choices=["auto", "groq32b", "cerebras235b"],
                        help="Force using a specific tier (default: auto routing)")
    args = parser.parse_args()

    print("=== DPO Deep Diagnosis — Qwen Purity Edition ===")
    print(f"Workspace: {args.workspace or 'realtime'}")
    print(f"Focus:     {args.focus or 'comprehensive'}")
    print(f"Tier:      {args.tier}")
    print("Running...\n")

    result_str = chay_deep_diagnosis(
        workspace_path=args.workspace or None,
        van_de_cu_the=args.focus or None,
        auto_trigger=False,
    )
    result = json.loads(result_str)

    if result.get("loi_neu_co"):
        print(f"ERROR: {result['loi_neu_co']}")
        sys.exit(1)

    phan_tich = result.get("phan_tich_qwen", {})
    tier      = result.get("model_tier", "UNKNOWN")
    print(f"=== SUMMARY [{tier}] ===")
    print(phan_tich.get("tom_tat_tinh_huong", ""))
    print("\n=== MAIN ISSUES ===")
    for vd in phan_tich.get("van_de_chinh", []):
        print(f"{vd.get('thu_tu_uu_tien', '?')}. {vd.get('ten_van_de', '')}")
        print(f"   Wyckoff/Elliott: {vd.get('bang_chung_wyckoff_elliott', vd.get('nguyen_nhan_goc_re', ''))}")
        print(f"   Solution:  {vd.get('huong_giai_quyet_cu_the', '')}")
        print()
    print("\n=== PRIORITY ACTION CHAIN ===")
    for step in phan_tich.get("chuoi_han_dong_uu_tien", []):
        print(f"  {step}")
    print(f"\nFile: dpo_lab/evaluations/deep_diagnosis_{result['timestamp_unix']}.json")
    print(f"Duration: {result.get('thoi_gian_phan_tich')}s | Model: {tier}")


# ══════════════════════════════════════════════════════════════════════════════
# PART 5 & 6 — Consolidated via llm_router.A05_PURITY
MAJOR_ASSETS = {"BTC", "ETH", "BNB", "BTCUSDT", "ETHUSDT", "BNBUSDT"}
MID_ASSETS   = {"SOL", "AVAX", "MATIC", "ARB", "SOL/USDT", "AVAX/USDT"}

# Paths for postmortem output moved to top

# --- IMPERIAL CONSTANTS & LIBS ---
CEREBRAS_MODEL = "qwen-3-235b-a22b-instruct-2507"

# ══════════════════════════════════════════════════════════════════════════════
# PART 6 — MAIN 235B POST-MORTEM (HUNTING + RIDING)
# ══════════════════════════════════════════════════════════════════════════════

POSTMORTEM_SYSTEM = """[IMPERIAL_SOUL_SEAL — SUPREME JUDGE]
You are Qwen3-235B, the Supreme Judge of Zero-Cutloss Trading Empire.
Task: Deeply analyze the ERRORS of A05 — find the true ROOT CAUSE, not surface reasons.

IMMUTABLE PHILOSOPHY:
- Elite money flow is hidden but leaves traces — A05 SAW the traces but MISREAD them
- Phase B looks very similar to Phase C — this is the most common trap
- Major assets (BTC/ETH/BNB): they distribute slowly, exiting late is extremely expensive
- Penny coins: they pump rapidly without warning, exiting early loses 300%+ upside

OUTPUT MUST BE PURE JSON. No markdown, no explanations outside JSON."""


def _build_hunting_prompt(snapshot: dict, ban_an: dict) -> str:
    ctx       = snapshot.get("Bo_Lao_Tu_Van", {})
    kn        = snapshot.get("judgment", {})
    if isinstance(kn, str):
        try: kn = json.loads(kn)
        except: kn = {}
    
    ket_qua   = ban_an.get("ket_qua", {})
    bai_hoc   = ban_an.get("bai_hoc", "")
    phan_loai = ban_an.get("phan_loai_dpo", "REJECTED")

    a04_PA = ctx.get('A04_PriceAction', {}).get('Thong_Tin_Du_Lieu', '?')
    a10_MF = ctx.get('A10_MacroFlow', {}).get('Thong_Tin_Du_Lieu', '?')
    
    div = snapshot.get("divergence_matrix", {})
    conflict = div.get("conflict_type", "?")
    score    = div.get("divergence_score", "?")

    return f"""[ERROR ANALYSIS — HUNTING MODE]
Snapshot ID: {ban_an.get('snapshot_id', '?')}
Result: {phan_loai} | Profit: {ket_qua.get('loi_nhuan_pct', 0)}% | Drawdown: {ket_qua.get('drawdown_max_pct', 0)}%

[T-0 CONTEXT AT ENTRY]
Wyckoff/Elliott: {a04_PA}
Macro Flow: {a10_MF}
Divergence: Score {score} | Conflict {conflict}
Nhan_Thong_Tin: {kn.get('Nhan_Thong_Tin', '?')}
Dien_Giai_Ly_Thuyet: {kn.get('Dien_Giai_Ly_Thuyet', '?')}
Execution Timing: {kn.get('Execution_Timing', '?')}

[CURRENT LESSON OF A05 (needs improvement)]
{bai_hoc}

[REQUIREMENTS — 4 DEEP ANALYSIS STEPS]
Step 1: Re-read the context — what signals were PRESENT at T-0 but A05 misunderstood?
Step 2: Find reasoning errors — Phase B mistaken for Phase C? Or was Conflict ignored?
Step 3: Analyze Elite traps — Evidence of Trap present in data but unrecognized by A05?
Step 4: Write lesson for Qwen3.5-9B — concise, practical, ≤4 sentences

JSON OUTPUT:
{{
  "buoc_1_tin_hieu_bi_hieu_sai": "...",
  "buoc_2_loi_suy_luan_chinh": "...",
  "buoc_3_bay_elite_bi_bo_qua": "...",
  "lesson_for_9b": "...",
  "phan_loai_loi": "PHASE_CONFUSION|CONSENSUS_IGNORED|DIVERGENCE_MISSED|OTHER",
  "quality_score": 0-100,
  "do_tin_cay_phan_tich": 0-100
}}"""


def _build_riding_prompt(snapshot: dict, ban_an: dict, alert_type: str, ma_coin: str) -> str:
    ctx       = snapshot.get("Bo_Lao_Tu_Van", {})
    kn        = snapshot.get("judgment", {})
    if isinstance(kn, str):
        try: kn = json.loads(kn)
        except: kn = {}
    ket_qua = ban_an.get("ket_qua", {})

    ticker = ma_coin.replace("/USDT", "").upper()
    if ticker in {t.replace("/USDT", "").upper() for t in MAJOR_ASSETS}:
        asset_tier = "MAJOR"
        tier_rule  = "BTC/ETH/BNB: exit when volume divergence + Elliott W5 confirm. Late exit = WRONG."
    elif ticker in {t.replace("/USDT", "").upper() for t in MID_ASSETS}:
        asset_tier = "MID"
        tier_rule  = "Mid-cap: exit when 2+ distribution signals. Balance between not early and not late."
    else:
        asset_tier = "PENNY"
        tier_rule  = "Penny coin: DO NOT exit before left shoulder. Hold through spike and shoulder confirmation."
        
    a04_PA = ctx.get('A04_PriceAction', {}).get('Thong_Tin_Du_Lieu', '?')

    return f"""[ERROR ANALYSIS — RIDING MODE]
Coin: {ma_coin} | Tier: {asset_tier}
Alert type: {alert_type}
Actual result: Profit {ket_qua.get('loi_nhuan_pct', 0)}% | Drawdown {ket_qua.get('drawdown_max_pct', 0)}%

[TIER RULE FOR {asset_tier}]
{tier_rule}

[POSITION CONTEXT]
Wyckoff/Elliott: {a04_PA}
Exit execution timing: {kn.get('Execution_Timing', '?')}

[ERROR TYPE TO ANALYZE]
{alert_type}:
- LEVERAGE_WICKED: leverage caused liq zone to be swept by wick — Wick-Safe zone calculated incorrectly
- EXIT_TOO_EARLY_PENNY: closed penny before left shoulder formed — missed large upside
- EXIT_TOO_LATE_MAJOR: closed BTC/ETH after right shoulder — distribution completed, price peaked
- OVER_LEVERAGE_IMPULSE: added positions in impulse wave swept — leverage management incorrect

[REQUIREMENTS — 4 STEPS]
Step 1: Shoulder (Left/Right) analysis (Wyckoff + Volume)
Step 2: What is the CORRECT exit point/leverage? Based on what data?
Step 3: What signals did A05 ignore leading to this error?
Step 4: Specific rule for {asset_tier} tier — prevention for next time

JSON OUTPUT:
{{
  "asset_tier": "{asset_tier}",
  "exit_error_type": "{alert_type}",
  "buoc_1_shoulder_analysis": "...",
  "buoc_2_diem_thoat_dung": "...",
  "buoc_3_tin_hieu_bo_qua": "...",
  "lesson_for_9b": "...",
  "tier_rule_updated": "...",
  "quality_score": 0-100
}}"""


def _save_postmortem(snapshot_id: str, mode: str, report: dict, ban_an: dict):
    """Save new postmortem report by appending to file in imperial_brain.py"""
    full_record = {
        "mode":           mode,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "report":         report,
        "phan_loai_dpo":  "REJECTED",
        "model_used":     CEREBRAS_MODEL,
    }
    # Pass "rejected" string to the host library to write file
    from imperial_brain import matrix, log
    import imperial_brain as ib
    brain = ib.ImperialBrain()
    # Call in correct order: snapshot_id, folder_type, content
    brain.memory.store_a05_lesson(snapshot_id, "rejected", full_record)

    # Push to Matrix Stream (xadd) instead of set
    matrix.xadd("A05", "postmortem:stream", full_record, maxlen=50)
    log.info(f"[A05 postmortem] Saved to rejected DPO | Snapshot: {snapshot_id}")








def _kich_hoat_postmortem_chuyen_sau(record: dict, snap_id: str, action: str, entry_val: float, sl_val: float):
    log.info(f"[_kich_hoat_postmortem_chuyen_sau] Start Deep Diagnostic for {snap_id}")
    snapshot = record.get("data", record.get("content", {}))
    
    loi_nhuan_pct = round((sl_val - entry_val)/entry_val*100, 2) if action in ["LONG", "MUA", "MỞ_LỆNH"] else round((entry_val - sl_val)/entry_val*100, 2)
    ban_an = {
        "snapshot_id": snap_id,
        "phan_loai_dpo": "REJECTED",
        "bai_hoc": "",
        "ket_qua": {
            "loi_nhuan_pct": loi_nhuan_pct,
            "drawdown_max_pct": loi_nhuan_pct
        }
    }
    
    if action in ["LONG", "SHORT", "MUA", "BÁN", "MỞ_LỆNH"]:
        mode = "HUNTING"
        prompt = _build_hunting_prompt(snapshot, ban_an)
    else:
        mode = "RIDING"
        alert_type = "LEVERAGE_WICKED" if abs(loi_nhuan_pct) < 5 else "EXIT_ERROR"
        prompt = _build_riding_prompt(snapshot, ban_an, alert_type, "BTC/USDT")
        
    try:
        from imperial_brain import brain
        ket_qua_str = brain.think_as("A05", prompt, brain_mode="A05_PURITY", est_tokens=4096)
        parsed = _parse_qwen_response(ket_qua_str)
        _save_postmortem(snap_id, mode, parsed, ban_an)
        log.info(f"🎯 Postmortem {mode} Completed: Saved results for {snap_id}")
    except Exception as e:
        log.error(f"Error running deep Postmortem for {snap_id}: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# PART 7 — DAEMON HEARTBEAT: DETERMINE RIGHT/WRONG BY SCANNING ORDERS
# ══════════════════════════════════════════════════════════════════════════════

import glob

def chay_heartbeat_soi_lenh():
    log.info("[A05 Diagnosis] Starting Forensic Loop (Heartbeat) scanning logs/dpo_lab...")
    while True:
        # Path to the generated Evaluator directory:
        khuyen_nghi_dir = os.path.join(BASE_DIR, "logs", "dpo_lab", "A05", "khuyen_nghi")
        if not os.path.exists(khuyen_nghi_dir):
            time.sleep(60)
            continue
            
        for file in glob.glob(os.path.join(khuyen_nghi_dir, "*.jsonl")):
            try:
                with open(file, 'r', encoding='utf-8') as fh:
                    lines = fh.readlines()
                    
                for line in lines:
                    if not line.strip(): continue
                    try:
                        record = json.loads(line)
                    except:
                        continue
                        
                    snap_id = record.get("snapshot_id", "")
                    if not snap_id: continue
                    
                    # Target file (in Root DPO_LAB)
                    judge_file = os.path.join(JUDGE_DIR, f"{snap_id}.json")
                    reject_file = os.path.join(REJECTED_DIR, f"{snap_id}.json")
                    
                    # Skip if already audited
                    if os.path.exists(judge_file) or os.path.exists(reject_file):
                        continue
                        
                    payload = record.get("data", record.get("content", {}))
                    judg = payload.get("judgment", {})
                    if isinstance(judg, str):
                        try:
                            # DNA v16.6: Extract JSON from markdown block if present
                            if "```json" in judg:
                                import re
                                match = re.search(r"```json\s*(\{.*?\})\s*```", judg, re.DOTALL)
                                if match:
                                    judg = json.loads(match.group(1))
                                else:
                                    judg = json.loads(judg)
                            else:
                                judg = json.loads(judg)
                        except:
                            judg = {}
                            
                    if not isinstance(judg, dict):
                        continue
                        
                    action = str(judg.get("Action", "")).strip().upper()
                    if action not in ["LONG", "SHORT", "MUA", "BÁN", "MỞ_LỆNH", "CẮT_LỖ", "TAKEPROFIT", "THOÁT"]:
                        continue
                    
                    # ── Determine RIGHT/WRONG via OHLCV after Snapshot (Extracted from dpo_evaluator) ──
                    try:
                        entry_val = float(judg.get("Entry", judg.get("Entry_Price", 0)) or 0)
                        target_val = float(judg.get("Target", judg.get("Take_Profit", 0)) or 0)
                        sl_val = float(judg.get("Stoploss", judg.get("Stop_Loss", 0)) or 0)
                    except (ValueError, TypeError):
                        continue
                        
                    if not entry_val or not target_val or not sl_val:
                        continue # Order missing parameters, default to unable to audit PnL
                        
                    ts_unix = record.get("timestamp_unix", 0)
                    if not ts_unix: continue
                    
                    status = "PENDING"
                    import ccxt
                    try:
                        san = ccxt.binance({'enableRateLimit': True})
                        ma_coin = payload.get("symbol", "BTC/USDT")
                        # Get 15m candles from the time order was placed (A05 Evaluator)
                        nen = san.fetch_ohlcv(ma_coin, '15m', since=int(ts_unix * 1000), limit=500)
                        if nen:
                            for n in nen:
                                high, low = n[2], n[3]
                                if action in ["LONG", "MUA", "MỞ_LỆNH"]:
                                    if low <= sl_val:
                                        status = "REJECTED"
                                        break
                                    elif high >= target_val:
                                        status = "CHOSEN"
                                        break
                                elif action in ["SHORT", "BÁN"]:
                                    if high >= sl_val:
                                        status = "REJECTED"
                                        break
                                    elif low <= target_val:
                                        status = "CHOSEN"
                                        break
                    except Exception as eccxt:
                        log.error(f"[HEARTBEAT] Error fetching CCXT to audit order {snap_id}: {eccxt}")
                        continue
                        
                    if status == "PENDING":
                        continue # Skip, TP/SL not hit yet, leave for next Heartbeat check
                        
                    is_chosen = (status == "CHOSEN")
 
                    if is_chosen:
                        with open(judge_file, 'w', encoding='utf-8') as jf:
                            json.dump(record, jf, ensure_ascii=False)
                        log.info(f"🎯 [HEARTBEAT] CHOSEN (Hit Target): {snap_id} -> Moved to {judge_file}")
                    else:
                        with open(reject_file, 'w', encoding='utf-8') as rf:
                            json.dump(record, rf, ensure_ascii=False)
                        log.info(f"💔 [HEARTBEAT] REJECTED (Hit Stoploss): {snap_id} -> Moved to {reject_file} (Triggering 397B Deep Diagnostic!)")
                        
                        # AUTOMATICALLY TRIGGER DEEP POST-MORTEM FOR FAILED ORDER USING DEEP FUNCTION
                        import threading
                        threading.Thread(target=_kich_hoat_postmortem_chuyen_sau, 
                                         args=(record, snap_id, action, entry_val, sl_val), 
                                         daemon=True).start()
            except Exception as e:
                log.error(f"[HEARTBEAT] Error when auditing file {file}: {e}")
                
        time.sleep(300) # Heartbeat every 5 minutes
