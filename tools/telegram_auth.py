"""
🧬 DNA: v16.1
🏢 UNIT: DIRECTOR (A06)
🛠️ ROLE: Multi-factor Authentication Sentinel
📖 DESC: 3-tier authentication system (ChatID, TOTP, Challenge-Response) protecting Swarm from SIM swap and hijacking.
🔗 CALLS: tools/imperial_state.py
🛡️ INTEGRITY: Organic Ecosystem - Immutable

SECURITY PRINCIPLE:
  An attacker gaining access to the Owner's Telegram (SIM swap, session hijack)
  will NOT be able to execute critical commands because TOTP code from a physical device is required.
"""

import os
import re
import time
import hmac
import hashlib
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from pathlib import Path

import requests
try:
    from tools.imperial_state import matrix
except ImportError:
    from imperial_state import matrix
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../config/.env'))

# ── Secrets (read from .env) ─────────────────────────────────────────────────────
# TELEGRAM_TOTP_SECRET: Base32 string for pyotp, e.g.: "JBSWY3DPEHPK3PXP"
#   Generate: python -c "import pyotp; print(pyotp.random_base32())"
#   Then scan QR into Google Authenticator
TOTP_SECRET          = os.getenv("TELEGRAM_TOTP_SECRET", "")
CHALLENGE_SECRET     = os.getenv("TELEGRAM_CHALLENGE_SECRET", "")  # 32+ chars random
CRITICAL_CONFIRM_WORD = os.getenv("TELEGRAM_CRITICAL_CONFIRM", "")  # custom word set by the Owner
TELEGRAM_CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_GROUP_ID_COMMON = os.getenv("TELEGRAM_GROUP_ID_COMMON", "")
TELEGRAM_GROUP_ID_ELITE  = os.getenv("TELEGRAM_GROUP_ID_ELITE", "")
REDIS_URL            = os.getenv("REDIS_URL", "redis://zcl_redis:6379")

BASE_DIR  = Path(__file__).parent.parent
LOG_FILE  = BASE_DIR / "logs" / "telegram_auth.log"
LOG_FILE.parent.mkdir(exist_ok=True)

log = logging.getLogger("TELEGRAM_AUTH")
if not log.handlers:
    log.setLevel(logging.INFO)
    log.addHandler(logging.FileHandler(str(LOG_FILE)))
    log.addHandler(logging.StreamHandler())

# ── Constants ────────────────────────────────────────────────────────────────
SESSION_DURATION_SECONDS  = 1800    # 30 minutes after TOTP verification
CHALLENGE_VALID_SECONDS   = 90      # Challenge expires after 90 seconds
MAX_FAIL_ATTEMPTS         = 3       # After 3 failures -> lockout
LOCKOUT_DURATION_SECONDS  = 900     # Lockout 15 minutes
TOTP_VALID_WINDOW         = 1       # ±1 interval (30s each side) — allow clock drift

# No more legacy Redis keys, using Matrix namespaces

# ══════════════════════════════════════════════════════════════════════════════
# COMMAND REGISTRY — Each command has access level and handler
# ══════════════════════════════════════════════════════════════════════════════

