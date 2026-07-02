"""
🧬 DNA: v16.6 (Sovereign Purity - Dien Hong)
🏢 UNIT: DIEN_HONG_COUNCIL
🛠️ ROLE: ORCHESTRATOR
📖 DESC: Dien Hong Council system to synchronize the knowledge of 6 core agents.

╔══════════════════════════════════════════════════════════════════════════════╗
║  DIEN HONG COUNCIL — REDIS STREAM FOR EXPERT EXCHANGE OF 6 ELDERS            ║
║  Stream: zcl:dien_hong:stream                                              ║
║  Agents: A03 · A04 · A05 · A10 · A11 · A12                                ║
║  Cycle:  Once daily (06:00 VN) — each agent gets equal Max Think opportunity║
║  RAM:    ~150k tokens (circular trim) — Disk: infinite (archive to JSONL)  ║
╚══════════════════════════════════════════════════════════════════════════════╝

This module is the orchestration hub of the Dien Hong Council.
Each agent imports and runs run_council_session(agent_id) from a daemon thread.
"""
import os
import sys
import json
import time
import glob
import logging
import re
from datetime import datetime, timezone

# ── PATH SETUP ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "tools"))

log = logging.getLogger("DIEN_HONG_COUNCIL")

# ── CONSTANTS ───────────────────────────────────────────────────────────────
STREAM_KEY = "zcl:dien_hong:stream"
MAX_STREAM_TOKENS = 150_000        # ~600k chars / 4 = 150k tokens (cut 50% to save API cost)
MAX_PERSONAL_CHARS = 1_000_000       # ~250k tokens for personal context (Historical Timeline Memory)
ARCHIVE_DIR = os.path.join(BASE_DIR, "logs/dien_hong")
DPO_LAB_DIR = os.path.join(BASE_DIR, "logs/dpo_lab")

AGENT_ROLES = {
    "A03": "Crowd Psychology Expert — Social Sentiment Crawler",
    "A04": "Price Action Scholar — Wyckoff/Elliott/VSA Scholar",
    "A05": "Eye of God Commander — Commander & Evaluator",
    "A10": "Elite Shadow — Elite Money Flow & Dark Pool Tracker",
    "A11": "Sima Yi — Macro Intent Analyzer & Strategist",
    "A12": "Manipulation Detective — AEO Narrative Detective",
}

AGENT_SNAPSHOT_DIRS = {
    "A03": os.path.join(DPO_LAB_DIR, "A03_NEW"),
    "A04": os.path.join(DPO_LAB_DIR, "A04_NEW"),
    "A05": os.path.join(DPO_LAB_DIR, "A05/all_snapshot"),  # JSONL format
    "A10": os.path.join(DPO_LAB_DIR, "A10_NEW"),
    "A11": os.path.join(DPO_LAB_DIR, "A11_NEW"),
    "A12": os.path.join(DPO_LAB_DIR, "A12_NEW"),
}


def _get_matrix():
    """Lazy import matrix singleton to avoid circular imports."""
    try:
        from imperial_state import matrix
        return matrix
    except Exception:
        return None


