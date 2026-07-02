"""
🧬 DNA: v16.7 (Sovereign Watchdog)
🏢 UNIT: A04_CHROMA_WATCHDOG
🛠️ ROLE: CONTINUOUS_SYNC_MONITOR
📖 DESC: 24/7 Sentry. Detects creation/modification of engram files (.jsonl) in any subdirectory of dpo_lab/engrams/A04/
🔗 CALLS: A04_CHROMA_SYNC.py
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
log = logging.getLogger("A04_WATCHDOG")

class EngramAutoSyncHandler(FileSystemEventHandler):
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self._recent_events = {}

    def _debounce(self, path):
        """Avoid continuous triggering when a file is written multiple times within 1 second."""
        current_time = time.time()
        last_time = self._recent_events.get(path, 0)
        if current_time - last_time < 3.0: # Cooldown 3s
            return False
        self._recent_events[path] = current_time
        return True

    def _trigger_sync(self, filepath_str):
        path_obj = Path(filepath_str)
        
        # Only interested in JSONL engrams
        if not path_obj.suffix == '.jsonl':
            return
            
        # Example path: /app/dpo_lab/engrams/A04/boosting/file.jsonl
        subfolder = path_obj.parent.name
        filename = path_obj.name
        
        if not self._debounce(filepath_str):
            return
            
        log.info(f"🔥 [WATCHDOG DETECTED] Array {subfolder}/{filename} has just been created/modified!")
        
        # Trigger Local Sync (Pass file to A04_CHROMA_SYNC to Ingest Chroma)
        try:
            cmd = ["python", "/app/scripts/A04_CHROMA_SYNC.py", "--target", subfolder, "--file", filename]
            log.info(f"🔄 [WATCHDOG COMMAND] {' '.join(cmd)}")
            subprocess.Popen(cmd) # Run in background without blocking Watchdog
        except Exception as e:
            log.error(f"❌ [WATCHDOG TRIGGER ERROR] {e}")

    def on_created(self, event):
        if not event.is_directory:
            self._trigger_sync(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._trigger_sync(event.src_path)

def main():
    default_path = "/app/dpo_lab/engrams/A04"
    watch_path = sys.argv[1] if len(sys.argv) > 1 else default_path
    
    if not os.path.exists(watch_path):
        log.warning(f"⚠️ [A04_WATCHDOG] Engram directory {watch_path} not found. Waiting...")
        os.makedirs(watch_path, exist_ok=True)
    
    event_handler = EngramAutoSyncHandler(watch_path)
    observer = Observer()
    # Recursive watchdog - monitors boosting, genesis
    observer.schedule(event_handler, watch_path, recursive=True)
    observer.start()
    
    log.info(f"🔱 [A04_WATCHDOG] WATCHDOG ACTIVE ON {watch_path}. (Recursive scan enabled)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        log.info("🔱 [A04_WATCHDOG] Watchdog stopped.")
    observer.join()

if __name__ == "__main__":
    main()