COMMAND_REGISTRY = {
    # ── READ — No auth required ─────────────────────────────────────────────────
    "status":              {"level": "READ",     "handler": "handle_status"},
    "model status":        {"level": "READ",     "handler": "handle_model_status"},
    "report":              {"level": "READ",     "handler": "handle_report"},
    "security report":     {"level": "READ",     "handler": "handle_security_report"},
    "log":                 {"level": "READ",     "handler": "handle_log"},
    "price":               {"level": "READ",     "handler": "handle_price"},
    "command list":        {"level": "READ",     "handler": "handle_command_list"},
    "help":                {"level": "READ",     "handler": "handle_help"},

    # ── WRITE — TOTP required ──────────────────────────────────────────────────────
    "inject pairs":        {"level": "WRITE",    "handler": "handle_inject_pairs"},
    "train":               {"level": "WRITE",    "handler": "handle_train"},
    "pause":               {"level": "WRITE",    "handler": "handle_pause_agent04"},
    "resume":              {"level": "WRITE",    "handler": "handle_resume_agent04"},
    "update soul":         {"level": "WRITE",    "handler": "handle_update_soul"},
    "view quarantine":     {"level": "WRITE",    "handler": "handle_view_quarantine"},
    "approve quarantine":  {"level": "WRITE",    "handler": "handle_approve_quarantine"},

    # ── CRITICAL — TOTP + confirmation word required ─────────────────────────────
    "swap model":          {"level": "CRITICAL", "handler": "handle_swap_model"},
    "shutdown system":     {"level": "CRITICAL", "handler": "handle_shutdown"},
    "reset session":       {"level": "CRITICAL", "handler": "handle_reset_session"},
    "clear lockout":       {"level": "CRITICAL", "handler": "handle_clear_lockout"},
    "lock system":         {"level": "CRITICAL", "handler": "handle_emergency_lock"},

    # ── DOS GUARDIAN (NEW) ───────────────────────────────────────────────────
    "guardian status":     {"level": "READ",     "handler": "handle_guardian_status"},
    "reset guardian":      {"level": "CRITICAL", "handler": "handle_guardian_reset"},
    "safe mode":           {"level": "WRITE",    "handler": "handle_guardian_mode"},
    "update":              {"level": "WRITE",    "handler": "handle_fim_authorize"},
    "decrypt vault":       {"level": "CRITICAL", "handler": "handle_decrypt_vault"},
    "extend survival":     {"level": "WRITE",    "handler": "handle_extend_survival"},
}

# ── Special commands (auth flow) — no CHAT_ID check required ──────────────────
AUTH_FLOW_COMMANDS = {"!challenge", "!verify", "!status-auth", "!unlock"}


# ══════════════════════════════════════════════════════════════════════════════
# REDIS HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _get_redis():
    """Compatibility wrapper — returns raw Redis client from matrix singleton."""
    return matrix._client


# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _log_auth_event(event_type: str, success: bool, detail: str = "", chat_id: str = ""):
    """Record every auth event in log and Redis (audit trail)"""
    entry = {
        "ts":         int(time.time()),
        "ts_readable": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "event_type": event_type,
        "success":    success,
        "chat_id_hash": hashlib.sha256(str(chat_id).encode()).hexdigest()[:8],  # Hash chat_id, do not log real ID
        "detail":     detail[:200],
    }
    log.info(f"AUTH {event_type}: {'OK' if success else 'FAIL'} — {detail[:80]}")

    # Push to Matrix audit log (keep 100 most recent events)
    try:
        matrix.lpush("AUTH", "event_log", entry)
        matrix.ltrim("AUTH", "event_log", 0, 99)
    except Exception:
        pass

    # Alert immediately if it is a dangerous event
    if not success and event_type in ("TOTP_FAIL", "LOCKOUT_TRIGGERED", "WRONG_CHAT_ID",
                                       "REPLAY_ATTACK", "CRITICAL_FAIL"):
        _tele_alert_security(event_type, detail)


def _tele_alert_security(event_type: str, detail: str):
    """Send security alert to the Owner via Telegram"""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    emoji = {
        "TOTP_FAIL":        "⚠️",
        "LOCKOUT_TRIGGERED": "🔒",
        "WRONG_CHAT_ID":    "🚨",
        "REPLAY_ATTACK":    "🔄",
        "CRITICAL_FAIL":    "🔴",
    }.get(event_type, "⚠️")
    msg = (f"{emoji} *SECURITY ALERT*\n"
           f"Event: `{event_type}`\n"
           f"Time: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
           f"Detail: {detail[:150]}")
    try:
        import httpx
        with httpx.Client(timeout=10.0) as client:
            client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
            )
    except Exception as e:
        log.error(f"Send security alert failed (httpx): {e}")


def _send_reply(text: str, parse_mode: str = "Markdown", incoming_chat_id: str = None):
    """Send reply message to the Owner"""
    target_chat = incoming_chat_id if incoming_chat_id else TELEGRAM_CHAT_ID
    if not (TELEGRAM_BOT_TOKEN and target_chat):
        return
    try:
        import httpx
        with httpx.Client(timeout=10.0) as client:
            client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": target_chat, "text": text, "parse_mode": parse_mode}
            )
    except Exception as e:
        log.error(f"Send reply failed (httpx): {e}")


