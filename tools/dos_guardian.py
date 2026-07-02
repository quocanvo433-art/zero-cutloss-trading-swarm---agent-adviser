"""
🧬 DNA: v16.6 (Sovereign Purity & Immunity)
🏢 UNIT: DOS_GUARDIAN
🛠️ ROLE: DOS_GUARDIAN, FIM_ENFORCER
📖 DESC: Deep protection system managing Rate Limiting, Circuit Breakers (GPU/VRAM), and orchestrating operational modes (NORMAL/SURVIVAL/LOCKDOWN).
🔗 CALLS: tools/imperial_state.py, tools/llm_router.py
📟 I/O: Redis: zcl:guardian:*, zcl:ollama:*
🛡️ INTEGRITY: Organic Ecosystem - Immutable - Realtime Hardening
"""


import os
import json
import time
import logging
import hashlib
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from imperial_state import matrix
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../config/.env'))

REDIS_URL        = os.getenv("REDIS_URL", "redis://zcl_redis:6379")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_BOT     = os.getenv("TELEGRAM_BOT_TOKEN", "")

BASE_DIR = Path(__file__).parent.parent
LOG_FILE = BASE_DIR / "logs" / "dos_guardian.log"
LOG_FILE.parent.mkdir(exist_ok=True)

log = logging.getLogger("DOS_GUARDIAN")
if not log.handlers:
    log.setLevel(logging.INFO)
    try:
        log.addHandler(logging.FileHandler(str(LOG_FILE)))
    except PermissionError:
        pass
    log.addHandler(logging.StreamHandler())

# ── Redis keys ────────────────────────────────────────────────────────────────
RK_SYSTEM_MODE       = "zcl:guardian:system_mode"      # NORMAL/CAUTION/SURVIVAL/LOCKDOWN
RK_MODE_REASON       = "zcl:guardian:mode_reason"      # Mode transition reason
RK_MODE_TS           = "zcl:guardian:mode_ts"          # Mode transition timestamp
RK_RATE_TELE_GLOBAL  = "zcl:guardian:rate:tele:global" # Global Telegram rate
RK_REDIS_SATURATION  = "zcl:guardian:redis_sat"        # Redis saturation score
RK_CIRCUIT_TRAIN     = "zcl:guardian:circuit:train"    # Circuit breaker: training
RK_CIRCUIT_A03       = "zcl:guardian:circuit:a03"      # Circuit breaker: A03
RK_CIRCUIT_CHROMA    = "zcl:guardian:circuit:chroma"   # Circuit breaker: ChromaDB
RK_NARRATIVE_FREEZE  = "zcl:guardian:narrative_freeze" # Blindness protocol active
RK_DOS_EVENT_LOG     = "zcl:guardian:dos_events"       # List of DoS events
RK_RECOVERY_TS       = "zcl:guardian:recovery_ts"      # When to try NORMAL again

# ── Infrastructure mode keys (Stage 27) ─────────────────────────────────
RK_INFRA_MODE        = "zcl:guardian:infra_mode"        # LOCAL_ONLY/HYBRID/CLOUD_ONLY/CLOUD_BOOSTED/...
RK_INFRA_REASON      = "zcl:cloud:infra_mode_reason"    # Infra mode transition reason
RK_OLLAMA_LOCK       = "zcl:ollama:inference_lock"       # Distributed mutex for Ollama
RK_OLLAMA_QUEUE      = "zcl:ollama:inference_queue"     # Priority queue (sorted set)
RK_FROZEN_SINCE      = "zcl:guardian:frozen_since"       # Timestamp when entering FROZEN state
RK_RECOVERY_STEP     = "zcl:guardian:recovery_step"      # Step in GRADUAL_RECOVERY (0-4)

# Ollama access priority (higher = more prioritized)
OLLAMA_PRIORITY = {
    "A05": 100,   # CRITICAL: Grand Judge — trading decision
    "A04": 80,    # HIGH: Wyckoff brain — core analysis
    "A11": 60,    # MEDIUM: EMF intent — strategic
    "A12": 50,    # MEDIUM: AEO Detective
    "A03": 40,    # MEDIUM: Social crawler
    "A10": 40,    # MEDIUM: EMF signal
    "A09": 30,    # LOW-MED: Immunity scan
    "DEFAULT": 20,
}
OLLAMA_LOCK_TTL_SEC = 60   # Auto-release after 60s if agent dies mid-execution

# Gradual recovery steps (from lowest to highest)
RECOVERY_STEPS = [
    (0, "FROZEN",            "Completely frozen — only A09 Immunity scan"),
    (1, "LOCAL_ONLY",        "Step 1: Start local Qwen3 — only A04/A05"),
    (2, "LOCAL_ONLY",        "Step 2: Expand to A03/A10 — social + EMF"),
    (3, "HYBRID",            "Step 3: Try cloud canary — if OK switch to HYBRID"),
    (4, "NORMAL",            "Step 4: Full recovery"),
]

# ── Thresholds ─────────────────────────────────────────────────────────────────
# Rate limiting
TELE_RATE_LIMIT_PER_MIN_GLOBAL = 30    # Max 30 msg/min globally
TELE_RATE_LIMIT_PER_MIN_CHAT   = 20    # Max 20 msg/min per chat_id
TELE_RATE_LIMIT_UNKNOWN        = 5     # Unknown chat_id: 5 msg/min then drop

# Redis saturation
REDIS_MSG_RATE_WARN   = 500    # msg/min → CAUTION
REDIS_MSG_RATE_DANGER = 2000   # msg/min → SURVIVAL
REDIS_PAYLOAD_MAX_KB  = 512    # KB — payloads larger than this are dropped

# Circuit breaker
CB_FAIL_THRESHOLD      = 3     # 3 consecutive failures -> open
CB_HALF_OPEN_AFTER_SEC = 300   # 5 minutes later -> retry (half-open)
CB_RECOVERY_AFTER_SEC  = 600   # 10 minutes in SURVIVAL -> try to recover to CAUTION

# Narrative saturation
NARRATIVE_CRITICAL_CYCLES = 5  # ≥5 consecutive CRITICAL cycles -> Blindness Protocol
NARRATIVE_FREEZE_SEC       = 1800  # Freeze A03 for 30 minutes

# ChromaDB
CHROMA_WRITE_RATE_LIMIT  = 10  # max writes/minute
CHROMA_ALIEN_THRESHOLD   = 3   # ≥3 alien docs within 5 minutes -> circuit open


# ══════════════════════════════════════════════════════════════════════════════
# REDIS HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _get_redis():
    """
    Compatibility wrapper — returns raw Redis client from matrix singleton.
    Used for operations requiring raw keys (RK_* constants without passing through PREFIX_MAP).
    """
    return matrix._client



# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM MODE MANAGER
# ══════════════════════════════════════════════════════════════════════════════

