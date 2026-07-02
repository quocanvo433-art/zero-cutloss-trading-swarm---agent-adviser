#!/usr/bin/env python3
"""
🧬 DNA: v1.0 (Zero Cutloss Unified Self-Cleaner)
🏢 UNIT: MAINTENANCE
🛠️ ROLE: UNIFIED_JANITOR
📖 DESC: Safe periodic cleanup: compress/delete old logs, delete expired DPO snapshots, trim/purge junk Redis keys, and clean up junk Docker images/containers.
         DO NOT affect Algo score (divergence_stream) or LLM context.
"""
import os
import sys
import time
import shutil
import tarfile
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# Define main directories
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
TMP_ARENA_DIR = BASE_DIR / "tmp" / "arena"
CLAUDE_ARENA_DIR = Path("/home/newuser/ClaudeWorkspace/tmp/arena")

# Add tools to sys.path to import imperial_state
sys.path.append(str(BASE_DIR / "tools"))
try:
    from imperial_state import matrix
except ImportError:
    matrix = None

# Add scripts to sys.path to import redis_hygiene
sys.path.append(str(BASE_DIR / "scripts"))
try:
    import redis_hygiene
except ImportError:
    redis_hygiene = None

def get_file_age_days(file_path: Path) -> float:
    """Calculate file age in days."""
    try:
        mtime = file_path.stat().st_mtime
        return (time.time() - mtime) / 86400.0
    except Exception:
        return 0.0

def clean_local_files(dry_run=False):
    """Clean local logs, dpo_lab snapshots, and tmp arena."""
    print("📁 [FILESYSTEM] Starting local file cleanup...")
    
    # 1. Clean logs/dpo_lab/*.md (raw large LLM snapshots > 7 days)
    dpo_lab_dir = LOGS_DIR / "dpo_lab"
    deleted_snapshots = 0
    if dpo_lab_dir.exists():
        for md_file in dpo_lab_dir.glob("**/*.md"):
            if get_file_age_days(md_file) > 7.0:
                if not dry_run:
                    md_file.unlink()
                deleted_snapshots += 1
                if dry_run:
                    print(f"  [DRY-RUN] Will delete snapshot: {md_file.relative_to(BASE_DIR)}")
                    
    print(f"  🗑️  DPO snapshots cleaned: {deleted_snapshots} files")

    # 2. Clean tmp/arena/*.md (> 7 days)
    deleted_arena = 0
    for arena_dir in [TMP_ARENA_DIR, CLAUDE_ARENA_DIR]:
        if arena_dir.exists():
            for md_file in arena_dir.glob("*.md"):
                if get_file_age_days(md_file) > 7.0:
                    if not dry_run:
                        md_file.unlink()
                    deleted_arena += 1
                    if dry_run:
                        print(f"  [DRY-RUN] Will delete arena report: {md_file}")
    print(f"  🗑️  Arena reports cleaned: {deleted_arena} files")

    # 3. Compress logs/A{XX}/*.jsonl and logs/redis_flow/*.log (> 14 days)
    # Store in logs/archive/, delete original files after successful compression. Delete archives > 30 days.
    archive_dir = LOGS_DIR / "archive"
    if not dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)
        
    archived_files = 0
    for path in LOGS_DIR.glob("**/*"):
        if not path.is_file():
            continue
        # Skip checkpoints, archives and engrams
        if "checkpoints" in path.parts or "archive" in path.parts or ".opus" in path.parts:
            continue
        # Only compress large log files (.jsonl, .log)
        if path.suffix in [".jsonl", ".log"]:
            age = get_file_age_days(path)
            if age > 14.0:
                archive_name = f"{path.stem}_{datetime.now().strftime('%Y%m%d')}.tar.gz"
                archive_path = archive_dir / archive_name
                
                if dry_run:
                    print(f"  [DRY-RUN] Will compress log: {path.relative_to(BASE_DIR)} -> {archive_name}")
                else:
                    try:
                        with tarfile.open(archive_path, "w:gz") as tar:
                            tar.add(path, arcname=path.name)
                        path.unlink()  # Delete original file after compression
                        archived_files += 1
                    except Exception as e:
                        print(f"  ❌ Error compressing {path.name}: {e}")
                        
    print(f"  📦 Old logs compressed & archived: {archived_files} files")

    # 4. Delete archives > 30 days
    deleted_archives = 0
    if archive_dir.exists():
        for arc in archive_dir.glob("*.tar.gz"):
            if get_file_age_days(arc) > 30.0:
                if not dry_run:
                    arc.unlink()
                deleted_archives += 1
                if dry_run:
                    print(f"  [DRY-RUN] Will delete expired archive: {arc.name}")
    print(f"  🗑️  Expired archives deleted: {deleted_archives} files")