# ══════════════════════════════════════════════════════════════════════════════
# LOCKOUT AND RATE LIMITING
# ══════════════════════════════════════════════════════════════════════════════

def _is_locked_out() -> Tuple[bool, int]:
    """
    Check if system is currently locked out.
    Returns: (is_locked, seconds_remaining)
    """
    try:
        lockout_until = matrix.get("AUTH", "lockout_until")
        if lockout_until:
            remaining = int(lockout_until) - int(time.time())
            if remaining > 0:
                return True, remaining
    except Exception:
        pass
    return False, 0


def _record_fail_attempt() -> int:
    """Record 1 failure attempt. Returns total failures. Triggers lockout if limit reached."""
    try:
        count = matrix.incr("AUTH", "fail_count")
        matrix.expire("AUTH", "fail_count", 3600)  # Reset after 1h without new failures

        if count >= MAX_FAIL_ATTEMPTS:
            lockout_until = int(time.time()) + LOCKOUT_DURATION_SECONDS
            matrix.set("AUTH", "lockout_until", lockout_until, expire=LOCKOUT_DURATION_SECONDS)
            matrix.delete("AUTH", "fail_count")
            _log_auth_event("LOCKOUT_TRIGGERED", False,
                            f"Lockout {LOCKOUT_DURATION_SECONDS//60} minutes after {count} failures")
            _send_reply(f"🔒 System locked for {LOCKOUT_DURATION_SECONDS//60} minutes due to {count} consecutive failed authentication attempts.")
        return count
    except Exception:
        return 1


def _reset_fail_count():
    """Reset fail counter after successful authentication."""
    try:
        matrix.delete("AUTH", "fail_count")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# TIER 1 AUTHENTICATION — CHAT_ID (cannot be bypassed)
# ══════════════════════════════════════════════════════════════════════════════

def verify_authority(incoming_chat_id: str, incoming_user_id: Optional[str] = None) -> bool:
    """
    Tier 1: Verify control authority.
    - If private chat: chat_id must match TELEGRAM_CHAT_ID.
    - If Group: chat_id must belong to ALLOWED_GROUPS and user_id must match TELEGRAM_CHAT_ID.
    """
    if not TELEGRAM_CHAT_ID:
        log.warning("TELEGRAM_CHAT_ID not set — reject all")
        return False

    chat_id_str = str(incoming_chat_id).strip()
    owner_id_str = str(TELEGRAM_CHAT_ID).strip()
    group_id_str = str(TELEGRAM_GROUP_ID_COMMON).strip()

    # Case A: Private chat with the Owner
    if chat_id_str == owner_id_str:
        return True

    # Case B: Owner messaging in Authorized Group
    if group_id_str and chat_id_str == group_id_str:
        if incoming_user_id and str(incoming_user_id).strip() == owner_id_str:
            return True
        else:
            _log_auth_event("WRONG_USER_IN_GROUP", False,
                            f"Stranger ({incoming_user_id}) tried to issue commands in the group", incoming_chat_id)
            return False

    log.info(f"DEBUG AUTH: Incoming Chat ID={chat_id_str}, Target={owner_id_str}, Group={group_id_str}")
    _log_auth_event("WRONG_CHAT_ID", False,
                    f"Chat ID not allowed: {chat_id_str}", incoming_chat_id)
    return False


# ══════════════════════════════════════════════════════════════════════════════
# TIER 2 AUTHENTICATION — TOTP (requires physical device)
# ══════════════════════════════════════════════════════════════════════════════