MODE_LEVELS = {"NORMAL": 0, "CAUTION": 1, "SURVIVAL": 2, "LOCKDOWN": 3}
MODE_ICONS  = {"NORMAL": "🟢", "CAUTION": "🟡", "SURVIVAL": "🟠", "LOCKDOWN": "🔴"}

INFRA_MODES = {"LOCAL_ONLY", "HYBRID", "CLOUD_ONLY", "CLOUD_BOOSTED",
               "CLOUD_ONLY_DETACH", "FROZEN", "GRADUAL_RECOVERY"}
INFRA_ICONS = {
    "LOCAL_ONLY":           "💾",
    "HYBRID":               "🔀",
    "CLOUD_ONLY":           "☁️",
    "CLOUD_BOOSTED":        "⚡☁️",
    "CLOUD_ONLY_DETACH":    "☁️🔒",    # Cloud lock: Detach from HW
    "FROZEN":               "❄️",         # Frozen: cloud + HW offline
    "GRADUAL_RECOVERY":     "🌱",         # Step-by-step recovery
}

# Detailed description of each infra mode (used for /mode status and ZCL_SYSTEM_REPORT)
INFRA_DESCRIPTIONS = {
    "LOCAL_ONLY":           "Local GPU + Qwen3:14b. Cloud off. Training OK.",
    "HYBRID":               "Local + Cloud in parallel. Canary probe every 30s.",
    "CLOUD_ONLY":           "Gemini Flash/Pro only. Ollama off.",
    "CLOUD_BOOSTED":        "High priority Cloud + Quota calibrated. Flash+Pro full.",
    "CLOUD_ONLY_DETACH":    "HW detached, maintenance/upgrade. Cloud only. A09 still pings local.",
    "FROZEN":               "Frozen. Cloud down + HW not ready. Only A09+A07 log.",
    "GRADUAL_RECOVERY":     "Gradual recovery from FROZEN to NORMAL.",
}


def get_system_mode() -> str:
    """Read current system mode from Matrix."""
    try:
        return matrix.get("GUARDIAN", "system_mode") or "NORMAL"
    except Exception:
        return "CAUTION"


def set_system_mode(mode: str, reason: str, notify: bool = True) -> bool:
    """
    Switch system mode. Only escalates or stays same, no auto-downgrade.
    Downgrading must pass recovery check.
    Returns True if successful, False if invalid mode.
    """
    if mode not in MODE_LEVELS:
        log.warning(f"Invalid mode: {mode}")
        return False

    current = get_system_mode()
    current_level = MODE_LEVELS.get(current, 0)
    new_level     = MODE_LEVELS[mode]

    # No auto-downgrade — only escalation
    if new_level <= current_level and mode != current:
        log.info(f"Mode {mode} < current {current} — no auto-downgrade")
        return True   # Not an error, just no action needed

    try:
        matrix.set("GUARDIAN", "system_mode", mode)
        matrix.set("GUARDIAN", "mode_reason", reason[:200])
        matrix.set("GUARDIAN", "mode_ts", int(time.time()))

        if mode in ("SURVIVAL", "LOCKDOWN"):
            matrix.set("GUARDIAN", "recovery_ts", int(time.time()) + CB_RECOVERY_AFTER_SEC)
    except Exception:
        return False

    icon = MODE_ICONS.get(mode, "⚪")
    log.warning(f"[MODE CHANGE] {current} → {mode} | Reason: {reason[:80]}")
    _log_dos_event(f"MODE_{mode}", reason)

    if notify and current != mode:
        _tele_alert(
            f"{icon} *System mode changed to: {mode}*\n"
            f"From: {current}\n"
            f"Reason: {reason[:150]}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
        )
    return True


def get_infrastructure_mode() -> str:
    """Get current infrastructure mode."""
    try:
        return matrix.get("GUARDIAN", "infra_mode") or "HYBRID"
    except Exception:
        return "HYBRID"


def set_infrastructure_mode(mode: str, reason: str, notify: bool = True) -> bool:
    """
    Switch infrastructure mode.
    Operates independently from security mode — no conflict.
    """
    if mode not in INFRA_MODES:
        log.warning(f"Invalid infra mode: {mode} (must be {INFRA_MODES})")
        return False

    current = get_infrastructure_mode()

    try:
        matrix.set("GUARDIAN", "infra_mode", mode)
        matrix.set("GUARDIAN", "infra_mode_reason", reason[:200])
    except Exception:
        return False

    icon = INFRA_ICONS.get(mode, "⚪")
    log.warning(f"[INFRA MODE] {current} → {mode} | {reason[:80]}")
    _log_dos_event(f"INFRA_{mode}", reason)

    if notify and current != mode:
        _tele_alert(
            f"{icon} *Infrastructure mode changed to: {mode}*\n"
            f"From: {current}\n"
            f"Reason: {reason[:150]}"
        )
    return True


RK_SURVIVAL_EXTENSION = "zcl:guardian:survival_extension"

def extend_survival_mode(minutes: int = 30) -> int:
    """Extend hallucination containment duration in SURVIVAL."""
    try:
        current_ext = int(matrix.get("GUARDIAN", "survival_extension") or 0)
        new_ext = current_ext + minutes * 60
        matrix.set("GUARDIAN", "survival_extension", new_ext, expire=86400)
        return int(new_ext / 60)
    except Exception:
        return 0

