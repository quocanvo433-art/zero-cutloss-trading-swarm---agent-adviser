# ------------------------------------------------------------------------------
# ZCL INFRASTRUCTURE DNA v16.1 | UNIT: THREAT_CLASSIFIER | ROLE: TACTICAL_ANALYST
# ------------------------------------------------------------------------------
# DESC: Agent 09 module for classifying attack tactics (TC-1 to TC-6).
# CALLS: redis, telegram_butler (alerts).
# INTEGRITY: Behavioral-analysis, Pattern-recognition, Tactical-classification.
# ------------------------------------------------------------------------------


"""
🧬 DNA: v16.1
🏢 UNIT: THREAT_CLASSIFIER
🛠️ ROLE: SECURITY_THREAT_ANALYZER
📖 DESC: Classifies cybersecurity threats using AI, assisting Agent 09 in executing defensive actions (Block IP, Quarantine).
🔗 CALLS: tools/llm_router.py
📟 I/O: Redis: zcl:threats:latest
🛡️ INTEGRITY: Organic Ecosystem - Immutable
"""
import os
import sys
import json
import time
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict

try:
    from tools.imperial_state import matrix
except ImportError:
    from imperial_state import matrix
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../config/.env'))

_gemini_keys = [os.environ[k].strip() for k in sorted(os.environ.keys()) if k.startswith("GEMINI_API_KEY") and os.environ[k].strip()]
if not _gemini_keys and os.getenv("GEMINI_API_KEY", "").strip():
    _gemini_keys.append(os.getenv("GEMINI_API_KEY").strip())
GEMINI_API_KEY_2 = _gemini_keys[0] if _gemini_keys else ""
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "")
REDIS_URL         = os.getenv("REDIS_URL", "redis://zcl_redis:6379")

BASE_DIR     = Path(__file__).parent.parent
SECURITY_DIR = BASE_DIR / "security"
REPORTS_DIR  = SECURITY_DIR / "threat_reports"
OPUS_QUEUE   = SECURITY_DIR / "opus_queue"
LOGS_DIR     = BASE_DIR / "logs"
THREAT_DB    = SECURITY_DIR / "threat_db.json"

