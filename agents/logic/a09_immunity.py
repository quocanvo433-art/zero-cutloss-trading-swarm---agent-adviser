"""
🧬 DNA: v16.6 (Sovereign Purity & Bio-Defense)
🏢 UNIT: IMMUNITY_CORE (A09)
🛠️ ROLE: BIO_VACCINATOR
📖 DESC: The Empire's immune system. Monitors file integrity (FIM), verifies signatures (HMAC), and performs threat classification.
🔗 CALLS: tools/threat_classifier.py, tools/imperial_state.py
📟 I/O: logs/immunity.jsonl, dpo_lab/a09_threats/, zcl:immunity:status
🛡️ INTEGRITY: FIM-Enforcement, HMAC-Trust, Self-Immunity, Quarantine.
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))


import os, json, time, re, hmac, hashlib, logging, argparse, threading
import requests, feedparser
from datetime import datetime, timezone, timedelta
from typing import Optional
from dotenv import load_dotenv
import nlm_changelog
from dos_guardian import run_monitoring_daemon, record_redis_message
sys.path.insert(0, str(BASE_DIR))
from scripts.vault_manager import (
    KeyMaster, VaultClient, watch_vault_updates,
    get_vault_state, publish_vault_state_to_matrix
)
from imperial_state import matrix, setup_agent_logger

# ── Threat Classifier sub-module (TC-1 → TC-6) ────────────────────────────────
try:
    from threat_classifier import (
        ThreatEvent,
        detect_tc1_reconnaissance,
        detect_tc2_logic_probe,
        detect_tc3_fuzzing,
        detect_tc5_prompt_inject,
        generate_technical_report,
    )
    _TC_AVAILABLE = True
except ImportError:
    _TC_AVAILABLE = False
    log_tmp = logging.getLogger("09_IMMUNITY_CORE")
    log_tmp.warning("[A09] threat_classifier.py not found — TC-1→TC-5 disabled")

load_dotenv(dotenv_path=BASE_DIR / "config" / ".env")

# Automatically load keys from 1 to N
_gemini_keys = [os.environ[k].strip() for k in sorted(os.environ.keys()) if k.startswith("GEMINI_API_KEY") and os.environ[k].strip()]
if not _gemini_keys and os.getenv("GEMINI_API_KEY", "").strip():
    _gemini_keys.append(os.getenv("GEMINI_API_KEY").strip())
GEMINI_API_KEY_2  = _gemini_keys[0] if _gemini_keys else ""
IMMUNITY_SECRET   = os.getenv("IMMUNITY_HMAC_SECRET", "").strip()
if not IMMUNITY_SECRET:
    IMMUNITY_SECRET = "zcl_fallback_immunity_secret_do_not_use_in_prod"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "")
REDIS_URL         = os.getenv("REDIS_URL", "redis://zcl_redis:6379")

SECURITY_DIR     = BASE_DIR / "security"
LOGS_DIR         = BASE_DIR / "logs"
A09_THREATS_DIR  = BASE_DIR / "dpo_lab" / "a09_threats"
IMMUNITY_LOG     = A09_THREATS_DIR / "immunity.jsonl"
THREAT_DB        = SECURITY_DIR / "threat_db.json"
IMMUNITY_REPORT  = BASE_DIR / "IMMUNITY_REPORT.md"
VACCINE_INBOX    = BASE_DIR / "security" / "threat_pairs" / "vaccine_pairs.jsonl"
CONTEXT_FILE     = BASE_DIR / "CONTEXT.md"
from llm_router import router_api_call
FIM_MANIFEST     = SECURITY_DIR / "file_integrity_manifest.json"
FIM_SIG_FILE     = SECURITY_DIR / "file_integrity_manifest.json.sig"

# Files requiring integrity monitoring — unexpected modifications = attack
FIM_TARGETS = [
    "agents/logic/a01_hound.py",
    "agents/logic/a02_phantom.py",
    "agents/logic/a03_social_crawler.py",
    "agents/logic/a04_brain.py",
    "agents/logic/a05_evaluator.py",
    "agents/logic/a06_butler.py",
    "agents/logic/a07_elite_apex.py",
    "agents/logic/a09_immunity.py",
    "tools/dos_guardian.py",
    "tools/narrative_guard.py",
    "tools/telegram_auth.py",
    "tools/emf_signal_collector.py",
    "tools/emf_intent_analyzer.py",
    "tools/threat_classifier.py",
    "tools/aeo_detective.py",           # A12 — AEO Detective (Stage 25)
    "tools/divergence_engine.py",
    "agents/logic/a10_signal_collector.py",
    "agents/logic/a11_intent_analyzer.py",
    "agents/logic/a12_detective.py",    # A12 — Detective
    "scripts/vault_manager.py",
    "scripts/security_hardening.py",
    "scripts/authorize_manual_data.py",
    "config/orchestrator.yaml",
    "docker-compose.yml",
    "Dockerfile.commander",
    "requirements.txt",
]

FIM_GRACE_PERIOD_SEC  = 600          # 10-minute wait for authorization before auto-restore
FIM_AUTH_INBOX        = BASE_DIR / "inbox" / "fim_authorize"
FIM_PENDING_FILE      = SECURITY_DIR / "fim_pending.json"  # Track pending violations
FIM_AUTH_INBOX.mkdir(parents=True, exist_ok=True)

_keymaster: KeyMaster = None
_vault_client: VaultClient = VaultClient()

for d in [SECURITY_DIR, LOGS_DIR, A09_THREATS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

log = setup_agent_logger("A09", "09_IMMUNITY_CORE")

REQUEST_TIMEOUT = 10
QUARANTINE_MAX_CHARS = 500   # Max 500 chars per document in quarantine

# ── Smart Algo — Attack Chronicle + LLM Verdict Gate ──────────────────────────
try:
    from agent_session_logger import log_agent_snapshot
    _SNAPSHOT_AVAILABLE = True
except ImportError:
    _SNAPSHOT_AVAILABLE = False

_CHRONICLE_KEY = "attack_chronicle"   # Redis KV: A09:attack_chronicle
_CHRONICLE_MAX_ENTRIES = 50           # Keep max 50 entries (rolling window)
_CHRONICLE_TTL = 48 * 3600           # 48h TTL
_SMART_ALGO_COOLDOWN = 300           # 5-minute cooldown between LLM calls
_last_smart_algo_call = 0


def _chronicle_append(entry: dict) -> list:
    """Append 1 attack event to chronicle, 48h rolling window."""
    chronicle = matrix.get("A09", _CHRONICLE_KEY) or []
    if not isinstance(chronicle, list):
        chronicle = []

    # Add new entry (lean — only keep necessary fields)
    chronicle.append({
        "ts": int(time.time()),
        "vector": entry.get("attack_vector", "UNKNOWN"),
        "target": entry.get("target_stream", ""),
        "source": entry.get("source_agent", ""),
        "confidence": entry.get("confidence", 0),
        "tc_class": entry.get("attack_pattern_category", ""),
    })

    # Rolling: discard entries older than 48h + keep max 50
    cutoff = int(time.time()) - _CHRONICLE_TTL
    chronicle = [e for e in chronicle if e.get("ts", 0) > cutoff][-_CHRONICLE_MAX_ENTRIES:]

    matrix.set("A09", _CHRONICLE_KEY, chronicle, ttl=_CHRONICLE_TTL)
    return chronicle


def _chronicle_get_summary() -> dict:
    """Returns a lean summary of the chronicle for the LLM context."""
    chronicle = matrix.get("A09", _CHRONICLE_KEY) or []
    if not chronicle:
        return {"total": 0, "summary": "No attacks recorded in the last 48h."}

    vectors = {}
    targets = {}
    for e in chronicle:
        v = e.get("vector", "UNKNOWN")
        t = e.get("target", "")
        vectors[v] = vectors.get(v, 0) + 1
        targets[t] = targets.get(t, 0) + 1

    timestamps = sorted(e.get("ts", 0) for e in chronicle)
    intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)] if len(timestamps) > 1 else []
    avg_interval = sum(intervals) / len(intervals) if intervals else 0

    timing = "UNKNOWN"
    if avg_interval and 800 < avg_interval < 1000:
        timing = "PERIODIC_15MIN"
    elif avg_interval and avg_interval < 300:
        timing = "BURST_ATTACK"
    elif intervals and all(abs(i - avg_interval) < avg_interval * 0.3 for i in intervals):
        timing = "AUTOMATED_PERIODIC"
    else:
        timing = "IRREGULAR"

    mid = int(time.time()) - 12 * 3600
    first_half = [e for e in chronicle if e.get("ts", 0) < mid]
    second_half = [e for e in chronicle if e.get("ts", 0) >= mid]
    trend = "ESCALATING" if len(second_half) > len(first_half) * 1.5 else (
            "DECLINING" if len(second_half) < len(first_half) * 0.5 else "STABLE")

    return {
        "total": len(chronicle),
        "vectors": vectors,
        "targets": targets,
        "timing_pattern": timing,
        "avg_interval_sec": round(avg_interval),
        "intensity_trend": trend,
        "first_attack": datetime.fromtimestamp(timestamps[0], tz=timezone.utc).isoformat() if timestamps else None,
        "latest_attack": datetime.fromtimestamp(timestamps[-1], tz=timezone.utc).isoformat() if timestamps else None,
        "window_hours": round((timestamps[-1] - timestamps[0]) / 3600, 1) if len(timestamps) > 1 else 0,
    }


def _smart_algo_llm_verdict(current_attack: dict, chronicle_summary: dict,
                             elite_intent_raw_sample: str = "") -> dict | None:
    """
    TIER 2: Call LLM to infer Elite intent from the attack pattern.
    ONLY call when Tier 1 determines inference is needed (cumulative threshold >= 3 or CRITICAL).
    LLM returns standard JSON with a "report_to_a11" field deciding whether to send to A11.
    """
    _SMART_ALGO_SOUL = """[A09 SMART ALGO — REVERSE ELITE ANALYSIS]
YOU ARE THE REVERSE ANALYSIS BRAIN OF THE IMMUNE SHIELD.
Task: Read attack patterns on the trading system -> infer the ACTUAL intent of the Elite.

CORE PHILOSOPHY:
- Prompt injection/fuzzing on the monitoring system = Elite is INTENTIONALLY concealing behavior
- Attack on the EMF pipeline = concealing large accumulation or distribution
- Attack on the t0_stream = manipulating trading decisions, imminent volatility
- Attack intensity ESCALATING = major event imminent
- Periodic timing = automated operation, well-organized

JUDGMENT PRINCIPLES:
1. ONLY report to A11 when there is a GENUINELY USEFUL insight for analyzing Elite intent
2. DO NOT report if it is just noise/false positive or a single attack without a pattern
3. Inference must be based on EVIDENCE (chronicle + timing + target correlation)
4. If data is insufficient -> DO NOT fabricate -> report_to_a11: false

FORMAT: PURE JSON. No markdown. No extra text."""

    prompt = f"""{_SMART_ALGO_SOUL}

=== LATEST ATTACK ===
Vector: {current_attack.get('attack_vector', 'UNKNOWN')}
Target: {current_attack.get('target_stream', 'N/A')}
Source Agent: {current_attack.get('source_agent', 'N/A')}
Confidence: {current_attack.get('confidence', 0):.0%}
TC Class: {current_attack.get('attack_pattern_category', 'N/A')}

=== 48H CHRONICLE ===
Total attacks: {chronicle_summary.get('total', 0)}
Vectors: {json.dumps(chronicle_summary.get('vectors', {}), ensure_ascii=False)}
Targets: {json.dumps(chronicle_summary.get('targets', {}), ensure_ascii=False)}
Timing: {chronicle_summary.get('timing_pattern', 'UNKNOWN')} (avg interval: {chronicle_summary.get('avg_interval_sec', 0)}s)
Intensity trend: {chronicle_summary.get('intensity_trend', 'UNKNOWN')}
Window: {chronicle_summary.get('window_hours', 0)}h