def get_operational_profile() -> dict:
    """
    Synthesize both modes — agents call this single function instead of querying both systems.
    Returns profile dict.
    """
    sec_mode   = get_system_mode()
    infra_mode = get_infrastructure_mode()

    # Calculate duration spent in the current system mode
    mode_duration_sec = 0
    survival_extension = 0
    try:
        mode_ts = matrix.get("GUARDIAN", "mode_ts")
        if mode_ts:
            mode_duration_sec = int(time.time()) - int(mode_ts)
        
        # Read extension parameter
        if sec_mode == "SURVIVAL":
            survival_extension = int(matrix.get("GUARDIAN", "survival_extension") or 0)
        else:
            matrix.delete("GUARDIAN", "survival_extension")
    except Exception:
        pass

    # Determine operational profile name
    force_close_risk = False
    allow_new_recs = True
    allow_train = sec_mode not in ("SURVIVAL", "LOCKDOWN")

    if sec_mode == "LOCKDOWN":
        profile = "AUTHORIZED_SHUTDOWN" if infra_mode == "LOCAL_ONLY" else "LOCKDOWN_CLOUD"
        allow_new_recs = False
        force_close_risk = True
    elif sec_mode == "SURVIVAL":
        # HALLUCINATION CONTAINMENT: Base 60 minutes (3600s) + extension from Master
        max_duration = 3600 + survival_extension
        if mode_duration_sec > max_duration:
            profile = "ENHANCED_DEFENSE"
            allow_new_recs = False
            force_close_risk = True
        else:
            # Short-term SURVIVAL: still allows trading based on cached context.
            profile = "SHORT_TERM_SURVIVAL"
            allow_new_recs = False
            force_close_risk = False
    elif infra_mode == "LOCAL_ONLY" and sec_mode == "NORMAL":
        profile = "TRAINING"
    elif infra_mode in ("CLOUD_BOOSTED",) and sec_mode == "NORMAL":
        profile = "PEAK_EFFICIENCY"
    else:
        profile = "OPERATION"

    use_cloud = infra_mode not in ("LOCAL_ONLY", "FROZEN")
    use_local = infra_mode not in ("CLOUD_ONLY", "CLOUD_BOOSTED", "CLOUD_ONLY_DETACH", "FROZEN")

    # Compute level from cloud prober
    compute_level = "UNKNOWN"
    try:
        compute_level = matrix.get("SYSTEM", "cloud:compute_level") or "UNKNOWN"
    except Exception:
        pass

    return {
        "security_mode":   sec_mode,
        "infra_mode":      infra_mode,
        "profile":         profile,
        "mode_duration":   mode_duration_sec,
        "allow_new_recs":  allow_new_recs,
        "force_close_risk": force_close_risk,
        "allow_training":  allow_train,
        "use_cloud":       use_cloud,
        "use_local":       use_local,
        "compute_level":   compute_level,
        "a03_weight":      get_a03_weight_multiplier(),
        "min_confluence":  4 if sec_mode == "CAUTION" else 3,
    }









# ── Stage 28: FROZEN + CLOUD_ONLY_DETACH + GRADUAL_RECOVERY ─────────────────

def freeze_system(reason: str = "Manual") -> bool:
    """
    FROZEN mode — Complete system freeze.
    Triggered when: Cloud down + Hardware not yet recovered.

    FROZEN State:
      - No Ollama inference (GPU offline or overheating)
      - No Cloud (API failed)
      - Only A09 immunity scan (from cache) + A07 log persistence
      - Redis heartbeat every 60s to prevent state loss
      - Automatic tracking of freeze duration

    When Cloud OR HW recovers -> call advance_recovery_step(0)
    """
    current_infra = get_infrastructure_mode()
    if current_infra == "FROZEN":
        log.info("[FROZEN] System is already FROZEN")
        return True

    # Save state before freezing
    matrix.set("GUARDIAN", "infra_mode", "FROZEN")
    matrix.set("GUARDIAN", "infra_mode_reason", reason[:200])
    matrix.set("GUARDIAN", "frozen_since", int(time.time()))
    matrix.set("GUARDIAN", "recovery_step", 0)

    # Escalate security mode
    current_sec = get_system_mode()
    if current_sec not in ("SURVIVAL", "LOCKDOWN"):
        matrix.set("GUARDIAN", "system_mode", "SURVIVAL")
        matrix.set("GUARDIAN", "mode_reason", f"Auto SURVIVAL due to FROZEN: {reason[:80]}")

    _log_dos_event("FROZEN", reason)
    log.warning(f"[FROZEN] System frozen — {reason[:80]}")
    _tele_alert(
        f"❄️ *SYSTEM FROZEN*\n"
        f"Reason: {reason[:150]}\n\n"
        f"• Cloud: ❌ UNAVAILABLE\n"
        f"• Hardware: ❌ UNAVAILABLE\n"
        f"• Only A09+A07 logs maintained\n"
        f"• Security: SURVIVAL\n\n"
        f"When either recovers -> /mode recovery"
    )
    return True


def detach_to_cloud(reason: str = "Manual") -> bool:
    """
    CLOUD_ONLY_DETACH — Detach hardware, run entirely on Cloud.
    Triggered when: Master wants to rest GPUs, upgrade HW, or relocate.

    Unlike FROZEN:
      - Cloud STILL operates fine
      - HW is actively turned off (not a malfunction)
      - A04/A05 fall back to Gemini Flash (instead of Qwen3)
      - A07 injecting to Gemini Web is still OK

    When HW is ready again -> /mode continuous or /mode smart
    """
    matrix.set("GUARDIAN", "infra_mode", "CLOUD_ONLY_DETACH")
    matrix.set("GUARDIAN", "infra_mode_reason", reason[:200])



    _log_dos_event("CLOUD_ONLY_DETACH", reason)
    log.info(f"[DETACH] GPU detached — Cloud only: {reason[:60]}")
    _tele_alert(
        f"☁️🔒 *HARDWARE DETACHED — CLOUD ONLY*\n"
        f"Reason: {reason[:150]}\n\n"
        f"• GPU/HW: 🔌 OFFLINE (proactive)\n"
        f"• Cloud Gemini: ✅ OPERATIONAL\n"
        f"• A04/A05: using Flash instead of Qwen3\n\n"
        f"When HW is ready: /mode continuous or /mode smart"
    )
    return True


def advance_recovery_step(manual_step: int = -1) -> dict:
    """
    GRADUAL_RECOVERY — Step-by-step recovery from FROZEN to NORMAL.

    Steps (RECOVERY_STEPS):
      0: FROZEN -> Only A09 ping local + A07 log
      1: LOCAL_ONLY + A04/A05 start Qwen3
      2: LOCAL_ONLY + expand to A03/A10/A12
      3: HYBRID -> try cloud canary, if OK switch
      4: NORMAL -> full recovery

    Called when:
      - Cloud recovers (from FROZEN)
      - HW recovers (from FROZEN)
      - Master triggers manually via /mode recovery
    """
    current_step = int(matrix.get("GUARDIAN", "recovery_step") or 0)
    next_step = (current_step + 1) if manual_step < 0 else manual_step

    if next_step >= len(RECOVERY_STEPS):
        # Recovery completed
        matrix.set("GUARDIAN", "infra_mode", "HYBRID")
        matrix.set("GUARDIAN", "system_mode", "NORMAL")
        matrix.set("GUARDIAN", "infra_mode_reason", "GRADUAL_RECOVERY completed")
        matrix.delete("GUARDIAN", "frozen_since")
        matrix.delete("GUARDIAN", "recovery_step")
        log.info("[RECOVERY] Full recovery")
        _tele_alert("🌱 GRADUAL_RECOVERY completed — system NORMAL+HYBRID")
        return {"ok": True, "step": len(RECOVERY_STEPS), "profile": "NORMAL+HYBRID"}

    step_num, infra, desc = RECOVERY_STEPS[next_step]
    matrix.set("GUARDIAN", "recovery_step", next_step)
    matrix.set("GUARDIAN", "infra_mode", "GRADUAL_RECOVERY")
    matrix.set("GUARDIAN", "infra_mode_reason", f"Step {next_step}: {desc[:80]}")

    # Adjust security mode based on recovery step
    if next_step >= 3:
        matrix.set("GUARDIAN", "system_mode", "CAUTION")
    elif next_step >= 1:
        # Maintain SURVIVAL but allow inference
        pass

    frozen_since = int(matrix.get("GUARDIAN", "frozen_since") or time.time())
    frozen_min   = int((time.time() - frozen_since) / 60)

    _log_dos_event("GRADUAL_RECOVERY", f"Step {next_step}: {desc}")
    log.info(f"[RECOVERY] Step {next_step}/{len(RECOVERY_STEPS)-1}: {desc}")
    _tele_alert(
        f"🌱 *RECOVERY STEP {next_step}/{len(RECOVERY_STEPS)-1}*\n"
        f"• {desc}\n"
        f"• Frozen for: {frozen_min} minutes\n\n"
        f"Use /mode recovery to proceed."
    )
    return {
        "ok":      True,
        "step":    next_step,
        "total":   len(RECOVERY_STEPS) - 1,
        "desc":    desc,
        "infra":   infra,
    }