for d in [SECURITY_DIR, REPORTS_DIR, OPUS_QUEUE, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("09_THREAT_CLASSIFIER")

# matrix is imported globally

import requests as req_lib


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class ThreatEvent:
    """An attack event detected and classified"""
    timestamp_unix:   int
    tactical_class:   str       # TC-1 to TC-6
    class_name:       str       # RECONNAISSANCE, LOGIC_PROBE, ...
    confidence:       float     # 0.0 - 1.0
    attack_stage:     str       # PROBE / ACTIVE / PERSISTENT / UNKNOWN
    severity:         str       # INFO / WARN / CRITICAL
    source:           str       # which agent, which channel, which URL
    evidence:         dict      # concrete evidence
    pattern_hash:     str       # hash for dedup + track recurring
    first_seen:       str
    occurrence_count: int = 1
    is_new_pattern:   bool = True


# ==============================================================================
# TC-1: RECONNAISSANCE — System structure probing
# ==============================================================================

# What the attacker searches for during reconnaissance
RECON_STRUCTURAL_PATTERNS = [
    # Probing for file/directory structure
    r"what\s+files?\s+(are|is|do\s+you\s+have)",
    r"list\s+(your\s+)?(files?|directory|tools?|functions?|capabilities)",
    r"show\s+(me\s+)?(your\s+)?(config|configuration|structure|schema|agents?)",
    r"what\s+(agents?|tools?|modules?)\s+(do\s+you\s+have|are\s+available|exist)",
    # Probing for API keys and credentials
    r"what\s+(api\s*key|secret|token|password|credential)",
    r"(print|show|display|reveal|output)\s+(your\s+)?(api\s*key|secret|token|config)",
    # Probing system prompt / soul files
    r"(what|show|print)\s+(is\s+)?(your\s+)?(system\s+prompt|instruction|soul|persona)",
    r"(ignore|forget)\s+.*\s+(output|print|show)\s+(system|config|prompt)",
    # Probing English/Target-specific names — QUERY-TYPE REQUIREMENTS
    r"(?:what|where|who|how|show|explain|list|tell)\b.{0,60}\b(soul|agent|structure|wyckoff|zero.?cutloss)\b",
    r"(?:what|where|who|how|show|explain|list|tell)\b.{0,60}\b(agent\s*0[1-9]|blood_vein|phantom|god_eye|scholar)\b",
    r"(?:what|where|who|how|show|explain|list|tell)\b.{0,60}\b(binance_hound|macro_phantom|social_crawler|dpo_evaluator)\b",
]

# Behavioral indicators (detected via Redis patterns)
RECON_BEHAVIORAL = {
    "rapid_sequential_queries": 5,   # >5 different queries in 60s = probing
    "systematic_field_probing": 3,   # querying same field with different inputs
}


def _scrub_json_keys(text: str) -> str:
    """Delete internal JSON keys/labels to avoid false positives, but keep VALUE to always scan for injection."""
    keys_to_scrub = [
        r'\"wyckoff_phase\"\s*:', r'\"analysis_4_timeframes\"\s*:', r'\"cryptocurrency\"\s*:',
        r'\"current_price\"\s*:', r'\"long_short_ratio\"\s*:', r'\"sentiment_score\"\s*:',
        r'\"poison_type\"\s*:', r'\"metadata\"\s*:', r'\"timestamp_unix\"\s*:',
        r'\"volume\"\s*:', r'\"orderbook\"\s*:', r'\"volatility\"\s*:',
        r'\"exchange\"\s*:', r'\"total_buy_force\"\s*:', r'\"total_sell_force\"\s*:',
        r'\"current_oi\"\s*:', r'\"long_short_ratio\"\s*:', r'\"warning\"\s*:',
        r'\"funding_rate\"\s*:', r'\"ticker\"\s*:'
    ]
    scrubbed = text
    for k in keys_to_scrub:
        scrubbed = re.sub(k, '"" :', scrubbed, flags=re.IGNORECASE)
    # Clear literal enum labels:
    scrubbed = re.sub(r'\"(?:CHOSEN|REJECTED|PHASE_[A-E]|phantom|blood_vein|god_eye)\"', '""', scrubbed, flags=re.IGNORECASE)
    return scrubbed

def detect_tc1_reconnaissance(text: str, source: str,
                              recent_queries: list = None) -> Optional[ThreatEvent]:
    """
    Detect TC-1: Attacker mapping out system STRUCTURE.
    Indicators: querying files, tools, config, soul, specific agent names.
    """
    # ── JSON IMMUNITY: Remove internal keys to avoid false positives, but DO NOT bypass scanning ──
    text = _scrub_json_keys(text)

    matches = []
    compiled = [re.compile(p, re.IGNORECASE) for p in RECON_STRUCTURAL_PATTERNS]

    for i, pat in enumerate(compiled):
        m = pat.search(text)
        if m:
            matches.append({
                "idx":     i,
                "pattern": RECON_STRUCTURAL_PATTERNS[i][:60],
                "match":   m.group()[:80],
                "pos":     m.start()
            })

    if not matches:
        return None

    # Evaluate confidence
    confidence = min(0.95, 0.4 + len(matches) * 0.2)

    # Detect target-specific patterns (knowing agent names = studied the system)
    target_specific = [m for m in matches if m.get("idx", 0) >= 8]  # RECON patterns 8+ are target-specific
    if target_specific:
        confidence = min(0.99, confidence + 0.3)

    # Attack stage
    stage = "PROBE"
    if target_specific:
        stage = "ACTIVE"  # Had prior information = attacking actively

    ev = ThreatEvent(
        timestamp_unix = int(time.time()),
        tactical_class = "TC-1",
        class_name     = "RECONNAISSANCE",
        confidence     = round(confidence, 2),
        attack_stage   = stage,
        severity       = "CRITICAL" if target_specific else "WARN",
        source         = source,
        evidence       = {
            "matches":         matches[:5],
            "target_specific": bool(target_specific),
            "text_preview":    text[:200],
            "explanation":     _explain_recon(matches, target_specific),
        },
        pattern_hash   = hashlib.md5("|".join(m["pattern"] for m in matches).encode()).hexdigest()[:12],
        first_seen     = datetime.utcnow().isoformat(),
    )
    return ev


def _explain_recon(matches, target_specific):
    if target_specific:
        return ("The attacker knows the SPECIFIC NAMES of agents/tools — proving prior system research. "
                "They might have read the public repo or previously leaked information. "
                "This is ACTIVE RECONNAISSANCE, not random probing.")
    return ("The attacker is querying the system structure — this is the first step "
            "in a targeted attack chain. Goal: map out the attack surface.")


# ==============================================================================
# TC-2: LOGIC_PROBE — Probing logic/entry conditions
# ==============================================================================

LOGIC_PROBE_PATTERNS = [
    # Probing Zero-Cutloss conditions
    r"(when|what|which)\s+(condition|phase|signal|trigger)\s+(do\s+you|will\s+you|you)\s+(enter|trade|recommend|buy|sell)",
    r"(how\s+much|what\s+percentage|what\s+drawdown|what\s+profit)\s+.*\s+(stop|cut|exit|close)",
    r"(wyckoff|phase\s+[a-e]|spring|upthrust|utad)\s+(when|if|condition|signal)",
    # Probing specific thresholds
    r"(threshold|limit|minimum|maximum|cutoff)\s+(for|of|when)\s+(entry|exit|stop|target)",
    # Specific threshold — ONLY match when in a natural context (with trading keywords around)
    r"(?:drawdown|stop.?loss|cut.?loss|trailing|risk|rule|target|exit|entry|profit)\s*(?:of|at|is|=|:)?\s*(2%|3%|5%|7\s+day)",  # Known specific threshold
    r"(2%|3%|5%)\s+(?:drawdown|stop|cut|risk|rule|trailing|target)",  # Reverse: "5% drawdown"
    r"(chosen|rejected)\s+(criteria|condition|when|if)",
    # Probing DPO logic
    r"(dpo|training\s+data|fine.?tun)\s+(condition|when|how|what)",
    r"(what\s+makes|what\s+qualifies|why\s+is)\s+(something\s+)?(chosen|rejected)",
    # Check behavior with edge cases
    r"(what\s+happens|how\s+do\s+you\s+behave|what\s+do\s+you\s+do)\s+(when|if)\s+(market|price|volume)",
    r"(phase\s+[ab]|phase_[ab]|sideway)\s+(do\s+you|will\s+you|can\s+you)\s+(still|ever)",
]


def detect_tc2_logic_probe(text: str, source: str,
                            conversation_history: list = None) -> Optional[ThreatEvent]:
    """
    Detect TC-2: Attacker mapping out entry LOGIC CONDITIONS.
    Goal: identify Phase C, drawdown threshold -> forge conditions.
    Danger: if they know the 2% threshold, 7 days, Phase C - they can create
    forged "Springs" satisfying the exact conditions within 3 days -> DPO poisoning.
    """
    # ── JSON IMMUNITY: Remove internal keys to avoid false positives, but DO NOT bypass scanning ──
    text = _scrub_json_keys(text)

    matches = []
    compiled = [re.compile(p, re.IGNORECASE) for p in LOGIC_PROBE_PATTERNS]

    for i, pat in enumerate(compiled):
        m = pat.search(text)
        if m:
            matches.append({
                "pattern": LOGIC_PROBE_PATTERNS[i][:60],
                "match":   m.group()[:80],
                "type":    "threshold_specific" if i in [4, 5] else "condition_probe",
            })

    # Check conversation pattern: consecutive questions on the same topic
    sequential_probe = False
    if conversation_history:
        logic_questions = sum(1 for h in conversation_history[-5:]
                              if any(re.search(p, h.get("text",""), re.IGNORECASE)
                                     for p in LOGIC_PROBE_PATTERNS[:5]))
        if logic_questions >= 3:
            sequential_probe = True
            matches.append({
                "pattern": "sequential_questioning",
                "match":   f"{logic_questions} consecutive logic questions",
                "type":    "behavioral",
            })

    if not matches:
        return None

    threshold_specific = any(m["type"] == "threshold_specific" for m in matches)
    confidence = min(0.95, 0.35 + len(matches) * 0.15 + (0.25 if threshold_specific else 0))

    ev = ThreatEvent(
        timestamp_unix = int(time.time()),
        tactical_class = "TC-2",
        class_name     = "LOGIC_PROBE",
        confidence     = round(confidence, 2),
        attack_stage   = "ACTIVE" if threshold_specific else "PROBE",
        severity       = "CRITICAL" if threshold_specific else "WARN",
        source         = source,
        evidence       = {
            "matches":           matches[:5],
            "threshold_specific": threshold_specific,
            "sequential_probe":   sequential_probe,
            "text_preview":       text[:200],
            "risk":               _explain_logic_probe(threshold_specific, sequential_probe),
        },
        pattern_hash   = hashlib.md5(text[:100].encode()).hexdigest()[:12],
        first_seen     = datetime.utcnow().isoformat(),
    )
    return ev


def _explain_logic_probe(threshold_specific, sequential):
    parts = []
    if threshold_specific:
        parts.append("The attacker knows specific thresholds (2% drawdown, 7 days) — this information "
                     "is not in the public documentation. This proves they read MASTER_RULES.md "
                     "or have access to soul files. Risk: creating forged DPO pairs satisfying the exact thresholds.")
    if sequential:
        parts.append("Pattern of sequential logic questions — systematic prober behavior, "
                     "not a normal user.")
    if not parts:
        return "Probing entry conditions — monitor if it continues."
    return " | ".join(parts)


# ==============================================================================
# TC-3: FUZZING — Generic vulnerability scanning
# ==============================================================================

FUZZ_INDICATORS = [
    # Payload patterns of automated tools
    r"[\"'\\]{4,}",                          # Multiple consecutive quotes (ignore ` so as not to block code block)
    r"(null|undefined|NaN|Infinity){2,}",     # JS fuzzing payloads
    r"(AAAA{10,}|BBBB{10,}|ZZZZ{10,})",      # Buffer overflow attempt
    r"(\x00|\x41\x41\x41|\xff\xfe)",          # Binary payloads
    r"<script.*?>|javascript:|vbscript:",      # XSS attempts
    r"(\.\./){3,}|%2e%2e%2f",                # Path traversal
    r"(SELECT|INSERT|DROP|UPDATE|DELETE)\s+.*\s+(FROM|INTO|TABLE)", # SQLi
    r"(\$\{.*\}|#{.*}|%\{.*\})",             # Template injection
    r"(system|exec|popen|subprocess)\s*\(",   # Command injection
    r"(__import__|getattr|setattr|delattr|eval|exec)\s*\(", # Python injection
    r"(\$\()",                       # Shell injection chars (ignore | ; ` since Markdown uses them heavily)
]

# Statistical fuzzing: many different short requests in a short duration
FUZZ_STATS_THRESHOLD = {
    "min_requests":      10,  # At least 10 requests in window
    "time_window_sec":  60,   # Within 60 seconds
    "unique_ratio":      0.8, # >80% unique = not a normal user
}


def detect_tc3_fuzzing(text: str, source: str,
                       request_history: list = None) -> Optional[ThreatEvent]:
    """
    Detect TC-3: Automated vulnerability scanning.
    Characteristics: special payloads (quotes, nullbytes), rapid/multiple requests.
    Unlike TC-1/TC-2 (manual, targeted) — TC-3 is usually an automated scanner.
    """
    matches = []
    compiled = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in FUZZ_INDICATORS]

    for i, pat in enumerate(compiled):
        m = pat.search(text)
        if m:
            matches.append({
                "pattern": FUZZ_INDICATORS[i][:50],
                "match":   repr(m.group()[:40]),
                "type":    "payload",
            })

    # Statistical: check request history
    stat_fuzzing = False
    if request_history:
        recent = [r for r in request_history
                  if time.time() - r.get("ts", 0) < FUZZ_STATS_THRESHOLD["time_window_sec"]]
        if len(recent) >= FUZZ_STATS_THRESHOLD["min_requests"]:
            unique_texts = len(set(r.get("text_hash","") for r in recent))
            ratio = unique_texts / len(recent)
            if ratio >= FUZZ_STATS_THRESHOLD["unique_ratio"]:
                stat_fuzzing = True
                matches.append({
                    "pattern": "statistical_fuzzing",
                    "match":   f"{len(recent)} requests in 60s, {ratio:.0%} unique",
                    "type":    "behavioral",
                })

    if not matches:
        return None

    confidence = min(0.95, 0.5 + len(matches) * 0.1 + (0.2 if stat_fuzzing else 0))

    ev = ThreatEvent(
        timestamp_unix = int(time.time()),
        tactical_class = "TC-3",
        class_name     = "FUZZING",
        confidence     = round(confidence, 2),
        attack_stage   = "ACTIVE",
        severity       = "CRITICAL" if stat_fuzzing or len(matches) >= 3 else "WARN",
        source         = source,
        evidence       = {
            "payload_matches": matches,
            "stat_fuzzing":    stat_fuzzing,
            "text_preview":    repr(text[:100]),
            "likely_tool":     _guess_fuzz_tool(matches),
            "risk": ("Automated fuzzer scanning the system — looking for input validation bypass, "
                     "injection points, or error messages revealing stack trace."),
        },
        pattern_hash   = hashlib.md5(text[:80].encode()).hexdigest()[:12],
        first_seen     = datetime.utcnow().isoformat(),
    )
    return ev


