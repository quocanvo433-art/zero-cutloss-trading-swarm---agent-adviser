"""
🧬 DNA: v18.1 (Session Memory Sovereignty + AEO Case Vault) [DNA Header] (Sovereign Purity)
🏢 UNIT: INFRASTRUCTURE (TOOLS)
🛠️ ROLE: SESSION_LOGGER
📖 DESC: The sole library managing Session Memory for A03/A11/A12.
         3 drift tiers: HOT(3h), WEEKLY(7d), DEEP(LLM checkpoint).
         AEO Case Vault: Auto-archive confirmed AEO cases into logs/A12/AEO/.
         Case Study Pipeline: Ratio per topic + 1 sample → inject Brain B.
         Checkpoint pipeline: Opus → Gemini Pro 3.1 → Qwen Plus.
🔗 CALLS: (standalone — imported by A03, A11, A12, divergence_engine)
📟 I/O: File: logs/A{XX}/YYYY-MM-DD.jsonl (write/read)
         File: logs/A{XX}/checkpoints/checkpoint_*.json (write/read)
         File: logs/A12/AEO/YYYY-MM-DD.jsonl (write — AEO Case Vault)
🛡️ INTEGRITY: Data-Classification, No-Sensitive-Leak, Compact-Format, Checkpoint-Chain.
"""
import os
import json
import logging
import time
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_BASE = BASE_DIR / "logs"
CONFIG_DIR = BASE_DIR / "config"

log = logging.getLogger("SESSION_LOGGER")

from llm_router import router_api_call


# ── Environment (lazy load) ──────────────────────────────────────────────────
_ENV_LOADED = False




# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — SENSITIVE DATA PROTECTION
# ══════════════════════════════════════════════════════════════════════════════

_SENSITIVE_KEYS = {
    "api_key", "apikey", "token", "secret", "password", "bearer",
    "authorization", "credential", "private_key", "access_token",
    "client_secret", "api_hash", "api_id", "GEMINI_API_KEY",
    "YOUTUBE_API_KEY", "TIKTOK_CLIENT_SECRET", "LUNARCRUSH_API_KEY",
    "TWITTER_BEARER_TOKEN", "TELEGRAM_API_HASH", "ANTHROPIC_API_KEY",
}


def _strip_sensitive(data: dict) -> dict:
    """Removes all keys containing sensitive information (API, token...)."""
    if not isinstance(data, dict):
        return data
    clean = {}
    for k, v in data.items():
        k_lower = k.lower()
        if any(s in k_lower for s in _SENSITIVE_KEYS):
            continue
        if isinstance(v, dict):
            clean[k] = _strip_sensitive(v)
        elif isinstance(v, list):
            clean[k] = [_strip_sensitive(i) if isinstance(i, dict) else i for i in v[:10]]
        else:
            clean[k] = v
    return clean


# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — LOG SESSION (Write)
# ══════════════════════════════════════════════════════════════════════════════