def get_frozen_status() -> dict:
    """Read current FROZEN/RECOVERY status."""
    infra = get_infrastructure_mode()
    if infra not in ("FROZEN", "GRADUAL_RECOVERY"):
        return {"frozen": False, "infra": infra}
    try:
        frozen_since = int(matrix.get("GUARDIAN", "frozen_since") or time.time())
        frozen_min   = int((time.time() - frozen_since) / 60)
        step         = int(matrix.get("GUARDIAN", "recovery_step") or 0)
        return {
            "frozen":        infra == "FROZEN",
            "in_recovery":   infra == "GRADUAL_RECOVERY",
            "infra":         infra,
            "frozen_since_ts": frozen_since,
            "frozen_minutes":  frozen_min,
            "recovery_step":   step,
            "recovery_total":  len(RECOVERY_STEPS) - 1,
            "current_desc":    RECOVERY_STEPS[step][2] if step < len(RECOVERY_STEPS) else "Completed",
        }
    except Exception:
        return {"frozen": False}


def try_recovery():
    """
    Check if the system can downgrade its severity.
    Called periodically (every 10 mins) by daemon loop.
    """
    current = get_system_mode()
    if current == "NORMAL":
        return

    try:
        recovery_ts = matrix.get("GUARDIAN", "recovery_ts")
        if not recovery_ts or int(time.time()) < int(recovery_ts):
            return

        threats = _check_active_threats()
        if not threats["any_active"]:
            target = {"LOCKDOWN": "SURVIVAL", "SURVIVAL": "CAUTION", "CAUTION": "NORMAL"}[current]
            matrix.set("GUARDIAN", "system_mode", target)
            matrix.set("GUARDIAN", "mode_reason", "Auto-recovery: no threats")
            matrix.set("GUARDIAN", "recovery_ts", int(time.time()) + CB_RECOVERY_AFTER_SEC)
            log.info(f"[RECOVERY] {current} → {target}")
            _tele_alert(f"🌱 Auto-recovery triggered: {current} → {target} (No active threats detected)")
        else:
            matrix.set("GUARDIAN", "recovery_ts", int(time.time()) + CB_RECOVERY_AFTER_SEC)
    except Exception:
        pass


def _check_active_threats() -> dict:
    """Check currently active threats."""
    threats = []

    try:
        sat = matrix.get("GUARDIAN", "redis_sat")
        if sat and float(sat) > REDIS_MSG_RATE_WARN:
            threats.append(f"Redis saturation: {sat}")

        if matrix.get("GUARDIAN", "narrative_freeze"):
            threats.append("Narrative freeze")

        for cb_name in ["train", "a03", "chroma"]:
            cb = matrix.get("GUARDIAN", f"circuit:{cb_name}")
            if cb and cb.get("state") == "OPEN":
                threats.append(f"Circuit {cb_name}: OPEN")
    except Exception:
        pass

    return {
        "any_active": len(threats) > 0,
        "threats":    threats,
        "summary":    " | ".join(threats),
    }


# ══════════════════════════════════════════════════════════════════════════════
# P1 — RATE LIMITER (Telegram Auth Flooding)
# ══════════════════════════════════════════════════════════════════════════════

# In-memory sliding window (no Redis to avoid extra load)
_rate_windows: dict = defaultdict(deque)   # chat_id → deque of timestamps
_rate_lock = threading.Lock()


def check_telegram_rate_limit(chat_id: str) -> Tuple[bool, str]:
    """
    Check rate limit for Telegram messages.
    Uses in-memory sliding window — no Redis calls.

    Returns: (allowed: bool, reason: str)
    """
    now = time.time()
    window_sec = 60   # 1-minute sliding window

    with _rate_lock:
        # Clean old timestamps
        window = _rate_windows[chat_id]
        while window and now - window[0] > window_sec:
            window.popleft()

        # Global window
        global_window = _rate_windows["__global__"]
        while global_window and now - global_window[0] > window_sec:
            global_window.popleft()

        # Check global rate
        if len(global_window) >= TELE_RATE_LIMIT_PER_MIN_GLOBAL:
            _log_dos_event("GLOBAL_RATE_EXCEEDED",
                           f"Global: {len(global_window)} msg/minute")
            return False, "global_rate_limit"

        # Check per-chat rate
        is_owner = (str(chat_id) == str(TELEGRAM_CHAT_ID))
        limit = TELE_RATE_LIMIT_PER_MIN_CHAT if is_owner else TELE_RATE_LIMIT_UNKNOWN

        if len(window) >= limit:
            if not is_owner:
                # Unknown user exceeds rate limit -> escalate severity if frequent
                _handle_unknown_flood(chat_id, len(window))
            return False, f"chat_rate_limit ({len(window)}/{limit} per min)"

        # Allowed — record timestamp
        window.append(now)
        global_window.append(now)

    return True, ""


def _handle_unknown_flood(chat_id: str, count: int):
    """Handle unknown chat_id flooding."""
    hashed_id = hashlib.sha256(str(chat_id).encode()).hexdigest()[:8]
    log.warning(f"[FLOOD] chat_id_hash={hashed_id} count={count}/min")
    _log_dos_event("UNKNOWN_CHAT_FLOOD", f"hash={hashed_id} count={count}")

    try:
        flood_count = matrix.incr("GUARDIAN", "unknown_flood_count")
        matrix.expire("GUARDIAN", "unknown_flood_count", 300)
        if flood_count >= 10:
            set_system_mode("CAUTION",
                            f"Auth flooding: {flood_count} unknown chats")
    except Exception:
        pass