def clean_redis_purity(dry_run=False):
    """Call safe Redis cleanup modules."""
    print("🔱 [REDIS] Starting Redis Matrix hygiene...")
    if not matrix or not matrix.client:
        print("  ❌ Error: Cannot connect to Redis.")
        return

    # 1. Trim streams exceeding limit
    if redis_hygiene:
        print("  ✂️  Trimming streams...")
        redis_hygiene.trim_streams(matrix.client)
        print("  🧹 Cleaning expired quota keys...")
        redis_hygiene.clean_expired_quota_keys(matrix.client)
        print("  🧹 Cleaning double-prefix keys...")
        redis_hygiene.clean_double_prefix_keys(matrix.client)
    else:
        print("  ❌ Cannot import redis_hygiene")

    # 2. Purge junk keys (unregistered keys)
    try:
        from redis_purity_purge import get_safe_patterns, is_safe
        safe_patterns = get_safe_patterns()
        all_keys = matrix.client.keys("*")
        junk_keys = [k for k in all_keys if not is_safe(k, safe_patterns)]
        
        if junk_keys:
            print(f"  ⚠️  Detected {len(junk_keys)} Junk keys:")
            for jk in junk_keys:
                if dry_run:
                    print(f"    - [DRY-RUN Junk]: {jk}")
                else:
                    matrix.client.delete(jk)
                    print(f"    - [DELETED Junk]: {jk}")
            print(f"  🗑️  Cleaned {len(junk_keys)} junk keys.")
        else:
            print("  ✅ Matrix purity achieved. No junk keys.")
    except Exception as e:
        print(f"  ❌ Error scanning junk keys: {e}")

def clean_docker_infra(dry_run=False):
    """Clean up Docker garbage (dangling images, stopped containers)."""
    print("🐳 [DOCKER] Starting Docker infrastructure cleanup...")
    if dry_run:
        print("  [DRY-RUN] Will execute 'docker container prune -f'")
        print("  [DRY-RUN] Will execute 'docker image prune -af --filter \"until=168h\"'")
        return
        
    try:
        # Container prune
        res1 = subprocess.run(["docker", "container", "prune", "-f"], capture_output=True, text=True, timeout=30)
        if res1.returncode == 0:
            print("  ✅ Docker container prune successful.")
        
        # Image prune (images unused > 7 days)
        res2 = subprocess.run(["docker", "image", "prune", "-af", "--filter", "until=168h"], capture_output=True, text=True, timeout=60)
        if res2.returncode == 0:
            print("  ✅ Docker image prune (until=168h) successful.")
    except Exception as e:
        print(f"  ❌ Error cleaning Docker: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ZCL Unified Self-Cleaner")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode without deleting")
    args = parser.parse_args()

    print(f"\n==================================================")
    print(f"🔱 ZCL UNIFIED CLEANER - Starting... [DRY_RUN={args.dry_run}]")
    print(f"==================================================")
    
    clean_local_files(args.dry_run)
    print("")
    clean_redis_purity(args.dry_run)
    print("")
    clean_docker_infra(args.dry_run)
    
    print(f"==================================================")
    print(f"🏁 Hygiene cleanup completed!")
    print(f"==================================================\n")

if __name__ == "__main__":
    main()