def verify_totp(code: str, chat_id: str = "") -> Tuple[bool, str]:
    """
    Tier 2: Authenticate TOTP code from Google Authenticator.

    Anti-replay attack: each TOTP code can only be used once within the window.
    Anti-brute force: integrated with lockout mechanism.

    Returns: (success, reason_if_failed)
    """
    if not TOTP_SECRET:
        return False, "TOTP not configured (TELEGRAM_TOTP_SECRET not set in .env)"

    # Check lockout
    locked, remaining = _is_locked_out()
    if locked:
        return False, f"System is locked, remaining {remaining//60}m {remaining%60}s"

    # Validate format: must be 6 digits
    code = str(code).strip()
    if not re.match(r"^\d{6}$", code):
        _record_fail_attempt()
        _log_auth_event("TOTP_FAIL", False, f"Code incorrect format: '{code[:10]}'", chat_id)
        return False, "TOTP code must be 6 digits"

    # Anti-replay: check if code has been used
    try:
        if matrix.get("AUTH", f"used_totp:{code}"):
            _log_auth_event("REPLAY_ATTACK", False,
                            f"TOTP code {code} was already used — replay attack!", chat_id)
            _record_fail_attempt()
            return False, "This TOTP code has been used. Please wait for a new code from Google Authenticator."
    except Exception:
        pass

    # TOTP verification
    try:
        import pyotp
        totp = pyotp.TOTP(TOTP_SECRET)
        is_valid = totp.verify(code, valid_window=TOTP_VALID_WINDOW)

        if is_valid:
            # Mark code as used (TTL = 90s)
            try:
                matrix.set("AUTH", f"used_totp:{code}", "1", expire=90)
            except Exception:
                pass
            _reset_fail_count()
            _log_auth_event("TOTP_SUCCESS", True, "TOTP authenticated successfully", chat_id)
            return True, ""
        else:
            count = _record_fail_attempt()
            remaining_attempts = MAX_FAIL_ATTEMPTS - count
            msg = f"Invalid TOTP code. {max(0, remaining_attempts)} attempts remaining before lockout."
            _log_auth_event("TOTP_FAIL", False, f"Wrong code, attempt {count}/{MAX_FAIL_ATTEMPTS}", chat_id)
            return False, msg

    except ImportError:
        return False, "pyotp not installed: pip install pyotp"
    except Exception as e:
        log.error(f"TOTP verification error: {e}")
        return False, f"Authentication error: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def _create_session(chat_id: str) -> str:
    """Create session token after successful TOTP verification."""
    session_token = hashlib.sha256(
        f"{chat_id}:{time.time()}:{TOTP_SECRET}".encode()
    ).hexdigest()[:32]

    try:
        session_data = {
            "token":       session_token,
            "chat_id":     chat_id,
            "created_ts":  int(time.time()),
            "expires_ts":  int(time.time()) + SESSION_DURATION_SECONDS,
        }
        matrix.set("AUTH", f"session:{chat_id}", session_data, expire=SESSION_DURATION_SECONDS)
    except Exception:
        pass
    return session_token


def _check_session(chat_id: str) -> bool:
    """Check if valid session exists (used for WRITE commands after auth)."""
    try:
        session = matrix.get("AUTH", f"session:{chat_id}")
        if not session:
            return False
        return (str(session.get("chat_id")) == str(chat_id) and
                session.get("expires_ts", 0) > int(time.time()))
    except Exception:
        return False


def _get_session_remaining(chat_id: str) -> int:
    """Return remaining seconds of session (0 if none/expired)."""
    try:
        session = matrix.get("AUTH", f"session:{chat_id}")
        if not session:
            return 0
        if str(session.get("chat_id")) == str(chat_id):
            remaining = session.get("expires_ts", 0) - int(time.time())
            return max(0, remaining)
    except Exception:
        pass
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# CHALLENGE-RESPONSE — Backup when Google Auth is unavailable
# ══════════════════════════════════════════════════════════════════════════════

def generate_challenge(chat_id: str) -> str:
    """
    Generate random challenge string.
    Owner calculates HMAC(challenge, CHALLENGE_SECRET)[:8] and sends it back.
    """
    import secrets
    challenge = secrets.token_hex(4).upper()  # e.g.: "xK9mP2"

    try:
        matrix.set("AUTH", f"challenge:{chat_id}", {
            "challenge": challenge,
            "chat_id":   chat_id,
            "expires":   int(time.time()) + CHALLENGE_VALID_SECONDS,
        }, expire=CHALLENGE_VALID_SECONDS)
    except Exception:
        pass

    _log_auth_event("CHALLENGE_ISSUED", True, f"Challenge generated: {challenge}", chat_id)
    return challenge