def get_rate_stats() -> dict:
    """Return current rate statistics."""
    now = time.time()
    with _rate_lock:
        global_count = len([t for t in _rate_windows.get("__global__", [])
                            if now - t <= 60])
        chat_counts  = {k: len([t for t in v if now - t <= 60])
                        for k, v in _rate_windows.items()
                        if k != "__global__"}
    return {
        "global_per_min": global_count,
        "global_limit":   TELE_RATE_LIMIT_PER_MIN_GLOBAL,
        "chat_counts":    chat_counts,
    }


# ══════════════════════════════════════════════════════════════════════════════
# P2 — CIRCUIT BREAKER (VRAM GPU Deadlock Protection)
# ══════════════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """
    Circuit Breaker pattern for heavy tasks.
    States: CLOSED (normal) -> OPEN (error status) -> HALF_OPEN (retry)

    CLOSED: Allows all requests.
    OPEN: Rejects all, returns fallback immediately.
    HALF_OPEN: Allows 1 test request; if successful -> CLOSED, else -> OPEN.
    """

    def __init__(self, name: str, redis_key: str):
        self.name      = name
        self.redis_key = redis_key

    def _load(self) -> dict:
        try:
            return matrix.get("GUARDIAN", f"circuit:{self.name}") or {"state": "CLOSED", "failures": 0}
        except Exception:
            return {"state": "CLOSED", "failures": 0}

    def _save(self, data: dict):
        try:
            matrix.set("GUARDIAN", f"circuit:{self.name}", data, expire=3600)
        except Exception:
            pass

    def is_open(self) -> bool:
        data = self._load()
        state = data.get("state", "CLOSED")

        if state == "OPEN":
            # Check if transition to HALF_OPEN is possible
            opened_ts = data.get("opened_ts", 0)
            if time.time() - opened_ts > CB_HALF_OPEN_AFTER_SEC:
                data["state"] = "HALF_OPEN"
                self._save(data)
                log.info(f"Circuit {self.name}: OPEN → HALF_OPEN (retry)")
                return False   # HALF_OPEN: allow 1 request
            return True        # OPEN: block

        return False   # CLOSED / HALF_OPEN: allow



    def record_failure(self, reason: str = ""):
        data = self._load()
        data["failures"] = data.get("failures", 0) + 1
        data["last_fail_reason"] = reason[:100]
        data["last_fail_ts"] = int(time.time())

        if data["failures"] >= CB_FAIL_THRESHOLD or data.get("state") == "HALF_OPEN":
            if data.get("state") != "OPEN":
                log.warning(f"Circuit {self.name}: OPEN ({data['failures']} failures)")
                _log_dos_event(f"CIRCUIT_OPEN_{self.name.upper()}", reason)
            data["state"]     = "OPEN"
            data["opened_ts"] = int(time.time())
            self._save(data)

            # Escalate system mode if necessary
            if self.name == "training":
                set_system_mode("SURVIVAL",
                                f"Circuit OPEN: {self.name} — {reason[:60]}")
            elif self.name == "a03":
                _activate_narrative_blindness("Circuit breaker: A03 failed repeatedly")
        else:
            data["state"] = "CLOSED"
            self._save(data)

    def get_state(self) -> str:
        return self._load().get("state", "CLOSED")


# Singleton circuit breakers
CB_TRAINING = CircuitBreaker("training", RK_CIRCUIT_TRAIN)
CB_A03      = CircuitBreaker("a03",      RK_CIRCUIT_A03)
CB_CHROMA   = CircuitBreaker("chroma",   RK_CIRCUIT_CHROMA)








# ══════════════════════════════════════════════════════════════════════════════
# P3 — REDIS BUS MONITOR (Saturation Detection)
# ══════════════════════════════════════════════════════════════════════════════

# Sliding window counting message rate on Redis bus
_redis_msg_window: deque = deque()
_redis_lock = threading.Lock()


def record_redis_message(channel: str, payload_bytes: int):
    """
    Called from daemon detector whenever a message is received on Redis pub/sub.
    Monitors rate and payload size.
    """
    now = time.time()

    with _redis_lock:
        _redis_msg_window.append((now, channel, payload_bytes))
        # Maintain 1-minute sliding window
        while _redis_msg_window and now - _redis_msg_window[0][0] > 60:
            _redis_msg_window.popleft()

        msg_rate = len(_redis_msg_window)

    # Check for oversized payload -> drop and log
    payload_kb = payload_bytes / 1024
    if payload_kb > REDIS_PAYLOAD_MAX_KB:
        log.warning(f"[REDIS] Oversized payload: {payload_kb:.0f}KB on {channel} — dropped")
        _log_dos_event("REDIS_OVERSIZED_PAYLOAD", f"channel={channel} size={payload_kb:.0f}KB")
        return False   # Signal: drop this message

    # Update saturation score in Matrix
    matrix.set("GUARDIAN", "redis_sat", msg_rate, ttl=120)

    # Handle based on rate
    if msg_rate >= REDIS_MSG_RATE_DANGER:
        set_system_mode("SURVIVAL",
                        f"Redis saturation: {msg_rate} msg/minute (limit {REDIS_MSG_RATE_DANGER})")
        return False   # Drop message
    elif msg_rate >= REDIS_MSG_RATE_WARN:
        set_system_mode("CAUTION",
                        f"Redis elevated: {msg_rate} msg/minute")
        # Throttle: drop all non-urgent messages
        if channel not in ("zcl:alerts:urgent", "zcl:tracker:raw"):
            return False

    return True   # OK — process message


def get_redis_saturation() -> dict:
    """Return current Redis bus status."""
    with _redis_lock:
        now = time.time()
        recent = [(ch, pb) for ts, ch, pb in _redis_msg_window if now - ts <= 60]
    rate = len(recent)
    channels = defaultdict(int)
    for ch, _ in recent:
        channels[ch] += 1
    level = ("DANGER" if rate >= REDIS_MSG_RATE_DANGER else
             "WARN"   if rate >= REDIS_MSG_RATE_WARN   else "NORMAL")
    return {
        "msg_per_min":  rate,
        "level":        level,
        "top_channels": dict(sorted(channels.items(), key=lambda x: x[1], reverse=True)[:5]),
    }


# ══════════════════════════════════════════════════════════════════════════════
# P4 — NARRATIVE BLINDNESS PROTOCOL (Saturation → Freeze A03)
# ══════════════════════════════════════════════════════════════════════════════

_narrative_critical_count: int = 0
_narrative_lock = threading.Lock()


def record_narrative_pressure(alert_level: str):
    """
    Called from narrative_guard.py after each A03 cycle.
    Counts consecutive CRITICAL cycles — if threshold is exceeded -> triggers Blindness Protocol.
    """
    global _narrative_critical_count

    with _narrative_lock:
        if alert_level in ("CRITICAL", "HIGH"):
            _narrative_critical_count += 1
        else:
            _narrative_critical_count = 0   # Reset if no pressure remains

        count = _narrative_critical_count

    if count >= NARRATIVE_CRITICAL_CYCLES:
        _activate_narrative_blindness(
            f"Narrative pressure CRITICAL consecutively for {count} cycles "
            f"({count * 30}+ minutes) — Logic DoS suspected"
        )


def _activate_narrative_blindness(reason: str):
    """
    Activate Blindness Protocol:
    - Freeze A03 for 30 minutes
    - A04 relies solely on technical analysis (A01 + A02)
    - DO NOT change min_confluence (stays 3/4) to avoid being overly conservative
    """
    already_frozen = matrix.get("GUARDIAN", "narrative_freeze")
    if already_frozen:
        return   # Already frozen

    matrix.set("GUARDIAN", "narrative_freeze", json.dumps({
        "reason":     reason[:200],
        "frozen_ts":  int(time.time()),
        "expires_ts": int(time.time()) + NARRATIVE_FREEZE_SEC,
    }), ttl=NARRATIVE_FREEZE_SEC)

    log.warning(f"[BLINDNESS PROTOCOL] {reason[:80]}")
    _log_dos_event("NARRATIVE_BLINDNESS_ACTIVATED", reason)
    set_system_mode("CAUTION",
                    f"Blindness Protocol: {reason[:60]}")


def is_a03_frozen() -> Tuple[bool, str]:
    """
    Check if A03 is currently frozen.
    Called by social_crawler.py and elliott_wyckoff_brain.py before using A03 data.
    """
    # SURVIVAL+ level -> A03 completely bypassed
    mode = get_system_mode()
    if mode in ("SURVIVAL", "LOCKDOWN"):
        return True, f"System mode {mode}: A03 bypassed"

    # Check Blindness Protocol
    freeze_raw = matrix.get("GUARDIAN", "narrative_freeze")
    if not freeze_raw:
        return False, ""

    try:
        if isinstance(freeze_raw, str):
            freeze = json.loads(freeze_raw)
        else:
            freeze = freeze_raw
        expires = freeze.get("expires_ts", 0)
        if time.time() < expires:
            remaining = int((expires - time.time()) / 60)
            return True, f"Blindness Protocol active — {remaining}m remaining"
    except Exception:
        pass

    # Expired -> delete
    matrix.delete("GUARDIAN", "narrative_freeze")
    return False, ""


def get_a03_weight_multiplier() -> float:
    """
    Return weight reduction factor for A03 based on system mode.
    Used when calculating MM Fingerprint and confluence.
    """
    mode = get_system_mode()
    if mode in ("SURVIVAL", "LOCKDOWN"):
        return 0.0   # A03 completely unweighted
    if mode == "CAUTION":
        return 0.5   # Reduce by 50%
    return 1.0       # Normal


# ══════════════════════════════════════════════════════════════════════════════
# P5 — CHROMADB WRITE THROTTLE
# ══════════════════════════════════════════════════════════════════════════════

_chroma_write_window: deque = deque()
_chroma_alien_window: deque = deque()
_chroma_lock = threading.Lock()


def check_chroma_write_allowed(doc_type: str = "unknown") -> Tuple[bool, str]:
    """
    Check if writing to ChromaDB is allowed.
    Limits write rate and alien documents.
    """
    if CB_CHROMA.is_open():
        return False, "Circuit breaker CHROMA: OPEN"

    now = time.time()

    with _chroma_lock:
        # Clean old window
        while _chroma_write_window and now - _chroma_write_window[0] > 60:
            _chroma_write_window.popleft()
        while _chroma_alien_window and now - _chroma_alien_window[0] > 300:  # 5m
            _chroma_alien_window.popleft()

        write_rate = len(_chroma_write_window)
        alien_rate = len(_chroma_alien_window)

        # Check alien document rate
        allowed_types = {"ly_thuyet", "lich_su_binance", "dpo_chosen", "dpo_rejected"}
        if doc_type not in allowed_types:
            _chroma_alien_window.append(now)
            alien_rate += 1
            if alien_rate >= CHROMA_ALIEN_THRESHOLD:
                CB_CHROMA.record_failure(f"Alien doc flood: {alien_rate} docs within 5m")
                return False, f"Alien doc rate: {alien_rate}/{CHROMA_ALIEN_THRESHOLD} within 5m"
            return False, f"Alien doc type: '{doc_type}' not allowed"

        # Check write rate
        if write_rate >= CHROMA_WRITE_RATE_LIMIT:
            _log_dos_event("CHROMA_RATE_EXCEEDED", f"{write_rate} writes/minute")
            return False, f"ChromaDB write rate: {write_rate}/{CHROMA_WRITE_RATE_LIMIT} per min"

        _chroma_write_window.append(now)

    return True, ""


# ══════════════════════════════════════════════════════════════════════════════
# AGENT BEHAVIOR MAP — What each agent does in each mode
# ══════════════════════════════════════════════════════════════════════════════

"""
AGENT BEHAVIOR MAP (for agents to query operational guidelines):