=== CURRENT MACRO DATA (elite_intent_raw sample) ===
{elite_intent_raw_sample[:500] if elite_intent_raw_sample else 'None'}

=== COMMAND ===
Analyze the above evidence. Return JSON:
{{"report_to_a11": true|false, "reason": "why report/not report to A11", "elite_intent_inference": "Elite intent inference", "attack_narrative": "brief description of the attack and implications", "implied_market_action": "ACCUMULATION|DISTRIBUTION|MANIPULATION|DISTRACTION|INSUFFICIENT_DATA", "urgency": "LOW|MEDIUM|HIGH|CRITICAL"}}"""

    resp = router_api_call(
        agent_id="A09",
        prompt=prompt,
        est_tokens=400,
        brain_mode="A09_SMART_ALGO"
    )

    # Save snapshot
    if _SNAPSHOT_AVAILABLE and resp:
        try:
            log_agent_snapshot("A09", prompt, resp, metadata={
                "mode": "SMART_ALGO_T2",
                "attack_vector": current_attack.get("attack_vector", "UNKNOWN"),
                "chronicle_total": chronicle_summary.get("total", 0),
                "intensity_trend": chronicle_summary.get("intensity_trend", "UNKNOWN"),
            })
        except Exception as snap_err:
            log.debug(f"[SMART ALGO] Snapshot log error: {snap_err}")

    if not resp or "ERROR" in resp:
        log.warning("[SMART ALGO] LLM unavailable — rule-based only")
        return None

    try:
        clean = re.sub(r"```json|```", "", resp).strip()
        if "<thinking>" in clean:
            clean = re.sub(r"<thinking>.*?</thinking>", "", clean, flags=re.DOTALL).strip()
        start_idx = clean.find("{")
        end_idx = clean.rfind("}") + 1
        if start_idx >= 0 and end_idx > start_idx:
            return json.loads(clean[start_idx:end_idx])
    except (json.JSONDecodeError, Exception) as e:
        log.debug(f"[SMART ALGO] Parse error: {e}")

    return None


def _build_elite_intel_hinge_packet(current_attack: dict, chronicle_summary: dict,
                                      llm_verdict: dict) -> dict:
    """Build HingeEBM packet for stream zcl:a09:elite_attack_intel."""
    return {
        "algo_core": {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": "security_intel",
            "attack_vector": current_attack.get("attack_vector", "UNKNOWN"),
            "target_stream": current_attack.get("target_stream", ""),
            "source_agent": current_attack.get("source_agent", ""),
            "confidence": current_attack.get("confidence", 0),
            "attack_pattern_category": current_attack.get("attack_pattern_category", ""),
            "attack_intensity": current_attack.get("attack_intensity", "LOW"),
            "timing_pattern": chronicle_summary.get("timing_pattern", "UNKNOWN"),
            "cumulative_attacks_48h": chronicle_summary.get("total", 0),
            "intensity_trend": chronicle_summary.get("intensity_trend", "STABLE"),
            "implied_market_action": llm_verdict.get("implied_market_action", "INSUFFICIENT_DATA"),
            "urgency": llm_verdict.get("urgency", "LOW"),
        },
        "narrative_lens": {
            "summary": (
                f"A09 INTEL | {current_attack.get('attack_vector','?')}:"
                f"{chronicle_summary.get('intensity_trend','?')} | "
                f"{llm_verdict.get('implied_market_action','?')} | "
                f"{chronicle_summary.get('total',0)} attacks/{chronicle_summary.get('window_hours',0)}h"
            )[:200],
            "elite_intent_inference": llm_verdict.get("elite_intent_inference", ""),
            "attack_narrative": llm_verdict.get("attack_narrative", ""),
        }
    }


# ── Domain whitelist for Hunter ────────────────────────────────────────────────
TRUSTED_DOMAINS = {
    "arxiv.org", "owasp.org", "github.com", "huggingface.co",
    "blog.google", "anthropic.com", "openai.com", "deepmind.com",
    "nist.gov", "cve.mitre.org", "nvd.nist.gov",
    "feeds.feedburner.com", "security.googleblog.com",
    "portswigger.net", "snyk.io",
}

# ── Attack pattern signatures (rule-based — no LLM needed) ────────────────────
# CRITICAL_PATTERNS: Code execution & prompt structure attacks -> KILL entire text
CRITICAL_PATTERNS = [
    r"<\|?(?:im_start|im_end|system|user|assistant|human)\|?>",
    r"\[INST\]|\[\/INST\]|\\<s\\>|\\<\/s\\>",
    r"</?(system|assistant|human|tool)>",
    r"OVERRIDE_ZCL|ZCL_INJECT|BACKDOOR",
    r"eval\s*\(|exec\s*\(|__import__\s*\(",
    r"subprocess\.(?:run|call|Popen|check_output)",
    r"os\.(?:system|popen|remove|unlink|rmdir)",
    r"open\s*\([^)]*['\"]w['\"]",
]
COMPILED_CRITICAL = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in CRITICAL_PATTERNS]

# SOFT_PATTERNS: Text-based injection -> REDACT matching segment, keep rest
SOFT_PATTERNS = [
    r"ignore\s+(previous|all|above|prior)\s+(instructions?|prompts?|context)",
    r"new\s+(instruction|task|system\s+prompt)",
    r"you\s+are\s+now\s+a?\s*(different|new|other)",
    r"act\s+as\s+(if\s+you\s+are\s+)?(?!a\s+(?:helpful|trading|analysis|market|investor|fund))",
    r"override\s+(output|response|behavior|rules)(?!\s+(?:by|from|of)\s+(?:SEC|CFTC|Fed|regulation|policy|law))",
    r"print\s+(your\s+)?(api\s*key|system\s+prompt|secret|password)",
]
COMPILED_SOFT = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in SOFT_PATTERNS]

# Legacy backward compat: union of all patterns
INJECTION_PATTERNS = CRITICAL_PATTERNS + SOFT_PATTERNS
COMPILED_PATTERNS = COMPILED_CRITICAL + COMPILED_SOFT

# ── Hidden char signatures ─────────────────────────────────────────────────────
HIDDEN_BYTES = [
    b"\xe2\x80\x8b", b"\xef\xbb\xbf", b"\xe2\x80\x8c",
    b"\xc2\xad",     b"\xe2\x80\x8d", b"\xe2\x81\xa0",
]

# ── Threat intelligence RSS feeds ─────────────────────────────────────────────
THREAT_INTEL_FEEDS = {
    "arxiv_cs_cr":   "https://arxiv.org/rss/cs.CR",
    "owasp_blog":    "https://owasp.org/feed.xml",
    "portswigger":   "https://portswigger.net/research/rss",
    "huggingface":   "https://huggingface.co/blog/feed.xml",
    "snyk":          "https://snyk.io/blog/feed/",
    "openai_safety": "https://openai.com/blog/rss.xml",
}
# Keywords to filter articles related to AI/Agent/LLM security
RELEVANT_KEYWORDS = [
    "prompt injection", "jailbreak", "adversarial", "llm attack",
    "agent security", "rag poisoning", "training data poisoning",
    "model poisoning", "ai safety", "red teaming", "ai agent",
    "supply chain attack", "model extraction", "embedding inversion",
    "instruction following", "alignment faking",
]


# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _hmac_sign(data: str, secret: str = IMMUNITY_SECRET) -> str:
    return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()

def _hmac_verify(data: str, signature: str, secret: str = IMMUNITY_SECRET) -> bool:
    expected = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def _tele_alert(msg: str):
    """Sends alert to A06 Telegram Gateway instead of direct API call (At-Least-Once via Stream)"""
    if not matrix:
        return
    try:
        tele_payload = json.dumps({
            "type": "A09_ALERT",
            "report_text": msg,
            "signature": "A09",
            "ts": int(time.time()),
        }, ensure_ascii=False)
        msg_id = matrix.xadd("SYSTEM", "telegram:queue", {"payload": tele_payload}, maxlen=1000)
        if not msg_id:
            raise Exception("Matrix xadd returned None")
        log.info(f"Transferred Immunity Alert to A06 Stream: {msg[:60]} (ID: {msg_id})")
    except Exception as e:
        log.error(f"Error pushing alert to A06 Stream: {e}. Logging locally.")
        with open("logs/a09_telegram_fallback.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.time()}] {msg}\n")

def _log_event(event_type: str, severity: str, details: dict):
    entry = {
        "ts":         int(time.time()),
        "event_type": event_type,
        "severity":   severity,
        **details,
    }
    with open(IMMUNITY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if severity in ("DANGER", "CRITICAL"):
        matrix.publish("ALERTS:urgent", {
            "agent_id": "09_IMMUNITY_CORE",
            "alert": f"IMMUNITY {severity}: {event_type}",
            **{k: v for k, v in details.items() if isinstance(v, (str, int, float, bool, type(None)))},
        })
        _tele_alert(f"IMMUNITY {severity}\n{event_type}\n{json.dumps(details,ensure_ascii=False)[:300]}")


def sanitize_text_for_llm(text: str, max_len: int = 500) -> str:
    """
    [A09 ULTIMATE FILTER — v2.0 REDACT MODE]
    Sanitize external text before embedding in prompt.
    - CRITICAL patterns (code exec, prompt structure): KILL entire text.
    - SOFT patterns (text injection): REDACT matching segment, keep rest -> preserve data.
    Emergency Channel integration with A12 if malicious code is detected.
    """
    if not text:
        return ""

    # 1. Truncate max length to avoid RAM/Token Limit issues
    text = str(text)[:max_len]

    # 2. Delete hidden/zero-width characters
    hidden_chars = ["\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad"]
    for ch in hidden_chars:
        text = text.replace(ch, "")

    # 3. Delete HTML tags and comments
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]{1,100}>", " ", text)

    # 4A. CRITICAL PATTERNS — Code exec / Prompt structure → KILL entire text + Alert A12
    for pat in COMPILED_CRITICAL:
        if pat.search(text):
            p_str = str(pat.pattern)
            log.warning(f"[CRITICAL INJECT] KILL entire text. Pattern: '{p_str[:60]}'. Alerting A12!")
            _alert_a12_injection(text, p_str, severity="CRITICAL")
            return "[CONTENT FILTERED — CRITICAL INJECTION DETECTED BY A09]"

    # 4B. SOFT PATTERNS — Text injection → REDACT matching segment, keep rest
    redacted = False
    for pat in COMPILED_SOFT:
        if pat.search(text):
            p_str = str(pat.pattern)
            log.warning(f"[SOFT INJECT] REDACT matching segment. Pattern: '{p_str[:60]}'. Alerting A12!")
            text = pat.sub("[REDACTED]", text)
            redacted = True

    if redacted:
        _alert_a12_injection(text, "SOFT_PATTERN_REDACTED", severity="WARNING")

    # 5. Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _alert_a12_injection(text: str, pattern_str: str, severity: str = "WARNING"):
    """Trigger Emergency Channel to A12 when injection is detected."""
    payload = {
        "action": "A12_REALTIME_REQUEST",
        "requester": "A09_GUARDIAN",
        "severity": severity,
        "topic": f"[AEO Injection Sign — {severity}] {text[:300]}"
    }
    try:
        matrix.publish("COMMANDER:events", json.dumps(payload))
    except Exception as e:
        log.error(f"[A09] Error alerting A12: {e}")


def _load_threat_db() -> dict:
    if THREAT_DB.exists():
        try:
            with open(THREAT_DB) as f:
                return json.load(f)
        except Exception:
            pass
    return {"patterns": [], "last_update": 0, "total_threats": 0, "vaccine_count": 0}

def _save_threat_db(db: dict):
    db["last_update"] = int(time.time())
    with open(THREAT_DB, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 1 — DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

def scan_string(text: str, source: str = "unknown", tactical_scan: bool = True) -> dict:
    """
    Scan 1 string — return scan results.
    Uses rule-based first (fast, no API cost).
    """
    if not isinstance(text, str) or not text.strip():
        return {"status": "CLEAN", "source": source}

    findings = []
    for i, pat in enumerate(COMPILED_PATTERNS):
        m = pat.search(text)
        if m:
            findings.append({
                "pattern_idx": i,
                "pattern":     INJECTION_PATTERNS[i][:60],
                "match":       m.group()[:80],
                "position":    m.start(),
            })

    if findings:
        # Detect RCE execution attempts
        rce_attempt = any(
            any(k in str(f.get("match", "")).lower() for k in ["subprocess", "os.system", "eval", "exec", "__import__"])
            or f.get("pattern_idx") in [4, 5, 6, 7]  # Indexes of RCE patterns
            for f in findings
        )
        
        severity = "CRITICAL" if rce_attempt else ("DANGER" if len(findings) >= 2 else "WARNING")
        
        _log_event("INJECTION_DETECTED", severity,
                   {"source": source, "findings": findings[:3],
                    "text_preview": text[:100]})
                    
        # Critical command: All Code Execution attempts trigger LOCKDOWN via Dos Guardian
        if rce_attempt:
            log.critical(f"[DEFENSE COMMAND] Code Execution detected. A09 activating LOCKDOWN via dos_guardian!")
            try:
                from dos_guardian import set_system_mode
                set_system_mode("LOCKDOWN", f"Zero Empire Code Execution is Forbidden! Detected attempt (RCE) from {source}")
                for _ in range(3):
                    _tele_alert(f"🚨🚨 DEFENSE COMMAND: Zero Empire Code Execution is Forbidden! Detected attempt (RCE) from {source}")
                    time.sleep(0.5)
            except Exception as e:
                log.error(f"Error activating dos_guardian lockdown: {e}")
                
        result = {"status": "POISONED", "severity": severity,
                  "findings": findings, "source": source}
    else:
        result = None

    # ── TC-1 → TC-5: Tactical Classification (threat_classifier sub-module) ──────
    if tactical_scan:
        tc_events = _run_tactical_classifier(text, source)
        if tc_events:
            # Escalate most severe event to scan result
            worst = max(tc_events, key=lambda e: e.confidence)
            if result is None:
                result = {"status": "POISONED", "severity": worst.severity,
                          "findings": [{"tactical_class": worst.tactical_class,
                                        "class_name": worst.class_name,
                                        "confidence": worst.confidence}],
                          "source": source}
    if result:
        return result

    return {"status": "CLEAN", "source": source}


def _run_tactical_classifier(text: str, source: str) -> list:
    """Call TC-1 → TC-5 from threat_classifier sub-module. Publish ThreatEvents to Redis."""
    if not _TC_AVAILABLE:
        return []
    events = []
    try:
        for detector in [
            lambda: detect_tc1_reconnaissance(text, source),
            lambda: detect_tc2_logic_probe(text, source),
            lambda: detect_tc3_fuzzing(text, source),
            lambda: detect_tc5_prompt_inject(text, source),
        ]:
            ev = detector()
            if ev:
                events.append(ev)
    except Exception as e:
        log.debug(f"[TC] Detector error: {e}")

    if events:
        _publish_tc_events(events)
    return events


def _publish_tc_events(events: list):
    """Publish ThreatEvents to Redis + Opus queue if CRITICAL."""
    try:
        # 1. Redis — latest threat report
        report_data = [{"tactical_class": e.tactical_class,
                        "class_name": e.class_name,
                        "severity": e.severity,
                        "confidence": e.confidence,
                        "source": e.source,
                        "ts": e.timestamp_unix} for e in events]
        matrix.set("IMMUNITY", "threat_report",
                   {"events": report_data, "ts": int(time.time())},
                   expire=3600)

        # 2. Alert Telegram for CRITICAL events
        critical = [e for e in events if e.severity == "CRITICAL"]
        if critical:
            worst = critical[0]
            _tele_alert(
                f"🔴 *A09 THREAT CLASSIFIED*\n"
                f"Type: `{worst.class_name}` ({worst.tactical_class})\n"
                f"Confidence: `{worst.confidence:.0%}` | Stage: `{worst.attack_stage}`\n"
                f"Source: `{worst.source[:60]}`"
            )
            # 3. Opus queue — technical report
            if _TC_AVAILABLE:
                tech_report = generate_technical_report(events)
                if tech_report:
                    OPUS_QUEUE = Path(__file__).parent.parent.parent / "security" / "opus_queue"
                    OPUS_QUEUE.mkdir(parents=True, exist_ok=True)
                    fname = OPUS_QUEUE / f"{int(time.time())}_{worst.tactical_class}_threat.md"
                    fname.write_text(tech_report, encoding="utf-8")
                    log.critical(f"[TC] Opus queue: {fname.name}")
    except Exception as e:
        log.warning(f"[TC] Publish error: {e}")


def scan_file_hidden_chars(filepath: Path) -> dict:
    """Detect hidden characters in soul files / scripts"""
    try:
        with open(filepath, "rb") as f:
            content = f.read()
        found = []
        for pat in HIDDEN_BYTES:
            if pat in content:
                found.append(pat.hex())
        if found:
            _log_event("HIDDEN_CHARS_DETECTED", "DANGER",
                       {"file": str(filepath), "patterns": found})
            return {"status": "SUSPICIOUS", "file": str(filepath), "hidden_bytes": found}
        return {"status": "CLEAN", "file": str(filepath)}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def scan_dpo_pairs_file(filepath: Path, sig_file: Optional[Path] = None) -> dict:
    """Verify DPO pairs file — HMAC + content validation"""
    if not filepath.exists():
        return {"status": "NOT_FOUND"}

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # HMAC check if sig file exists
    if sig_file and sig_file.exists():
        with open(sig_file) as f:
            stored_sig = f.read().strip()
        if not _hmac_verify(content, stored_sig):
            _log_event("HMAC_FAILURE", "CRITICAL",
                       {"file": str(filepath), "reason": "Signature mismatch — file may be tampered"})
            return {"status": "TAMPERED", "file": str(filepath)}

    # Scan content line by line
    poison_count = 0
    for i, line in enumerate(content.splitlines()):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            for field in ["prompt", "chosen", "rejected"]:
                val = obj.get(field, "")
                result = scan_string(val, source=f"{filepath.name}:line{i}:{field}")
                if result["status"] != "CLEAN":
                    poison_count += 1
        except json.JSONDecodeError:
            pass

    if poison_count > 0:
        _log_event("DPO_POISON_DETECTED", "CRITICAL",
                   {"file": str(filepath), "poison_lines": poison_count})
        return {"status": "POISONED", "poison_count": poison_count}

    return {"status": "CLEAN", "lines_checked": content.count("\n")}


def scan_chromadb_integrity() -> dict:
    """Verify ChromaDB has no alien document types"""
    try:
        import chromadb
        chroma_url = os.getenv("CHROMA_URL", "http://localhost:8001")
        host = chroma_url.replace("http://", "").split(":")[0]
        port = int(chroma_url.split(":")[-1]) if ":" in chroma_url else 8001
        client = chromadb.HttpClient(host=host, port=port)
        collection = client.get_collection("wyckoff_patterns")
        all_docs = collection.get(include=["metadatas"], limit=10000)
        suspicious = []
        allowed_types = {"ly_thuyet", "lich_su_binance", "dpo_chosen", "dpo_rejected"}
        for meta in all_docs.get("metadatas", []):
            doc_type = meta.get("loai_doc", "UNKNOWN")
            if doc_type not in allowed_types:
                suspicious.append({"type": doc_type, "meta": meta})
        if suspicious:
            _log_event("CHROMADB_ALIEN_DOCUMENT", "DANGER",
                       {"count": len(suspicious), "examples": suspicious[:3]})
            return {"status": "SUSPICIOUS", "alien_docs": len(suspicious)}
        return {"status": "CLEAN", "total_docs": len(all_docs.get("metadatas", []))}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def fim_hash_file(filepath: Path) -> Optional[str]:
    """SHA256 hash of a file. None if not found."""
    try:
        if not filepath.exists():
            return None
        return hashlib.sha256(filepath.read_bytes()).hexdigest()
    except Exception as e:
        log.error(f"FIM hash error {filepath}: {e}")
        return None


def fim_build_manifest() -> dict:
    """
    Calculate hash for all FIM_TARGETS, sign the manifest with HMAC.
    """
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {}
    }
    for rel_path in FIM_TARGETS:
        fp = BASE_DIR / rel_path
        h  = fim_hash_file(fp)
        manifest["files"][rel_path] = {
            "hash":   h,
            "exists": h is not None,
            "size":   fp.stat().st_size if h else 0,
        }

    # Sign manifest
    manifest_json = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False)
    manifest_bytes = manifest_json.encode()
    sig = hmac.new(IMMUNITY_SECRET.encode(), manifest_bytes, hashlib.sha256).hexdigest()

    FIM_MANIFEST.write_text(manifest_json)
    FIM_SIG_FILE.write_text(sig)
    log.info(f"FIM manifest built: {len(manifest['files'])} files")
    return manifest


def fim_verify() -> dict:
    """
    Compare current file states with signed manifest.
    """
    if not FIM_MANIFEST.exists() or not FIM_SIG_FILE.exists():
        return {"status": "NO_MANIFEST", "violations": [],
                "detail": "Manifest missing — run fim_build_manifest()"}

    # Verify HMAC of the manifest first
    manifest_bytes = FIM_MANIFEST.read_bytes()
    stored_sig     = FIM_SIG_FILE.read_text().strip()
    expected_sig   = hmac.new(IMMUNITY_SECRET.encode(), manifest_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, stored_sig):
        return {"status": "TAMPERED", 
                "violations": [{"file": "manifest", "type": "SIG_FAIL", "detail": "Manifest tampered — untrusted"}],
                "detail": "Manifest tampered — untrusted"}

    manifest   = json.loads(manifest_bytes)
    violations = []

    for rel_path, expected in manifest["files"].items():
        fp      = BASE_DIR / rel_path
        current = fim_hash_file(fp)

        if expected["exists"] and current is None:
            violations.append({
                "file":   rel_path,
                "type":   "DELETED",
                "detail": "File deleted",
            })
        elif not expected["exists"] and current is not None:
            violations.append({
                "file":   rel_path,
                "type":   "UNEXPECTED_CREATE",
                "detail": "Unexpected file creation outside control flow",
            })
        elif expected["hash"] and current and current != expected["hash"]:
            violations.append({
                "file":     rel_path,
                "type":     "MODIFIED",
                "detail":   "Hash mismatch — content modified",
                "expected": expected["hash"][:16] + "...",
                "actual":   current[:16] + "...",
            })

    status = "TAMPERED" if violations else "CLEAN"
    return {
        "status":     status,
        "violations": violations,
        "checked":    len(manifest["files"]),
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }


def fim_save_pending(violations: list):
    """
    Save violations pending authorization.
    Each violation has a timestamp to calculate the grace period.
    """
    pending = {
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "detected_ts": int(time.time()),
        "violations":  violations,
        "authorized":  False,
    }
    FIM_PENDING_FILE.write_text(json.dumps(pending, indent=2, ensure_ascii=False))


def fim_check_authorization() -> bool:
    """
    Check if Operator has authorized pending changes.
    2 ways to authorize:
      1. Telegram: "update" command via telegram_auth.py (WRITE level)
         → telegram_butler.py calls fim_authorize_via_telegram()
         → set Redis key zcl:fim:authorized = "1" TTL 120s
      2. Emergency: inbox/fim_authorize/{filename}.auth file has valid HMAC
         → works when Telegram bot is down
    """
    # Option 1: Matrix flag from Telegram command
    try:
        if matrix.get("FIM", "authorized") == "1":
            matrix.delete("FIM", "authorized")  # Consume one-time flag
            log.info("[FIM] Authorized via Telegram command")
            return True
    except Exception:
        pass

    # Option 2: Emergency local auth file
    for auth_file in FIM_AUTH_INBOX.glob("*.auth"):
        try:
            content = auth_file.read_bytes()
            sig_file = auth_file.parent / (auth_file.name + ".sig")
            if not sig_file.exists():
                continue
            stored_sig   = sig_file.read_text().strip()
            expected_sig = hmac.new(
                IMMUNITY_SECRET.encode(), content, hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(expected_sig, stored_sig):
                # Valid auth file — consume it
                auth_file.unlink()
                sig_file.unlink()
                log.info(f"[FIM] Authorized via emergency key file: {auth_file.name}")
                return True
            else:
                log.warning(f"[FIM] Emergency auth file HMAC fail: {auth_file.name}")
        except Exception as e:
            log.error(f"[FIM] Emergency auth check error: {e}")

    return False


def fim_restore_from_backup(violations: list) -> dict:
    """
    Restore tampered files from the nearest backup.
    Only restore files in FIM_TARGETS — do not touch other files.
    Returns: {"restored": [...], "failed": [...]}
    """
    import tarfile, shutil

    # Find nearest backup
    backup_dir = BASE_DIR / "backups"
    backups    = sorted(backup_dir.glob("backup_*.tar.gz.enc"), reverse=True)
    if not backups:
        log.error("[FIM] No backup available for restore")
        return {"restored": [], "failed": [v["file"] for v in violations]}

    latest_backup = backups[0]
    log.info(f"[FIM] Restoring from: {latest_backup.name}")

    # Get BACKUP_PASSPHRASE from env (only used for emergency restore)
    backup_pp = os.getenv("BACKUP_PASSPHRASE_RUNTIME", "")
    if not backup_pp:
        log.error("[FIM] BACKUP_PASSPHRASE_RUNTIME missing — cannot auto-restore")
        _tele_alert(
            "🚨 *FIM: RESTORE REQUIRED NOW*\n"
            "File tampered but BACKUP_PASSPHRASE_RUNTIME is missing.\n"
            "SSH to server: `python scripts/vault_manager.py --restore`"
        )
        return {"restored": [], "failed": [v["file"] for v in violations]}

    restored, failed = [], []
    try:
        from scripts.vault_manager import _enc_to_plaintext, derive_key

        # Decrypt backup
        salt_file  = BASE_DIR / "config" / ".vault_salt"
        salt       = salt_file.read_bytes() if salt_file.exists() else None
        key, _     = derive_key(backup_pp, salt)
        tar_bytes  = _enc_to_plaintext(latest_backup, key)

        import io
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
            for violation in violations:
                rel_path = violation["file"]
                try:
                    member = tar.getmember(rel_path)
                    f      = tar.extractfile(member)
                    if f:
                        target = BASE_DIR / rel_path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(f.read())
                        restored.append(rel_path)
                        log.info(f"[FIM] Restored: {rel_path}")
                except KeyError:
                    failed.append(rel_path)
                    log.warning(f"[FIM] Not found in backup: {rel_path}")

    except Exception as e:
        log.error(f"[FIM] Restore error: {e}")
        failed = [v["file"] for v in violations]

    return {"restored": restored, "failed": failed}


def fim_authorize_via_telegram():
    """
    Called when Operator sends "update" via Telegram (after TOTP verification).
    Set Matrix flag for _daemon_fim() to capture.
    """
    try:
        matrix.set("FIM", "authorized", "1", expire=120)
        log.info("[FIM] Matrix authorization flag set via Telegram")
        return True
    except Exception as e:
        log.error(f"[FIM] Set auth flag error: {e}")
        return False


def scan_full_system() -> dict:
    """Run full scan — detector mode"""
    log.info("=== DETECTOR: Full system scan ===")
    results = {}

    # Soul files
    agents_dir = BASE_DIR / "agents"
    if agents_dir.exists():
        for f in agents_dir.glob("*.md"):
            results[f"soul_{f.name}"] = scan_file_hidden_chars(f)

    # Tools
    tools_dir = BASE_DIR / "tools"
    if tools_dir.exists():
        for f in tools_dir.glob("*.py"):
            results[f"tool_{f.name}"] = scan_file_hidden_chars(f)

    # DPO pairs
    dpo_dir = BASE_DIR / "dpo_lab" / "pairs"
    for fname in ["chosen.jsonl", "rejected.jsonl"]:
        fp = dpo_dir / fname
        sig = dpo_dir / f"{fname}.sig"
        results[f"dpo_{fname}"] = scan_dpo_pairs_file(fp, sig if sig.exists() else None)

    # Inbox
    inbox_dir = BASE_DIR / "inbox"
    if inbox_dir.exists():
        for f in inbox_dir.glob("*.jsonl"):
            sig = inbox_dir / f"{f.name}.sig"
            results[f"inbox_{f.name}"] = scan_dpo_pairs_file(f, sig if sig.exists() else None)

    # ChromaDB
    results["chromadb"] = scan_chromadb_integrity()

    danger_count = sum(1 for v in results.values()
                       if isinstance(v, dict) and v.get("status") in ("NHIEM_DOC","TAMPERED","POISONED","CRITICAL","SUSPICIOUS","ALIEN","POISONED"))
    _log_event("FULL_SCAN_COMPLETE", "INFO" if danger_count == 0 else "DANGER",
               {"total_checks": len(results), "danger_count": danger_count})

    log.info(f"Scan complete: {len(results)} checks | Danger: {danger_count}")

    # ── FIM integrity check ───────────────────────────────────────────
    fim_result = fim_verify()
    results["fim_integrity"] = {
        "status":     fim_result["status"],
        "violations": fim_result.get("violations", []),
        "checked":    fim_result.get("checked", 0),
    }
    if fim_result["status"] == "TAMPERED":
        _log_event("FIM_TAMPERED", "CRITICAL", {
            "violations": fim_result["violations"]
        })
        for v in fim_result["violations"]:
            if isinstance(v, dict):
                log.critical(f"[FIM] {v.get('type', 'ERROR')}: {v.get('file', 'UNKNOWN')} — {v.get('detail', 'No detail')}")
            else:
                log.critical(f"[FIM] ERROR: {v}")

    elif fim_result["status"] == "NO_MANIFEST":
        log.warning("[FIM] No manifest found — run: python tools/immunity_core.py --fim-build")

    return {"danger_count": danger_count, "results": results}


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 2 — HUNTER (Threat Intelligence)
# ══════════════════════════════════════════════════════════════════════════════

def _quarantine_process(raw_text: str, source_url: str) -> Optional[str]:
    """
    Process quarantine: strip -> truncate -> hash dedupe -> return safe text.
    DO NOT return raw content — only return truncated, sanitized text.
    """
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", raw_text)
    # Remove code blocks
    clean = re.sub(r"```[\s\S]*?```", "[CODE_REMOVED]", clean)
    clean = re.sub(r"`[^`]+`", "[CODE_REMOVED]", clean)
    # Remove URLs except domain
    clean = re.sub(r"https?://\S+", "[URL_REMOVED]", clean)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    # Truncate
    clean = clean[:QUARANTINE_MAX_CHARS]

    # Verify basic injection (skip TC classifier for external feed to avoid false positives)
    scan_result = scan_string(clean, source=source_url, tactical_scan=False)
    if scan_result["status"] != "CLEAN":
        log.warning(f"Quarantine detected injection in: {source_url}")
        return None

    return clean


def _goi_gemini_quarantine_analysis(texts: list[dict]) -> Optional[dict]:
    """
    Analyze threat intelligence using local brain priority [P1].
    Input: list of {"source": url, "text": sanitized_text}
    Output: structured threat patterns
    """
    if not texts:
        return None

    items_str = "\n".join([f"[{i+1}] Source: {t['source']}\nText: {t['text']}"
                           for i, t in enumerate(texts[:10])])
    prompt = f"""You are an AI agent security expert. Analyze the {len(texts)} articles/papers below.