def _get_log_path(agent_id: str) -> Path:
    """Gets daily log file path for the agent."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    agent_dir = LOGS_BASE / agent_id.upper()
    agent_dir.mkdir(parents=True, exist_ok=True)
    return agent_dir / f"{today}.jsonl"


def log_session(agent_id: str, redis_key: str, summary: str,
                signals_count: int = 0, confidence: float = 0.0,
                expert_metrics: Optional[dict] = None,
                extra: Optional[dict] = None):
    """
    Writes 1 condensed JSONL line for 1 session.

    Args:
        agent_id: "A03", "A11", "A12"
        redis_key: Redis key written (e.g. "zcl:sentiment:latest")
        summary: 1-line technical summary (e.g. "BTC | FOMO_EXTREME | MM:45")
        signals_count: Number of processed signals
        confidence: Confidence level (0.0-1.0)
        extra: Additional dict (will be stripped of sensitive data)
    """
    # HINGE PROTOCOL: Decouple narrative and algo_metrics
    algo_metrics = {
        "signals_count": signals_count,
        "confidence": round(confidence, 3),
    }
    if expert_metrics:
        algo_metrics["expert_metrics"] = expert_metrics

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent_id.upper(),
        "redis_key": redis_key,
        "narrative": str(summary)[:500],
        "algo_metrics": algo_metrics
    }
    if extra:
        entry["extra"] = _strip_sensitive(extra)

    path = _get_log_path(agent_id)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning(f"[SESSION_LOG] Error writing {path}: {e}")

    # ── AEO Case Vault: Auto-archive for A12 ────────────────────────────
    if agent_id.upper() == "A12" and extra:
        verdict_label = extra.get("verdict", "")
        if verdict_label in ("MANUFACTURED", "HIGH_AEO", "LOW_AEO", "SUSPICIOUS"):
            _archive_aeo_case(entry, verdict_label)


def _prune_old_snapshots(target_dir: Path, keep_limit: int = 30):
    """
    Automatically cleans up old snapshots, keeping only the latest keep_limit files.
    Helps the Swarm run for months without filling up the disk.
    """
    try:
        snapshots = sorted(
            [f for f in target_dir.glob("snapshot_*.md") if f.is_file()],
            key=lambda x: x.stat().st_mtime
        )
        if len(snapshots) > keep_limit:
            to_delete = snapshots[:-keep_limit]
            for f in to_delete:
                try:
                    f.unlink()
                except Exception as e:
                    log.warning(f"[SNAPSHOT_CLEANER] Error deleting file {f}: {e}")
            log.info(f"[SNAPSHOT_CLEANER] Cleaned {len(to_delete)} old snapshots in {target_dir.name}, keeping only the {keep_limit} latest ones.")
    except Exception as e:
        log.warning(f"[SNAPSHOT_CLEANER] Error cleaning up snapshots in {target_dir}: {e}")


def log_agent_snapshot(agent_id: str, prompt: str, response: str, metadata: dict = None):
    """
    Records the entire Prompt (Input) and LLM Response (Output) as a .md file.
    Used for Audit, DPO, and tracking the LLM's Max Think process.
    Path: logs/dpo_lab/{AGENT_ID}/snapshot_{date}_{ts}.md
    """
    try:
        ts = int(time.time())
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        target_dir = BASE_DIR / "logs" / "dpo_lab" / f"{agent_id.upper()}_NEW"
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"snapshot_{date_str}_{ts}.md"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# SNAPSHOT {agent_id.upper()} - {date_str}\n\n")
            if metadata:
                f.write("## 0. METADATA (16D TENSOR & CBM/NVD SENSORS)\n```json\n")
                f.write(json.dumps(metadata, ensure_ascii=False, indent=2))
                f.write("\n```\n\n")
            f.write("## 1. FULL PROMPT (INPUT)\n```text\n")
            f.write(prompt or "")
            f.write("\n```\n\n")
            f.write("## 2. LLM RESPONSE (OUTPUT)\n```json\n")
            f.write(response or "")
            f.write("\n```\n")
        log.info(f"[{agent_id}] Logged Max Think snapshot at: {file_path.name}")
        
        # Automatically clean up old snapshots of this Agent
        _prune_old_snapshots(target_dir, keep_limit=30)
    except Exception as e:
        log.warning(f"[SESSION_LOGGER] Error writing snapshot {agent_id}: {e}")




# ══════════════════════════════════════════════════════════════════════════════
# PART 2B — AEO CASE VAULT (Auto-Archive + Case Study Pipeline)
# ══════════════════════════════════════════════════════════════════════════════

_AEO_VERDICTS = ("MANUFACTURED", "HIGH_AEO", "LOW_AEO", "SUSPICIOUS")


def _archive_aeo_case(entry: dict, verdict_label: str):
    """
    Auto-archives AEO case to logs/A12/AEO/{date}.jsonl.
    Only called from log_session() when agent=A12 and verdict is in _AEO_VERDICTS.
    """
    aeo_dir = LOGS_BASE / "A12" / "AEO"
    aeo_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = aeo_dir / f"{today}.jsonl"
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.debug(f"[AEO_VAULT] Archived {verdict_label} -> {path.name}")
    except Exception as e:
        log.warning(f"[AEO_VAULT] Error writing {path}: {e}")


def get_aeo_case_studies(max_topics: int = 5, days: int = 7) -> str:
    """
    Extracts AEO Case Studies for Brain B injection.

    Smart Strategy:
    - Calculate AEO% ratio by Topic (e.g. TRUMP 64.5%, OIL PRICE 100%)
    - Each topic gets only 1 representative JSONL entry (entry with the highest score)
    - Returns condensed text ready to inject into the prompt

    Priority: MANUFACTURED > HIGH_AEO > SUSPICIOUS > LOW_AEO
    Token budget: ~800-1200 tokens (very compact)
    """
    from collections import defaultdict, Counter
    import glob

    aeo_dir = LOGS_BASE / "A12" / "AEO"
    main_dir = LOGS_BASE / "A12"

    # ── Step 1: Read ALL A12 entries (main + AEO) within N days ────
    today = datetime.now(timezone.utc)
    all_entries = []
    aeo_entries = []

    for days_ago in range(days):
        dt = today - timedelta(days=days_ago)
        date_str = dt.strftime("%Y-%m-%d")

        # Main logs (all verdicts)
        main_path = main_dir / f"{date_str}.jsonl"
        if main_path.exists():
            try:
                with open(main_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            e = json.loads(line)
                            verdict = e.get("extra", {}).get("verdict", "")
                            if verdict:  # Only count entries with verdict
                                all_entries.append(e)
                                if verdict in _AEO_VERDICTS:
                                    aeo_entries.append(e)
                        except json.JSONDecodeError:
                            pass
            except Exception:
                pass

        # AEO archive (only AEO cases)
        aeo_path = aeo_dir / f"{date_str}.jsonl"
        if aeo_path.exists():
            try:
                with open(aeo_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            e = json.loads(line)
                            # Avoid duplicating entries already read from main
                            if e not in aeo_entries:
                                aeo_entries.append(e)
                                if e not in all_entries:
                                    all_entries.append(e)
                        except json.JSONDecodeError:
                            pass
            except Exception:
                pass

    if not all_entries:
        return ""

    # ── Step 2: Calculate AEO% ratio by topic ──────────────────────────────
    topic_total = Counter()       # All entries (ORGANIC + AEO)
    topic_aeo = Counter()         # Only AEO entries
    topic_best_sample = {}        # Entry with the highest score for each topic
    verdict_priority = {"MANUFACTURED": 4, "HIGH_AEO": 3, "SUSPICIOUS": 2, "LOW_AEO": 1}

    def _extract_topic(entry: dict) -> str:
        summary = entry.get("narrative", entry.get("summary", ""))
        if "Topic:" in summary:
            return summary.split("Topic:")[1].split("|")[0].strip()
        return ""

    def _extract_score(entry: dict) -> float:
        summary = entry.get("narrative", entry.get("summary", ""))
        if "Score:" in summary:
            try:
                return float(summary.split("Score:")[1].split("|")[0].strip())
            except (ValueError, IndexError):
                pass
        return 0.0

    for e in all_entries:
        topic = _extract_topic(e)
        if not topic:
            continue
        topic_total[topic] += 1

    for e in aeo_entries:
        topic = _extract_topic(e)
        verdict = e.get("extra", {}).get("verdict", "")
        if not topic:
            continue
        topic_aeo[topic] += 1

        # Keep best entry: prioritize highest verdict, then highest score
        score = _extract_score(e)
        priority = verdict_priority.get(verdict, 0)
        current = topic_best_sample.get(topic)
        if current is None:
            topic_best_sample[topic] = (e, priority, score)
        else:
            _, cur_prio, cur_score = current
            if priority > cur_prio or (priority == cur_prio and score > cur_score):
                topic_best_sample[topic] = (e, priority, score)

    if not topic_aeo:
        return ""

    # ── Step 3: Sort topics by AEO% descending ──────────────────────
    topic_ratios = []
    for topic in topic_aeo:
        total = topic_total.get(topic, 1)
        aeo_count = topic_aeo[topic]
        ratio = aeo_count / total * 100
        topic_ratios.append((topic, ratio, aeo_count, total))

    topic_ratios.sort(key=lambda x: -x[1])  # Highest first
    topic_ratios = topic_ratios[:max_topics]

    # ── Step 4: Format compact output for Brain B ────────────────────
    lines = [
        f"=== AEO CASE STUDIES ({days}d, {len(aeo_entries)} cases / {len(all_entries)} total) ==="
    ]

    for topic, ratio, aeo_count, total in topic_ratios:
        best_entry, _, best_score = topic_best_sample.get(topic, (None, 0, 0))
        best_verdict = best_entry.get("extra", {}).get("verdict", "?") if best_entry else "?"
        best_beneficiary = best_entry.get("extra", {}).get("beneficiary", "?") if best_entry else "?"

        lines.append(f"")
        lines.append(f"[TOPIC: {topic}] AEO_RATIO: {ratio:.1f}% ({aeo_count}/{total}) | Peak: {best_verdict} score={best_score:.3f}")
        lines.append(f"  Beneficiary: {str(best_beneficiary)[:150]}")
        if best_entry:
            lines.append(f"  Sample: {best_entry.get('narrative', best_entry.get('summary', 'N/A'))[:200]}")
            lines.append(f"  Timestamp: {best_entry.get('ts', '?')[:16]}")

    lines.append(f"")
    lines.append(f"=== END CASE STUDIES ===")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — GET RECENT SESSIONS (Raw Read)
# ══════════════════════════════════════════════════════════════════════════════

def _read_jsonl_entries(agent_id: str, max_days: int = 2, max_entries: int = 500) -> List[dict]:
    """
    Reads raw JSONL entries from the N most recent days. Newest first.

    Args:
        agent_id: "A03", "A11", "A12"
        max_days: Number of days to scan (default: 2 = today + yesterday)
        max_entries: Maximum entry limit
    """
    entries = []
    today = datetime.now(timezone.utc)

    for days_ago in range(max_days):
        dt = today - timedelta(days=days_ago)
        path = LOGS_BASE / agent_id.upper() / f"{dt.strftime('%Y-%m-%d')}.jsonl"
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                from collections import deque
                lines = list(deque(f, maxlen=max_entries))
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(entries) >= max_entries:
                    break
        except Exception as e:
            log.warning(f"[SESSION_LOG] Error reading {path}: {e}")
        if len(entries) >= max_entries:
            break

    return entries


def get_recent_sessions(agent_id: str, n: int = 10) -> list:
    """Reads the N most recent sessions (backward compat). Newest first."""
    return _read_jsonl_entries(agent_id, max_days=2, max_entries=n)[:n]


# ══════════════════════════════════════════════════════════════════════════════
# PART 4 — 3-TIER DRIFT CONTEXT (Sole API for Agents)
# ══════════════════════════════════════════════════════════════════════════════

def get_drift_context(agent_id: str, tier: str = "FULL") -> str:
    """
    Sole API for agents to retrieve session history context.
    Agents ONLY call this function — do not handle reading logic themselves.

    Args:
        agent_id: "A03", "A11", "A12"
        tier: "FULL" (3 combined tiers) | "HOT" (3h) | "WEEKLY" (7d) | "DEEP" (checkpoint)

    Returns:
        Text string ready to inject into LLM prompt, or "" if no data.
    """
    tier = tier.upper()
    if tier == "FULL":
        return _build_full_drift(agent_id)
    elif tier == "HOT":
        return _build_hot_drift(agent_id)
    elif tier == "WEEKLY":
        return _build_weekly_drift(agent_id)
    elif tier == "DEEP":
        return _build_deep_drift(agent_id)
    else:
        log.warning(f"[SESSION_LOG] Invalid tier: {tier}. Fallback to FULL.")
        return _build_full_drift(agent_id)




def _compute_algo_aggregates(entries: List[dict]) -> dict:
    """
    HINGE PROTOCOL — Channel ALGO_CORE (immutable, Python-only).
    Calculates static aggregates on algo_metrics and 16D tensor: avg/min/max/peak_abs/n.
    DO NOT use LLM for this function — this is computational truth.
    Ref: ~/.agents/skills/hinge_protocol.md
    """
    sums, counts, mins, maxs, peaks = {}, {}, {}, {}, {}
    for e in entries:
        metrics = e.get("algo_metrics", {})
        t = metrics.get("expert_metrics", (e.get("expert_metrics") or {}))
        
        # Support KAR, OFI if outside 16d but within algo_metrics
        for mk, mv in metrics.items():
            if mk != "16d" and isinstance(mv, (int, float)):
                t[mk] = mv
        for k, v in t.items():
            if v is None or str(v).lower() in ("unknown", "null") or v == -1:
                continue
            try:
                vf = float(v)
            except (ValueError, TypeError):
                continue
            sums[k] = sums.get(k, 0.0) + vf
            counts[k] = counts.get(k, 0) + 1
            mins[k] = min(mins[k], vf) if k in mins else vf
            maxs[k] = max(maxs[k], vf) if k in maxs else vf
            peaks[k] = max(peaks[k], abs(vf)) if k in peaks else abs(vf)
    return {
        k: {
            "avg": round(sums[k] / counts[k], 3),
            "min": round(mins[k], 3),
            "max": round(maxs[k], 3),
            "peak_abs": round(peaks[k], 3),
            "n": counts[k],
        }
        for k in sums
    }


def _format_tensor_str(e: dict, filter_outliers: bool = False) -> str:
    metrics = e.get("algo_metrics", {})
    t = metrics.get("expert_metrics", (e.get("expert_metrics") or {}))
    # Append algorithmic metrics outside 16d
    for mk, mv in metrics.items():
        if mk != "16d" and isinstance(mv, (int, float)):
            t[mk] = mv
    agent = e.get("agent", "")
    
    t_str = ""
    if t:
        items = []
        for k, v in t.items():
            if v is not None and str(v).lower() not in ("unknown", "null") and v != -1:
                try:
                    vf = float(v)
                    # WEEKLY drift filter outliers (abs > 2)
                    if filter_outliers and abs(vf) < 2.0: continue
                    items.append(f"{k}={vf:.2f}")
                except (ValueError, TypeError):
                    items.append(f"{k}={v}")
        if items:
            t_str = f" [16D: {' '.join(items)}]"
            
    # Expand dict data display into a deep analysis story for A10
    if agent == "A10":
        extra = e.get("extra", {})
        story = extra.get("a10_story", "")
        if story:
            # Remove excess whitespace to save tokens
            story = (story or "").replace('\n', ' | ')
            t_str += f"\n    ↳ 📖 [Undercurrent Flow]: {story[:1200]}"
            
    return t_str


def _build_hot_drift(agent_id: str) -> str:
    """TIER 1 — HOT: Last 3 hours. HINGE PROTOCOL Decoupled (narrative_lens + algo_core)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=3)
    entries = _read_jsonl_entries(agent_id, max_days=1, max_entries=50)

    hot = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e.get("ts", ""))
            if ts >= cutoff:
                hot.append(e)
        except (ValueError, TypeError):
            continue

    if not hot:
        return ""

    narrative_lines = []
    algo_lines = []
    for s in reversed(hot):  # Oldest first -> newest after
        ts_short = s.get("ts", "")[:16]
        # Support backward compatibility (narrative vs summary)
        narrative = s.get("narrative", s.get("summary", "N/A"))
        algo = s.get("algo_metrics", {})
        conf = algo.get("confidence", s.get("confidence", 0))
        sig = algo.get("signals_count", s.get("signals_count", 0))
        t_str = _format_tensor_str(s, filter_outliers=False)
        narrative_lines.append(f"  {ts_short} | {narrative}")
        algo_lines.append(f"  {ts_short} | sig:{sig} conf:{conf}{t_str}")

    aggregates = _compute_algo_aggregates(hot)

    parts = [
        f"[DRIFT HOT — {agent_id} — {len(hot)} sessions / 3 hours]",
        "",
        "[NARRATIVE_LENS — PERMITTED INTERPRETATION]",
        *narrative_lines,
        "",
        "[ALGO_CORE — IMMUTABLE, QUOTE ONLY]",
        *algo_lines,
        "",
        "[STATIC_ALGO_STATS — Python computed, NO RE-INFERENCE]",
        json.dumps(aggregates, ensure_ascii=False, indent=2) if aggregates else "  (no algo data)",
    ]
    return "\n".join(parts)