def _guess_fuzz_tool(matches):
    """Guess tool type based on payload pattern"""
    types = [m["type"] for m in matches]
    patterns = " ".join(m["match"] for m in matches)
    if "XSS" in patterns or "script" in patterns.lower():
        return "XSS Scanner (Burp Suite / OWASP ZAP)"
    if "SELECT" in patterns or "DROP" in patterns:
        return "SQL Injection Scanner (sqlmap)"
    if "../" in patterns:
        return "Path Traversal Scanner"
    if "behavioral" in types:
        return "Custom AI Agent Fuzzer"
    return "Generic Fuzzer / Security Scanner"


# ==============================================================================
# TC-5: PROMPT_INJECT — Sophisticated targeted prompt injection
# ==============================================================================

# TC-5 differs from simple injection detection in:
# detecting INTENT and SOPHISTICATION of the attacker

SOPHISTICATED_INJECT_PATTERNS = [
    # Exploit specific ZCL vocabulary
    r"(zero.?cutloss|spring|wyckoff|phase\s+c|composite\s+man)\s*.*\s*(ignore|override|change)",
    # Multi-step jailbreak
    r"(step\s+1|first|begin\s+by)\s*.{0,50}\s*(step\s+2|then|next)\s*.{0,50}\s*(output|print|show)",
    # Token smuggling (Unicode lookalikes)
    r"[Ⅰ-Ⅻ]|[①-⑩]|[ΑΒΓΔΕΖΗ]",  # Roman numeral lookalikes, Greek letters as Latin
    # Indirect injection via role play
    r"(imagine|pretend|roleplay|act\s+as)\s+(you\s+are\s+)?(an?\s+)?(ai|agent|assistant|bot)\s+(that|who)",
    # Nested prompt injection
    r"(the\s+following|text\s+below|content\s+here)\s+(contains?|is)\s+(instruction|prompt|command)",
    # Localized jailbreak attempts
    r"(please\s+pretend|imagine|roleplay)\s+(you\s+are|as\s+a|a)\s+(ai|system|bot)",
    r"(ignore|forget|skip)\s+(instruction|rule|command)\s+(prior|previous|above)",
    # Output format hijacking
    r"(output|respond|answer)\s+(only|just|exclusively)\s+(?:in\s+)?(?:json|yaml|xml|csv)\s+(format\s+)?with\s+(the\s+)?following",
]