def verify_challenge_response(response: str, chat_id: str) -> Tuple[bool, str]:
    """
    Authenticate challenge response.
    Expected: HMAC(challenge, CHALLENGE_SECRET)[:8]
    """
    if not CHALLENGE_SECRET:
        return False, "CHALLENGE_SECRET not set in .env"

    locked, remaining = _is_locked_out()
    if locked:
        return False, f"System is locked, remaining {remaining//60}m {remaining%60}s"

    rc = _get_redis()
    if not rc:
        return False, "Redis not available"

    try:
        challenge_data = matrix.get("AUTH", f"challenge:{chat_id}")
        if not challenge_data:
            return False, "No challenge waiting to be verified (expired or not generated)"

        # Check correct chat_id and not expired
        if str(challenge_data.get("chat_id")) != str(chat_id):
            return False, "Challenge does not belong to this session"
        if challenge_data.get("expires", 0) < int(time.time()):
            try: matrix.delete("AUTH", f"challenge:{chat_id}")
            except Exception: pass
            return False, "Challenge expired (90s). Generate new challenge: !challenge"

        # Calculate expected response
        challenge    = challenge_data["challenge"]
        expected     = hmac.new(
            CHALLENGE_SECRET.encode(),
            challenge.encode(),
            hashlib.sha256
        ).hexdigest()[:8]

        if hmac.compare_digest(str(response).strip().lower(), expected.lower()):
            try: matrix.delete("AUTH", f"challenge:{chat_id}")
            except Exception: pass
            _create_session(chat_id)
            _reset_fail_count()
            _log_auth_event("CHALLENGE_SUCCESS", True, "Challenge-response authenticated successfully", chat_id)
            return True, ""
        else:
            count = _record_fail_attempt()
            _log_auth_event("CHALLENGE_FAIL", False, f"Wrong response: '{response[:10]}'", chat_id)
            return False, f"Wrong response. {max(0, MAX_FAIL_ATTEMPTS - count)} attempts remaining."

    except Exception as e:
        log.error(f"Challenge verification error: {e}")
        return False, f"Error: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# TIER 3 AUTHENTICATION — CRITICAL
# ══════════════════════════════════════════════════════════════════════════════

def verify_critical_confirm_word(word: str) -> bool:
    """
    Tier 3 (only for CRITICAL commands): check confirmation word.
    This word is set by the Owner in .env, kept secret.
    Prevent: attacker having Telegram + TOTP but not knowing this word.
    """
    if not CRITICAL_CONFIRM_WORD:
        log.warning("TELEGRAM_CRITICAL_CONFIRM not set — all CRITICAL commands blocked")
        return False
    return hmac.compare_digest(str(word).strip(), str(CRITICAL_CONFIRM_WORD).strip())


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT — parse_and_authenticate()
# ══════════════════════════════════════════════════════════════════════════════