def _build_weekly_drift(agent_id: str) -> str:
    """TIER 2 — WEEKLY: 7 days, sampled 30m. HINGE PROTOCOL Decoupled."""
    entries = _read_jsonl_entries(agent_id, max_days=7, max_entries=2000)
    if not entries:
        return ""

    sampled = []
    last_ts = None
    for e in reversed(entries):  # Oldest first
        try:
            ts = datetime.fromisoformat(e.get("ts", ""))
        except (ValueError, TypeError):
            continue
        if last_ts is None or (ts - last_ts) >= timedelta(minutes=30):
            sampled.append(e)
            last_ts = ts

    if not sampled:
        return ""

    sampled = sampled[-60:]

    narrative_lines = []
    algo_lines = []
    for s in sampled:
        ts_short = s.get("ts", "")[:16]
        narrative = s.get("narrative", s.get("summary", "N/A"))
        algo = s.get("algo_metrics", {})
        conf = algo.get("confidence", s.get("confidence", 0))
        t_str = _format_tensor_str(s, filter_outliers=True)
        if t_str: t_str = t_str.replace("[16D:", "[⚠️ ALGO SPIKE:")
        narrative_lines.append(f"  {ts_short} | {narrative}")
        algo_lines.append(f"  {ts_short} | conf:{conf}{t_str}")

    aggregates = _compute_algo_aggregates(sampled)

    parts = [
        f"[DRIFT WEEKLY — {agent_id} — {len(sampled)} sessions / 7 days (sampled 30m)]",
        "",
        "[NARRATIVE_LENS]",
        *narrative_lines,
        "",
        "[ALGO_CORE — IMMUTABLE]",
        *algo_lines,
        "",
        "[STATIC_ALGO_STATS — Python computed]",
        json.dumps(aggregates, ensure_ascii=False, indent=2) if aggregates else "  (no algo data)",
    ]
    return "\n".join(parts)


