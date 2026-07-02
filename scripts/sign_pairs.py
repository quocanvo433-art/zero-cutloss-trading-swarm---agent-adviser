"""
🧬 DNA: v16.6 (Sovereign Purity & Trust)
🏢 UNIT: SIGN_PAIRS
🛠️ ROLE: TRUST_PROVISIONER
📖 DESC: Digital signing system (HMAC-SHA256) for DPO pairs, ensuring origin authenticity and anti-tampering during training.
🔗 CALLS: hmac, hashlib
📟 I/O: inbox/*.jsonl (Input/Output), .env: PAIRS_SIGNING_SECRET
🛡️ INTEGRITY: Data-Origin-Auth, Tamper-Resistance, Deterministial-Serialization.
"""

import os
import sys
import hmac
import json
import hashlib
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../config/.env'))

SIGNING_SECRET = os.getenv("PAIRS_SIGNING_SECRET", "")
BASE_DIR       = Path(__file__).parent.parent
INBOX_DIR      = BASE_DIR / "inbox"

log = logging.getLogger("SIGN_PAIRS")
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[
        logging.FileHandler(str(BASE_DIR / "logs" / "agent_execution.log")),
        logging.StreamHandler()
    ]
)


# ══════════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _ky_mot_record(record: dict) -> dict:
    """
    Compute HMAC for 1 JSON record, adding '__sig' field.
    Do not sign '__sig' field if already present (avoid loops).
    """
    if not SIGNING_SECRET:
        raise ValueError("PAIRS_SIGNING_SECRET has not been set in .env!")

    # Remove old signature if present, to normalize
    record_clean = {k: v for k, v in record.items() if k != "__sig"}

    # Serialize deterministically
    payload = json.dumps(record_clean, sort_keys=True, ensure_ascii=False)

    # HMAC-SHA256
    sig = hmac.new(
        SIGNING_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    record_clean["__sig"] = sig
    record_clean["__signed_at"] = datetime.now(timezone.utc).isoformat()
    return record_clean


def _xac_minh_mot_record(record: dict) -> bool:
    """Verify HMAC of 1 record. Returns True if valid."""
    if not SIGNING_SECRET:
        raise ValueError("PAIRS_SIGNING_SECRET has not been set in .env!")

    sig_received = record.get("__sig", "")
    if not sig_received:
        return False

    # Recreate payload without __sig and __signed_at
    record_clean = {k: v for k, v in record.items() if k not in ("__sig", "__signed_at")}
    payload = json.dumps(record_clean, sort_keys=True, ensure_ascii=False)

    sig_expected = hmac.new(
        SIGNING_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(sig_received, sig_expected)


def ky_file(filepath: Path) -> dict:
    """Sign all records in a .jsonl file. Overwrites original file."""
    if not filepath.exists():
        log.error(f"File does not exist: {filepath}")
        return {"status": "ERROR", "error": f"Not found: {filepath}"}

    records = []
    errors = 0
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                signed = _ky_mot_record(rec)
                records.append(signed)
            except Exception as e:
                log.warning(f"Line {i}: {e}")
                errors += 1

    # Write back signed file
    with open(filepath, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    log.info(f"Signed: {filepath} | {len(records)} records | {errors} errors")
    return {"status": "SUCCESS", "signed_count": len(records), "errors": errors, "file": str(filepath)}


def xac_minh_file(filepath: Path) -> dict:
    """Verify HMAC of all records in a .jsonl file."""
    if not filepath.exists():
        return {"status": "ERROR", "error": f"Not found: {filepath}"}

    hop_le = 0
    khong_hop_le = 0
    thieu_sig = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if "__sig" not in rec:
                    thieu_sig += 1
                    continue
                if _xac_minh_mot_record(rec):
                    hop_le += 1
                else:
                    khong_hop_le += 1
                    log.warning(f"HMAC FAIL at line {i}: signature mismatch!")
            except Exception as e:
                log.warning(f"Line {i} parse error: {e}")
                khong_hop_le += 1

    status = ("SUCCESS" if khong_hop_le == 0 and thieu_sig == 0
                  else ("WARNING" if khong_hop_le == 0 else "FAILED"))

    log.info(f"Verify {filepath}: {hop_le} OK | {khong_hop_le} FAIL | {thieu_sig} missing sig")
    return {
        "status": status,
        "valid": hop_le,
        "invalid": khong_hop_le,
        "missing_sig": thieu_sig,
        "file": str(filepath)
    }


def ky_tat_ca_inbox() -> list:
    """Sign all .jsonl files in inbox/."""
    ket_qua = []
    for f in INBOX_DIR.rglob("*.jsonl"):
        ket_qua.append(ky_file(f))
    log.info(f"Sign-all: {len(ket_qua)} files processed")
    return ket_qua


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not SIGNING_SECRET:
        print("❌ ERROR: PAIRS_SIGNING_SECRET is missing from .env!")
        print("   Create using: python -c \"import secrets; print(secrets.token_hex(32))\"")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="HMAC sign/verify DPO pairs")
    sub = parser.add_subparsers(dest="cmd")

    p_sign = sub.add_parser("sign", help="Sign 1 .jsonl file")
    p_sign.add_argument("--file", type=str, required=True)

    p_verify = sub.add_parser("verify", help="Verify HMAC of 1 .jsonl file")
    p_verify.add_argument("--file", type=str, required=True)

    sub.add_parser("sign-all", help="Sign all .jsonl files in inbox/")

    args = parser.parse_args()

    if args.cmd == "sign":
        result = ky_file(Path(args.file))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["status"] == "SUCCESS" else 1)

    elif args.cmd == "verify":
        result = xac_minh_file(Path(args.file))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["status"] == "SUCCESS" else 1)

    elif args.cmd == "sign-all":
        results = ky_tat_ca_inbox()
        print(json.dumps(results, indent=2, ensure_ascii=False))
        sys.exit(0)

    else:
        parser.print_help()
