"""
🧬 DNA: v1.0 (Redis Hygiene — Periodic Cleanup)
🏢 UNIT: MAINTENANCE
🛠️ ROLE: REDIS_JANITOR
📖 DESC: Scan and clean Redis garbage: expired quota keys, bloated streams, legacy double-prefix bugs.
🔗 CALLS: redis-py
📟 I/O: Redis: zcl:* (READ + DELETE garbage only)
🛡️ INTEGRITY: Delete verified garbage only, DO NOT touch business data.
"""
import os
import sys
import time
import redis
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ── Load config ──
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_PASS = os.getenv("REDIS_PASSWORD", None)

# ── STREAM TRIM CONFIG ──
STREAM_MAXLEN = {
    "zcl:emf:signals:raw": 100,
    "zcl:emf:signals:scored": 50,
    "zcl:emf:intent:report": 30,
    "zcl:a05:t0_stream": 30,
    "zcl:a05:divergence_stream": 20,
    "zcl:system:model_state": 20,
    "zcl:claw:outbox": 30,
    "zcl:claw:queue:coder": 30,
    "zcl:claw:queue:verifier": 30,
}

def connect_redis():
    """Connect to Redis via standard URL."""
    try:
        r = redis.Redis.from_url(REDIS_URL, password=REDIS_PASS, decode_responses=True, socket_timeout=10)
        r.ping()
        return r
    except Exception as e:
        print(f"❌ Could not connect to Redis: {e}")
        sys.exit(1)


def clean_double_prefix_keys(r):
    """Delete keys with double-prefix bug: zcl:system:zcl:system:*"""
    pattern = "zcl:system:zcl:system:*"
    cursor = 0
    total_deleted = 0
    
    while True:
        cursor, keys = r.scan(cursor, match=pattern, count=200)
        if keys:
            r.delete(*keys)
            total_deleted += len(keys)
        if cursor == 0:
            break
    
    if total_deleted > 0:
        print(f"🗑️  [DOUBLE-PREFIX] Deleted {total_deleted} garbage keys (zcl:system:zcl:system:*)")
    else:
        print(f"✅  [DOUBLE-PREFIX] Clean — no garbage keys found.")
    return total_deleted


def clean_expired_quota_keys(r):
    """Delete quota keys older than 6 hours (no longer useful for tracking)."""
    pattern = "zcl:system:quota:*"
    cursor = 0
    total_deleted = 0
    now = datetime.now()
    
    while True:
        cursor, keys = r.scan(cursor, match=pattern, count=200)
        for key in keys:
            # Format: zcl:system:quota:TYPE:AGENT:YYYYMMDD_HH
            parts = key.rsplit(":", 1)
            if len(parts) < 2:
                continue
            time_part = parts[-1]
            
            # Parse YYYYMMDD_HH
            try:
                key_dt = datetime.strptime(time_part, "%Y%m%d_%H")
                age_hours = (now - key_dt).total_seconds() / 3600
                if age_hours > 6:
                    r.delete(key)
                    total_deleted += 1
            except ValueError:
                # Not a timestamp format -> skip (might be a system key)
                continue
        
        if cursor == 0:
            break
    
    if total_deleted > 0:
        print(f"🗑️  [QUOTA_EXPIRED] Deleted {total_deleted} quota keys older than 6h.")
    else:
        print(f"✅  [QUOTA_EXPIRED] Clean — no expired quota keys.")
    return total_deleted


def trim_streams(r):
    """Trim streams exceeding their allowed MAXLEN."""
    total_trimmed = 0
    
    for stream_key, maxlen in STREAM_MAXLEN.items():
        try:
            current_len = r.xlen(stream_key)
            if current_len > maxlen:
                r.xtrim(stream_key, maxlen=maxlen, approximate=True)
                trimmed = current_len - maxlen
                total_trimmed += trimmed
                print(f"✂️  [STREAM] {stream_key}: {current_len} → ~{maxlen} (trimmed ~{trimmed} entries)")
        except redis.exceptions.ResponseError:
            # Key does not exist or is not a stream -> skip
            pass
    
    if total_trimmed == 0:
        print(f"✅  [STREAM] All streams within limits.")
    return total_trimmed


def report_health(r):
    """Print Redis health report."""
    info_mem = r.info("memory")
    info_stats = r.info("stats")
    info_clients = r.info("clients")
    dbsize = r.dbsize()
    
    print(f"\n{'='*60}")
    print(f"📊 REDIS HEALTH REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"  📦 Total keys:         {dbsize}")
    print(f"  💾 Memory used:       {info_mem.get('used_memory_human', 'N/A')}")
    print(f"  📈 Memory peak:       {info_mem.get('used_memory_peak_human', 'N/A')}")
    print(f"  🔀 Fragmentation:     {info_mem.get('mem_fragmentation_ratio', 'N/A')}")
    print(f"  👥 Connected clients: {info_clients.get('connected_clients', 'N/A')}")
    print(f"  🚫 Blocked clients:   {info_clients.get('blocked_clients', 'N/A')}")
    print(f"  ⚡ Ops/sec:           {info_stats.get('instantaneous_ops_per_sec', 'N/A')}")
    print(f"  ❌ Expired keys:      {info_stats.get('expired_keys', 'N/A')}")
    print(f"  🚪 Evicted keys:      {info_stats.get('evicted_keys', 'N/A')}")
    
    # Auth fail check
    cmd_stats = r.info("commandstats")
    auth_stat = cmd_stats.get("cmdstat_auth", {})
    if isinstance(auth_stat, dict):
        auth_calls = auth_stat.get("calls", 0)
        auth_fails = auth_stat.get("failed_calls", 0)
        if auth_fails > 100:
            print(f"  🚨 AUTH FAIL:         {auth_fails}/{auth_calls} ({auth_fails*100//max(auth_calls,1)}% fail!)")
        else:
            print(f"  🔐 AUTH stats:        {auth_calls} calls, {auth_fails} fails")
    
    print(f"{'='*60}\n")


def main():
    print(f"\n... Redis Hygiene — Starting cleanup... [{datetime.now().strftime('%H:%M:%S')}]\n")
    
    r = connect_redis()
    
    # 1. Delete double-prefix keys (legacy bug)
    d1 = clean_double_prefix_keys(r)
    
    # 2. Delete expired quota keys
    d2 = clean_expired_quota_keys(r)
    
    # 3. Trim streams
    d3 = trim_streams(r)
    
    # 4. Report
    report_health(r)
    
    total = d1 + d2 + d3
    if total > 0:
        print(f"🏁 Summary: Cleaned {total} garbage items. Redis is clean!")
    else:
        print(f"🏁 Redis is already clean — no garbage to clean.")


if __name__ == "__main__":
    main()