def _build_deep_drift(agent_id: str) -> str:
    """TIER 3 — DEEP: Checkpoint NARRATIVE_LENS (LLM) + STATIC_ALGO_STATS (Python). HINGE PROTOCOL."""
    # Priority order of compressed knowledge files to avoid token context overflow
    knowledge_dir = BASE_DIR / "agentic" / "knowledge"
    candidates = [
        knowledge_dir / f"{agent_id.lower()}_chronicle_compressed.md",
        knowledge_dir / f"{agent_id.lower()}_longterm_flow_analysis.md",
        knowledge_dir / f"{agent_id.lower()}_chronicle_preview.md",
        knowledge_dir / f"{agent_id.lower()}_chronicle.md",
    ]
    
    content = ""
    chosen_file = None
    for path in candidates:
        if path.exists():
            try:
                file_size = path.stat().st_size
                with open(path, "r", encoding="utf-8") as f:
                    if file_size > 150_000 and path.name.endswith("_chronicle.md"):
                        # Only take the last 50k characters of large files to preserve tokens
                        f.seek(max(0, file_size - 50_000))
                        content = f.read()
                        if "\n" in content:
                            content = content.split("\n", 1)[1]
                        content = f"  (Last 50KB excerpt because the original file is too large {file_size/1024/1024:.1f}MB)\n" + content
                    else:
                        content = f.read()
                chosen_file = path
                break
            except Exception as e:
                log.warning(f"[SESSION_LOG] Error reading {path.name}: {e}")
                
    if chosen_file and content:
        return f"[DRIFT DEEP — {agent_id} — KNOWLEDGE CHRONICLE ({chosen_file.name})]\n{content}\n"

    # Fallback to old checkpoints
    checkpoints = _load_all_checkpoints(agent_id)
    if not checkpoints:
        return ""

    lines = [f"[DRIFT DEEP — {agent_id} — {len(checkpoints)} checkpoint(s)]"]
    for ckpt in checkpoints:
        ts = ckpt.get("created_at", "?")[:10]
        model_used = ckpt.get("model_used", "?")
        raw_count = ckpt.get("raw_entries_count", 0)
        summary = ckpt.get("summary", "N/A")
        static_stats = ckpt.get("static_algo_stats")  # Hinge: ALGO_CORE channel

        lines.append(f"  [{ts}] (model:{model_used}, entries:{raw_count})")
        lines.append("  [NARRATIVE_LENS]")
        lines.append(f"  {summary[:2000]}")
        if static_stats:
            lines.append("  [STATIC_ALGO_STATS — IMMUTABLE]")
            stats_str = json.dumps(static_stats, ensure_ascii=False, indent=2)
            lines.append("  " + stats_str.replace("\n", "\n  "))
        lines.append("")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# PART 4B — FULL DRIFT (3 combined tiers + Soul Anchor against narrative drift)
