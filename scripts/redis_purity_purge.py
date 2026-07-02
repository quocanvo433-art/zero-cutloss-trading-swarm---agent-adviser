"""
🧬 DNA: v16.6 (Sovereign Purity & Infrastructure Integrity)
🏢 UNIT: REDIS_PURITY_PURGE
🛠️ ROLE: MATRIX_CLEANER
📖 DESC: Scan and purge unauthorized Redis keys (Junk Keys). Dry run by default to protect infrastructure.
🔗 CALLS: imperial_state:matrix
📟 I/O: Redis: keys *, delete
🛡️ INTEGRITY: Vetting-Before-Purge, Safe-Zone-Protection, Dry-Run-Default.
"""
import os
import sys
from pathlib import Path
import re

# DNA v16.6: Sovereign Purity & Discovery
# UNIT: REDIS_PURGE_TOOL

# Add tools to path to import imperial_state
sys.path.append(str(Path(__file__).resolve().parent.parent / "tools"))
from imperial_state import matrix

def get_safe_patterns():
    safe_patterns = set()
    
    # 1. Get from imperial_state.py PREFIX_MAP
    from imperial_state import PREFIX_MAP
    for prefix in PREFIX_MAP.values():
        safe_patterns.add(f"{prefix}:*")
    
    # 2. Get from REDIS.md (Scan keys in backticks ``)
    redis_md_path = Path(__file__).resolve().parent.parent / "REDIS.md"
    if redis_md_path.exists():
        content = redis_md_path.read_text()
        # Find strings in backticks
        matches = re.findall(r'`([^`]+)`', content)
        for m in matches:
            if ":" in m or "*" in m:
                # If it is a pattern (has * or :), add it
                safe_patterns.add(m.strip())
            else:
                # If it is a specific key
                safe_patterns.add(m.strip())

    # 3. Default event channels
    safe_patterns.add("zcl:events:*")
    safe_patterns.add("zcl:system:*")
    
    return list(safe_patterns)

def is_safe(key, safe_patterns):
    for p in safe_patterns:
        # Convert redis pattern to regex (Fix SyntaxWarning v113.9)
        regex_pattern = p.replace("*", ".*").replace(":", r"\:")
        if re.fullmatch(f"^{regex_pattern}$", key) or key.startswith(p.replace("*", "")):
            return True
    return False

def purge_junk(dry_run=True):
    print(f"🔱 [SOVEREIGN_PURGE] Initializing Redis Matrix scan (DRY_RUN={dry_run})...")
    
    if not matrix.client:
        print("❌ Error: Cannot connect to Redis.")
        return

    safe_patterns = get_safe_patterns()
    print(f"📊 Located {len(safe_patterns)} Safe Zones.")

    all_keys = matrix.client.keys("*")
    print(f"🔍 Found {len(all_keys)} keys on the system.")

    junk_keys = []
    for k in all_keys:
        if not is_safe(k, safe_patterns):
            junk_keys.append(k)

    if not junk_keys:
        print("✅ Matrix is in absolute pure state. No junk keys found.")
        return

    print(f"⚠️ WARNING: Detected {len(junk_keys)} Junk Keys:")
    for jk in junk_keys:
        print(f"  - [POTENTIAL JUNK]: {jk}")

    if dry_run:
        print("\n🔱 [SAFE MODE]: No keys deleted. Please review the list above first!")
        return

    print("\n🔱 Executing purge command...")
    for jk in junk_keys:
        matrix.client.delete(jk)
        print(f"  [X] Destroyed: {jk}")

    print(f"\n✅ PURGING COMPLETED. Deleted {len(junk_keys)} junk keys.")

if __name__ == "__main__":
    # DNA v107.0: Always default to True to ensure maximum safety.
    purge_junk(dry_run=True)
