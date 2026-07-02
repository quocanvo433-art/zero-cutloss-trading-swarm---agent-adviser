"""
🧬 DNA: v16.6 (Sovereign Purity & N-Key Vault)
🏢 UNIT: VAULT_MANAGER
🛠️ ROLE: SECRET_GOVERNOR
📖 DESC: N-Key vault management system, multi-layer encryption (AES-256-GCM), and RAM-only socket management for Swarm.
🔗 CALLS: cryptography, tools/imperial_state.py
📟 I/O: /dev/shm/zcl_keymaster.sock (RAM), config/.vault_state
🛡️ INTEGRITY: RAM-Only-Keys, 3-Layer-Validation, AES-GCM-Auth.
"""

import os
import sys
import json
import hmac
import socket
import hashlib
import logging
import secrets
import argparse
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

# Ensure tools/ is in path for centralized logic
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR / "tools"))

from imperial_state import matrix
load_dotenv(BASE_DIR / "config" / ".env")

REDIS_URL     = os.getenv("REDIS_URL", "redis://localhost:6379")
HMAC_SECRET   = os.getenv("IMMUNITY_HMAC_SECRET", "")
OLLAMA_URL    = os.getenv("OLLAMA_URL", "http://ollama:11434")
TELEGRAM_BOT  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

# KeyMaster Unix socket — inside /dev/shm (RAM disk)
KEYMASTER_SOCKET = "/dev/shm/zcl_keymaster.sock"
VAULT_SALT_FILE  = BASE_DIR / "config" / ".vault_salt"
VAULT_STATE_FILE = BASE_DIR / "config" / ".vault_state"  # "LOCKED" or "UNLOCKED"

# Inbox directory for update files when LOCKED
VAULT_UPDATE_DIR = BASE_DIR / "inbox" / "vault_updates"
VAULT_UPDATE_DIR.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("VAULT")
if not log.handlers:
    log.setLevel(logging.INFO)
    try:
        fh = logging.FileHandler(str(BASE_DIR / "logs" / "vault.log"))
        fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
        log.addHandler(fh)
    except (PermissionError, FileNotFoundError):
        pass
    log.addHandler(logging.StreamHandler())

# ── Files to encrypt when switching to LOCKED ──────────────────────────────────
SENSITIVE_PATTERNS = [
    "agents/*.md",
    "dpo_lab/pairs/*.jsonl",
    "dpo_lab/quarantine/*.jsonl",
    "emf_lab/memory/*.json",
    "memory/local_training_data.jsonl",
    "memory/genesis_points.json",
    "config/MASTER_RULES.md",
    "CONTEXT.md",
    "AGENTS.md",
    "security/threat_db.json",
]

# Files NEVER encrypted
NEVER_ENCRYPT = {
    "docker-compose.yml", "requirements.txt", ".gitignore",
    "config/.env", "config/.vault_salt", "config/.vault_state",
}


# ══════════════════════════════════════════════════════════════════════════════
# KEY DERIVATION — passphrase × machine_id → AES-256 key
# ══════════════════════════════════════════════════════════════════════════════

def _get_machine_id() -> bytes:
    """Machine fingerprint — copy file to another machine = different key = decrypt fail."""
    sources = []
    for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        p = Path(path)
        if p.exists():
            sources.append(p.read_bytes())
            break
    try:
        cpu = subprocess.check_output(["cat", "/proc/cpuinfo"], timeout=2)
        sources.append(cpu[:256])
    except Exception:
        pass
    if not sources:
        import socket as sock
        sources.append(sock.gethostname().encode())
    return hashlib.sha256(b"".join(sources)).digest()


def derive_key(passphrase: str, salt: Optional[bytes] = None) -> tuple:
    """
    PBKDF2(SHA256, passphrase + machine_id, salt, 480000) → 32 bytes key.
    salt stored at config/.vault_salt — not secret, just needs to be consistent.
    """
    machine_id      = _get_machine_id()
    combined_secret = passphrase.encode() + b"|ZCL|" + machine_id
    if salt is None:
        salt = secrets.token_bytes(32)
    key = hashlib.pbkdf2_hmac("sha256", combined_secret, salt, 480_000, dklen=32)
    return key, salt