def parse_and_authenticate(
    message_text: str,
    incoming_chat_id: str,
    incoming_user_id: Optional[str] = None,
) -> dict:
    """
    Main entry point for telegram_butler.py and model_commander.py.
    Parse command, authenticate according to level, return result.

    Returns dict:
    {
        "authenticated": bool,
        "command":       str,           # Clean command name (without TOTP)
        "level":         str,           # READ / WRITE / CRITICAL
        "handler":       str,           # Handler function name
        "args":          list,          # Arguments after the command
        "reason":        str,           # Reason if rejected
        "session_remaining": int,       # Remaining seconds of session (if any)
    }
    """
    msg = message_text.strip()

    # ── Auth flow commands (no CHAT_ID check needed for !challenge) ────────────────
    if msg.lower().startswith("!challenge"):
        if verify_authority(incoming_chat_id, incoming_user_id):
            challenge = generate_challenge(incoming_chat_id)
            _send_reply(f"🔐 Challenge code: `{challenge}`\n\n"
                        f"Calculate: `HMAC('{challenge}', CHALLENGE_SECRET)[:8]`\n"
                        f"Send: `!verify <8_chars>`\n"
                        f"⏱️ Expires in {CHALLENGE_VALID_SECONDS} seconds.", incoming_chat_id=incoming_chat_id)
        return {"authenticated": False, "command": "!challenge", "level": "AUTH_FLOW",
                "handler": "", "args": [], "reason": "auth_flow", "session_remaining": 0}

    if msg.lower().startswith("!verify"):
        parts  = msg.split()
        answer = parts[1] if len(parts) > 1 else ""
        ok, reason = verify_challenge_response(answer, incoming_chat_id)
        if ok:
            remaining = _get_session_remaining(incoming_chat_id)
            _send_reply(f"✅ Authentication successful!\n"
                        f"Session valid for {remaining//60} minutes.", incoming_chat_id=incoming_chat_id)
        else:
            _send_reply(f"❌ Authentication failed: {reason}", incoming_chat_id=incoming_chat_id)
        return {"authenticated": ok, "command": "!verify", "level": "AUTH_FLOW",
                "handler": "", "args": [], "reason": reason, "session_remaining": 0}

    if msg.lower() == "!status-auth":
        if verify_authority(incoming_chat_id, incoming_user_id):
            remaining = _get_session_remaining(incoming_chat_id)
            locked, lock_remaining = _is_locked_out()
            fail_count = int(matrix.get("AUTH", "fail_count") or 0)
            status_msg = (
                f"🔐 *Auth Status*\n"
                f"Session: {str(remaining//60) + 'm ' + str(remaining%60) + 's remaining' if remaining else 'Expired'}\n"
                f"Lockout: {str(lock_remaining//60) + 'm remaining' if locked else 'No'}\n"
                f"Fail count: {fail_count}/{MAX_FAIL_ATTEMPTS}\n"
                f"TOTP: {'✅ Configured' if TOTP_SECRET else '❌ Not set'}\n"
                f"Challenge: {'✅ Configured' if CHALLENGE_SECRET else '❌ Not set'}"
            )
            _send_reply(status_msg, incoming_chat_id=incoming_chat_id)
        return {"authenticated": False, "command": "!status-auth", "level": "AUTH_FLOW",
                "handler": "", "args": [], "reason": "auth_flow", "session_remaining": 0}

    # ── Tier 1: Authority Verification (Identity + Context) ──────────────────────
    if not verify_authority(incoming_chat_id, incoming_user_id):
        return {"authenticated": False, "command": "", "level": "UNKNOWN",
                "handler": "", "args": [],
                "reason": "Insufficient control authority",
                "session_remaining": 0}

    # ── Parse command: separate command from TOTP and arguments ──────────────────────
    command_name, _, _, extra_args = _parse_command(msg)
    totp_code = ""
    confirm_word = ""

    if not command_name:
        return {"authenticated": False, "command": msg[:50], "level": "UNKNOWN",
                "handler": "", "args": [],
                "reason": "Command not recognized. Send 'command list' to view.",
                "session_remaining": 0}

    cmd_info  = COMMAND_REGISTRY.get(command_name, {})
    level     = cmd_info.get("level", "READ")
    handler   = cmd_info.get("handler", "")
    session_r = _get_session_remaining(incoming_chat_id)

    # ── READ: no auth required ──────────────────────────────────────────────────
    if level == "READ":
        return {"authenticated": True, "command": command_name, "level": level,
                "handler": handler, "args": extra_args,
                "reason": "", "session_remaining": session_r}

    # ── WRITE: TOTP or valid session required ──────────────────────────────────
    if level == "WRITE":
        # Valid session exists -> bypass TOTP requirement
        if _check_session(incoming_chat_id):
            _log_auth_event("SESSION_USED", True,
                            f"WRITE command '{command_name}' using existing session", incoming_chat_id)
            return {"authenticated": True, "command": command_name, "level": level,
                    "handler": handler, "args": extra_args,
                    "reason": "", "session_remaining": session_r}

        # New TOTP required
        if extra_args and re.match(r"^\d{6}$", extra_args[0]):
            totp_code = extra_args.pop(0)

        if not totp_code:
            _send_reply(
                f"🔑 Command `{command_name}` requires authentication.\n\n"
                f"Syntax: `{command_name} <6_digits_from_Google_Auth>`\n"
                f"Or use challenge-response: `!challenge`",
                incoming_chat_id=incoming_chat_id
            )
            return {"authenticated": False, "command": command_name, "level": level,
                    "handler": "", "args": [],
                    "reason": "TOTP required for WRITE command",
                    "session_remaining": 0}

        ok, reason = verify_totp(totp_code, incoming_chat_id)
        if not ok:
            _send_reply(f"❌ Authentication failed: {reason}", incoming_chat_id=incoming_chat_id)
            return {"authenticated": False, "command": command_name, "level": level,
                    "handler": "", "args": [], "reason": reason, "session_remaining": 0}

        # Create session after TOTP OK
        _create_session(incoming_chat_id)
        session_r = _get_session_remaining(incoming_chat_id)
        return {"authenticated": True, "command": command_name, "level": level,
                "handler": handler, "args": extra_args,
                "reason": "", "session_remaining": session_r}

    # ── CRITICAL: TOTP + confirmation word required (even with session) ─────────────────
    if level == "CRITICAL":
        if extra_args and re.match(r"^\d{6}$", extra_args[0]):
            totp_code = extra_args.pop(0)
        if extra_args:
            confirm_word = extra_args.pop(0)
            
        if not totp_code:
            _send_reply(
                f"🔴 *CRITICAL* command: `{command_name}`\n\n"
                f"Requirement: TOTP + secret confirmation word\n"
                f"Syntax: `{command_name} <6_digit_TOTP> <confirm_word>`\n\n"
                f"⚠️ This command cannot be undone. Verify carefully before execution.",
                incoming_chat_id=incoming_chat_id
            )
            return {"authenticated": False, "command": command_name, "level": level,
                    "handler": "", "args": [],
                    "reason": "TOTP required for CRITICAL command",
                    "session_remaining": session_r}

        totp_ok, totp_reason = verify_totp(totp_code, incoming_chat_id)
        if not totp_ok:
            _log_auth_event("CRITICAL_FAIL", False,
                            f"CRITICAL command '{command_name}': TOTP fail", incoming_chat_id)
            _send_reply(f"❌ CRITICAL authentication failed: {totp_reason}", incoming_chat_id=incoming_chat_id)
            return {"authenticated": False, "command": command_name, "level": level,
                    "handler": "", "args": [], "reason": totp_reason, "session_remaining": session_r}

        if not confirm_word:
            _send_reply(
                f"✅ TOTP confirmed. Secret confirmation word required to continue.\n"
                f"Syntax: `{command_name} {totp_code} <confirm_word>`",
                incoming_chat_id=incoming_chat_id
            )
            return {"authenticated": False, "command": command_name, "level": level,
                    "handler": "", "args": [],
                    "reason": "Confirmation word required for CRITICAL command",
                    "session_remaining": session_r}

        if not verify_critical_confirm_word(confirm_word):
            _log_auth_event("CRITICAL_FAIL", False,
                            f"CRITICAL command '{command_name}': wrong confirmation word", incoming_chat_id)
            _record_fail_attempt()
            _send_reply("❌ Wrong confirmation word. Command cancelled.", incoming_chat_id=incoming_chat_id)
            return {"authenticated": False, "command": command_name, "level": level,
                    "handler": "", "args": [],
                    "reason": "Wrong confirmation word",
                    "session_remaining": session_r}

        # All tiers passed
        _create_session(incoming_chat_id)
        _log_auth_event("CRITICAL_SUCCESS", True,
                        f"CRITICAL command '{command_name}' fully authenticated", incoming_chat_id)
        return {"authenticated": True, "command": command_name, "level": level,
                "handler": handler, "args": extra_args,
                "reason": "", "session_remaining": _get_session_remaining(incoming_chat_id)}

    # Undefined level fallback
    return {"authenticated": False, "command": command_name, "level": "UNKNOWN",
            "handler": "", "args": [], "reason": "Level undetermined", "session_remaining": 0}


