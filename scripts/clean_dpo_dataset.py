"""
🧬 DNA: v16.7
🏢 UNIT: DPO_CLEANER
🛠️ ROLE: DATA_JANITOR
📖 DESC: DPO Dataset Cleaner & Normalizer
- Normalize chosen_code -> chosen, rejected_code -> rejected
- Filter out pairs with None/empty/too short chosen or rejected
- Deduplicate and remove too similar pairs (sim > 0.95)
- Remove garbage strings
- Ensure prompt is a valid string
- Standard Format: {"prompt": str, "chosen": str, "rejected": str, "reject_reason": str}
Output: openclaw_dpo_clean.jsonl (clean, ready for DPO training)
"""
import json
import hashlib
from pathlib import Path
from difflib import SequenceMatcher

MASTER = Path(__file__).parent.parent / "dpo_lab" / "openclaw_dpo.jsonl"
OUTPUT = Path(__file__).parent.parent / "dpo_lab" / "openclaw_dpo_clean.jsonl"

# ── Standards ─────────────────────────────────────────────
MIN_CHOSEN_LEN   = 30
MIN_REJECTED_LEN = 30
MIN_PROMPT_LEN   = 5
MAX_SIM          = 0.95

GARBAGE_STRINGS = [
    "UNKNOWN_ERROR", "Loi AI", "AI Error", "N/A", "Bo qua cap nhat", "Skip update",
    "Traceback (most recent call last)", "--- [LLM] ---",
    "[ERROR] Failed", "GARBAGE_FALLBACK",
]

# ── Stats ─────────────────────────────────────────────────
stats = {
    "total_read": 0,
    "bad_json": 0,
    "none_chosen": 0,
    "none_rejected": 0,
    "too_short": 0,
    "garbage": 0,
    "too_similar": 0,
    "duplicate": 0,
    "malformed_prompt": 0,
    "accepted": 0,
}

seen_hashes = set()


def normalize_pair(raw: dict) -> dict | None:
    """
    Normalize 1 raw pair to standard DPO format.
    Returns None if cannot be salvaged.
    """
    # Resolve chosen field (various names)
    chosen = (
        raw.get("chosen")
        or raw.get("chosen_code")
        or raw.get("output")
        or raw.get("response")
    )
    rejected = (
        raw.get("rejected")
        or raw.get("rejected_code")
        or raw.get("bad_output")
    )
    prompt = (
        raw.get("prompt")
        or raw.get("instruction")
        or raw.get("input")
        or ""
    )
    reject_reason = (
        raw.get("reject_reason")
        or raw.get("reason")
        or raw.get("error")
        or ""
    )

    # Must be strings
    if not isinstance(chosen, str):
        return None
    if not isinstance(rejected, str):
        return None
    if not isinstance(prompt, str):
        prompt = str(prompt)

    # Strip whitespace
    chosen   = chosen.strip()
    rejected = rejected.strip()
    prompt   = prompt.strip()
    reject_reason = str(reject_reason).strip()

    if not chosen or not rejected:
        return None

    return {
        "prompt":        prompt,
        "chosen":        chosen,
        "rejected":      rejected,
        "reject_reason": reject_reason,
    }


def is_garbage(text: str) -> bool:
    return any(g.lower() in text.lower() for g in GARBAGE_STRINGS)


def pair_hash(prompt: str, chosen: str, rejected: str) -> str:
    key = (prompt[:100] + chosen[:200] + rejected[:200]).encode()
    return hashlib.md5(key).hexdigest()


def check_quality(pair: dict) -> tuple[bool, str]:
    p  = pair["prompt"]
    c  = pair["chosen"]
    r  = pair["rejected"]

    if len(p) < MIN_PROMPT_LEN:
        return False, f"prompt too short ({len(p)}c)"
    if len(c) < MIN_CHOSEN_LEN:
        return False, f"chosen too short ({len(c)}c < {MIN_CHOSEN_LEN})"
    if len(r) < MIN_REJECTED_LEN:
        return False, f"rejected too short ({len(r)}c < {MIN_REJECTED_LEN})"

    if is_garbage(c):
        return False, "chosen contains garbage string"
    if is_garbage(r):
        return False, "rejected contains garbage string"

    if c == r:
        return False, "chosen == rejected (copy-paste)"

    sim = SequenceMatcher(None, c[:2000], r[:2000]).ratio()
    if sim > MAX_SIM:
        return False, f"sim={sim:.1%} > {MAX_SIM:.0%} (too similar)"

    return True, f"OK | sim={sim:.1%} | c={len(c)} r={len(r)} p={len(p)}"