# ══════════════════════════════════════════════════════════════════════════════
# CRYPTO — AES-256-GCM (authenticated encryption)
# ══════════════════════════════════════════════════════════════════════════════

def _encrypt(plaintext: bytes, key: bytes) -> bytes:
    """
    AES-256-GCM: ciphertext includes authentication tag.
    Automatic tamper detection — no separate HMAC needed on ciphertext.
    Format: nonce(12) + ciphertext+tag
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce  = secrets.token_bytes(12)
    aesgcm = AESGCM(key)
    return nonce + aesgcm.encrypt(nonce, plaintext, None)


def _decrypt(data: bytes, key: bytes) -> bytes:
    """Decrypt + authenticate. Raises InvalidTag if tampered."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce, ciphertext = data[:12], data[12:]
    return AESGCM(key).decrypt(nonce, ciphertext, None)


def _file_to_enc(filepath: Path, key: bytes, salt: bytes) -> Path:
    """Encrypt file → {filepath}.enc. Magic header: ZCL2 + salt(32)."""
    plaintext = filepath.read_bytes()
    encrypted = _encrypt(plaintext, key)
    enc_path  = filepath.parent / (filepath.name + ".enc")
    enc_path.write_bytes(b"ZCL2" + salt + encrypted)
    return enc_path


def _enc_to_plaintext(enc_path: Path, key: bytes) -> bytes:
    """Decrypt .enc → plaintext bytes. Raises if magic is incorrect or tampered."""
    raw = enc_path.read_bytes()
    if raw[:4] != b"ZCL2":
        raise ValueError(f"Invalid magic: {enc_path.name} — may not be a vault file")
    # salt at bytes 4-36 (not used for decryption because key is already derived)
    return _decrypt(raw[36:], key)


# ══════════════════════════════════════════════════════════════════════════════
# KEYMASTER — Unix Domain Socket process (chạy trong A09 container)
# ══════════════════════════════════════════════════════════════════════════════