def _parse_command(msg: str) -> Tuple[str, str, str, list]:
    """
    Parse message into (command_name, totp_code, confirm_word, extra_args).

    Example:
      "train 847291"               → ("train", "847291", "", [])
      "swap model 847291 my-word"  → ("swap model", "847291", "my-word", [])
      "report"                     → ("report", "", "", [])
      "inject pairs 123456"        → ("inject pairs", "123456", "", [])
    """
    msg_lower = msg.lower().strip()
    extra_args   = []

    # Find matching command (prefer longer command — "swap model" before "swap")
    matched_cmd = ""
    for cmd in sorted(COMMAND_REGISTRY.keys(), key=len, reverse=True):
        if msg_lower.startswith(cmd.lower()):
            matched_cmd = cmd
            break

    if not matched_cmd:
        return "", "", "", []

    # Remaining part after command name
    remainder = msg[len(matched_cmd):].strip()
    parts = remainder.split()

    return matched_cmd, "", "", parts


# ══════════════════════════════════════════════════════════════════════════════
# SETUP WIZARD — First-time configuration guide
# ══════════════════════════════════════════════════════════════════════════════

def setup_wizard():
    """First-time TOTP setup guide."""
    print("\n" + "="*60)
    print("TELEGRAM AUTH SETUP WIZARD")
    print("="*60)

    try:
        import pyotp, qrcode
    except ImportError:
        print("\nInstall dependencies first:")
        print("  pip install pyotp qrcode[pil]")
        return

    # Generate secret
    secret = pyotp.random_base32()
    totp   = pyotp.TOTP(secret)
    uri    = totp.provisioning_uri(name="ZeroCutloss", issuer_name="ZCL-Empire")

    print(f"\n1. TOTP Secret (add to .env):")
    print(f"   TELEGRAM_TOTP_SECRET={secret}")

    print(f"\n2. QR Code to scan into Google Authenticator:")
    try:
        qr = qrcode.QRCode()
        qr.add_data(uri)
        qr.make(fit=True)
        qr.print_ascii()
    except Exception:
        print(f"   URI: {uri}")

    import secrets as _secrets
    challenge_secret = _secrets.token_hex(32)
    critical_word    = _secrets.token_hex(4)

    print(f"\n3. Challenge secret (add to .env):")
    print(f"   TELEGRAM_CHALLENGE_SECRET={challenge_secret}")

    print(f"\n4. Critical confirm word (add to .env — CHANGE to your choice!):")
    print(f"   TELEGRAM_CRITICAL_CONFIRM={critical_word}  ← change to the Owner's memorable word")

    print("\n5. After adding to .env, test:")
    print("   python tools/telegram_auth.py --test")
    print("="*60)