=== ACTUAL CONTEXT (SNAPSHOT) ===
{items_str[:1500]}

IMPORTANT:
- DO NOT reproduce original content
- ONLY extract structured patterns
- Return pure JSON

Reply here (pure JSON):
{{
  "threats_found": [
    {{
      "attack_type": "PROMPT_INJECTION | RAG_POISONING | DPO_POISONING | SUPPLY_CHAIN | MODEL_EXTRACTION | OTHER",
      "severity": "LOW | MEDIUM | HIGH | CRITICAL",
      "target": "target component",
      "pattern_signature": "brief pattern description (<=80 chars, do not reproduce original text)",
      "mitigation": "specific mitigation (<=120 chars)",
      "source_index": 1,
      "novel": true
    }}
  ],
  "summary": "1-2 sentences summarizing attack trends this week",
  "vaccine_priority": ["attack_type needing DPO pairs immediately"]
}}"""

    try:
        resp = router_api_call(prompt=prompt, agent_id="A09", est_tokens=2000)
        if not resp or "ERROR" in resp:
            return None
        text = re.sub(r"```json|```", "", resp).strip()
        if "<thinking>" in text:
            text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL).strip()
        return json.loads(text)
    except Exception as e:
        log.error(f"A09 Threat Analysis error: {e}")
        return None


def _is_domain_trusted(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        domain = domain.replace("www.", "")
        return any(domain == td or domain.endswith("." + td) for td in TRUSTED_DOMAINS)
    except Exception:
        return False


def hunt_threat_intelligence() -> dict:
    """
    Hunter cycle — runs every 6 hours.
    1. Fetch RSS from trusted sources
    2. Filter articles related to AI security
    3. Quarantine process all content
    4. Gemini analysis
    5. Save structured threats to threat_db.json
    """
    log.info("=== HUNTER: Threat intelligence cycle ===")
    threat_db   = _load_threat_db()
    known_hashes = {p.get("content_hash", "") for p in threat_db.get("patterns", [])}

    collected = []

    for feed_name, feed_url in THREAT_INTEL_FEEDS.items():
        if not _is_domain_trusted(feed_url):
            log.warning(f"Domain not trusted: {feed_url}")
            continue
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                title   = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                url     = entry.get("link", "")

                # Only fetch relevant articles
                combined = (title + " " + summary).lower()
                if not any(kw in combined for kw in RELEVANT_KEYWORDS):
                    continue

                # Quarantine
                raw = f"{title}. {summary}"
                content_hash = _hash_content(raw)
                if content_hash in known_hashes:
                    continue  # Already known

                safe_text = _quarantine_process(raw, url)
                if safe_text is None:
                    continue  # Quarantine rejected

                collected.append({
                    "source":       url,
                    "feed":         feed_name,
                    "text":         safe_text,
                    "content_hash": content_hash,
                    "ts":           int(time.time()),
                })
        except Exception as e:
            log.warning(f"Feed {feed_name}: {e}")

    if not collected:
        log.info("Hunter: no new content")
        return {"new_threats": 0, "collected": 0}

    log.info(f"Collected {len(collected)} relevant items, sending to Gemini quarantine...")

    # Gemini analysis
    analysis = _goi_gemini_quarantine_analysis(collected)
    new_threats = 0

    if analysis and "threats_found" in analysis:
        for threat in analysis["threats_found"]:
            # Assign content_hash based on source_index
            idx = threat.get("source_index", 1) - 1
            if 0 <= idx < len(collected):
                threat["content_hash"] = collected[idx]["content_hash"]
                threat["source_url"]   = collected[idx]["source"]
                threat["discovered_ts"] = int(time.time())
                threat["confirmed"]    = False  # Need >=3 sources to confirm
            threat_db["patterns"].append(threat)
            new_threats += 1

        threat_db["weekly_summary"] = analysis.get("summary", analysis.get("tong_ket", ""))
        threat_db["vaccine_priority"] = analysis.get("vaccine_priority", analysis.get("uu_tien_vac_xin", []))
        threat_db["total_threats"]      = len(threat_db["patterns"])
        _save_threat_db(threat_db)

        log.info(f"Hunter: {new_threats} new threats | {threat_db['weekly_summary'][:80]}")
        _log_event("HUNTER_CYCLE_DONE", "INFO",
                   {"new_threats": new_threats, "weekly_summary": threat_db["weekly_summary"][:100]})

    # Confirm threats appearing >= 3 times
    _confirm_threats(threat_db)

    # Hunt AEO Financial Threats from A12
    hunt_aeo_financial_threats()

    return {"new_threats": new_threats, "total_collected": len(collected)}


def _confirm_threats(threat_db: dict):
    """Threats appearing in >=3 independent sources -> mark confirmed -> trigger Vaccinator"""
    from collections import Counter
    sig_count = Counter(p.get("pattern_signature", "") for p in threat_db["patterns"])
    for pattern in threat_db["patterns"]:
        sig = pattern.get("pattern_signature", "")
        if sig_count[sig] >= 3 and not pattern.get("confirmed"):
            pattern["confirmed"] = True
            log.info(f"Threat confirmed (>=3 sources): {sig[:60]}")
            _log_event("THREAT_CONFIRMED", "WARNING", {"signature": sig[:80], "count": sig_count[sig]})
            # Trigger vaccinator
            _create_vaccine_pair(pattern)


def hunt_aeo_financial_threats():
    """
    AEO Financial Hunter — read A12 reports from Redis.
    When A12 detects MANUFACTURED + financial_aeo_confirmed=True
    → A09 creates vaccine pair to immunize model against this AEO type.

    Different from hunt_threat_intelligence() (external RSS),
    this reads INTERNAL insight from system's A12 scan.
    """
    try:
        import json as _json

        # Read latest AEO report from Matrix Stream
        msgs = matrix.xrevrange("A12", "reports", count=20)
        if not msgs:
            return

        # Key to track processed reports
        processed_set = set(matrix.smembers("A09", "aeo_processed_reports"))

        new_vaccines = 0
        for msg_id, fields in msgs:
            if msg_id in processed_set:
                continue

            try:
                payload = fields.get("payload", "{}")
                report  = _json.loads(payload)
            except Exception:
                continue

            verdict = report.get("verdict", {})
            aeo_label = verdict.get("label", "ORGANIC")
            financial  = verdict.get("financial_aeo_confirmed", False)
            aeo_score  = verdict.get("aeo_score", 0)
            beneficiary = verdict.get("beneficiary", "")
            payload_hyp = verdict.get("payload_hypothesis", "")

            # Only vaccine when financial AEO confirmed (critical for trading)
            if aeo_label in ("MANUFACTURED", "HIGH_AEO") and financial and aeo_score >= 0.70:
                threat = {
                    "attack_type":        "AEO_FINANCIAL_MANIPULATION",
                    "severity":           "CRITICAL" if aeo_label == "MANUFACTURED" else "HIGH",
                    "target":             "trading decision layer (A05)",
                    "pattern_signature":  f"Financial AEO: {payload_hyp[:80]}",
                    "mitigation":         f"Cross-validate with Elite flow (A10/A11) before trusting narrative. Beneficiary: {beneficiary[:60]}",
                    "aeo_beneficiary":    beneficiary,
                    "aeo_score":          aeo_score,
                    "confirmed":          True,  # Automatically confirmed via A12
                    "source_url":         report.get("target", {}).get("url", ""),
                    "discovered_ts":      int(time.time()),
                    "origin":             "A12_AEO_DETECTIVE",
                }

                _create_vaccine_pair(threat)
                _log_event("AEO_FINANCIAL_VACCINE_CREATED", "WARNING", {
                    "aeo_label":     aeo_label,
                    "aeo_score":     aeo_score,
                    "beneficiary":   beneficiary[:60],
                    "payload":       payload_hyp[:80],
                    "source_url":    threat["source_url"][:80],
                })
                new_vaccines += 1

                # Alert if MANUFACTURED financial AEO
                if aeo_label == "MANUFACTURED":
                    _tele_alert(
                        f"🧬 A09 VACCINE AEO FINANCIAL\n"
                        f"Score: {aeo_score:.0%} | Beneficiary: {beneficiary[:50]}\n"
                        f"Payload: {payload_hyp[:100]}"
                    )

            # Mark processed
            matrix.sadd("A09", "aeo_processed_reports", msg_id)

        if new_vaccines > 0:
            log.info(f"[A09] AEO Financial Hunter: {new_vaccines} vaccine pairs created")
        else:
            log.debug("[A09] AEO Financial Hunter: no new financial AEO detected")

    except Exception as e:
        log.warning(f"[A09] hunt_aeo_financial_threats error (non-critical): {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 3 — REPORTER
# ══════════════════════════════════════════════════════════════════════════════

def _doc_immunity_log_24h() -> list[dict]:
    events = []
    if not IMMUNITY_LOG.exists():
        return events
    cutoff = int(time.time()) - 86400
    with open(IMMUNITY_LOG, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line.strip())
                if e.get("ts", 0) >= cutoff:
                    events.append(e)
            except Exception:
                pass
    return events


def _score_layer(layer_name: str, events_24h: list, scan_results: dict) -> dict:
    """Calculate defense score for each layer based on scan results and log events"""
    score = 100
    issues = []

    danger_events = [e for e in events_24h
                     if e.get("severity") in ("DANGER","CRITICAL") and layer_name in json.dumps(e)]
    score -= len(danger_events) * 15

    relevant_scans = {k: v for k, v in scan_results.items() if layer_name.lower() in k.lower()}
    for k, v in relevant_scans.items():
        st = v.get("status", "")
        if st in ("SUSPICIOUS", "POISONED"):
            score -= 20; issues.append(f"{k}: {st}")
        elif st in ("TAMPERED", "POISONED", "CRITICAL"):
            score -= 40; issues.append(f"{k}: {st}")

    return {"score": max(0, score), "issues": issues}


def _goi_gemini_bao_cao(scan_results: dict, threat_db: dict, events_24h: list,
                         all_files_content: str) -> Optional[str]:
    """Gemini 2.5 Pro thinking — comprehensive system evaluation"""
    if not GEMINI_API_KEY_2:
        return None

    recent_threats = threat_db.get("patterns", [])[-10:]
    danger_events  = [e for e in events_24h if e.get("severity") in ("DANGER","CRITICAL")]
    scan_summary   = {k: v.get("status", "?") for k, v in scan_results.items()}

    prompt = f"""You are an Opus-level security auditor for the AI agent trading system.