MODE: NORMAL
  A01 (Binance Hound)  : Fully active — 30s scan, cross-validate CoinGecko
  A02 (Macro Phantom)  : Fully active — 15m scan
  A03 (Social Crawler) : Fully active — weight = 1.0
  A04 (Brain)          : Fully active — Qwen3 + RAG + A03 data
  A05 (Judge)          : Fully active — 4h judge, MM consensus ≥2/3
  ChromaDB             : Write allowed

MODE: CAUTION
  A01: Fully active
  A02: Fully active
  A03: Active but weight = 0.5 (reduced influence)
  A04: Elevate min_confluence to 4/4, skepticism threshold reduced
  A05: MM consensus requires 3/3 (instead of 2/3)
  ChromaDB: Write throttled

MODE: SURVIVAL  ← "Small fish hiding"
  A01: Fully active (core data, irreplaceable)
  A02: Fully active (core data, irreplaceable)
  A03: BYPASS completely — do not call, do not use cached data
  A04: Technical-only mode — only use A01+A02, pure Wyckoff
       No new positions — only monitor open positions
       RAG still active (read-only, no write)
  A05: No new recommendations (DUNG_NGOAI_QUAN_SAT mandatory)
       Still monitor drawdown of open positions
  A09: Increase scan frequency to every 5 minutes

MODE: LOCKDOWN  ← "Complete shutdown"
  A01: Fully active (irreplaceable)
  A02: Fully active (irreplaceable)
  A03: BYPASS
  A04: BYPASS completely — do not call Qwen3
  A05: Only monitor SL of open positions, no new judgments
  A06: Alert Master of LOCKDOWN immediately, continue monitoring open positions
  A07: Send LOCKDOWN report to Ha Ngung Thuong
  A09: Full scan every 2 minutes