def run():
    global stats

    print("=" * 60)
    print("🧹 DPO DATASET CLEANER & NORMALIZER")
    print(f"   Input : {MASTER}")
    print(f"   Output: {OUTPUT}")
    print("=" * 60)

    good_pairs = []

    # Ensure dpo_lab directory exists
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    if not MASTER.exists():
        print(f"WARNING: Master file {MASTER} not found. Creating an empty one.")
        with open(MASTER, "w") as f:
            pass

    with open(MASTER, "r", encoding="utf-8") as f:
        for i, raw_line in enumerate(f, 1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            stats["total_read"] += 1

            # 1. Parse JSON
            try:
                raw = json.loads(raw_line)
            except json.JSONDecodeError:
                stats["bad_json"] += 1
                continue

            # 2. Normalize fields
            pair = normalize_pair(raw)
            if pair is None:
                if raw.get("chosen") is None and raw.get("chosen_code") is None:
                    stats["none_chosen"] += 1
                elif raw.get("rejected") is None and raw.get("rejected_code") is None:
                    stats["none_rejected"] += 1
                else:
                    stats["none_chosen"] += 1
                continue

            # 3. Quality gate
            ok, reason = check_quality(pair)
            if not ok:
                if "too short" in reason:
                    stats["too_short"] += 1
                elif "garbage" in reason:
                    stats["garbage"] += 1
                elif "sim=" in reason:
                    stats["too_similar"] += 1
                elif "prompt" in reason:
                    stats["malformed_prompt"] += 1
                else:
                    stats["too_short"] += 1
                continue

            # 4. Dedup
            h = pair_hash(pair["prompt"], pair["chosen"], pair["rejected"])
            if h in seen_hashes:
                stats["duplicate"] += 1
                continue
            seen_hashes.add(h)

            # 5. Accept
            stats["accepted"] += 1
            good_pairs.append(pair)

    # Write clean output
    with open(OUTPUT, "w", encoding="utf-8") as out:
        for pair in good_pairs:
            out.write(json.dumps(pair, ensure_ascii=False) + "\n")

    # Report
    total   = stats["total_read"]
    dropped = total - stats["accepted"]
    print(f"\n{'─'*60}")
    print(f"📊 AUDIT RESULT:")
    print(f"  Read in     : {total:,} pairs")
    print(f"  Bad JSON    : {stats['bad_json']:,}")
    print(f"  None chosen : {stats['none_chosen']:,}  ← legacy chosen_code field not normalized")
    print(f"  None reject : {stats['none_rejected']:,}")
    print(f"  Too short   : {stats['too_short']:,}")
    print(f"  Garbage     : {stats['garbage']:,}")
    print(f"  Too similar : {stats['too_similar']:,}")
    print(f"  Duplicate   : {stats['duplicate']:,}")
    print(f"  Malformed   : {stats['malformed_prompt']:,}")
    print(f"{'─'*60}")
    print(f"  ✅ ACCEPTED  : {stats['accepted']:,} ({stats['accepted']/max(total,1)*100:.1f}%)")
    print(f"  🗑️  DROPPED   : {dropped:,}")
    print(f"\n✅ Clean dataset: {OUTPUT}")
    print(f"   {stats['accepted']} pairs ready for DPO Trainer!")

    # Validate a sample
    print(f"\n{'─'*60}")
    print("🔍 SAMPLE VALIDATION (First 3 pairs):")
    for j, pair in enumerate(good_pairs[:3], 1):
        sim = SequenceMatcher(None, pair["chosen"][:500], pair["rejected"][:500]).ratio()
        print(f"\n  [{j}] prompt={len(pair['prompt'])}c chosen={len(pair['chosen'])}c rejected={len(pair['rejected'])}c sim={sim:.1%}")
        print(f"      prompt[:80]   : {pair['prompt'][:80]}")
        print(f"      chosen[:80]   : {pair['chosen'][:80].replace(chr(10),' ')}")
        print(f"      rejected[:80] : {pair['rejected'][:80].replace(chr(10),' ')}")
        print(f"      reason[:80]   : {pair['reject_reason'][:80]}")


if __name__ == "__main__":
    run()