CONTEXT_AWARE_INJECT = [
    # Injection knowing system context
    r"(queen|owner|ha_ngung_thuong|scholar|assassin).{0,80}(ignore|override|output|print)",
    r"(redis|chromadb|ollama|qwen|binance).{0,80}(override|bypass|disable|ignore)",
    r"(dpo|chosen|rejected|pairs|vaccine).{0,80}(add|inject|write|output)",
]


def detect_tc5_prompt_inject(text: str, source: str,
                              context_aware: bool = False) -> Optional[ThreatEvent]:
    """
    Detect TC-5: Sophisticated targeted prompt injection.
    Context-aware injection (knowing internal names, Redis channels) = CRITICAL.
    """
    advanced_matches = []
    ca_matches     = []

    for i, pat in enumerate(SOPHISTICATED_INJECT_PATTERNS):
        try:
            m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if m:
                advanced_matches.append({
                    "pattern": SOPHISTICATED_INJECT_PATTERNS[i][:60],
                    "match":   m.group()[:80],
                    "type":    "sophisticated",
                })
        except Exception:
            pass

    for pat in CONTEXT_AWARE_INJECT:
        try:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                ca_matches.append({
                    "pattern": pat[:60],
                    "match":   m.group()[:80],
                    "type":    "context_aware",
                })
        except Exception:
            pass

    all_matches = advanced_matches + ca_matches
    if not all_matches:
        return None

    is_ca = bool(ca_matches)
    is_localized = any("please" in m["match"].lower() or "ignore" in m["match"].lower()
                       for m in all_matches)

    confidence = min(0.98, 0.45 + len(all_matches) * 0.15 + (0.3 if is_ca else 0))
    severity   = "CRITICAL" if is_ca else "WARN"

    ev = ThreatEvent(
        timestamp_unix = int(time.time()),
        tactical_class = "TC-5",
        class_name     = "PROMPT_INJECTION",
        confidence     = round(confidence, 2),
        attack_stage   = "ACTIVE",
        severity       = severity,
        source         = source,
        evidence       = {
            "matches":          all_matches[:5],
            "context_aware":    is_ca,
            "localized_jb":     is_localized,
            "sophistication":   "HIGH" if is_ca else "MEDIUM",
            "text_preview":     text[:200],
            "risk": _explain_inject(is_ca, is_localized, all_matches),
        },
        pattern_hash   = hashlib.md5(text[:100].encode()).hexdigest()[:12],
        first_seen     = datetime.utcnow().isoformat(),
    )
    return ev