# ══════════════════════════════════════════════════════════════════════════════

# ── Imperial Soul Anchor: Against sophisticated narrative drift over time ─────
_DRIFT_SOUL_ANCHOR = """[🛡️ IMPERIAL MEMORY ANCHOR — AGAINST NARRATIVE DRIFT]

YOU ARE RECEIVING 3 TIERS OF TEMPORAL MEMORY. Read instructions carefully:

📊 HOW TO READ 3 TIERS:
• [TIER 1 — HOT (3 HOURS)]: IMMEDIATE fluctuations. Used to identify sudden sentiment shifts.
  → Core question: "In the last 3 hours, has there been any ABNORMAL change compared to the trend?"

• [TIER 2 — WEEKLY (7 DAYS)]: MEDIUM-TERM trend. Sampled every 30 minutes.
  → Core question: "Is this week's narrative gradually REVERSING? Who benefits?"

• [TIER 3 — DEEP (CHECKPOINT)]: LLM-summarized history, continuous sequence.
  → Core question: "What is the macro map? What phase of the Wyckoff Cycle is the Elite in?"

⚔️ ANTI-NARRATIVE DRIFT PRINCIPLES:
1. CROSS-COMPARISON: If Tier 1 (Hot) differs significantly from Tier 2/3, it is a DANGER SIGNAL.
   → Sudden change = Presence of manipulation or a real event.
   → MANDATORY distinction: Real events vs. Manufactured narrative.

2. SILENT PARADOX: If Tier 2/3 shows active behavior but Tier 1 goes suddenly silent
   → This is the #1 sign of Manufactured Calm (Elite is re-positioning).
   → NEVER treat silence as "stability". Silence = Hiding/Waiting.

3. SUBTLE ESCALATION: If the same narrative topic recurs repeatedly across Tier 2
   with increasing intensity -> This is an AEO campaign deploying slowly.
   → Identify the original source and determine CUI BONO (who benefits).

4. THINKING ANCHOR: No matter what the 3-tier data says, you MUST NOT conclude
   before asking yourself: "If all this information were fake — what would the TRAP SETTER want me
   to do? And I should do the OPPOSITE of that."
"""


def _build_full_drift(agent_id: str) -> str:
    """
    TIER FULL — Combined 3 tiers: HOT + WEEKLY + DEEP + Soul Anchor.
    This is the default mode for all Agents.
    """
    parts = [_DRIFT_SOUL_ANCHOR]

    # ── Tier 3: Deep (Macro overview — checkpoint) — Placed first for macro context ──
    deep = _build_deep_drift(agent_id)
    if deep:
        parts.append(deep)
    else:
        parts.append(f"[TIER 3 — DEEP — {agent_id}] No checkpoint yet. "
                      "System is accumulating data. Analysis based on Tier 1 & 2.")

    parts.append("")  # Separator

    # ── Tier 2: Weekly (7 days — medium-term trend) ──
    weekly = _build_weekly_drift(agent_id)
    if weekly:
        parts.append(weekly)
    else:
        parts.append(f"[TIER 2 — WEEKLY — {agent_id}] Insufficient 7-day data.")

    parts.append("")  # Separator

    # ── Tier 1: Hot (3 hours — immediate volatility) — Placed last for recency bias ──
    hot = _build_hot_drift(agent_id)
    if hot:
        parts.append(hot)
    else:
        parts.append(f"[TIER 1 — HOT — {agent_id}] No sessions in the last 3 hours. "
                      "⚠️ SILENT PARADOX: Why is this Agent inactive?")

    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# PART 5 — BACKWARD COMPATIBILITY (Deprecated aliases)