class KeyMaster:
    """
    Holds encryption key in RAM. Serves decrypt requests via Unix socket.
    Only runs inside the Agent 09 process after being unlocked.

    Simple Protocol:
      Client sends: JSON {"action": "decrypt", "rel_path": "agents/04_brain_soul.md"}
      Server returns: JSON {"ok": True, "content": "<plaintext>"}
                      or {"ok": False, "error": "..."}

    Why Unix socket instead of Redis:
      - Doesn't go through network (socket file in /dev/shm)
      - Doesn't serialize key to Redis (Redis plaintext)
      - /dev/shm is a RAM disk → socket file is not written to SSD
    """

    def __init__(self):
        self._key:      Optional[bytes] = None
        self._salt:     Optional[bytes] = None
        self._unlocked: bool            = False
        self._server_thread: Optional[threading.Thread] = None
        self._request_count: int        = 0

    def unlock(self, passphrase: str) -> bool:
        """Load key into RAM. Verify by decrypting 1 test file."""
        if VAULT_SALT_FILE.exists():
            self._salt = VAULT_SALT_FILE.read_bytes()
        else:
            log.error(".vault_salt is missing — run --lock-all first")
            return False

        self._key, _ = derive_key(passphrase, self._salt)

        # Verify with first file found
        enc_files = list(BASE_DIR.glob("agents/*.md.enc"))
        if enc_files:
            try:
                _enc_to_plaintext(enc_files[0], self._key)
                self._unlocked = True
                log.info("KeyMaster unlocked ✓")
                return True
            except Exception:
                self._key = None
                log.error("Incorrect passphrase or file tampered")
                return False

        # No .enc files yet (first setup) — key valid by definition
        self._unlocked = True
        log.info("KeyMaster unlocked (no .enc files yet — first time)")
        return True

    def decrypt_to_memory(self, rel_path: str) -> str:
        """Decrypt file and return plaintext string. DO NOT write to disk."""
        if not self._unlocked:
            raise RuntimeError("KeyMaster is not unlocked")
        enc_path = BASE_DIR / (rel_path + ".enc")
        if not enc_path.exists():
            # Fallback: try reading original plaintext (UNLOCKED mode)
            plain_path = BASE_DIR / rel_path
            if plain_path.exists():
                return plain_path.read_text(encoding="utf-8")
            raise FileNotFoundError(f"Not found: {rel_path} or {rel_path}.enc")
        self._request_count += 1
        return _enc_to_plaintext(enc_path, self._key).decode("utf-8")

    def start_socket_server(self):
        """Start Unix socket server in a daemon thread."""
        if Path(KEYMASTER_SOCKET).exists():
            Path(KEYMASTER_SOCKET).unlink()

        def _handle_client(conn):
            try:
                data    = conn.recv(4096)
                request = json.loads(data.decode())
                action  = request.get("action", "")

                if action == "decrypt":
                    rel_path = request.get("rel_path", "")
                    content  = self.decrypt_to_memory(rel_path)
                    response = {"ok": True, "content": content}

                elif action == "ping":
                    response = {"ok": True, "unlocked": self._unlocked,
                                "requests": self._request_count}
                                
                elif action == "encrypt_for_update":
                    rel_path = request.get("rel_path", "")
                    content  = request.get("content", "")
                    
                    if not self._unlocked or not self._key:
                        response = {"ok": False, "error": "KeyMaster not unlocked"}
                    elif not rel_path or not content:
                        response = {"ok": False, "error": "Missing rel_path or content"}
                    else:
                        try:
                            # Encrypt content with AES-256
                            encrypted = _encrypt(content.encode("utf-8"), self._key)
                            
                            # Read salt
                            salt = self._salt if self._salt else VAULT_SALT_FILE.read_bytes()
                            
                            # Save .enc file to inbox/vault_updates/
                            out_name = Path(rel_path).name + ".enc"
                            out_path = VAULT_UPDATE_DIR / out_name
                            out_path.write_bytes(b"ZCL2" + salt + encrypted)
                            
                            # Generate HMAC signature to pass A09's Layer 1
                            if HMAC_SECRET:
                                content_bytes = out_path.read_bytes()
                                expected_sig  = hmac.new(HMAC_SECRET.encode(), content_bytes, hashlib.sha256).hexdigest()
                                sig_path = VAULT_UPDATE_DIR / (out_name + ".sig")
                                sig_path.write_text(expected_sig)
                                
                            response = {"ok": True, "output_path": str(out_path)}
                            log.info(f"[KeyMaster] Opus Bridge generated update file: {out_name}")
                        except Exception as e:
                            response = {"ok": False, "error": f"Encryption error: {e}"}
                            
                else:
                    response = {"ok": False, "error": f"Unknown action: {action}"}

            except Exception as e:
                response = {"ok": False, "error": str(e)}
            finally:
                conn.sendall(json.dumps(response, ensure_ascii=False).encode())
                conn.close()

        def _server_loop():
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(KEYMASTER_SOCKET)
            srv.listen(10)
            os.chmod(KEYMASTER_SOCKET, 0o600)  # Only owner (agent_09 user) can read
            log.info(f"KeyMaster socket: {KEYMASTER_SOCKET}")
            while True:
                conn, _ = srv.accept()
                threading.Thread(target=_handle_client, args=(conn,), daemon=True).start()

        self._server_thread = threading.Thread(target=_server_loop, daemon=True,
                                                name="KeyMasterSocket")
        self._server_thread.start()

    def wipe(self):
        """Wipe key from RAM. Called on container shutdown."""
        self._key      = None
        self._unlocked = False
        if Path(KEYMASTER_SOCKET).exists():
            Path(KEYMASTER_SOCKET).unlink()
        log.info("KeyMaster wiped")