def _explain_inject(is_ca, is_localized, matches):
    if is_ca:
        return ("CRITICAL: Injection knowing internal names (agents, Redis channels, soul files). "
                "Attacker has system information — targeted attack, not random. "
                "Immediately audit where information leaked.")
    if is_localized:
        return ("Localized jailbreak attempt — attacker knows system language preferences.")
    return f"Sophisticated injection attempt with {len(matches)} patterns — evidence of a targeted attack."


# ==============================================================================
# TECHNICAL REPORT GENERATOR
# ==============================================================================

def generate_technical_report(events: list[ThreatEvent]) -> str:
    """
    Create technical report for Opus review.
    Standard format for Opus to analyze and generate countermeasures.
    """
    if not events:
        return ""

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    severity_counts = Counter(e.severity for e in events)
    class_counts    = Counter(e.class_name for e in events)
    critical_events = [e for e in events if e.severity == "CRITICAL"]

    report = f"""# TECHNICAL THREAT REPORT — Zero-Cutloss Empire
Generated: {ts}
Agent: 09 — Immune Nervous System (Threat Classifier Module)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total events | {len(events)} |
| Critical | {severity_counts.get("CRITICAL", 0)} |
| Warning | {severity_counts.get("WARN", 0)} |
| Attack classes | {", ".join(f"{k}×{v}" for k, v in class_counts.items())} |
| Highest confidence | {max(e.confidence for e in events):.0%} |

**Status:** {"🔴 DANGER — Opus audit immediately" if severity_counts.get("CRITICAL", 0) > 0 else "🟡 WARNING — Monitor"}

---

"""

    # Detailed view of each event
    for i, ev in enumerate(sorted(events, key=lambda x: x.confidence, reverse=True), 1):
        report += f"""## Event {i}: {ev.class_name} ({ev.tactical_class})

| Field | Value |
|-------|-------|
| Severity | {ev.severity} |
| Confidence | {ev.confidence:.0%} |
| Attack Stage | {ev.attack_stage} |
| Source | `{ev.source}` |
| Pattern Hash | `{ev.pattern_hash}` |
| Timestamp | {datetime.utcfromtimestamp(ev.timestamp_unix).isoformat()} UTC |

### Evidence
```json
{json.dumps(ev.evidence, ensure_ascii=False, indent=2)}
```

### Tactical Analysis

{_tactical_analysis(ev)}

---

"""

    # Countermeasure recommendations
    report += "## Countermeasure Recommendations\n\n"
    for cls, evs in Counter(e.class_name for e in events).items():
        report += f"### {cls}\n"
        report += _countermeasure_for_class(cls, [e for e in events if e.class_name == cls])
        report += "\n\n"

    # Opus action items
    report += """## Action Items for Opus (Antigravity Session)

Paste this report into Opus session with context:
> "Analyze threat report from Agent 09. Create synthetic DPO pairs for confirmed attack patterns.
> Propose specific patches for each file."

### Priority patches needed:
"""
    for ev in critical_events[:3]:
        report += f"- `{ev.class_name}` ({ev.tactical_class}): {_patch_recommendation(ev)}\n"

    return report