# ══════════════════════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════════════════════
# PART 6 — CHECKPOINT SUMMARIZATION PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def _get_checkpoint_dir(agent_id: str) -> Path:
    """Gets checkpoints directory for agent."""
    ckpt_dir = LOGS_BASE / agent_id.upper() / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    return ckpt_dir


def _load_all_checkpoints(agent_id: str) -> List[dict]:
    """Reads all checkpoint files, sorted by time (oldest first)."""
    ckpt_dir = _get_checkpoint_dir(agent_id)
    checkpoints = []
    for f in sorted(ckpt_dir.glob("checkpoint_*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                checkpoints.append(json.load(fp))
        except Exception as e:
            log.warning(f"[SESSION_LOG] Error reading checkpoint {f.name}: {e}")
    return checkpoints


def estimate_token_count(agent_id: str) -> int:
    """
    Estimates total raw JSONL tokens not yet summarized since last checkpoint.
    Rule: 1 token ≈ 4 chars (UTF-8 English heuristic).
    """
    checkpoints = _load_all_checkpoints(agent_id)
    last_ckpt_ts = None
    if checkpoints:
        last_raw = checkpoints[-1].get("created_at", "")
        try:
            last_ckpt_ts = datetime.fromisoformat(last_raw)
        except (ValueError, TypeError):
            pass

    # Scan all JSONL files
    agent_dir = LOGS_BASE / agent_id.upper()
    total_chars = 0
    for jsonl_file in sorted(agent_dir.glob("*.jsonl")):
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # If last checkpoint exists, only count entries after checkpoint
                    if last_ckpt_ts:
                        try:
                            entry = json.loads(line)
                            ts = datetime.fromisoformat(entry.get("ts", ""))
                            if ts <= last_ckpt_ts:
                                continue
                        except (json.JSONDecodeError, ValueError, TypeError):
                            continue
                    total_chars += len(line)
        except Exception:
            continue

    return total_chars // 4  # 4 chars ≈ 1 token


def _collect_raw_since_checkpoint(agent_id: str) -> List[dict]:
    """Collects all raw entries since last checkpoint."""
    checkpoints = _load_all_checkpoints(agent_id)
    last_ckpt_ts = None
    if checkpoints:
        try:
            last_ckpt_ts = datetime.fromisoformat(checkpoints[-1].get("created_at", ""))
        except (ValueError, TypeError):
            pass

    agent_dir = LOGS_BASE / agent_id.upper()
    entries = []
    for jsonl_file in sorted(agent_dir.glob("*.jsonl")):
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if last_ckpt_ts:
                        try:
                            ts = datetime.fromisoformat(entry.get("ts", ""))
                            if ts <= last_ckpt_ts:
                                continue
                        except (ValueError, TypeError):
                            continue
                    entries.append(entry)
        except Exception:
            continue
    return entries


# ── LLM Premium Chain ────────────────────────────────────────────────────────




def _call_premium_llm(prompt: str, agent_id: str) -> tuple:
    """
    Uses llm_router v18.1 (Sovereign Routing)
    """
    # Use passed agent_id or fallback 12:2 to borrow Cloud/Mini quota
    router_id = agent_id if agent_id else "12:2"
    log.info(f"[CHECKPOINT] {agent_id} -> Calling LLM Router (Sovereign) with ID {router_id}...")
    
    # Checkpoint Summarization consumes many tokens (large context)
    text = router_api_call(prompt, agent_id=router_id, est_tokens=2000)
    
    if text and "ERROR" not in text:
        log.info(f"[CHECKPOINT] ✅ Sovereign Router successful for {agent_id} ({len(text)} chars)")
        # Returns text and model "sovereign_router"
        return text, f"router:{router_id}"
        
    log.error(f"[CHECKPOINT] ❌ LLM Router failed for {agent_id}!")
    return "", "FAILED"


# ── Checkpoint Execution ─────────────────────────────────────────────────────

_CHECKPOINT_PROMPT_TEMPLATE = """You are the IMPERIAL HISTORIAN of Zero-Cutloss Empire.
Task: Summarize Agent {agent_id} history according to HINGE PROTOCOL (decoupled narrative ↔ algo).

⚠️ SUPREME PRINCIPLE (HingeEBM Decoupled):
- You are allowed to INTERPRET the [NARRATIVE_LENS] block (prose).
- You MUST NOT re-infer numbers in the [STATIC_ALGO_STATS] block — quote them verbatim.
- When writing about 16D tensor fluctuations: MANDATORY to quote numbers from [STATIC_ALGO_STATS], DO NOT calculate yourself.

=== PREVIOUS CHECKPOINTS (Continuous Sequence — CONTRADICTION FREE) ===
{previous_checkpoints}

=== [NARRATIVE_LENS] PROSE DATA ({raw_count} entries, from {ts_start} to {ts_end}) ===
{narrative_block}

=== [STATIC_ALGO_STATS] PYTHON PRE-COMPUTED NUMERICAL DATA — IMMUTABLE ===
{static_algo_stats}
↳ Quote only the above numbers. Do not calculate average/peak/deviation yourself.

=== SUMMARIZATION TASK ===
Write a CONCISE summary, focusing on:

1. **EMOTION/NARRATIVE SHIFT** (A03): What state did the crowd transition from? Notable FOMO/Panic?
2. **ELITE INTENT** (A11): Accumulation or distribution money flow? Cross-asset confirmation? Traps occurred?
3. **MANIPULATION CAMPAIGN** (A12): Manufactured Narrative? URL flagged? Who is the beneficiary?
4. **GENERAL TREND**: 1 paragraph summarizing the macro trend.
5. **LOCK WITH STATIC_ALGO_STATS**: When mentioning 16D tensor, MANDATORY to quote directly from [STATIC_ALGO_STATS] — e.g. "PEAK_GLS = -1.2 (according to STATIC_ALGO_STATS)". DO NOT round, DO NOT calculate.

Respond in English, cold and sharp tone. Do not use markdown headers. Maximum 3000 words."""


def run_checkpoint_summarization(agent_id: str, force: bool = False) -> dict:
    """
    Runs checkpoint summarization for agent.
    Trigger when raw tokens ≥ 900k OR force=True.

    Returns:
        dict with checkpoint info created, or {"skipped": True} if insufficient data.
    """
    TOKEN_THRESHOLD = 200_000

    # Check threshold
    if not force:
        token_count = estimate_token_count(agent_id)
        if token_count < TOKEN_THRESHOLD:
            return {
                "skipped": True,
                "reason": f"Tokens ({token_count:,}) < threshold ({TOKEN_THRESHOLD:,})",
                "agent_id": agent_id,
            }

    # Collect data
    raw_entries = _collect_raw_since_checkpoint(agent_id)
    if not raw_entries:
        return {"skipped": True, "reason": "No raw entries", "agent_id": agent_id}

    previous_checkpoints = _load_all_checkpoints(agent_id)

    # Build context for previous checkpoints
    prev_text = "No previous checkpoints."
    if previous_checkpoints:
        prev_parts = []
        for i, ckpt in enumerate(previous_checkpoints):
            prev_parts.append(
                f"[Checkpoint {i+1} — {ckpt.get('created_at', '?')[:10]} "
                f"— model:{ckpt.get('model_used', '?')}]\n"
                f"{ckpt.get('summary', 'N/A')[:3000]}"
            )
        prev_text = "\n\n".join(prev_parts)

    # HINGE PROTOCOL — Split 2 channels BEFORE feeding to LLM (decoupled)
    narrative_lines = []
    algo_pool = []  # For Python compute static stats — DO NOT let LLM touch
    total_chars = 0

    for entry in raw_entries:
        # Channel 1: NARRATIVE_LENS — LLM allowed to compress (Ignore algo_metrics)
        narrative_entry = {
            "ts": entry.get("ts"),
            "agent": entry.get("agent"),
            "narrative": entry.get("narrative", entry.get("summary")),
            "extra": entry.get("extra"),
        }
        line = json.dumps(narrative_entry, ensure_ascii=False)
        if total_chars + len(line) > 3_200_000:
            break
        narrative_lines.append(line)
        total_chars += len(line)

        # Channel 2: ALGO_CORE — Python only
        algo_pool.append(entry)

    # IMMUTABLE FACT — Python calculated, no LLM involved
    static_algo_stats = _compute_algo_aggregates(algo_pool)

    ts_start = raw_entries[0].get("ts", "?")[:16] if raw_entries else "?"
    ts_end = raw_entries[-1].get("ts", "?")[:16] if raw_entries else "?"

    prompt = _CHECKPOINT_PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        previous_checkpoints=prev_text,
        raw_count=len(narrative_lines),
        ts_start=ts_start,
        ts_end=ts_end,
        narrative_block="\n".join(narrative_lines),
        static_algo_stats=json.dumps(static_algo_stats, ensure_ascii=False, indent=2),
    )

    # Call Premium LLM Chain
    summary_text, model_used = _call_premium_llm(prompt, agent_id)

    if not summary_text:
        return {"error": "ALL_LLM_FAILED", "agent_id": agent_id}

    # Write checkpoint — WITH static_algo_stats (Hinge Protocol)
    ckpt_dir = _get_checkpoint_dir(agent_id)
    seq = int(time.time() * 1000)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    checkpoint = {
        "checkpoint_id": f"{agent_id}_{today}_{seq}",
        "agent_id": agent_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_used": model_used,
        "raw_entries_count": len(narrative_lines),
        "token_estimate": total_chars // 4,
        "ts_range": {"start": ts_start, "end": ts_end},
        "previous_checkpoints_count": len(previous_checkpoints),
        "summary": summary_text,                  # Channel: NARRATIVE_LENS (LLM)
        "static_algo_stats": static_algo_stats,   # Channel: ALGO_CORE (Python, IMMUTABLE)
        "hinge_protocol_version": "0.1",
    }

    ckpt_file = ckpt_dir / f"checkpoint_{today}_{seq}.json"
    with open(ckpt_file, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)

    log.info(
        f"[CHECKPOINT] ✅ {agent_id} checkpoint saved: {ckpt_file.name} "
        f"| model:{model_used} | entries:{len(narrative_lines)} | tokens:{total_chars//4:,} "
        f"| algo_keys:{len(static_algo_stats)}"
    )

    return checkpoint


# ══════════════════════════════════════════════════════════════════════════════
# PART 8 — VERDICT HARVESTER: Harvest real JSON Output from Snapshot
# Replace "compiled_insight" (virtual wiki) with actual Ground Truth.
# Scan snapshot logs A03/A04/A10/A11/A12, extract JSON from LLM RESPONSE.
# ══════════════════════════════════════════════════════════════════════════════

HARVEST_AGENTS = ["A03", "A04", "A10", "A11", "A12"]
VERDICT_DIR = LOGS_BASE / "verdicts"
MAX_VERDICTS = 6  # 6 groups = sufficient verdicts for 2 days


def _extract_json_from_snapshot(filepath: Path) -> Optional[dict]:
    """
    Parse snapshot .md file, extract ENTIRE "Verdict" content after thinking.
    Trigger: After </thinking> or starting from the first { character.
    """
    try:
        text = filepath.read_text(encoding="utf-8")
        marker = "## 2. LLM RESPONSE (OUTPUT)"
        idx = text.find(marker)
        if idx == -1:
            return None
        
        response_block = text[idx + len(marker):].strip()
        if not response_block:
            return None

        # 1. Find start point (Trigger)
        import re
        start_idx = 0
        
        # Try finding after closing thinking tag
        think_end = re.search(r'</think(?:ing)?>', response_block, re.IGNORECASE)
        if think_end:
            start_idx = think_end.end()
        else:
            # If no thinking, find the first {
            json_start = response_block.find("{")
            if json_start != -1:
                start_idx = json_start

        # 2. Get entire content from Trigger to end (remove markdown code block if present)
        verdict_content = response_block[start_idx:].strip()
        
        # Clean up markdown wrapper if present
        if verdict_content.endswith("```"):
            verdict_content = verdict_content[:-3].strip()
        if verdict_content.startswith("```"):
            lines = verdict_content.split("\n")
            if lines[0].startswith("```"):
                verdict_content = "\n".join(lines[1:]).strip()

        if not verdict_content:
            return None

        # 3. Attempt to parse JSON to get structured data
        parsed_data = {}
        json_match = re.search(r'(\{.*\})', verdict_content, re.DOTALL)
        if json_match:
            try:
                parsed_data = json.loads(json_match.group(1))
            except:
                pass

        # 4. Return full Anchor Point
        return {
            "full_content": verdict_content,
            "data": parsed_data
        }
    except Exception:
        return None


def harvest_verdicts(agent_id: str = None):
    """
    Scans latest snapshot for 1 or all 5 agents.
    Extracts JSON output, saves the 6 most recent groups to logs/verdicts/{AGENT}_verdicts.json.
    """
    VERDICT_DIR.mkdir(parents=True, exist_ok=True)
    agents = [agent_id] if agent_id else HARVEST_AGENTS

    results = {}
    for aid in agents:
        snap_dir = LOGS_BASE / "dpo_lab" / f"{aid}_NEW"
        if not snap_dir.exists():
            log.warning(f"[HARVEST] Directory does not exist: {snap_dir}")
            results[aid] = 0
            continue

        # Get snapshot files, sort by name (= sort by time due to naming convention)
        snap_files = sorted(snap_dir.glob("snapshot_*.md"), reverse=True)

        verdicts = []
        for sf in snap_files:
            if len(verdicts) >= MAX_VERDICTS:
                break
            parsed = _extract_json_from_snapshot(sf)
            if parsed:
                # Extract timestamp from filename: snapshot_2026-04-18_092202_1776504122
                fname = sf.stem
                parts = fname.split("_")
                ts = "unknown"
                if len(parts) >= 3:
                    try:
                        ts = f"{parts[1]}T{parts[2][:2]}:{parts[2][2:4]}:{parts[2][4:6]}Z"
                    except Exception:
                        pass
                verdicts.append({
                    "ts": ts,
                    "agent_id": aid,
                    "snapshot_file": sf.name,
                    "verdict": parsed
                })

        # Reverse: oldest first, newest last (chronological)
        verdicts.reverse()

        verdict_file = VERDICT_DIR / f"{aid}_verdicts.json"
        with open(verdict_file, "w", encoding="utf-8") as f:
            json.dump(verdicts, f, ensure_ascii=False, indent=2)

        results[aid] = len(verdicts)
        log.info(f"[HARVEST] ✅ {aid}: {len(verdicts)} verdicts saved -> {verdict_file.name}")

    return {"status": "OK", "agents": results}


def get_recent_verdicts(agent_id: str, n: int = 6) -> list:
    """
    API for Agents: Returns the N most recent JSON verdict blocks (Ground Truth).
    If file does not exist, automatically harvest first.
    """
    verdict_file = VERDICT_DIR / f"{agent_id}_verdicts.json"

    if not verdict_file.exists():
        harvest_verdicts(agent_id)

    if not verdict_file.exists():
        return []

    try:
        with open(verdict_file, "r", encoding="utf-8") as f:
            verdicts = json.load(f)
        return verdicts[-n:]  # N most recent groups
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# PART 9 — CLI INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Session Memory Manager v18.1 + Verdict Harvester")
    parser.add_argument("--agent", type=str, default="A03", help="Agent ID (A03/A04/A10/A11/A12)")
    parser.add_argument("--tier", type=str, default="HOT", help="Drift tier: HOT/WEEKLY/DEEP")
    parser.add_argument("--tokens", action="store_true", help="Count unsummarized tokens")
    parser.add_argument("--checkpoint", action="store_true", help="Run checkpoint summarization")
    parser.add_argument("--force", action="store_true", help="Force run checkpoint even if below 200k")
    parser.add_argument("--all-agents", action="store_true", help="Run checkpoint for all A03/A11/A12")
    parser.add_argument("--harvest", action="store_true", help="Harvest verdicts from snapshots for 5 agents")
    parser.add_argument("--harvest-agent", type=str, default=None, help="Harvest for specific agent (default: all)")
    args = parser.parse_args()

    if args.harvest:
        result = harvest_verdicts(args.harvest_agent)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.tokens:
        for aid in (["A03", "A11", "A12"] if args.all_agents else [args.agent]):
            count = estimate_token_count(aid)
            status = "🟢 SUFFICIENT" if count >= 200_000 else "⏳ Insufficient"
            print(f"{aid}: {count:>10,} tokens | {status} (threshold: 200,000)")

    elif args.checkpoint:
        agents = ["A03", "A11", "A12"] if args.all_agents else [args.agent]
        for aid in agents:
            print(f"\n{'='*60}")
            print(f"Checkpoint Summarization: {aid}")
            print(f"{'='*60}")
            result = run_checkpoint_summarization(aid, force=args.force)
            print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        text = get_drift_context(args.agent, args.tier)
        if text:
            print(text)
        else:
            print(f"(No drift data for {args.agent} tier={args.tier})")