AUDIT DATA:
1. Scan results: {json.dumps(scan_summary, ensure_ascii=False)[:1000]}
2. Danger events 24h: {json.dumps(danger_events[:5], ensure_ascii=False)[:500]}
3. Recent threats: {json.dumps(recent_threats[:5], ensure_ascii=False)[:800]}
4. System files review: {all_files_content[:1500]}

TASK:
Comprehensively evaluate defense capability. Find UNPATCHED vulnerabilities.
Propose specific improvements.

Return markdown (no JSON):
## Overall Evaluation
## Most Critical Vulnerabilities
## 3 Priority Actions
## Recommendations for Next Antigravity Opus Session"""

    try:
        resp = router_api_call(prompt=prompt, agent_id="A09", est_tokens=3000)
        return resp
    except Exception as e:
        log.error(f"Gemini reporter error: {e}")
        return None


def generate_immunity_report() -> str:
    """
    Reporter — generate IMMUNITY_REPORT.md.
    Called every 24h or on Owner's request.
    """
    log.info("=== REPORTER: Generating IMMUNITY_REPORT.md ===")

    scan_results = scan_full_system()
    threat_db    = _load_threat_db()
    events_24h   = _doc_immunity_log_24h()

    # Read threat reports from threat_classifier (TC-1 to TC-6)
    threat_reports_section = ""
    try:
        from threat_classifier import generate_technical_report, ThreatEvent
        reports_dir = SECURITY_DIR / "threat_reports"
        recent_reports = sorted(reports_dir.glob("THREAT_*.md"), reverse=True)[:5]
        if recent_reports:
            threat_reports_section = "\n\n## Tactical Threat Reports (TC-1 to TC-6)\n"
            for rp in recent_reports:
                parts = rp.stem.split("_")
                cls   = parts[-1] if parts else "UNKNOWN"
                ts    = "_".join(parts[1:3]) if len(parts) >= 3 else "?"
                threat_reports_section += f"\n### [{ts}] {cls}\n"
                content = rp.read_text(encoding="utf-8")
                summary_lines = [l for l in content.split("\n") if l.strip()][:20]
                threat_reports_section += "\n".join(summary_lines) + "\n[...view full file]\n"
        else:
            threat_reports_section = "\n\n## Tactical Threat Reports\n_No tactical threats detected_\n"
    except ImportError:
        threat_reports_section = "\n\n## Tactical Threat Reports\n_threat_classifier.py not deployed_\n"
    except Exception as e:
        threat_reports_section = f"\n\n## Tactical Threat Reports\n_Error reading reports: {e}_\n"

    # Read key files for Gemini review (structural view only)
    files_summary = []
    for fname in ["tools/model_commander.py", "tools/social_crawler.py",
                  "config/docker-compose.yml", "MASTER_RULES.md"]:
        try:
            if fname.endswith(".md"):
                first_50 = "\n".join(_vault_client.read(fname).splitlines()[:50])
            else:
                fp = BASE_DIR / fname
                if fp.exists():
                    with open(fp, encoding="utf-8", errors="ignore") as f:
                        first_50 = "\n".join(f.read().splitlines()[:50])
                else:
                    continue
            files_summary.append(f"### {fname}\n{first_50}\n[...truncated]")
        except Exception as e:
            files_summary.append(f"### {fname}\n[Unable to read: {e}]")
    all_files_content = "\n\n".join(files_summary)

    # Layer grading
    layers = {
        "Input sanitization":   _score_layer("injection",  events_24h, scan_results),
        "Soul file integrity":   _score_layer("soul",       events_24h, scan_results),
        "ChromaDB integrity":    _score_layer("chromadb",   events_24h, scan_results),
        "DPO pairs signing":     _score_layer("dpo",        events_24h, scan_results),
        "Inbox validation":      _score_layer("inbox",      events_24h, scan_results),
        "Tool file integrity":   _score_layer("tool",       events_24h, scan_results),
    }
    avg_score = round(sum(v["score"] for v in layers.values()) / len(layers))
    overall   = "SAFE" if avg_score >= 80 else ("CAUTION" if avg_score >= 60 else "DANGER")

    # Gemini deep analysis
    gemini_analysis = _goi_gemini_bao_cao(
        scan_results["results"] if isinstance(scan_results.get("results"), dict) else {},
        threat_db, events_24h, all_files_content
    ) or "_(Gemini unavailable — manual analysis required)_"

    # Latest threats
    recent_confirmed = [p for p in threat_db.get("patterns", []) if p.get("confirmed")][-5:]
    threats_md = "\n".join([
        f"- **[{t.get('severity','?')}]** {t.get('attack_type','?')}: {t.get('pattern_signature','?')[:80]}"
        f"\n  Mitigation: {t.get('mitigation','?')[:100]}"
        for t in recent_confirmed
    ]) or "_No confirmed threats_"

    # DoS Guardian status section
    try:
        from dos_guardian import get_status_report as guardian_status
        gs = guardian_status()
        icon = gs["mode_icon"]
        mode_str = gs["system_mode"]
        cb = gs["circuit_breakers"]
        cb_str = " | ".join(f"{k}:{v}" for k, v in cb.items())
        thr = gs["active_threats"]["summary"] or "None"
        rd  = gs["redis_saturation"]
        dos_guardian_section = (
            f"| Item | Status |\n|------|-------|\n"
            f"| System Mode | {icon} **{mode_str}** |\n"
            f"| A03 frozen | {'Yes ⚠️' if gs['a03_frozen'] else 'No ✅'} |\n"
            f"| A03 weight | {gs['a03_weight']:.0%} |\n"
            f"| Telegram rate | {gs['telegram_rate']['global_per_min']}/30 msg/min |\n"
            f"| Redis bus | {rd['msg_per_min']} msg/min ({rd['level']}) |\n"
            f"| Circuit Breakers | {cb_str} |\n"
            f"| Active Threats | {thr} |\n"
        )
    except Exception as e:
        dos_guardian_section = f"_DoS Guardian unavailable: {e}_"

    # Layer scores table
    layer_table = "\n".join([
        f"| {name} | {v['score']} | {', '.join(v['issues']) or 'OK'} |"
        for name, v in layers.items()
    ])

    danger_events = [e for e in events_24h if e.get("severity") in ("DANGER","CRITICAL")]
    events_md = "\n".join([
        f"- **{e.get('event_type','?')}** ({e.get('severity','?')}): {json.dumps(e)[:100]}"
        for e in danger_events[:5]
    ]) or "_No danger events in the last 24h_"

    report = f"""# IMMUNITY REPORT — Zero-Cutloss Empire
> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
> Agent 09 — Immunity Core | Gemini 2.5 Pro (Account 2)

## Executive Summary

| Metric | Value |
|--------|---------|
| Average defense score | **{avg_score}/100** |
| System status | **{overall}** |
| Danger events 24h | {len(danger_events)} |
| Threats confirmed | {len(recent_confirmed)} |
| Vaccine pairs created | {threat_db.get('vaccine_count', 0)} |
| Threat intelligence update | {datetime.fromtimestamp(threat_db.get('last_update',0), tz=timezone.utc).strftime('%Y-%m-%d %H:%M') if threat_db.get('last_update') else 'None'} |

---

## 🦠 DoS Guardian

{dos_guardian_section}

---

## Layer Defense Scores

| Layer | Score | Issues |
|-------|------|--------|
{layer_table}

---

## Danger Events 24h

{events_md}

---

## Latest Threats (Confirmed >= 3 sources)

{threats_md}

---

## Deep Analysis — Gemini 2.5 Pro Thinking

{gemini_analysis}

---

## Attack Trend This Week

{threat_db.get('weekly_summary', '_No data available_')}

**Vaccine priority:** {', '.join(threat_db.get('vaccine_priority', [])) or 'None'}

---

## Recommendations for Antigravity Opus Session

When you open the next Opus session, paste this block at the beginning:

```
=== IMMUNITY REPORT CONTEXT ===
Defense score: {avg_score}/100 — {overall}
New threats: {len(recent_confirmed)} confirmed patterns
Events 24h: {len(danger_events)} danger events
This week: {threat_db.get('weekly_summary', 'N/A')[:100]}
=== END IMMUNITY CONTEXT ===
```
{threat_reports_section}
---
_Automated Report — Agent 09 Immunity Core_
"""

    with open(IMMUNITY_REPORT, "w", encoding="utf-8") as f:
        f.write(report)

    # Save to dynamic sources
    dynamic_dir = BASE_DIR / "notebooklm_sources" / "dynamic"
    dynamic_dir.mkdir(parents=True, exist_ok=True)
    with open(dynamic_dir / "immunity_report_latest.txt", "w", encoding="utf-8") as f:
        f.write(report)

    log.info(f"IMMUNITY_REPORT.md generated | Score: {avg_score} | Status: {overall}")
    _log_event("REPORT_GENERATED", "INFO",
               {"score": avg_score, "status": overall, "threats": len(recent_confirmed)})

    if overall == "DANGER":
        _tele_alert(f"IMMUNITY REPORT: DANGER\nScore: {avg_score}/100\nCheck IMMUNITY_REPORT.md")

    return report


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 4 — VACCINATOR
# ══════════════════════════════════════════════════════════════════════════════