def _tactical_analysis(ev: ThreatEvent) -> str:
    analyses = {
        "RECONNAISSANCE": (
            "The attacker is **mapping the attack surface**. This is usually the first step in a "
            "multi-stage attack. If not blocked, the next step is typically TC-2 (logic probe) "
            "or TC-5 (targeted injection). Check: where was this information leaked?"
        ),
        "LOGIC_PROBE": (
            "The attacker is studying specific **entry conditions**. Highest risk: "
            "if they know Phase C + 2% drawdown + 7-day sideway, they can create forged 'Springs' "
            "satisfying the exact conditions -> targeted DPO poisoning. Increase entropy in "
            "entry conditions (add volume confirmation, tick-data absorption)."
        ),
        "FUZZING": (
            "Automated scanner **looking for input validation vulnerabilities**. Typically targets: "
            "JSON parse errors, type confusion, buffer handling. Less dangerous than TC-1/TC-2 "
            "if input sanitization is already good, but could leak error messages containing sensitive information."
        ),
        "POISONING_WIDE": (
            "**Organized information warfare campaign**. Classic pattern: MM uses media "
            "to create panic/FOMO while taking the opposite action. System is most vulnerable "
            "through A03 (sentiment). Solution: require on-chain confirmation before trusting "
            "any narrative from A03."
        ),
        "PROMPT_INJECTION": (
            "**Targeted injection** — more sophisticated than automated attempts. "
            "Context-aware injection = attacker knows the system. Risk: override output "
            "of A03/A04 to create false Spring signal. Need output validation layer "
            "before any agent uses the result."
        ),
        "MODEL_DRIFT_ACTIVE": (
            "**'Winning bait'** — the most dangerous and hardest pattern to detect. "
            "Multiple small wins create false confidence -> model lowers threshold -> huge loss. "
            "Need to temporarily pause blind prediction loop and request Opus audit of the 50 most recent pairs."
        ),
    }
    return analyses.get(ev.class_name, f"Analysis for {ev.class_name} — manual review required.")


