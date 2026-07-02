"""
🧬 DNA: v16.6 (Sovereign Purity & Data Authority)
🏢 UNIT: MANUAL_DATA_AUTH
🛠️ ROLE: DATA_GATEKEEPER
📖 DESC: External data authorization system, verifying integrity of DPO packages using HMAC-SHA256 before loading into the training pipeline.
🔗 CALLS: hmac, hashlib, tools/immunity_core.py
📟 I/O: dpo_lab/pairs/*.jsonl, *.sig (Output)
🛡️ INTEGRITY: HMAC-Verification, Manual-Override-Auth, Signature-Enforcement.
"""

import os
import hmac
import hashlib
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure tools/ is in path if needed (though this script is mostly self-contained)
sys_path_added = False
import sys
if os.path.join(os.path.dirname(__file__), '..') not in sys.path:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    sys_path_added = True

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../config/.env'))
HMAC_SECRET = os.getenv("IMMUNITY_HMAC_SECRET", "")

def calculate_hmac(file_path: Path) -> str:
    with open(file_path, "rb") as f:
        data = f.read()
    return hmac.new(HMAC_SECRET.encode(), data, hashlib.sha256).hexdigest()

def sign_file(file_path: Path):
    if not file_path.exists():
        print(f"ERROR: File {file_path} not found.")
        return
    
    signature = calculate_hmac(file_path)
    sig_path = file_path.with_suffix(file_path.suffix + ".sig")
    
    with open(sig_path, "w") as f:
        f.write(signature)
    print(f"SIGNED: {file_path.name} -> {sig_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Zero-Cutloss Data Signer")
    parser.add_argument("--sign-all", action="store_true", help="Sign all relevant training files")
    parser.add_argument("--file", type=str, help="Sign a specific file")
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent / "dpo_lab"
    
    if args.sign_all:
        files = [
            base_dir / "pairs" / "chosen.jsonl",
            base_dir / "pairs" / "rejected.jsonl",
            base_dir / "quarantine" / "suspicious.jsonl"
        ]
        for f in files:
            if f.exists():
                sign_file(f)
            else:
                print(f"SKIP: {f.name} (not found)")
    elif args.file:
        sign_file(Path(args.file))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