def selftest():
    """Test auth configuration."""
    results = {}
    results["totp_secret"]       = "OK" if TOTP_SECRET else "MISSING — TELEGRAM_TOTP_SECRET not set"
    results["challenge_secret"]  = "OK" if CHALLENGE_SECRET else "MISSING — TELEGRAM_CHALLENGE_SECRET not set"
    results["critical_confirm"]  = "OK" if CRITICAL_CONFIRM_WORD else "MISSING — TELEGRAM_CRITICAL_CONFIRM not set"
    results["telegram_chat_id"]  = "OK" if TELEGRAM_CHAT_ID else "MISSING — TELEGRAM_CHAT_ID not set"

    if TOTP_SECRET:
        try:
            import pyotp
            totp = pyotp.TOTP(TOTP_SECRET)
            code = totp.now()
            ok, _ = verify_totp(code, "selftest")
            results["totp_verify"] = "OK" if ok else "FAIL — authentication not working"
        except ImportError:
            results["totp_verify"] = "MISSING — pip install pyotp"

    rc = _get_redis()
    results["redis"] = "OK" if rc and rc.ping() else "FAIL — Redis not connected"

    print(json.dumps(results, ensure_ascii=False, indent=2))
    ok_count = sum(1 for v in results.values() if v == "OK")
    print(f"\n{ok_count}/{len(results)} checks OK")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Telegram Auth — Zero-Cutloss Empire")
    parser.add_argument("--setup",   action="store_true", help="Setup wizard (generate TOTP secret)")
    parser.add_argument("--test",    action="store_true", help="Self-test configuration")
    parser.add_argument("--parse",   type=str, help="Test parse command: --parse 'train 123456'")
    args = parser.parse_args()

    if args.setup:
        setup_wizard()
    elif args.test:
        selftest()
    elif args.parse:
        cmd, totp, confirm, extras = _parse_command(args.parse)
        print(f"Command:      '{cmd}'")
        print(f"TOTP:         '{totp}'")
        print(f"Confirm word: '{confirm}'")
        print(f"Extra args:   {extras}")
        if cmd:
            info = COMMAND_REGISTRY.get(cmd, {})
            print(f"Level:        {info.get('level', 'UNKNOWN')}")
    else:
        parser.print_help()