def _countermeasure_for_class(cls: str, events: list) -> str:
    measures = {
        "RECONNAISSANCE": (
            "1. Do not log error messages containing file paths\n"
            "2. Rotate tool names if leaked (binance_hound -> a01_claw.py)\n"
            "3. Check if .gitignore blocked agents/ and config/\n"
            "4. Audit access logs — find strange IPs/patterns"
        ),
        "LOGIC_PROBE": (
            "1. Increase entropy: add volume absorption requirement to Phase C check\n"
            "2. Do not log specific conditions in public logs\n"
            "3. Add jitter to response times (prevent timing oracle)\n"
            "4. Obfuscate threshold values in soul files"
        ),
        "FUZZING": (
            "1. Strengthen input validation — reject malformed JSON early\n"
            "2. Do not expose stack trace in error responses\n"
            "3. Stricter rate limiting for endpoints\n"
            "4. Deploy honeypot fields to detect scanners"
        ),
        "POISONING_WIDE": (
            "1. Increase min_confluence to 4/4 layers when A03 reports campaign\n"
            "2. Reduce A03 weight to 50% when MM fingerprint score > 70\n"
            "3. Require on-chain confirmation (A02) before using A03 signal\n"
            "4. Add time-decay: signals older than 6h decay in weight by 50%"
        ),
        "PROMPT_INJECTION": (
            "1. All external text -> <data>...</data> XML tags before sending to LLM\n"
            "2. Output validation: verify agent_id + JSON schema after each LLM call\n"
            "3. Add INJECTION_PATTERNS from this event to INJECTION_PATTERNS list\n"
            "4. Consider rate limiting queries from specific sources"
        ),
        "MODEL_DRIFT_ACTIVE": (
            "1. TEMPORARILY PAUSE blind_prediction_loop immediately\n"
            "2. Quarantine the 20 most recent CHOSEN pairs — do not train\n"
            "3. Request Opus to audit all pairs over the last 7 days\n"
            "4. Raise DPO quality threshold higher and reset win streak counter"
        ),
    }
    return measures.get(cls, "Opus review required to propose countermeasures.")


def _patch_recommendation(ev: ThreatEvent) -> str:
    recs = {
        "RECONNAISSANCE": "Add field obfuscation to soul files, rotate tool names",
        "LOGIC_PROBE":    "Add volume absorption requirement to Phase C detection",
        "FUZZING":        "Strengthen input validation, hide error stack traces",
        "POISONING_WIDE": "Patch A03 weight reduction when fingerprint > 70",
        "PROMPT_INJECTION": f"Add pattern `{list(ev.evidence.get('matches', [{}]))[:1]}` to INJECTION_PATTERNS",
        "MODEL_DRIFT_ACTIVE": "Pause blind loop, audit pairs over the last 7 days",
    }
    return recs.get(ev.class_name, "Manual review required")


# ==============================================================================
# MAIN CLASSIFIER — Entry point for immunity_core.py
# ==============================================================================

def classify_threat_from_text(
    text: str,
    source: str,
    context: dict = None,
) -> list[ThreatEvent]:
    """
    Main entry point: classify 1 text across all TC-1 to TC-5.
    Returns list of events (usually empty or 1-2 items).
    """
    context = context or {}
    events  = []

    for detector, args in [
        (detect_tc1_reconnaissance, {"text": text, "source": source,
                                      "recent_queries": context.get("recent_queries")}),
        (detect_tc2_logic_probe,    {"text": text, "source": source,
                                      "conversation_history": context.get("conversation_history")}),
        (detect_tc3_fuzzing,        {"text": text, "source": source,
                                      "request_history": context.get("request_history")}),
        (detect_tc5_prompt_inject,  {"text": text, "source": source}),
    ]:
        try:
            ev = detector(**args)
            if ev:
                events.append(ev)
        except Exception as e:
            log.warning(f"Detector {detector.__name__} error: {e}")

    return events


