"""
🧬 DNA: v16.6 (Sovereign Purity & Signal Audit)
🏢 UNIT: FLOW_LOGGER
🛠️ ROLE: SIGNAL_AUDITOR
📖 DESC: Redis Signal Flow Logging System (Redis Flow Logger). Monitors throughput, detects bottlenecks and ensures Matrix integrity.
🔗 CALLS: tools/imperial_state.py
📟 I/O: Redis: zcl:log:*, Console
🛡️ INTEGRITY: Signal-Transparency, Flow-Audit, Performance-Monitor.
"""

import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque

class RedisFlowLogger:
    """DNA v16.6 Metabolic Signal Tracer — Nervous system of the Swarm."""
    
    def __init__(self):
        self.log_dir = Path(__file__).resolve().parent.parent / "logs" / "redis_flow"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.buffer = deque()
        self.max_buffer = 100
        self.flush_interval = 20  # seconds
        self.last_flush = time.time()
        self.lock = threading.RLock()
        # [DNA v16.6] EMERGENCY: Disable by default to prevent 600MB explosions
        self.enabled = os.getenv("REDIS_FLOW_LOG", "OFF").upper() == "ON"
        self.sampling_rate = 1.0 # 100% flow logging for verification
        
        # Periodic flush thread
        self.stop_event = threading.Event()
        self.flush_thread = threading.Thread(target=self._auto_flush_loop, daemon=True)
        if self.enabled:
            self.flush_thread.start()

    def _get_log_file(self):
        today = datetime.now().strftime("%d-%m-%Y")
        return self.log_dir / f"redis_flow[{today}].log"

    def log_flow(self, agent_id: str, action: str, key: str, summary: str = ""):
        """Adds flow entry to logic buffer."""
        if not self.enabled:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{agent_id}] {action.upper()} [{key}]"
        if summary:
            entry += f" -> {summary}"
        
        with self.lock:
            self.buffer.append(entry)
            if len(self.buffer) >= self.max_buffer:
                self.flush()

    def flush(self):
        """Dumps buffer to disk and prunes logs older than 30 mins."""
        if not self.buffer:
            return
            
        with self.lock:
            lines_to_write = list(self.buffer)
            self.last_flush = time.time()
            
        try:
            log_file = self._get_log_file()
            content = "\n".join(lines_to_write) + "\n"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(content)
            
            with self.lock:
                for _ in range(len(lines_to_write)):
                    if self.buffer:
                        self.buffer.popleft()
            
            # [DNA v16.6] Metabolic Cleanup: Keep only last 30 minutes
            self._prune_old_logs(log_file)
        except Exception:
            pass

    def _prune_old_logs(self, log_file):
        """Metabolic Cleanup: Removes lines older than 30 minutes."""
        if not log_file.exists():
            return
            
        now = datetime.now()
        thirty_mins_ago = now - timedelta(minutes=30)
        
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            if not lines:
                return
                
            recent_lines = []
            for line in lines:
                try:
                    # Extract [HH:MM:SS]
                    if line.startswith("[") and "]" in line:
                        ts_str = line[1:9]
                        log_time = datetime.strptime(ts_str, "%H:%M:%S")
                        # Sync date with now as format only has HH:MM:SS
                        log_time = now.replace(hour=log_time.hour, minute=log_time.minute, second=log_time.second)
                        
                        # Handle day crossover (if log is from 23:55 and now is 00:05)
                        if log_time > now:
                            log_time -= timedelta(days=1)
                        
                        if log_time >= thirty_mins_ago:
                            recent_lines.append(line)
                    else:
                        # Keep lines that don't match format (rare)
                        recent_lines.append(line)
                except:
                    recent_lines.append(line)
            
            # Rewrite only if we actually removed something to save I/O
            if len(recent_lines) < len(lines):
                temp_file = log_file.with_suffix('.tmp')
                with open(temp_file, "w", encoding="utf-8") as f:
                    f.writelines(recent_lines)
                os.replace(temp_file, log_file)
        except Exception as e:
            # Silent fail for metabolic health
            pass

    def _auto_flush_loop(self):
        while not self.stop_event.is_set():
            time.sleep(1)
            if time.time() - self.last_flush >= self.flush_interval:
                self.flush()

# Singleton instance
flow_logger = RedisFlowLogger()