"""


def get_agent_instructions(agent_id: str) -> dict:
    """
    Return behavioral guidelines for each agent based on current mode.
    Each agent calls this function at the start of each cycle.
    """
    mode = get_system_mode()
    a03_frozen, freeze_reason = is_a03_frozen()

    base = {
        "mode":           mode,
        "a03_frozen":     a03_frozen,
        "freeze_reason":  freeze_reason,
        "a03_weight":     get_a03_weight_multiplier(),
        "allow_new_recs": mode not in ("SURVIVAL", "LOCKDOWN"),
        "allow_training": mode not in ("SURVIVAL", "LOCKDOWN"),
        "allow_swap":     mode not in ("SURVIVAL", "LOCKDOWN"),
        "chroma_write":   mode != "LOCKDOWN",
        "min_confluence": 4 if mode in ("CAUTION",) else 3,
        "mm_consensus_min": 3 if mode == "CAUTION" else 2,
    }

    # Specific instructions for each agent
    if agent_id == "04":
        base.update({
            "use_a03_data":    not a03_frozen and mode not in ("SURVIVAL", "LOCKDOWN"),
            "technical_only":  mode in ("SURVIVAL", "LOCKDOWN"),
            "rag_write":       mode not in ("LOCKDOWN"),
            "rag_read":        True,   # Always allow reading RAG
            "action":          ("DUNG_NGOAI_QUAN_SAT" if mode in ("SURVIVAL", "LOCKDOWN")
                                else "NORMAL"),
        })
    elif agent_id == "05":
        base.update({
            "allow_new_judge": mode != "LOCKDOWN",
            "monitor_open_sl": True,   # Always monitor SL
            "quarantine_threshold": 30 if mode == "CAUTION" else 40,
        })
    elif agent_id == "03":
        base.update({
            "should_skip": a03_frozen or mode in ("SURVIVAL", "LOCKDOWN"),
            "weight":      get_a03_weight_multiplier(),
        })
    return base


# ══════════════════════════════════════════════════════════════════════════════
# INTERNAL UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _log_dos_event(event_type: str, detail: str = ""):
    """Record DoS event into Redis list (retains 200 events)."""
    entry = {
        "ts":    int(time.time()),
        "type":  event_type,
        "detail": detail[:200],
    }
    try:
        matrix.lpush("GUARDIAN", "dos_events", entry, max_len=200)
    except Exception:
        pass
    log.warning(f"[DOS_EVENT] {event_type}: {detail[:80]}")


def _tele_alert(msg: str):
    """Send alert via Telegram."""
    if not (TELEGRAM_BOT and TELEGRAM_CHAT_ID):
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"[DOS GUARDIAN]\n{msg}",
                  "parse_mode": "Markdown"},
            timeout=8,
        )
    except Exception:
        pass


def get_status_report() -> dict:
    """Full status report — used by A07 and CLI."""
    mode = get_system_mode()

    rate_stats   = get_rate_stats()
    redis_sat    = get_redis_saturation()
    a03_frozen, fr = is_a03_frozen()
    threats      = _check_active_threats()

    cb_states = {}
    for name, cb in [("training", CB_TRAINING), ("a03", CB_A03), ("chroma", CB_CHROMA)]:
        cb_states[name] = cb.get_state()

    # Recent DoS events
    recent_events = []
    try:
        raw_events = matrix.lrange("GUARDIAN", "dos_events", 0, 9)
        for e in raw_events:
            if isinstance(e, dict):
                recent_events.append(e)
            elif isinstance(e, str):
                recent_events.append(json.loads(e))
    except Exception:
        pass

    return {
        "system_mode":       mode,
        "mode_icon":         MODE_ICONS.get(mode, "⚪"),
        "a03_frozen":        a03_frozen,
        "freeze_reason":     fr,
        "a03_weight":        get_a03_weight_multiplier(),
        "telegram_rate":     rate_stats,
        "redis_saturation":  redis_sat,
        "circuit_breakers":  cb_states,
        "active_threats":    threats,
        "recent_events":     recent_events[:5],
        "timestamp":         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# DAEMON — Background monitoring loop
# ══════════════════════════════════════════════════════════════════════════════

def run_monitoring_daemon(interval_sec: int = 60):
    """
    Background thread: monitors and triggers recovery.
    Called from immunity_core.py daemon mode.
    """
    import threading
    log.info("DoS Guardian daemon started")

    def _loop():
        while True:
            try:
                # Try recovery each interval
                try_recovery()

                # Check actual Redis saturation
                sat_raw = matrix.get("GUARDIAN", "redis_sat")
                if sat_raw:
                    sat = float(sat_raw)
                    if sat >= REDIS_MSG_RATE_DANGER:
                        set_system_mode("SURVIVAL",
                                        f"Redis sat daemon: {sat:.0f} msg/min")
                    elif sat >= REDIS_MSG_RATE_WARN and get_system_mode() == "NORMAL":
                        set_system_mode("CAUTION",
                                        f"Redis sat elevated: {sat:.0f} msg/min")

                # Push status to Matrix for A07
                status = get_status_report()
                matrix.set("GUARDIAN", "status", {
                    "mode":     status["system_mode"],
                    "threats":  status["active_threats"]["summary"],
                    "ts":       int(time.time()),
                }, ttl=300)

            except Exception as e:
                log.error(f"Guardian daemon error: {e}")

            time.sleep(interval_sec)

    t = threading.Thread(target=_loop, daemon=True, name="DosGuardianDaemon")
    t.start()
    return t


def get_system_status() -> str:
    """
    Return Markdown string to send via Telegram.
    Used by telegram_butler.py for 'protection status' command.
    """
    s    = get_status_report()
    icon = s["mode_icon"]
    mode = s["system_mode"]
    cb   = s["circuit_breakers"]
    rd   = s["redis_saturation"]
    tele = s["telegram_rate"]
    thr  = s["active_threats"]

    cb_lines = "\n".join(
        f"  • {k}: {'🔴 OPEN' if v == 'OPEN' else '🟡 HALF_OPEN' if v == 'HALF_OPEN' else '🟢 CLOSED'}"
        for k, v in cb.items()
    )

    events_str = ""
    for ev in s["recent_events"][:3]:
        ts = datetime.fromtimestamp(ev["ts"], tz=timezone.utc).strftime("%H:%M")
        events_str += f"\n  `[{ts}]` {ev['type']}: {ev['detail'][:50]}"

    return (
        f"{icon} *DoS Guardian — {mode}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 *Telegram:* {tele['global_per_min']}/{TELE_RATE_LIMIT_PER_MIN_GLOBAL} msg/min\n"
        f"🗄️ *Redis bus:* {rd['msg_per_min']} msg/min ({rd['level']})\n"
        f"🔌 *Circuit Breakers:*\n{cb_lines}\n"
        f"🧠 *A03 frozen:* {'Yes ⚠️ — ' + s['freeze_reason'][:50] if s['a03_frozen'] else 'No ✅'}\n"
        f"🎯 *A03 weight:* {s['a03_weight']:.0%}\n"
        f"⚠️ *Threats:* {thr['summary'] or 'None'}\n"
        f"{('📋 *Recent Events:*' + events_str) if events_str else ''}\n"
        f"_Updated: {s['timestamp']}_"
    )


def reset_guardian():
    """
    Reset entire DoS Guardian to NORMAL.
    Clears all circuit breakers, narrative freeze, and flood counters.
    Used by telegram_butler.py 'reset guardian' command (CRITICAL level).
    """
    matrix.set("GUARDIAN", "system_mode", "NORMAL")
    matrix.set("GUARDIAN", "mode_reason", "Manual reset by Master")
    matrix.set("GUARDIAN", "mode_ts", int(time.time()))
    matrix.delete("GUARDIAN", "narrative_freeze")
    matrix.delete("GUARDIAN", "circuit:train")
    matrix.delete("GUARDIAN", "circuit:a03")
    matrix.delete("GUARDIAN", "circuit:chroma")
    matrix.delete("GUARDIAN", "recovery_ts")
    matrix.delete("GUARDIAN", "unknown_flood_count")
    matrix.delete("GUARDIAN", "redis_sat")
    matrix.set("GUARDIAN", "infra_mode", "HYBRID")
    matrix.delete("GUARDIAN", "frozen_since")

    # Reset in-memory windows
    global _narrative_critical_count
    with _narrative_lock:
        _narrative_critical_count = 0
    with _chroma_lock:
        _chroma_write_window.clear()
        _chroma_alien_window.clear()
    with _rate_lock:
        _rate_windows.clear()
    with _redis_lock:
        _redis_msg_window.clear()

    log.info("[GUARDIAN RESET] Entire DoS Guardian has reset to NORMAL")
    _log_dos_event("MANUAL_RESET", "Reset by Master via Telegram")


# ══════════════════════════════════════════════════════════════════════════════
# P3 — FILE INTEGRITY MONITORING (FIM) — Legacy from Imperial Shield
# DNA v16.8: Shield merged into Guardian. FIM monitors sensitive file changes.
# ══════════════════════════════════════════════════════════════════════════════

FIM_TARGETS = [
    "tools/imperial_state.py",
    "tools/imperial_brain.py",
    "tools/dos_guardian.py",
    "tools/llm_router.py",
    "tools/binance_hound.py",
    "tools/telegram_butler.py",
    "agents/logic/a05_evaluator.py",
    "agents/logic/a09_immunity.py",
    "config/.env",
    "docker-compose.yml",
    "TOOL_REGISTRY.md",
    "AGENTS.md",
]

def _hash_file(filepath: str) -> str:
    """SHA-256 hash prefix (16 hex chars) of the file."""
    try:
        full_path = BASE_DIR / filepath
        if not full_path.exists():
            return "MISSING"
        return hashlib.sha256(full_path.read_bytes()).hexdigest()[:16]
    except Exception:
        return "ERROR"


def verify_fim_integrity() -> list:
    """Compare current hash with stored manifest.
    
    Returns:
        list: Violations list (list of dict). Empty = all OK.
    """
    stored = matrix.get("GUARDIAN", "fim:manifest")
    if not stored:
        log.warning("[FIM] No manifest in Redis yet")
        return [{"file": "SYSTEM", "expected": "manifest", "actual": "MISSING", "severity": "WARN"}]
    
    violations = []
    for target, expected_hash in stored.items():
        current_hash = _hash_file(target)
        if current_hash != expected_hash:
            severity = "CRITICAL" if target in ["config/.env", "docker-compose.yml", "AGENTS.md"] else "HIGH"
            violations.append({
                "file": target,
                "expected": expected_hash,
                "actual": current_hash,
                "severity": severity
            })
    
    if violations:
        log.warning(f"[FIM] ⚠️ {len(violations)} integrity violations!")
        _log_dos_event("FIM_VIOLATION", str([v["file"] for v in violations]))
        
        # Auto-upgrade System Mode if sensitive files are modified without authorization
        critical_count = sum(1 for v in violations if v["severity"] == "CRITICAL")
        if critical_count > 0:
            current_mode = get_system_mode()
            if current_mode == "NORMAL":
                set_system_mode("CAUTION", f"FIM: {critical_count} critical file(s) modified without authorization")
    else:
        log.info("[FIM] ✅ All files are intact.")
    
    return violations


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DoS Guardian — Zero-Cutloss Empire")
    parser.add_argument("--status",   action="store_true", help="View current status")
    parser.add_argument("--set-mode", type=str, choices=["NORMAL","CAUTION","SURVIVAL","LOCKDOWN"],
                        help="Manually set mode")
    parser.add_argument("--reason",   type=str, default="Manual override", help="Reason for setting mode")
    parser.add_argument("--reset",    action="store_true", help="Reset to NORMAL (force)")
    parser.add_argument("--events",   action="store_true", help="View 20 most recent DoS events")
    args = parser.parse_args()

    if args.reset:
        reset_guardian()
        print("✅ Reset to NORMAL and cleared all circuit breakers")
    elif args.set_mode:
        set_system_mode(args.set_mode, args.reason)
        print(f"✅ Mode set: {args.set_mode} ({args.reason})")
    elif args.events:
        events = matrix.lrange("GUARDIAN", "dos_events", 0, 19)
        print(f"\nDoS Events (20 most recent):")
        for e in events:
            try:
                d = e if isinstance(e, dict) else json.loads(e)
                ts = datetime.fromtimestamp(d['ts'], tz=timezone.utc).strftime('%H:%M')
                print(f"  [{ts}] {d['type']}: {d['detail'][:70]}")
            except Exception:
                pass
    else:
        status = get_status_report()
        icon = status["mode_icon"]
        print(f"\n{icon} System Mode: {status['system_mode']}")
        print(f"A03 frozen: {status['a03_frozen']} ({status['freeze_reason'] or 'N/A'})")
        print(f"A03 weight: {status['a03_weight']:.0%}")
        print(f"Telegram: {status['telegram_rate']['global_per_min']}/{TELE_RATE_LIMIT_PER_MIN_GLOBAL} msg/min")
        print(f"Redis: {status['redis_saturation']['msg_per_min']} msg/min ({status['redis_saturation']['level']})")
        print(f"Circuit breakers: {status['circuit_breakers']}")
        print(f"Active threats: {status['active_threats']['summary'] or 'None'}")
        if status["recent_events"]:
            print("\nRecent events:")
            for ev in status["recent_events"]:
                ts = datetime.fromtimestamp(ev['ts'], tz=timezone.utc).strftime('%H:%M')
                print(f"  [{ts}] {ev['type']}: {ev['detail'][:60]}")