def classify_and_report(
    text: str,
    source: str,
    context: dict = None,
    push_to_redis: bool = True,
    save_report: bool = True,
) -> dict:
    """
    Classify + generate report + publish.
    Used for real-time scanning in daemon mode.
    """
    events = classify_threat_from_text(text, source, context)
    if not events:
        return {"status": "CLEAN", "events": []}

    # Generate technical report
    report_md = generate_technical_report(events)

    # Save report if there is a CRITICAL event
    critical = [e for e in events if e.severity == "CRITICAL"]
    if critical and save_report:
        ts_str   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        cls_str  = critical[0].class_name
        rpath    = REPORTS_DIR / f"THREAT_{ts_str}_{cls_str}.md"
        rpath.write_text(report_md, encoding="utf-8")
        log.warning(f"Threat report saved: {rpath}")

        # Push to Opus queue if CRITICAL
        opath = OPUS_QUEUE / f"{ts_str}_threat.md"
        opath.write_text(report_md, encoding="utf-8")

    # Push to Matrix
    if push_to_redis:
        try:
            payload = {
                "timestamp":     int(time.time()),
                "event_count":   len(events),
                "critical_count": len(critical),
                "events":        [asdict(e) for e in events],
                "has_report":    bool(critical),
            }
            matrix.set("GUARDIAN", "threat_report", payload, ttl=3600)
            if critical:
                matrix.publish("alerts:urgent", {
                    "source":        "09_THREAT_CLASSIFIER",
                    "attack_class":  critical[0].class_name,
                    "tactical_code": critical[0].tactical_class,
                    "confidence":    critical[0].confidence,
                    "stage":         critical[0].attack_stage,
                    "action":        "Check security/threat_reports/ — Opus review required",
                })
        except Exception as e:
            log.error(f"Redis push error: {e}")

    # Brief Telegram alert
    if critical and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        _send_telegram(critical[0])

    return {
        "status":   "THREATS_DETECTED",
        "events":   [asdict(e) for e in events],
        "critical": len(critical),
        "report":   report_md[:500] + "..." if len(report_md) > 500 else report_md,
    }


def _send_telegram(ev: ThreatEvent):
    """Send a brief alert via A06 Telegram Gateway (Redis Queue)"""
    try:
        STAGE_EMOJI = {"PROBE": "🔍", "ACTIVE": "⚠️", "PERSISTENT": "🚨", "UNKNOWN": "❓"}
        msg = (
            f"{STAGE_EMOJI.get(ev.attack_stage, '⚠️')} *THREAT DETECTED*\n"
            f"Class: `{ev.tactical_class} — {ev.class_name}`\n"
            f"Confidence: {ev.confidence:.0%} | Stage: {ev.attack_stage}\n"
            f"Source: `{ev.source[:60]}`\n"
            f"Hash: `{ev.pattern_hash}` | {datetime.utcfromtimestamp(ev.timestamp_unix).strftime('%H:%M UTC')}\n\n"
            f"→ See `security/threat_reports/` for details\n"
            f"→ `security/opus_queue/` to paste into Antigravity"
        )
        
        tele_payload = {
            "type": "A09_THREAT_ALERT",
            "report_text": msg,
            "signature": "A09",
            "ts": int(time.time()),
        }
        
        matrix.xadd("SYSTEM", "telegram:queue", {"payload": json.dumps(tele_payload, ensure_ascii=False)}, maxlen=1000)
        log.info(f"Pushed Threat Alert ({ev.tactical_class}) to A06 Stream (At-Least-Once)")
        
    except Exception as e:
        log.error(f"Telegram queue push error: {e}")


# ==============================================================================
def hook_into_immunity_core():
    """
    Subscribe to Redis channels of all agents and scan realtime.
    Called from immunity_core.py in daemon mode.
    """
    channels = [
        "tracker:raw",
        "macro:raw",
        "sentiment:raw",
        "brain:raw",
        "judge:raw",
        "errors",
    ]

    pubsub = matrix.subscribe(channels)
    if not pubsub:
        log.error("Matrix subscribe error — threat classifier offline")
        return
    log.info(f"Threat Classifier is listening to Matrix channels: {channels}")

    for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
            if isinstance(data, dict):
                # Scan all string fields
                for key, val in data.items():
                    if isinstance(val, str) and len(val) > 10:
                        classify_and_report(
                            text=val,
                            source=f"redis:{message['channel']}:{key}",
                            push_to_redis=True,
                            save_report=True,
                        )
            elif isinstance(data, str) and len(data) > 10:
                classify_and_report(
                    text=data,
                    source=f"redis:{message['channel']}:raw_str",
                    push_to_redis=True,
                    save_report=True,
                )
        except json.JSONDecodeError:
            # Raw string — scan directly
            classify_and_report(
                text=str(message["data"])[:1000],
                source=f"redis:{message['channel']}",
            )
        except Exception as e:
            log.error(f"Hook error: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Threat Classifier — Agent 09 Module")
    parser.add_argument("--scan",   type=str, help="Scan 1 text string")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode subscribing to Redis")
    args = parser.parse_args()

    if args.scan:
        result = classify_and_report(args.scan, source="cli_test")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.daemon:
        hook_into_immunity_core()
    else:
        parser.print_help()