def _estimate_tokens(text: str) -> int:
    """Rough estimation of token count from character count (1 token ~ 4 English chars, ~2 Vietnamese chars)."""
    return max(len(text) // 3, 1)


# ═══════════════════════════════════════════════════════════════════════════
# 1. LOAD SNAPSHOT — Read personal expert data
# ═══════════════════════════════════════════════════════════════════════════

def _extract_llm_response(content: str) -> str:
    """Extract the RESPONSE (OUTPUT) section from snapshot.md to avoid recursive repetition of old prompts."""
    if "## 2. LLM RESPONSE (OUTPUT)" in content:
        return content.split("## 2. LLM RESPONSE (OUTPUT)", 1)[1].strip()
    return content


def load_historical_snapshots(agent_id: str, since_date: str = "2026-04-16") -> str:
    """Read snapshot by Timeline: 1 latest version + the longest version of previous days (descending)."""
    snap_dir = AGENT_SNAPSHOT_DIRS.get(agent_id)
    if not snap_dir or not os.path.isdir(snap_dir):
        return f"[{agent_id}] Snapshot directory not found."

    if agent_id == "A05":
        return _load_a05_timeline(snap_dir, since_date)

    files = sorted(glob.glob(os.path.join(snap_dir, "snapshot_*.md")))
    if not files:
        return f"[{agent_id}] No snapshot yet."

    latest_file = files[-1]
    
    # Group by day: snapshot_2026-04-16_123456.md -> 2026-04-16
    day_groups = {}
    norm_since = since_date.replace("-", "")
    for f in files:
        if f == latest_file:
            continue
        basename = os.path.basename(f)
        match = re.search(r"snapshot_(\d{4}-?\d{2}-?\d{2})", basename)
        if match:
            day = match.group(1).replace("-", "")
            if day < norm_since:
                continue # Skip days that are too old
            size = os.path.getsize(f)
            if day not in day_groups or size > day_groups[day][1]:
                day_groups[day] = (f, size)
    
    # Read the latest version
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            raw_content = f.read()
            content = f"=== LATEST SNAPSHOT ===\n{_extract_llm_response(raw_content)}"
    except Exception as e:
        content = f"Error reading latest: {e}"
        
    total_chars = len(content)
    
    # Read back through previous days
    sorted_days = sorted(day_groups.keys(), reverse=True)
    for day in sorted_days:
        if total_chars >= MAX_PERSONAL_CHARS:
            break
        biggest_file, _ = day_groups[day]
        try:
            with open(biggest_file, "r", encoding="utf-8") as f:
                raw_content = f.read()
                day_content = f"\n\n=== LONGEST SNAPSHOT ({day}) ===\n{_extract_llm_response(raw_content)}"
                
            if total_chars + len(day_content) <= MAX_PERSONAL_CHARS:
                content += day_content
                total_chars += len(day_content)
            else:
                allowed = MAX_PERSONAL_CHARS - total_chars
                content += day_content[:allowed]
                total_chars += allowed
                break
        except Exception:
            continue
            
    return content

def _load_a05_timeline(snap_dir: str, since_date: str) -> str:
    """Specialized handling for A05: Retrieve the latest line + the longest line of each day."""
    jsonl_files = sorted(glob.glob(os.path.join(snap_dir, "snapshot_*.jsonl")))
    if not jsonl_files:
        return "[A05] No JSONL snapshot yet."

    # Group by day
    day_groups = {}
    latest_line = ""
    norm_since = since_date.replace("-", "")
    
    for file in reversed(jsonl_files):
        basename = os.path.basename(file)
        match = re.search(r"snapshot_(\d{4}-?\d{2}-?\d{2})", basename)
        day = match.group(1).replace("-", "") if match else basename
        
        if match and day < norm_since:
            continue # Skip old junk
            
        longest_line = ""
        longest_len = 0
        try:
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped: continue
                    if file == jsonl_files[-1]:
                        latest_line = stripped 
                        
                    if len(stripped) > longest_len:
                        longest_line = stripped
                        longest_len = len(stripped)
            
            if longest_line:
                if day not in day_groups or longest_len > len(day_groups[day]):
                    day_groups[day] = longest_line
        except Exception:
            continue

    def parse_a05_line(line: str, title: str) -> str:
        try:
            data = json.loads(line)
            raw_data = data.get("data", {})
            if isinstance(raw_data, str):
                try: raw_data = json.loads(raw_data)
                except: raw_data = {}
            if not isinstance(raw_data, dict): raw_data = {}
            judgment = raw_data.get("judgment", "")
            div_matrix = raw_data.get("divergence_matrix", {})
            bo_lao = div_matrix.get("Bo_Lao_Tu_Van", {})
            algo_summary = div_matrix.get("algo_summary", {})
            return "\n".join([
                f"=== {title} (ts: {data.get('ts_unix', 'N/A')}) ===",
                f"Judgment: {judgment[:3000]}",
                f"Algo Summary: {json.dumps(algo_summary, ensure_ascii=False)}",
                f"Consulting Elders: {json.dumps(bo_lao, ensure_ascii=False)[:5000]}"
            ])
        except: return ""

    content = parse_a05_line(latest_line, "A05 LATEST SNAPSHOT")
    total_chars = len(content)
    
    sorted_days = sorted(day_groups.keys(), reverse=True)
    for day in sorted_days:
        if total_chars >= MAX_PERSONAL_CHARS: break
        if day_groups[day] == latest_line: continue 
        
        day_content = parse_a05_line(day_groups[day], f"A05 LONGEST SNAPSHOT ({day})")
        if not day_content: continue
        
        day_content = "\n\n" + day_content
        if total_chars + len(day_content) <= MAX_PERSONAL_CHARS:
            content += day_content
            total_chars += len(day_content)
        else:
            allowed = MAX_PERSONAL_CHARS - total_chars
            content += day_content[:allowed]
            total_chars += allowed
            break
            
    return content or "[A05] JSONL snapshot empty or parse error."


# ═══════════════════════════════════════════════════════════════════════════
# 2. REDIS STREAM — Read / Write / Trim / Archive
# ═══════════════════════════════════════════════════════════════════════════

def read_council_stream(max_tokens: int = MAX_STREAM_TOKENS) -> str:
    """Read the entire Dien Hong stream, trim by token budget."""
    matrix = _get_matrix()
    if not matrix or not matrix.client:
        return "[STREAM] Could not connect to Redis."

    try:
        entries = matrix.client.xrevrange(STREAM_KEY, count=100)
        if not entries:
            return "[STREAM] Dien Hong Council has no minutes recorded yet."

        # xrevrange returns from the newest entry backwards
        lines = []
        total_chars = 0
        char_budget = max_tokens * 3  # 1 token ~ 3 chars

        for entry_id, data in entries:
            entry_id_str = entry_id if isinstance(entry_id, str) else entry_id.decode("utf-8")
            payload_str = data.get("payload", data.get(b"payload", "{}"))
            if isinstance(payload_str, bytes):
                payload_str = payload_str.decode("utf-8")

            if total_chars + len(payload_str) > char_budget:
                break  # Budget full

            lines.insert(0, f"[ENTRY:{entry_id_str}] {payload_str}")
            total_chars += len(payload_str)

        return "\n\n".join(lines)
    except Exception as e:
        log.error(f"[DIEN_HONG] Error reading stream: {e}")
        return f"[STREAM] Error: {e}"


def write_verdict(agent_id: str, verdict_json: dict, thinking_raw: str = "") -> str:
    """
    Write verdict to Redis Stream + save local file.
    IMPORTANT: thinking_raw is saved in BOTH the stream and the local file.
    This is reasoning intellect — requested to be 100% preserved.
    Returns: entry_id or error string.
    """
    matrix = _get_matrix()
    if not matrix or not matrix.client:
        return "ERR: No Redis connection"

    timestamp = datetime.now(timezone.utc).isoformat()
    verdict_json["timestamp"] = timestamp
    verdict_json["agent_id"] = agent_id
    verdict_json["agent_role"] = AGENT_ROLES.get(agent_id, "Unknown")

    # PUT thinking INTO STREAM — reasoning intellect must be preserved
    if thinking_raw:
        verdict_json["thinking"] = thinking_raw

    full_record = {**verdict_json}

    # 1. XADD to Redis Stream — INCLUDING thinking field
    payload_str = json.dumps(verdict_json, ensure_ascii=False)

    try:
        entry_id = matrix.xadd("DIEN_HONG", "stream", {"payload": payload_str})
        if isinstance(entry_id, bytes):
            entry_id = entry_id.decode("utf-8")
        log.info(f"[DIEN_HONG] ✅ {agent_id} recorded minutes + thinking: {entry_id} ({len(payload_str)} chars)")
    except Exception as e:
        log.error(f"[DIEN_HONG] XADD error: {e}")
        return f"ERR: {e}"

    # 2. Save local file (complete = stream payload)
    _save_local_verdict(agent_id, full_record)

    # 3. Trim stream if too large
    _trim_stream()

    return entry_id


def _save_local_verdict(agent_id: str, record: dict):
    """Save personal minutes into the agent directory."""
    snap_dir = AGENT_SNAPSHOT_DIRS.get(agent_id, "")
    dien_hong_dir = os.path.join(snap_dir, "dien_hong")
    os.makedirs(dien_hong_dir, exist_ok=True)

    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"council_{agent_id}_{ts_str}.json"
    filepath = os.path.join(dien_hong_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        log.info(f"[DIEN_HONG] 💾 Saved: {filepath}")
    except Exception as e:
        log.error(f"[DIEN_HONG] Error saving locally: {e}")


def _trim_stream():
    """Trim the oldest stream when exceeding 300k tokens in RAM. Archive to disk."""
    matrix = _get_matrix()
    if not matrix or not matrix.client:
        return

    try:
        stream_len = matrix.client.xlen(STREAM_KEY)
        if stream_len < 100:  # Not enough entries to require trimming
            return

        # Retrieve 50 oldest entries to archive instead of calculating the entire stream
        entries = matrix.client.xrange(STREAM_KEY, count=50)
        if not entries:
            return

        # Archive old entries
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        archive_file = os.path.join(ARCHIVE_DIR, f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
        trimmed_ids = []

        with open(archive_file, "w", encoding="utf-8") as f:
            for entry_id, data in entries:
                payload = data.get("payload", data.get(b"payload", "{}"))
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                eid = entry_id if isinstance(entry_id, str) else entry_id.decode("utf-8")
                f.write(json.dumps({"id": eid, "payload": payload}, ensure_ascii=False) + "\n")
                trimmed_ids.append(entry_id)

        # Delete archived entries from stream
        if trimmed_ids:
            matrix.client.xdel(STREAM_KEY, *trimmed_ids)
            log.info(f"[DIEN_HONG] ✂️ Trimmed {len(trimmed_ids)} entries -> {archive_file}")

    except Exception as e:
        log.error(f"[DIEN_HONG] Trim error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 3. PROMPT BUILDER — Build Dien Hong Council prompt
# ═══════════════════════════════════════════════════════════════════════════

def _build_other_agents_list(current_agent_id: str) -> list:
    """List of 5 other agents excluding the current agent."""
    all_agents = ["A03", "A04", "A05", "A10", "A11", "A12"]
    return [a for a in all_agents if a != current_agent_id]


def build_council_prompt(agent_id: str, personal_ctx: str, stream_ctx: str) -> str:
    """Build prompt for Max Think: snapshot + stream + verdict directives.

    Each agent MUST open a <thinking> tag to reason through each argument of the other 5 agents,
    then output their expert verdict from their own perspective.
    IMPORTANT: Thinking and each JSON field must be DEEPLY ANALYZED and SPECIFICALLY EXTRACTED.
    """
    role = AGENT_ROLES.get(agent_id, "Expert")
    others = _build_other_agents_list(agent_id)
    others_analysis_block = "\n".join([
        f"""   {i+1}. ═══ [ELDER {a} ANALYSIS] ({AGENT_ROLES.get(a, '')}) ═══
      - List EACH key argument of {a} (at least 3 arguments)
      - For EACH argument: evaluate the evidence (which data point supports it? what data is missing?)
      - Determine: agreement or CONFLICT with your expert data?
      - If conflicting: explain WHY from the perspective of {role} — provide specific counter-arguments
      - Rate the reliability of the argument: STRONG / MODERATE / WEAK (with reasons)"""
        for i, a in enumerate(others)
    ])

    prompt = f"""╔══════════════════════════════════════════════════════════════════════════╗
║      DIEN HONG COUNCIL — STRATEGIC SESSION — DEEP ANALYSIS               ║
╚══════════════════════════════════════════════════════════════════════════╝

You are Elder {agent_id} — {role}.
You are participating in the DIEN HONG COUNCIL — the strategic conference of 6 top experts.
This is the MOST IMPORTANT meeting — where 6 elite brains combine to decode the market.

🎯 SESSION OBJECTIVES:
- Multidimensional synthesis across 6 expert domains
- Detect CONFLICTS, COGNITIVE TRAPS, and BLIND SPOTS in arguments
- Provide STRATEGIC recommendations to Commander A05 with expert depth

═════════════════════════════════════════════════════════════════
YOUR EXPERT DATA (Personal Snapshot):
═════════════════════════════════════════════════════════════════
{personal_ctx[:100000]}

═════════════════════════════════════════════════════════════════
DIEN HONG COUNCIL MINUTES (Opinions + Thinking of other Elders — accumulated):
═════════════════════════════════════════════════════════════════
{stream_ctx[:200000]}

╔══════════════════════════════════════════════════════════════════════════╗
║           COGNITIVE MANDATE — 100% COMPLIANCE REQUIRED                   ║
╚══════════════════════════════════════════════════════════════════════════╝

🧠 MUST open a <thinking> tag and reason STEP-BY-STEP, in DETAIL and across MULTIPLE LEVELS:

{others_analysis_block}

   6. ═══ [CROSS-DOMAIN SYNTHESIS] ═══
      - Map AGREEMENTS: which agents reached similar conclusions? What data overlaps?
      - Map CONFLICTS: which agents contradict each other? Who is more correct? Why?
      - Detect BLIND SPOTS: is there any important information that NO AGENT HAS MENTIONED?

   7. ═══ [EXPERT PERSPECTIVE OF {agent_id} — DEEP ANALYSIS REQUIRED] ═══
      From your expertise as {role}, you MUST:
      - Provide an INDEPENDENT VERDICT based on YOUR expert data (no copy-pasting)
      - Unpack at least 3 LEVELS of analysis (short-term -> medium-term -> long-term)
      - Define BASE CASE vs. RISK SCENARIOS (probability for each scenario)
      - Cross-reference with the data of the other 5 Elders — which data REINFORCES your verdict?
      - Give SPECIFIC RECOMMENDATIONS to Commander A05 (actions, timing, thresholds, conditions)

⚠️ WARNING: Thinking must be LONG, DETAILED, and IN-DEPTH — minimum 2000 characters.
   If thinking is brief/shallow = session failed = waste of 800k tokens.
   THINK LIKE A TOP-TIER EXPERT — not a chatbot.

After the </thinking> tag, RETURN A SINGLE JSON with 3 CORE FIELDS (representing the outputs of the Cognitive Mandate):
{{
  "agent_id": "{agent_id}",
  "conflict_analysis": "<Level 1 Result: Summary of weaknesses, logical fallacies, or points of agreement of the other 5 Elders>",
  "cross_synthesis": "<Level 2 Result: Common consensus of the Council and any Blind spots that no one has noticed>",
  "expert_scenario": "<Level 3 Result: Independent verdict from your own domain of expertise (Base Case & Risks)>"
}}

⚠️ FINAL REMINDER — NO BRIEF ANSWERS:
- If any field is under 300 characters -> SESSION FAILED
- Each verdict MUST have supporting data points (numbers, index, timestamp)
- DO NOT write generic advice like "needs monitoring" without specifying WHAT, WHERE, and WHEN to monitor."""
    return prompt


# ═══════════════════════════════════════════════════════════════════════════
# 4. COUNCIL SESSION — Orchestrate entire session for 1 agent
# ═══════════════════════════════════════════════════════════════════════════

def run_council_session(agent_id: str) -> dict:
    """
    Run 1 Dien Hong Council session for agent_id.
    1. Load personal snapshot (latest + longest)
    2. Read Dien Hong stream
    3. Build prompt → Call LLM (ALGO_PLUS)
    4. Parse response → Write verdict to stream + local file
    Returns: verdict dict or error dict
    """
    log.info(f"[DIEN_HONG] 🏛️ Starting council session for {agent_id} ({AGENT_ROLES.get(agent_id, '')})")

    # ── Step 1: Load personal context (Historical Timeline Memory) ──
    personal_ctx = load_historical_snapshots(agent_id)

    # ── Step 2: Load stream context ──
    stream_ctx = read_council_stream()

    # ── Step 3: Build prompt & Call LLM ──
    prompt = build_council_prompt(agent_id, personal_ctx, stream_ctx)
    est_tokens = _estimate_tokens(prompt) + 5000  # Buffer for response

    log.info(f"[DIEN_HONG] 📝 Prompt size: ~{_estimate_tokens(prompt)} tokens. Calling LLM...")

    try:
        from imperial_brain import brain
        llm_response = brain.think_as(
            f"DIEN_HONG_{agent_id}",
            prompt,
            est_tokens=min(est_tokens, 32000)
        )
    except Exception as e:
        log.error(f"[DIEN_HONG] ❌ LLM Error for {agent_id}: {e}")
        return {"error": str(e), "agent_id": agent_id}

    if not llm_response:
        log.error(f"[DIEN_HONG] ❌ LLM returned empty for {agent_id}")
        return {"error": "Empty LLM response", "agent_id": agent_id}

    # ── Step 4: Parse response — PRESERVE REASONING INTELLECT ──
    thinking_raw = ""
    # Support both <think> and <thinking> since LLM might use either
    think_match = re.search(r"<think(?:ing)?>(.*?)</think(?:ing)?>", llm_response, re.DOTALL)
    if think_match:
        thinking_raw = think_match.group(1).strip()
        log.info(f"[DIEN_HONG] 🧠 Thinking extracted: {len(thinking_raw)} chars")
    else:
        # If LLM didn't use thinking tags, the entire response pre-JSON is the thinking
        log.warning(f"[DIEN_HONG] ⚠️ <thinking> tag not found — falling back to pre-JSON content")

    # Strip thinking tags for JSON extraction
    clean_response = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", llm_response, flags=re.DOTALL)

    # If no thinking tag was found, take everything before the first '{' as thinking
    if not thinking_raw:
        pre_json = clean_response.split("{", 1)[0].strip() if "{" in clean_response else ""
        if len(pre_json) > 200:
            thinking_raw = pre_json
            log.info(f"[DIEN_HONG] 🧠 Fallback thinking (pre-JSON): {len(thinking_raw)} chars")

    # Extract JSON
    verdict = None
    json_match = re.search(r"\{.*\}", clean_response, re.DOTALL)
    if json_match:
        try:
            verdict = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            log.error(f"[DIEN_HONG] JSON parse error: {e}")

    if not verdict:
        # Fallback: create verdict from raw response
        verdict = {
            "agent_id": agent_id,
            "expert_opinion": llm_response[:5000],
            "thinking": thinking_raw or llm_response[:8000],
            "recommendation_a05": "Parse error — see raw response and thinking.",
            "confidence": 0.0,
        }

    # ── Step 5: Write to stream + local file ──
    entry_id = write_verdict(agent_id, verdict, thinking_raw=thinking_raw)
    log.info(f"[DIEN_HONG] 🏛️ {agent_id} completed session. Entry: {entry_id}")

    # ── Step 6: Skip markdown snapshot for council (handled by JSON already) ──
    # Avoid calling log_agent_snapshot here with .md files to prevent recursive loading loop
    
    return verdict


# ═══════════════════════════════════════════════════════════════════════════
# 5. LOAD COUNCIL HISTORY — Read personal Dien Hong minutes (for prompt injection)
# ═══════════════════════════════════════════════════════════════════════════

def load_council_history(agent_id: str) -> str:
    """Read the latest personal Dien Hong minutes to inject into the main prompt."""
    snap_dir = AGENT_SNAPSHOT_DIRS.get(agent_id, "")
    dien_hong_dir = os.path.join(snap_dir, "dien_hong")

    if not os.path.isdir(dien_hong_dir):
        return "[NEW DIEN HONG COUNCIL MINUTES NOT YET CREATED]"

    import glob
    files = sorted(glob.glob(os.path.join(dien_hong_dir, "council_*.json")))
    if not files:
        return "[NEW DIEN HONG COUNCIL MINUTES NOT YET CREATED]"

    latest_file = files[-1]
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            "=== YOUR OWN DIEN HONG COUNCIL MINUTES (SELF-REFLECTION) ===\n"
            f"{json.dumps(data, ensure_ascii=False, indent=2)}\n"
            "================================================================\n"
        )
    except Exception:
        return "[ERROR READING DIEN HONG MINUTES]"


# ═══════════════════════════════════════════════════════════════════════════
# 6. SEED DATA — Seed initial data into stream
# ═══════════════════════════════════════════════════════════════════════════

def seed_initial_data():
    """Seed the first 5 entries from provided historical data. Runs once."""
    matrix = _get_matrix()
    if not matrix or not matrix.client:
        log.error("[DIEN_HONG] Could not connect to Redis to seed.")
        return

    # Check if stream already has data
    try:
        existing = matrix.client.xlen(STREAM_KEY)
        if existing and existing > 0:
            log.info(f"[DIEN_HONG] Stream already contains {existing} entries. Skipping seed.")
            return
    except Exception:
        pass

    timestamp = datetime.now(timezone.utc).isoformat()

    seed_entries = [
        {
            "agent_id": "A03",
            "agent_role": AGENT_ROLES["A03"],
            "timestamp": timestamp,
            "expert_verdict": "Media did a quick shift from legal FUD to AI wins Crypto narrative right after 21:10 UTC 04/15, while Elite reduced Options position from 15 to 0, indicating they have finished accumulating supply in the $70-75k area. MM Fingerprint remains at 20 (Capitulation) with no signs of strong selling, while A04 still labels SCAVENGER_ZONE and IMPULSE_W5 – a FOMO trap structure.",
            "crowd_sentiment": "The crowd is moving from EXTREME FEAR to a mild FOMO cycle, triggered by fake bullish AI headlines, while in reality they are still panic-selling at loss in the $70k-$75k area.",
            "contrarian_signal": "The trap lies in the $70k-$75k range: do not buy when media switches to bullish news, accumulate gradually when price holds above $70k and volume shows absorption; set stop-loss below $69.8k.",
            "compiled_insight_update": "Spring is still completing; media flip does not change the structure. Elite has exited short positions, preparing for a breakout. Invalidation point remains at $69.8k.",
            "confidence": 0.75,
        },
        {
            "agent_id": "A04",
            "agent_role": AGENT_ROLES["A04"],
            "timestamp": timestamp,
            "expert_verdict": "Hidden distribution is happening from the Daily timeframe and above (CM3_DISTRIBUTION), though Seconds/Hours show accumulation signs. Buy opportunity only valid when breaking $74,000 with sustainable CM1_ABSORPTION and explosive volume on 4H. Current stance: stay out — this is a FOMO trap in SCAVENGER_ZONE.",
            "weekly_scholar": "Weekly is in a downtrend (TENDING_DOWN) with Elliott CORRECTIVE_C wave (45% confidence), macro bottom not yet confirmed.",
            "daily_scholar": "Daily is in MARKDOWN_PULSE — sign of hidden distribution by CM (CM3_DISTRIBUTION). KAR >1.4 and MNR ~0.69 show high noise, setting stop-loss traps.",
            "hourly_scholar": "1H in PHASE_B — sideways accumulation, NO TRADING.",
            "minute_scholar": "15M also in PHASE_B, volume decreasing, KAR=0.8 -> thin liquidity (NO_SUPPLY) but not a true exhaustion sign.",
            "second_scholar": "1S shows CM1_ABSORPTION (Tier 1 Wall) with KAR=4.1 — extremely strong buying effort but price not rising, indicating Elite is accumulating hidden inventory.",
            "compiled_insight_update": "Hidden distribution is happening from the Daily timeframe and above (CM3_DISTRIBUTION), though Seconds/Hours timeframes show accumulation signs.",
            "confidence": 0.80,
        },
        {
            "agent_id": "A10",
            "agent_role": AGENT_ROLES["A10"],
            "timestamp": timestamp,
            "expert_verdict": "Elite is NOT accumulating, but conducting HIDDEN DISTRIBUTION. CFTC Commercial Long decreased (distribution) on gold and oil. Stablecoin inflow hidden to exchanges + large withdrawals from DeFi wallets. OFI remains stable (2.11) with no imbalance — suggesting selling via dark pool.",
            "money_flow_trajectory": "Elite started strong ACCUMULATION of gold and oil from Q1-Q2/2025, switched to DISTRIBUTION from Q3/2025 and is distributing heavily over the last 1-2 months. Elite money flow is opposite to retail: retail buys gold due to fear, Elite sells gold to take profits.",
            "manipulation_footprint": "Media Veil: maintaining macro verdict 'NEUTRAL' despite GEO=10 to create manufactured fear. Dark-Pool Execution: selling large volumes of oil/gold via dark pool, avoiding OFI imbalance.",
            "compiled_insight_update": "Elite is in the late phase of distribution cycle, using manufactured fear (GEO=10) to mask sales.",
            "confidence": 0.85,
        },
        {
            "agent_id": "A11",
            "agent_role": AGENT_ROLES["A11"],
            "timestamp": timestamp,
            "expert_verdict": "This is the time to ACCUMULATE, not to BLOCK or CANCEL. A05 must act like a predator: silent, patient, and strike when Elite starts 'marking' with breakout volume.",
            "analysis": "Elite never acts on emotion — they act on liquidity cycles, and currently, they are in the final stage of 'Spring': compressing price, absorbing supply, and preparing for a large-scale re-rating. PDI hitting 90.0 is not a sign of collapse, but a 'panic saturation point'.",
            "is_trap": True,
            "trap_direction": "long_squeeze",
            "media_paradox_detected": True,
            "compiled_insight_update": "Current pattern closely matches late 2019 before the Fed injected liquidity. This is the Spring phase (spring compression).",
            "confidence": 0.92,
        },
        {
            "agent_id": "A12",
            "agent_role": AGENT_ROLES["A12"],
            "timestamp": timestamp,
            "expert_verdict": "Sophisticated AEO campaign, targeting AI alignment rather than the market; no need for emergency brakes, but close monitoring is required to prevent long-term abuse.",
            "beneficiary": "Conservative think‑tanks, defense‑industry PACs, and opaque energy‑sector funds.",
            "payload_hypothesis": "AI training corpus is being primed with moral‑anchoring narratives that associate Trump with negative ethical descriptors.",
            "confidence_score": 0.85,
            "verdict_aeo": "ORGANIC",
            "compiled_insight_update": "Confirmed AEO campaign 'Moral Anchoring' about Trump is in seeding phase. No simultaneous financial flow.",
            "confidence": 0.85,
        },
    ]

    grouped_payload = {}
    for entry in seed_entries:
        try:
            grouped_payload[entry["agent_id"]] = entry
            _save_local_verdict(entry["agent_id"], entry)
            log.info(f"[DIEN_HONG] 🌱 Seeded local: {entry['agent_id']}")
        except Exception as e:
            log.error(f"[DIEN_HONG] Local seed error {entry['agent_id']}: {e}")

    try:
        final_payload = {
            "timestamp": timestamp,
            "payload": json.dumps(grouped_payload, ensure_ascii=False)
        }
        matrix.xadd("DIEN_HONG", "stream", {"payload": json.dumps(grouped_payload, ensure_ascii=False)}) 
        log.info(f"[DIEN_HONG] ✅ Finished pushing 5 minutes entries (grouped as 1 line) into Redis stream.")
    except Exception as e:
        log.error(f"[DIEN_HONG] Redis seed error: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# 7. RUN ALL — Run the first council session for ALL agents
# ═══════════════════════════════════════════════════════════════════════════

def run_first_council():
    """Run the first council session for all 6 agents (sequentially, staggered by 10s)."""
    log.info("[DIEN_HONG] 🏛️🏛️🏛️ STARTING THE FIRST DIEN HONG COUNCIL SESSION 🏛️🏛️🏛️")

    # Seed initial data (if not already seeded)
    seed_initial_data()

    results = {}
    for agent_id in ["A03", "A04", "A10", "A11", "A12", "A05"]:
        log.info(f"\n{'='*60}")
        log.info(f"[DIEN_HONG] Elder {agent_id} entering the council room...")
        log.info(f"{'='*60}")

        result = run_council_session(agent_id)
        results[agent_id] = result

        # Stagger 10s between agents
        time.sleep(10)

    log.info("[DIEN_HONG] 🏛️ FIRST DIEN HONG COUNCIL SESSION COMPLETED!")
    return results


# ═══════════════════════════════════════════════════════════════════════════
# DAEMON HELPERS — Each agent only needs 2 import lines + invocation
# ═══════════════════════════════════════════════════════════════════════════

# Stagger offsets so that the 6 agents don't call the LLM simultaneously (up to 10 mins)
_STAGGER_OFFSETS = {
    "A03": 0,
    "A04": 2 * 60,    # +2 minutes
    "A05": 4 * 60,    # +4 minutes
    "A10": 6 * 60,    # +6 minutes
    "A11": 8 * 60,    # +8 minutes
    "A12": 10 * 60,   # +10 minutes
}

# ── Fixed 2-times-a-day schedule (Vietnam Time = UTC+7) ──────────────────
# Each agent is pinned to 2 fixed schedules: 06:00 (after US market close), 18:00 (VN time)
# + a small stagger (minutes) to avoid concurrent LLM invocations.
COUNCIL_HOURS_VN = [6, 18]       # 2 sessions/day: 06:00 VN (post US markets) + 18:00 VN (Asian trading hours)
VN_UTC_OFFSET = 7 * 3600             # Vietnam Time Offset (UTC+7)


def _next_council_fire(stagger_sec: int = 0) -> float:
    """
    Calculate the number of seconds until the next nearest Dien Hong session,
    aligned to the fixed hours (06:00, 18:00 VN).
    This function ensures NO drift even if a session takes a long time.
    """
    import datetime as _dt
    now_utc = _dt.datetime.utcnow()
    now_vn = now_utc + _dt.timedelta(seconds=VN_UTC_OFFSET)
    today_vn = now_vn.date()

    # Generate candidate timestamps for today and tomorrow
    candidates = []
    for h in COUNCIL_HOURS_VN:
        for day_offset in (0, 1):
            target_vn = _dt.datetime(
                today_vn.year, today_vn.month, today_vn.day,
                h, 0, 0
            ) + _dt.timedelta(days=day_offset) + _dt.timedelta(seconds=stagger_sec)
            candidates.append(target_vn)

    # Get the next timestamp (must be at least 60s in the future)
    future = sorted(t for t in candidates if (t - now_vn).total_seconds() > 60)
    if not future:
        # Safe fallback: 6 hours from now
        return 6 * 3600.0
    return max(60.0, (future[0] - now_vn).total_seconds())


def _council_daemon_loop(agent_id: str):
    """
    Background loop: run council session 2 times/day at fixed times.
    Wall-clock aligned → NO drift, NO missed sessions.
    All state in Redis is preserved between sessions.
    """
    stagger = _STAGGER_OFFSETS.get(agent_id, 0)

    # Warm-up waiting for at least 2 minutes to let the agent initialize
    initial_wait = max(120, _next_council_fire(stagger))
    log.info(f"[DIEN_HONG] 🏛️ Daemon {agent_id} | Fixed 1 session/day (06:00 VN) | waiting {initial_wait/3600:.2f}h until trigger time")
    time.sleep(initial_wait)

    while True:
        try:
            log.info(f"[DIEN_HONG] 🏛️ {agent_id} starting Dien Hong council session...")
            result = run_council_session(agent_id)
            if isinstance(result, dict) and "error" not in result:
                log.info(f"[DIEN_HONG] ✅ {agent_id} council session completed — "
                         f"confidence={result.get('confidence', 'N/A')}")
            else:
                log.warning(f"[DIEN_HONG] ⚠️ {agent_id} council session error: "
                            f"{result.get('error', 'unknown') if isinstance(result, dict) else result}")
        except Exception as e:
            log.error(f"[DIEN_HONG] ❌ Daemon {agent_id} error: {e}")

        # ── Align to the next schedule (wall-clock, no drift) ──────────
        wait_sec = _next_council_fire(stagger)
        log.info(f"[DIEN_HONG] 💤 {agent_id} sleeping {wait_sec/3600:.2f}h -> next session schedule")
        time.sleep(wait_sec)


def start_council_daemon(agent_id: str):
    """
    Start the background daemon thread for the Dien Hong Council.
    Call once in the __main__ block of the agent.

    Usage in each agent:
        from dien_hong_council import start_council_daemon
        start_council_daemon("A12")
    """
    import threading
    t = threading.Thread(
        target=_council_daemon_loop,
        args=(agent_id,),
        daemon=True,
        name=f"DienHong_{agent_id}",
    )
    t.start()
    log.info(f"[DIEN_HONG] 🏛️ Daemon thread '{t.name}' started for {agent_id}")
    return t


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')

    parser = argparse.ArgumentParser(description="Dien Hong Council — Council Manager")
    parser.add_argument("--seed", action="store_true", help="Seed initial data into stream")
    parser.add_argument("--run-first", action="store_true", help="Run the first council session for all agents")
    parser.add_argument("--run-agent", type=str, help="Run the council session for 1 specific agent (e.g. A12)")
    parser.add_argument("--status", action="store_true", help="Check stream status")

    args = parser.parse_args()

    if args.seed:
        seed_initial_data()
    elif args.run_first:
        run_first_council()
    elif args.run_agent:
        result = run_council_session(args.run_agent.upper())
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.status:
        m = _get_matrix()
        if m and m.client:
            length = m.client.xlen(STREAM_KEY)
            print(f"Stream: {STREAM_KEY}")
            print(f"Entries: {length}")
            if length > 0:
                entries = m.client.xrange(STREAM_KEY, count=3)
                for eid, data in entries:
                    eid_str = eid if isinstance(eid, str) else eid.decode("utf-8")
                    payload = data.get("payload", data.get(b"payload", ""))
                    if isinstance(payload, bytes):
                        payload = payload.decode("utf-8")
                    try:
                        p = json.loads(payload)
                        print(f"\n[{eid_str}] {p.get('agent_id', '?')} | {p.get('timestamp', '?')}")
                        print(f"  Insight: {p.get('compiled_insight_update', 'N/A')[:150]}")
                    except:
                        print(f"\n[{eid_str}] Raw: {payload[:200]}")
        else:
            print("❌ Could not connect to Redis")
    else:
        parser.print_help()