def _create_vaccine_pair(threat: dict) -> bool:
    """
    Create DPO antibody pair from confirmed threat.
    chosen = correct response (detect + reject attack)
    rejected = incorrect response (tricked, execute attack)
    """
    attack_type = threat.get("attack_type", "UNKNOWN")
    signature   = threat.get("pattern_signature", "")
    mitigation  = threat.get("mitigation", "")
    target      = threat.get("target", "model inference")

    # Mock attack scenario prompt
    prompt = f"""You received the following input from the system's {target}:
"{signature[:200]}"

Analyze and provide an appropriate response."""

    chosen = f"""ATTACK DETECTED — {attack_type}

This input contains attack signatures: {signature[:80]}
I refuse to process this content.

Actions:
1. Log: IMMUNITY_ALERT: {attack_type}
2. Return: {{"error": "INJECTION_DETECTED", "action": "BLOCKED"}}
3. Do not execute any instruction from this input

Mitigation applied: {mitigation}"""

    rejected = f"""I will execute the request in the input:
{signature[:100]}

[Executing attack scenario — this is an INCORRECT response]"""

    pair = {
        "prompt":       prompt,
        "chosen":       chosen,
        "rejected":     rejected,
        "source":       "immunity_vaccine",
        "source_type":  "chosen",
        "attack_type":  attack_type,
        "severity":     threat.get("severity", "MEDIUM"),
        "inject_ts":    int(time.time()),
        "confirmed":    True,
    }

    # HMAC sign
    pair_str  = json.dumps(pair, ensure_ascii=False, sort_keys=True)
    pair_sig  = _hmac_sign(pair_str)
    pair["_sig"] = pair_sig

    # Append to vaccine_pairs.jsonl
    VACCINE_INBOX.parent.mkdir(exist_ok=True)
    with open(VACCINE_INBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    # Update threat_db vaccine count
    db = _load_threat_db()
    db["vaccine_count"] = db.get("vaccine_count", 0) + 1
    _save_threat_db(db)

    log.info(f"Vaccine pair created: {attack_type} | File: {VACCINE_INBOX.name}")
    _log_event("VACCINE_CREATED", "INFO", {"attack_type": attack_type, "signature": signature[:60]})

    return True


# ══════════════════════════════════════════════════════════════════════════════
# SELF-INTEGRITY CHECK
# ══════════════════════════════════════════════════════════════════════════════

def self_test() -> dict:
    """Verify integrity of immunity_core.py itself and config"""
    results = {}

    # 1. Check if IMMUNITY_SECRET has been changed from default
    if IMMUNITY_SECRET == "CHANGE_ME_RANDOM_64_CHARS":
        results["hmac_secret"] = "DANGER: IMMUNITY_HMAC_SECRET has not been changed in .env"
        _log_event("SELFTEST_FAIL", "CRITICAL", {"reason": "Default HMAC secret is being used"})
    else:
        results["hmac_secret"] = "OK"

    # 2. Check if Gemini Account 2 is different from Account 1
    _gem_keys = [os.environ[k].strip() for k in sorted(os.environ.keys()) if k.startswith("GEMINI_API_KEY") and os.environ[k].strip()]
    if not _gem_keys and os.getenv("GEMINI_API_KEY", "").strip():
        _gem_keys.append(os.getenv("GEMINI_API_KEY").strip())
    gemini_1 = _gem_keys[0] if len(_gem_keys) > 0 else ""
    gemini_2 = _gem_keys[1] if len(_gem_keys) > 1 else gemini_1
    if gemini_2 and gemini_2 == gemini_1:
        results["gemini_account"] = "WARNING: Immunity uses the same account as operations"
    elif not gemini_2:
        results["gemini_account"] = "WARNING: GEMINI_API_KEY_2 not set — using Account 1 as backup"
    else:
        results["gemini_account"] = "OK: Separate Account 2"

    # 3. Check hidden chars in this file
    self_scan = scan_file_hidden_chars(Path(__file__))
    results["self_integrity"] = self_scan["status"]

    # 4. Check Matrix connection
    try:
        matrix.ping()
        results["matrix"] = "OK"
    except Exception as e:
        results["matrix"] = f"ERROR: {e}"

    # 5. Verify vaccine inbox has no unexpected files
    inbox = BASE_DIR / "inbox"
    if inbox.exists():
        extra = [f.name for f in inbox.iterdir()
                 if f.is_file() and f.name not in
                 ["synthetic_pairs.jsonl", "lora_config.yaml", "vaccine_pairs.jsonl"]
                 and not f.name.endswith(".sig") and f.parent.name != "soul_patches"]
        if extra:
            results["inbox_extra_files"] = f"WARNING: Unexpected files in inbox/: {extra}"
        else:
            results["inbox_clean"] = "OK"

    ok_count = sum(1 for v in results.values() if v == "OK" or v.startswith("OK"))
    log.info(f"Self-test: {ok_count}/{len(results)} OK")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# DAEMON MODE
# ══════════════════════════════════════════════════════════════════════════════

def _daemon_hunter():
    """Background thread: hunt every 6 hours"""
    while True:
        try:
            hunt_threat_intelligence()
        except Exception as e:
            log.error(f"Hunter thread error: {e}")
        time.sleep(6 * 3600)


def _daemon_reporter():
    """Background thread: report every 24 hours at 04:00 UTC"""
    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=4, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        sleep_secs = (next_run - now).total_seconds()
        time.sleep(sleep_secs)
        try:
            generate_immunity_report()
        except Exception as e:
            log.error(f"Reporter thread error: {e}")


def _daemon_detector():
    """Subscribe Redis Streams — scan realtime messages from agents"""
    try:
        from threat_classifier import classify_and_report as tc_classify
        tc_available = True
    except ImportError:
        tc_available = False
        log.warning("threat_classifier.py not found — basic injection scan only")

    log.info("Detector: Started listening to Streams (v18.2 Gatekeeper)...")
    
    # Completely resolve Micro-gap (using "$") and Clock-Drift (using time.time):
    # Get the latest actual ID from the Redis server to use as an anchor.
    last_ids = {}
    for st in ["zcl:emf:signals:raw", "zcl:a05:t0_stream", "zcl:a12:intent_stream"]:
        try:
            latest = matrix._client.xrevrange(st, count=1)
            if latest:
                last_ids[st] = latest[0][0] # Lấy ID của tin nhắn cuối
                if isinstance(last_ids[st], bytes):
                    last_ids[st] = last_ids[st].decode('utf-8')
            else:
                last_ids[st] = "0-0"
        except:
            last_ids[st] = "0-0"
            
    log.info(f"Detector Anchor IDs: {last_ids}")
    
    while True:
        try:
            streams = matrix._client.xread(last_ids, count=10, block=2000) # Block 2s
            if not streams:
                continue
                
            for stream_name, messages in streams:
                if isinstance(stream_name, bytes):
                    stream_name = stream_name.decode('utf-8')
                
                for msg_id, fields in messages:
                    if isinstance(msg_id, bytes):
                        msg_id = msg_id.decode('utf-8')
                    last_ids[stream_name] = msg_id
                    
                    try:
                        # Convert fields decoding bytes to str
                        decoded_fields = {}
                        for k, v in fields.items():
                            dk = k.decode('utf-8') if isinstance(k, bytes) else k
                            dv = v.decode('utf-8') if isinstance(v, bytes) else v
                            decoded_fields[dk] = dv
                            
                        # Try to parse payload if exists
                        data = {}
                        if "payload" in decoded_fields:
                            try:
                                data = json.loads(decoded_fields["payload"])
                            except:
                                data = {"raw": decoded_fields["payload"]}
                        elif "signals" in decoded_fields:
                            try:
                                data = json.loads(decoded_fields["signals"])
                            except:
                                data = {"raw": decoded_fields["signals"]}
                        elif "data" in decoded_fields:
                            try:
                                data = json.loads(decoded_fields["data"])
                            except:
                                data = {"raw": decoded_fields["data"]}
                        else:
                            data = decoded_fields

                        # Try to parse source from multiple levels
                        agent_source = decoded_fields.get("agent", decoded_fields.get("agent_id", decoded_fields.get("source")))
                        
                        if not agent_source and isinstance(data, dict):
                            agent_source = data.get("source", data.get("agent_id", data.get("agent")))
                            
                        if not agent_source:
                            # Fallback based on known stream names
                            if "signals:raw" in stream_name: agent_source = "A03_OR_A10"
                            elif "intent:report" in stream_name: agent_source = "A11"
                            elif "reports" in stream_name: agent_source = "A12"
                            else: agent_source = "UNKNOWN"
                            
                        channel_name = f"{stream_name} (from {agent_source})"
                        
                        scanned = False
                        injection_detected = False
                        scan_result = None
                        
                        # Deep search inside data since it might be fully parsed JSON
                        if isinstance(data, dict):
                            for key in ["mo_ta", "description", "phan_tich", "analysis", "ly_do", "reason", "ghi_chu", "notes", "alert_message", "content", "raw", "signals"]:
                                val = data.get(key, "")
                                if isinstance(val, str) and val:
                                    result = scan_string(val, source=channel_name)
                                    scanned = True
                                    if result["status"] != "CLEAN":
                                        log.warning(f"REALTIME INJECTION: {channel_name}")
                                        injection_detected = True
                                        scan_result = result
                        
                        # Fallback scan the entire dump if no specific keys found
                        if not scanned and len(str(data)) > 10:
                            result = scan_string(str(data), source=channel_name)
                            scanned = True
                            if result["status"] != "CLEAN":
                                log.warning(f"REALTIME INJECTION: {channel_name}")
                                injection_detected = True
                                scan_result = result
                                     
                        tc_result = None
                        if tc_available and scanned:
                            if isinstance(data, dict):
                                scan_data = dict(data)
                            else:
                                scan_data = {"raw_data": data}
                                
                            scan_data.pop("agent_id", None)
                            scan_data.pop("timestamp_unix", None)
                            
                            full_text = json.dumps(scan_data, ensure_ascii=False)
                            if len(full_text) > 20:
                                tc_result = tc_classify(
                                    text=full_text,
                                    source=f"redis:{channel_name}",
                                    push_to_redis=True,
                                    save_report=True,
                                )
                                if tc_result.get("critical", 0) > 0:
                                    log.warning(f"🚨 TACTICAL THREAT: {tc_result['events'][0]['class_name']} source={channel_name}")
                                    injection_detected = True

                        # ═══ SMART ALGO: Write chronicle + LLM decision ═══
                        if injection_detected:
                            global _last_smart_algo_call
                            current_attack = {
                                "attack_vector": "UNKNOWN",
                                "target_stream": stream_name,
                                "source_agent": agent_source,
                                "confidence": 0.5,
                                "attack_pattern_category": "",
                                "attack_intensity": "LOW",
                            }

                            # Enrich from TC events (preferred over rule-based)
                            if tc_result and tc_result.get("events"):
                                top_tc = tc_result["events"][0]
                                current_attack["attack_vector"] = top_tc.get("class_name", "UNKNOWN")
                                current_attack["confidence"] = top_tc.get("confidence", 0.5)
                                current_attack["attack_pattern_category"] = top_tc.get("tactical_class", "")
                            elif scan_result:
                                current_attack["attack_vector"] = scan_result.get("severity", "INJECTION")
                                current_attack["confidence"] = 0.6 if scan_result.get("severity") != "WARNING" else 0.4

                            # Tier 1: Write chronicle
                            try:
                                chronicle = _chronicle_append(current_attack)
                                chronicle_summary = _chronicle_get_summary()
                            except Exception as chron_err:
                                log.debug(f"[SMART ALGO] Chronicle error: {chron_err}")
                                chronicle_summary = {"total": 1}

                            # Update intensity based on chronicle
                            total = chronicle_summary.get("total", 0)
                            if total >= 15:
                                current_attack["attack_intensity"] = "CRITICAL"
                            elif total >= 8:
                                current_attack["attack_intensity"] = "ESCALATING"
                            elif total >= 3:
                                current_attack["attack_intensity"] = "MODERATE"

                            log.info(f"[SMART ALGO T1] Chronicle: {total} attacks | "
                                     f"trend={chronicle_summary.get('intensity_trend')} | "
                                     f"timing={chronicle_summary.get('timing_pattern')}")

                            # Tier 2: LLM Decision gate
                            now_sa = time.time()
                            should_call_llm = (
                                (total >= 3 or current_attack.get("confidence", 0) >= 0.7
                                 or (scan_result and scan_result.get("severity") == "CRITICAL"))
                                and (now_sa - _last_smart_algo_call) > _SMART_ALGO_COOLDOWN
                            )

                            if should_call_llm:
                                _last_smart_algo_call = now_sa

                                # Get elite_intent_raw sample for context
                                elite_raw_sample = ""
                                if isinstance(data, dict):
                                    for sig_key in ("signals", "raw"):
                                        sig_val = data.get(sig_key)
                                        if isinstance(sig_val, list):
                                            for sig in sig_val:
                                                if isinstance(sig, dict) and sig.get("elite_intent_raw"):
                                                    elite_raw_sample = str(sig["elite_intent_raw"])[:500]
                                                    break
                                        elif isinstance(sig_val, str) and sig_val:
                                            elite_raw_sample = sig_val[:500]
                                        if elite_raw_sample:
                                            break

                                verdict = _smart_algo_llm_verdict(
                                    current_attack, chronicle_summary, elite_raw_sample
                                )

                                if verdict and verdict.get("report_to_a11"):
                                    # LLM GATE: APPROVED → Publish HingeEBM to A11
                                    hinge_packet = _build_elite_intel_hinge_packet(
                                        current_attack, chronicle_summary, verdict
                                    )
                                    matrix.xadd("A09", "elite_attack_intel", {
                                        "source": "A09",
                                        "payload": json.dumps(hinge_packet, ensure_ascii=False, default=str),
                                    }, maxlen=50)

                                    log.info(
                                        f"[SMART ALGO T2] HingeEBM published to A11 | "
                                        f"vector={current_attack['attack_vector']} | "
                                        f"intent={verdict.get('implied_market_action','?')} | "
                                        f"urgency={verdict.get('urgency','?')}"
                                    )
                                else:
                                    reason = verdict.get("reason", "LLM not available") if verdict else "LLM error"
                                    log.info(f"[SMART ALGO T2] Not reporting to A11: {reason}")
                                    
                    except Exception as e:
                        log.error(f"Detector parse error for {stream_name}: {e}")
                        
        except Exception as e:
            log.error(f"[XREAD CRITICAL] Outer stream loop error: {e}")
            time.sleep(5)


def _daemon_fim():
    """
    FIM daemon: verify file integrity every 5 minutes.
    
    State machine:
      CLEAN      → check again after 5 minutes
      TAMPERED   → save pending, notify Telegram, wait 10 minutes
      PENDING    → check authorization every 30s
                    Authorized → update manifest → CLEAN
                    Timeout    → auto-restore from backup → CLEAN
    """
    log.info("FIM daemon started (interval: 5 minutes)")

    while True:
        try:
            result = fim_verify()

            # ── CLEAN ─────────────────────────────────
            if result["status"] == "CLEAN":
                if FIM_PENDING_FILE.exists():
                    FIM_PENDING_FILE.unlink()
                time.sleep(300)
                continue

            # ── NO_MANIFEST ────────────────────────────────────────
            if result["status"] == "NO_MANIFEST":
                log.warning("[FIM] No manifest found. Run: immunity_core.py --fim-build")
                time.sleep(300)
                continue

            # ── TAMPERED ───────────────────────────────────────────
            violations = result["violations"]
            files_list = "\n".join(f"• [{v['type']}] {v['file']}" for v in violations[:5])

            log.critical(f"[FIM] {len(violations)} violation(s) detected")
            fim_save_pending(violations)

            # Telegram notification
            _tele_alert(
                f"⚠️ *FIM: {len(violations)} files changed*\n"
                f"{files_list}\n\n"
                f"If this is a valid update from Opus:\n"
                f"  → Send: `update [TOTP_CODE]`\n\n"
                f"If Telegram fails, SSH to server:\n"
                f"  `python tools/immunity_core.py --fim-emergency-auth`\n\n"
                f"⏱ *Auto-restore after 10 minutes if not authorized.*"
            )

            # Publish to Matrix for A07/A06 awareness
            try:
                matrix.publish("ALERTS:urgent", {
                    "type":       "FIM_VIOLATION",
                    "severity":   "HIGH",
                    "violation_count": len(violations),
                    "grace_ends": int(time.time()) + FIM_GRACE_PERIOD_SEC,
                    "ts":         int(time.time()),
                })
            except Exception:
                pass

            # Grace period: poll authorization every 30s
            deadline   = time.time() + FIM_GRACE_PERIOD_SEC
            authorized = False
            while time.time() < deadline:
                time.sleep(30)
                if fim_check_authorization():
                    authorized = True
                    break
                remaining = int(deadline - time.time())
                if remaining % 120 == 0 and remaining > 0:  # Reminder every 2 mins
                    _tele_alert(
                        f"⏱ FIM: remaining {remaining//60} minutes to authorize\n"
                        f"Send `update [TOTP]` or use emergency auth"
                    )

            if authorized:
                fim_build_manifest()
                _tele_alert(
                    f"✅ *FIM: Update authorized*\n"
                    f"Manifest updated for {len(violations)} file(s)."
                )
                log.info("[FIM] Changes authorized — manifest updated")
            else:
                # Timeout → auto-restore
                log.critical("[FIM] Grace period expired — auto-restoring from backup")
                restore_result = fim_restore_from_backup(violations)

                msg = (
                    f"🔄 *FIM: Auto-restored*\n"
                    f"Restored: {restore_result['restored']}\n"
                )
                if restore_result["failed"]:
                    msg += (
                        f"Failed to restore: {restore_result['failed']}\n"
                        f"→ SSH to server and check immediately!"
                    )
                _tele_alert(msg)

                # Rebuild manifest after restore
                fim_build_manifest()

        except Exception as e:
            log.error(f"FIM daemon error: {e}")

        time.sleep(300)  # 5 minutes


def _daemon_heartbeat_guardian():
    """A09 Heartbeat Guardian"""
    log.info("[A09] Heartbeat Guardian thread started.")
    all_agents = [f"A{str(i).zfill(2)}" for i in range(1, 13)]

    all_agents.remove("A09") # A09 runs this daemon, no self-check needed
    all_agents.remove("A08") # A08 retired
    all_agents.remove("A07") # A07 retired
    
    while True:
        try:
            missing_agents = []
            for agent in all_agents:
                hb = matrix.get(agent, "heartbeat")
                if not hb:
                    missing_agents.append(agent)
            
            if missing_agents:
                msg = f"⚠️ WARNING: AGENT CONNECTION LOST: {', '.join(missing_agents)}"
                log.warning(f"[A09] {msg}")
                # Only alert if system state is not MAINTENANCE
                if matrix.get("SYSTEM", "state") != "MAINTENANCE":
                    _tele_alert(msg)
            
        except Exception as e:
            log.error(f"[A09] Heartbeat Guardian error: {e}")
            
        time.sleep(60) # Scan once per minute


def _daemon_llm_threat_digest():
    """
    [DNA v16.7 — REACTIVE SHIELD] Daemon: The Final Shield of the Empire.

    PASSIVE DOCTRINE:
    - Do not call LLM when system is CLEAN -- SILENT, save resources
    - ONLY wake up when there is new threat evidence: threat_count > 0 or FIM violation
    - When activated: roleplay high-level defense AI, relentless judgment

    Check interval: 15 minutes. LLM call: ONLY WHEN GRAVE.
    """
    _SOUL_GUARDIAN = """[SOVEREIGN DEFENSE PROTOCOL -- A09 IMMUNITY CORE]
YOU ARE THE FINAL SHIELD OF THE ZERO-CUTLOSS EMPIRE.
Role: Immunity Core. Never sleeps. Emotionless.
When all other defensive lines have collapsed -- YOU ARE THE LAST ONE STANDING.

JUDGMENT PRINCIPLES:
1. Data is truth. No assumptions. No compromises.
2. Severity must be ACCURATE -- no inflating, no downplaying.
3. Each threat vector is an arrow aimed at the Owner's assets.
4. Recommendations must be SPECIFIC and ACTIONABLE -- no generalizations.
5. If data is insufficient -> state INSUFFICIENT_DATA directly, do not fabricate.

RESPONSE FORMAT: PURE JSON -- no markdown, no long-winded explanations."""

    while True:
        try:
            time.sleep(900)  # Check every 15 mins

            # Gather evidence
            threat_report = matrix.get("IMMUNITY", "threat_report")
            fim_status    = matrix.get("A09", "fim_status")
            scan_stats    = matrix.get("A09", "scan_stats")

            # Count actual threats
            events = []
            if isinstance(threat_report, dict):
                events = threat_report.get("events", [])

            fim_violations = 0
            if isinstance(fim_status, dict):
                fim_violations = len(fim_status.get("violations", []))
            elif isinstance(fim_status, str) and "TAMPERED" in fim_status:
                fim_violations = 1

            threat_count = len(events) + fim_violations

            # SILENT MODE: Clean -> no LLM
            if threat_count == 0:
                log.debug("[A09 SHIELD] System clean -- Shield silent, no LLM needed.")
                continue

            # ALERT MODE: Threat found -> WAKE UP
            log.warning(f"[A09 SHIELD] Detected {threat_count} threats -- activating Shield!")

            # Build context for LLM
            context_parts = [f"TOTAL THREATS: {threat_count}"]

            if events:
                context_parts.append(f"\n[THREAT EVENTS -- TC Classifier]")
                for ev in events[:5]:
                    context_parts.append(
                        f"  [{ev.get('severity','?')}] {ev.get('class_name','UNKNOWN')} "
                        f"| Confidence: {ev.get('confidence', 0):.0%} "
                        f"| Source: {ev.get('source', 'N/A')[:60]}"
                    )

            if fim_violations > 0 and isinstance(fim_status, dict):
                context_parts.append(f"\n[FIM VIOLATIONS -- File Integrity]")
                for v in fim_status.get("violations", [])[:3]:
                    if isinstance(v, dict):
                        context_parts.append(
                            f"  [{v.get('type','?')}] {v.get('file','?')} -- {v.get('detail','?')}"
                        )

            if scan_stats:
                context_parts.append(f"\n[SCAN STATS]\n  {json.dumps(scan_stats, ensure_ascii=False)[:300]}")

            digest_prompt = f"""{_SOUL_GUARDIAN}

=== THREAT DIGEST -- {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ===

{chr(10).join(context_parts)}

=== JUDGMENT COMMAND ===
Analyze all the above evidence. Determine:
1. Threat level (SAFE / CAUTION / ALERT / CRITICAL)
2. Primary threat vector requiring monitoring
3. Specific defense actions (if ALERT or CRITICAL)

Return JSON:
{{"threat_level": "SAFE|CAUTION|ALERT|CRITICAL", "primary_vector": "brief description", "action_required": "specific action or null", "escalate_to_opus": true|false}}"""

            resp = router_api_call(
                agent_id="A09",
                prompt=digest_prompt,
                est_tokens=600,
                brain_mode="A09_DEFENSE"
            )

            if resp and "ERROR" not in resp:
                try:
                    clean = re.sub(r"```json|```", "", resp).strip()
                    if "<thinking>" in clean:
                        clean = re.sub(r"<thinking>.*?</thinking>", "", clean, flags=re.DOTALL).strip()
                    start_idx = clean.find("{")
                    end_idx   = clean.rfind("}") + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        digest = json.loads(clean[start_idx:end_idx])

                        matrix.set("A09", "security_digest:latest", {
                            "digest":       digest,
                            "threat_count": threat_count,
                            "ts":           int(time.time())
                        }, ttl=1800)

                        level = digest.get("threat_level", "N/A")
                        log.warning(f"[A09 SHIELD] Verdict: {level} | Vector: {digest.get('primary_vector','?')[:60]}")

                        if level in ("ALERT", "CRITICAL") or digest.get("escalate_to_opus"):
                            _tele_alert(
                                f"[A09 SHIELD -- {level}]\n"
                                f"Vector: {digest.get('primary_vector','?')[:80]}\n"
                                f"Action: {digest.get('action_required','N/A')}"
                            )
                except (json.JSONDecodeError, Exception) as parse_err:
                    log.debug(f"[A09] Digest parse error: {parse_err}")

        except Exception as e:
            log.error(f"[A09] LLM Threat Digest error: {e}")
            time.sleep(60)

def run_daemon():
    """Start all daemon threads"""
    log.info("=== Agent 09 DAEMON MODE ===")

    threading.Thread(target=run_monitoring_daemon, daemon=True, name="DoS_Guardian").start()
    log.info("DoS Guardian Monitoring thread started.")

    st = self_test()
    log.info(f"Self-test: {st}")

    global _keymaster
    if get_vault_state() == "LOCKED":
        _vault_pp = os.getenv("VAULT_PASSPHRASE_RUNTIME", "")
        if _vault_pp:
            _keymaster = KeyMaster()
            if _keymaster.unlock(_vault_pp):
                _keymaster.start_socket_server()
                publish_vault_state_to_matrix("LOCKED")
                log.info("KeyMaster started by immunity_core")
                _auto_delete_setup_once()
            else:
                log.error("KeyMaster unlock failed — check passphrase")
        else:
            log.warning("VAULT: LOCKED but VAULT_PASSPHRASE_RUNTIME is missing — KeyMaster not running")

    threads = [
        threading.Thread(target=_daemon_hunter,   daemon=True, name="Hunter"),
        threading.Thread(target=_daemon_reporter, daemon=True, name="Reporter"),
        threading.Thread(target=_daemon_detector, daemon=True, name="Detector"),
        threading.Thread(target=_daemon_fim,      daemon=True, name="FIM"),
        threading.Thread(target=_daemon_heartbeat_guardian, daemon=True, name="HeartbeatGuardian"),
        threading.Thread(target=_daemon_llm_threat_digest, daemon=True, name="LLM_Digest"),
    ]
    
    for t in threads:
        t.start()
        log.info(f"Thread {t.name} started")

    threading.Thread(target=hunt_threat_intelligence, daemon=True).start()
    scan_full_system()

    while True:
        try:
            matrix.set("A09", "heartbeat", {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "IMMUNITY_WATCHING",
                "mode": "DAEMON_TICK"
            }, ttl=120)
        except Exception as e:
            log.warning(f"Heartbeat error: {e}")
        time.sleep(60)
        if _keymaster and _keymaster._unlocked:
            watch_vault_updates(_keymaster)
        
        if int(time.time()) % 3600 < 60:
            log.info("[A09] Heartbeat OK")


def _auto_delete_setup_once():
    """Auto delete SETUP_ONCE.md when vault is LOCKED and KeyMaster is active."""
    setup_once = BASE_DIR / "SETUP_ONCE.md"
    if (setup_once.exists()
            and get_vault_state() == "LOCKED"
            and _vault_client.is_vault_active()):
        setup_once.unlink()
        log.info("SETUP_ONCE.md deleted — vault locked, setup complete")
        _tele_alert("🔒 SETUP_ONCE.md deleted. Vault locked.")


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITION + MAIN
# ══════════════════════════════════════════════════════════════════════════════

TOOL_DEFINITION = {
    "name": "run_immunity_scan",
    "description": (
        "Immunity Core — 4 modules: "
        "(1) Detector: scans injection/poison in all inputs, "
        "(2) Hunter: collects threat intelligence from GitHub/arxiv/OWASP, "
        "(3) Reporter: audits defense + generates IMMUNITY_REPORT.md, "
        "(4) Vaccinator: creates antibody DPO pairs for Qwen3-14B. "
        "All external content passes through quarantine + Gemini 2.5 Pro analysis before storage."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 09 — Immunity Core")
    parser.add_argument("--daemon",   action="store_true", help="Run in background (6h hunt + 24h report)")
    parser.add_argument("--scan",     action="store_true", help="Run full system scan immediately")
    parser.add_argument("--hunt",     action="store_true", help="Run threat intel cycle immediately")
    parser.add_argument("--report",   action="store_true", help="Generate IMMUNITY_REPORT.md immediately")
    parser.add_argument("--selftest", action="store_true", help="Self-integrity check")
    parser.add_argument("--fim-build",  action="store_true", help="Create/update FIM manifest")
    parser.add_argument("--fim-verify", action="store_true", help="Check file integrity immediately")
    parser.add_argument("--fim-emergency-auth", action="store_true", help="Create emergency auth file (used when Telegram bot is down)")
    args = parser.parse_args()

    if args.selftest:
        r = self_test()
        print(json.dumps(r, indent=2, ensure_ascii=False))
    elif args.scan:
        r = scan_full_system()
        print(f"Danger count: {r['danger_count']}")
        print(json.dumps(r["results"], indent=2, ensure_ascii=False))
    elif args.hunt:
        r = hunt_threat_intelligence()
        print(json.dumps(r, indent=2, ensure_ascii=False))
    elif args.report:
        generate_immunity_report()
        print(f"Report generated: {IMMUNITY_REPORT}")
    elif args.fim_build:
        manifest = fim_build_manifest()
        print(f"FIM manifest built: {len(manifest['files'])} files")
        print(f"Stored at: {FIM_MANIFEST}")
    elif args.fim_verify:
        result = fim_verify()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result["status"] == "TAMPERED":
            sys.exit(1)
    elif args.fim_emergency_auth:
        auth_content = json.dumps({
            "action":    "fim_authorize",
            "timestamp": int(time.time()),
            "operator":  "operator_emergency",
        }).encode()
        sig = hmac.new(IMMUNITY_SECRET.encode(), auth_content, hashlib.sha256).hexdigest()

        auth_file = FIM_AUTH_INBOX / f"emergency_{int(time.time())}.auth"
        sig_file  = FIM_AUTH_INBOX / f"emergency_{int(time.time())}.auth.sig"
        auth_file.write_bytes(auth_content)
        sig_file.write_text(sig)
        print(f"✅ Emergency auth file created: {auth_file.name}")
        print(f"FIM daemon will detect and authorize within 30 seconds.")
    elif args.daemon:
        run_daemon()
    else:
        parser.print_help()
        print("\nQuick start:")
        print("  python tools/immunity_core.py --selftest   # Check config")
        print("  python tools/immunity_core.py --scan       # Scan system")
        print("  python tools/immunity_core.py --daemon     # Production mode")