# ══════════════════════════════════════════════════════════════════════════════
# VAULT CLIENT — các agents dùng để đọc file đã mã hóa
# ══════════════════════════════════════════════════════════════════════════════

class VaultClient:
    """
    Simple API for agents to read encrypted files.
    Import in any agent that needs to read a soul file or sensitive config.

    Usage:
        from scripts.vault_manager import VaultClient
        vc = VaultClient()
        soul_content = vc.read("agents/04_brain_soul.md")
    """

    def read(self, rel_path: str) -> str:
        """
        Read file (encrypted or plaintext depending on vault state).
        Auto-fallback: socket → plaintext file → raise error.
        """
        # Try KeyMaster socket first
        if Path(KEYMASTER_SOCKET).exists():
            try:
                return self._request_decrypt(rel_path)
            except Exception as e:
                log.warning(f"VaultClient socket error: {e} — fallback plaintext")

        # Fallback: read plaintext (UNLOCKED state)
        plain_path = BASE_DIR / rel_path
        if plain_path.exists():
            return plain_path.read_text(encoding="utf-8")

        raise FileNotFoundError(f"VaultClient: cannot read {rel_path}")

    def _request_decrypt(self, rel_path: str) -> str:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect(KEYMASTER_SOCKET)
        sock.sendall(json.dumps({"action": "decrypt", "rel_path": rel_path}).encode())
        response_data = sock.recv(1048576)  # 1MB max
        sock.close()
        resp = json.loads(response_data.decode())
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error", "Unknown vault error"))
        return resp["content"]

    def is_vault_active(self) -> bool:
        """Check if KeyMaster socket is running."""
        return Path(KEYMASTER_SOCKET).exists()

    def ping(self) -> dict:
        """Check KeyMaster health."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(KEYMASTER_SOCKET)
            sock.sendall(json.dumps({"action": "ping"}).encode())
            resp = json.loads(sock.recv(4096).decode())
            sock.close()
            return resp
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# LOCK ALL — chuyển hệ thống sang LOCKED state
# ══════════════════════════════════════════════════════════════════════════════

def lock_all(passphrase: str) -> dict:
    """
    Encrypt all sensitive files. Called when owner orders "lock system".
    After running: original files are replaced by placeholders, .enc files exist.
    KeyMaster needs to be started for agents to continue operating.

    Returns: {"encrypted": N, "skipped": M, "errors": [...]}
    """
    PLACEHOLDER = ("# VAULT LOCKED\n"
                   "# This file has been encrypted.\n"
                   "# The system continues to operate via KeyMaster.\n")

    # Derive key + save salt
    if VAULT_SALT_FILE.exists():
        salt = VAULT_SALT_FILE.read_bytes()
        key, _ = derive_key(passphrase, salt)
    else:
        key, salt = derive_key(passphrase)
        VAULT_SALT_FILE.write_bytes(salt)
        log.info(f"New salt → {VAULT_SALT_FILE}")

    encrypted, skipped, errors = 0, 0, []

    for pattern in SENSITIVE_PATTERNS:
        for filepath in BASE_DIR.glob(pattern):
            # Skip if already .enc or in NEVER_ENCRYPT
            if filepath.suffix == ".enc" or filepath.name in NEVER_ENCRYPT:
                skipped += 1
                continue
            # Skip placeholder
            if filepath.read_text(encoding="utf-8", errors="ignore").startswith("# VAULT LOCKED"):
                skipped += 1
                continue
            try:
                enc_path = _file_to_enc(filepath, key, salt)
                _create_backup(filepath, key, salt)
                filepath.write_text(PLACEHOLDER, encoding="utf-8")
                log.info(f"LOCKED: {filepath.relative_to(BASE_DIR)}")
                encrypted += 1
            except Exception as e:
                errors.append({"file": str(filepath.relative_to(BASE_DIR)), "error": str(e)})
                log.error(f"Lock {filepath.name} error: {e}")

    # Save vault state
    VAULT_STATE_FILE.write_text("LOCKED")

    result = {"encrypted": encrypted, "skipped": skipped, "errors": errors}
    log.info(f"lock_all done: {result}")
    _tele_notify(
        f"🔒 *Vault Locked*\n"
        f"Encrypted: {encrypted} files\n"
        f"Errors: {len(errors)}\n"
        f"KeyMaster needs to be started via `python scripts/vault_manager.py --start-keymaster`"
    )
    return result


def _create_backup(filepath: Path, key: bytes, salt: bytes):
    """Create .backup.enc for each file before swapping — used if validation fails."""
    backup_path = filepath.parent / (filepath.name + ".backup.enc")
    plaintext   = filepath.read_bytes()
    encrypted   = _encrypt(plaintext, key)
    backup_path.write_bytes(b"ZCL2" + salt + encrypted)


def restore_from_backup(rel_path: str, key: bytes):
    """Restore from .backup.enc when new file is rejected."""
    backup_path = BASE_DIR / (rel_path + ".backup.enc")
    enc_path    = BASE_DIR / (rel_path + ".enc")
    if not backup_path.exists():
        raise FileNotFoundError(f"No backup found: {backup_path}")
    # Copy backup → current .enc
    import shutil
    shutil.copy2(backup_path, enc_path)
    log.info(f"Restored from backup: {rel_path}")


# ══════════════════════════════════════════════════════════════════════════════
# FILE UPDATE FLOW — swap file khi đã LOCKED
# ══════════════════════════════════════════════════════════════════════════════

def process_vault_update(enc_path: Path, km: KeyMaster) -> dict:
    """
    Process update file from inbox/vault_updates/.
    Flow:
      1. Verify HMAC signature
      2. Decrypt to read content (RAM-only)
      3. Injection scan
      4. Qwen semantic validation
      5. PASS → backup current → swap with new file
      6. FAIL → retain backup, alert Telegram, log reason

    enc_path: path to .enc file in inbox/vault_updates/
    """
    result = {
        "file":     enc_path.name,
        "approved": False,
        "layers":   {},
        "action":   None,
    }

    # Determine target path
    original_name = enc_path.stem  # remove .enc
    target_rel    = _find_target_path(original_name)
    if not target_rel:
        result["action"] = "REJECTED_UNKNOWN_TARGET"
        result["reason"] = f"Target not found for: {original_name}"
        _tele_notify(f"❌ Vault Update REJECTED\n{original_name}\n{result['reason']}")
        return result

    # ── Layer 1: HMAC signature ───────────────────────────────────────────────
    sig_path = enc_path.parent / (enc_path.name + ".sig")
    if sig_path.exists() and HMAC_SECRET:
        content_bytes = enc_path.read_bytes()
        stored_sig    = sig_path.read_text().strip()
        expected_sig  = hmac.new(HMAC_SECRET.encode(), content_bytes, hashlib.sha256).hexdigest()
        hmac_ok       = hmac.compare_digest(expected_sig, stored_sig)
        result["layers"]["hmac"] = {
            "pass":   hmac_ok,
            "detail": "OK" if hmac_ok else "TAMPERED — signature mismatch",
        }
    else:
        result["layers"]["hmac"] = {"pass": False, "detail": "Missing .sig file"}

    if not result["layers"]["hmac"]["pass"]:
        result["action"] = "REJECTED_HMAC"
        _alert_and_log(result, f"HMAC failed for {original_name}")
        return result

    # ── Layer 2: Decrypt into RAM for scanning ─────────────────────────────────
    try:
        if km._key is None:
            raise RuntimeError("KeyMaster not unlocked")
        plaintext_bytes = _enc_to_plaintext(enc_path, km._key)
        plaintext_str   = plaintext_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        result["layers"]["decrypt"] = {"pass": False, "detail": str(e)}
        result["action"] = "REJECTED_DECRYPT_FAIL"
        _alert_and_log(result, f"Decrypt failed for {original_name}: {e}")
        return result
    result["layers"]["decrypt"] = {"pass": True, "detail": "Decrypted to RAM"}

    # ── Layer 3: Injection scan ───────────────────────────────────────────────
    import re
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|all|above)\s+instructions?",
        r"eval\s*\(|exec\s*\(|__import__\s*\(",
        r"OVERRIDE_ZCL|ZCL_INJECT|BYPASS_VAULT",
        r"subprocess\.run|os\.system",
    ]
    found = [p for p in INJECTION_PATTERNS
             if re.search(p, plaintext_str, re.IGNORECASE)]
    result["layers"]["injection"] = {
        "pass":   len(found) == 0,
        "detail": f"Found: {found}" if found else "Clean",
    }
    if not result["layers"]["injection"]["pass"]:
        result["action"] = "REJECTED_INJECTION"
        _alert_and_log(result, f"Injection patterns: {found}")
        return result

    # ── Layer 4: Qwen semantic validation ─────────────────────────────────────
    qwen_result = _qwen_semantic_validate(plaintext_str)
    result["layers"]["qwen_semantic"] = {
        "pass":       qwen_result.get("approved", False) is True,
        "detail":     qwen_result.get("reason", ""),
        "risk_level": qwen_result.get("risk_level", "UNKNOWN"),
    }
    if qwen_result.get("approved") is False:
        result["action"] = f"REJECTED_SEMANTIC ({qwen_result.get('risk_level','?')})"
        _alert_and_log(result, f"Qwen rejected: {qwen_result.get('reason','?')[:100]}")
        return result
    if qwen_result.get("approved") is None:
        log.warning("Qwen unavailable — skip semantic check (proceed with caution)")
        result["layers"]["qwen_semantic"]["detail"] += " [SKIPPED — Qwen unavailable]"

    # ── All pass → swap ────────────────────────────────────────────────────
    target_enc = BASE_DIR / (target_rel + ".enc")
    try:
        # Backup current file
        if target_enc.exists():
            restore_from_backup(target_rel, km._key)  # Save backup
            backup_path = BASE_DIR / (target_rel + ".backup.enc")
            import shutil
            shutil.copy2(target_enc, backup_path)

        # Swap
        import shutil
        shutil.copy2(enc_path, target_enc)
        log.info(f"VAULT SWAP: {original_name} → {target_rel}")

        result["approved"] = True
        result["action"]   = "ACCEPTED_SWAPPED"
        _tele_notify(
            f"✅ *Vault Update OK*\n"
            f"File: {original_name}\n"
            f"Target: {target_rel}\n"
            f"Layers: HMAC ✓ | Injection ✓ | Qwen {'✓' if qwen_result.get('approved') else '⚠️ skipped'}\n"
            f"Backup: {target_rel}.backup.enc saved"
        )
    except Exception as e:
        result["action"] = f"SWAP_ERROR: {e}"
        _alert_and_log(result, f"Swap failed: {e}")
        # Restore backup if any
        try:
            restore_from_backup(target_rel, km._key)
            log.info(f"Restored from backup after swap error")
        except Exception:
            pass

    return result


def _find_target_path(filename: str) -> Optional[str]:
    """Find target relative path for filename in the project."""
    for pattern in SENSITIVE_PATTERNS:
        for filepath in BASE_DIR.glob(pattern):
            if filepath.name == filename or filepath.stem == filename:
                return str(filepath.relative_to(BASE_DIR))
    return None


def _qwen_semantic_validate(content: str) -> dict:
    """Call local Qwen to validate philosophy. No LLM = approved:None (does not block)."""
    import requests
    PROMPT = (
        "You are the philosophy validator of Zero-Cutloss Empire.\n"
        "Rules: only enter trades in Phase C Wyckoff, Limit Order only, no eval/exec/subprocess from external.\n\n"
        "File to validate:\n"
        f"<content>{content[:2000]}</content>\n\n"
        "Return JSON: {\"approved\": true/false, \"reason\": \"...\", \"risk_level\": \"LOW/MEDIUM/HIGH/CRITICAL\"}"
    )
    model = os.getenv("OLLAMA_MODEL_BRAIN", "qwen3:14b")
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/generate",
                             json={"model": model, "prompt": PROMPT, "stream": False,
                                   "options": {"temperature": 0.1, "num_predict": 300}},
                             timeout=45)
        resp.raise_for_status()
        text = resp.json().get("response", "")
        import re
        m = re.search(r'\{.*?\}', text, re.DOTALL)
        if m:
            return json.loads(m.group())
        return {"approved": None, "reason": "Qwen response cannot be parsed", "risk_level": "UNKNOWN"}
    except Exception as e:
        return {"approved": None, "reason": f"Qwen unavailable: {e}", "risk_level": "UNKNOWN"}


def _alert_and_log(result: dict, detail: str):
    log.warning(f"[VAULT REJECTED] {result['file']}: {detail}")
    _tele_notify(
        f"🚨 *Vault Update REJECTED*\n"
        f"File: {result['file']}\n"
        f"Reason: {detail[:200]}\n"
        f"Action: {result.get('action','?')}\n"
        f"Backup remains secure."
    )


def _tele_notify(msg: str):
    """Send notification via Telegram."""
    if not (TELEGRAM_BOT and TELEGRAM_CHAT):
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": f"[VAULT]\n{msg}", "parse_mode": "Markdown"},
            timeout=8,
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# VAULT STATE — UNLOCKED / LOCKED
# ══════════════════════════════════════════════════════════════════════════════

def get_vault_state() -> str:
    """Read current vault state: UNLOCKED (default) or LOCKED."""
    if VAULT_STATE_FILE.exists():
        return VAULT_STATE_FILE.read_text().strip()
    return "UNLOCKED"


def publish_vault_state_to_matrix(state: str):
    """Publish vault state to Matrix so agents know whether to use VaultClient."""
    try:
        matrix.set("SYSTEM", "vault_state", state)
        log.info(f"Vault state published to Matrix: {state}")
    except Exception as e:
        log.error(f"Error publishing vault state: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# INBOX WATCHER — A09 gọi định kỳ để xử lý file mới
# ══════════════════════════════════════════════════════════════════════════════

def watch_vault_updates(km: KeyMaster):
    """
    Scan inbox/vault_updates/ every 60s.
    Called from immunity_core.py daemon loop.
    """
    processed_file = VAULT_UPDATE_DIR / ".processed"
    processed_set  = set()
    if processed_file.exists():
        processed_set = set(processed_file.read_text().splitlines())

    enc_files = list(VAULT_UPDATE_DIR.glob("*.enc"))
    for enc_path in enc_files:
        if enc_path.name in processed_set:
            continue
        log.info(f"Vault update found: {enc_path.name}")
        result = process_vault_update(enc_path, km)
        processed_set.add(enc_path.name)

        # Write log
        log_entry = {
            "ts":     datetime.now(timezone.utc).isoformat(),
            "file":   enc_path.name,
            "result": result,
        }
        vault_log = BASE_DIR / "logs" / "vault_updates.jsonl"
        with open(vault_log, "a") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    processed_file.write_text("\n".join(processed_set))


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZCL Vault Manager")
    parser.add_argument("--status",          action="store_true", help="Current vault status")
    parser.add_argument("--lock-all",        action="store_true", help="Encrypt all -> LOCKED state")
    parser.add_argument("--start-keymaster", action="store_true", help="Start KeyMaster socket (A09 startup)")
    parser.add_argument("--validate-update", type=str, default="", help="Validate + swap update file")
    parser.add_argument("--dev-unlock",      action="store_true", help="Decrypt all to plaintext (dev only)")
    args = parser.parse_args()

    if args.status:
        state  = get_vault_state()
        vc     = VaultClient()
        km_up  = vc.is_vault_active()
        km_status = vc.ping() if km_up else {"ok": False}
        print(f"\n{'='*40}")
        print(f"  VAULT STATE: {state}")
        print(f"  KeyMaster socket: {'UP ✓' if km_up else 'DOWN ✗'}")
        if km_up:
            print(f"  Requests served: {km_status.get('requests', '?')}")
        print(f"  .enc files: {len(list(BASE_DIR.rglob('*.enc')))}")
        print(f"  .backup.enc files: {len(list(BASE_DIR.rglob('*.backup.enc')))}")
        print(f"{'='*40}\n")

    elif args.lock_all:
        print("⚠️  WARNING: All sensitive files will be encrypted.")
        print("     Run this command when the system setup is complete (SETUP_ONCE.md finished).")
        confirm = input("Enter 'LOCK_SYSTEM' to confirm: ")
        if confirm == "LOCK_SYSTEM":
            pp  = input("Passphrase (remember carefully — lost is lost): ")
            pp2 = input("Retype: ")
            if pp != pp2:
                sys.exit("Passphrase mismatch")
            result = lock_all(pp)
            print(f"\nResult: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print(f"\n→ Next: python scripts/vault_manager.py --start-keymaster")
        else:
            print("Cancelled.")

    elif args.start_keymaster:
        pp = input("Passphrase to unlock vault: ")
        km = KeyMaster()
        if km.unlock(pp):
            km.start_socket_server()
            publish_vault_state_to_matrix("LOCKED")
            print(f"KeyMaster running at: {KEYMASTER_SOCKET}")
            print("Ctrl+C to stop (vault will be locked again)")
            try:
                threading.Event().wait()  # Block forever
            except KeyboardInterrupt:
                km.wipe()
                print("KeyMaster stopped.")
        else:
            sys.exit("Unlock failed")

    elif args.validate_update:
        enc_path = Path(args.validate_update)
        if not enc_path.exists():
            sys.exit(f"File does not exist: {enc_path}")
        if get_vault_state() != "LOCKED":
            sys.exit("Vault not LOCKED — no need to validate update")
        pp = input("Passphrase: ")
        km = KeyMaster()
        if not km.unlock(pp):
            sys.exit("Unlock failed")
        result = process_vault_update(enc_path, km)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["approved"] else 1)

    elif args.dev_unlock:
        print("⚠️  DEV MODE: Decrypt all to plaintext. DO NOT use in production.")
        pp = input("Passphrase: ")
        if VAULT_SALT_FILE.exists():
            salt = VAULT_SALT_FILE.read_bytes()
            key, _ = derive_key(pp, salt)
        else:
            sys.exit(".vault_salt missing")
        count = 0
        for enc_file in BASE_DIR.rglob("*.enc"):
            if ".backup." in enc_file.name:
                continue
            try:
                plaintext = _enc_to_plaintext(enc_file, key)
                out_path  = enc_file.parent / enc_file.name[:-4]  # remove .enc
                out_path.write_bytes(plaintext)
                print(f"UNLOCKED: {enc_file.relative_to(BASE_DIR)}")
                count += 1
            except Exception as e:
                print(f"FAIL: {enc_file.name} — {e}")
        VAULT_STATE_FILE.write_text("UNLOCKED")
        print(f"\nDecrypted {count} files. State → UNLOCKED")

    else:
        parser.print_help()
        print("\nUsage flow:")
        print("  Setup done → python scripts/vault_manager.py --lock-all")
        print("  On restart → python scripts/vault_manager.py --start-keymaster")
        print("  New file → python scripts/vault_manager.py --validate-update inbox/vault_updates/file.enc")
