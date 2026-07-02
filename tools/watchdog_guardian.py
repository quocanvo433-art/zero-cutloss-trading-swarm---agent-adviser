"""
🧬 DNA: v17.0 (Sovereign Purity & Survival Watchdog — Ollama Zombie Edition)
🏢 UNIT: WATCHDOG
🛠️ ROLE: SURVIVAL_SENTINEL + OLLAMA_ZOMBIE_KILLER
📖 DESC: Survival monitoring system (Watchdog) running OUTSIDE Docker at Linux Host level.
         Monitors Agent Heartbeats, detects GPU Deadlocks, terminates Ollama
         zombies consuming VRAM, and automatically restarts hung containers.
🔗 CALLS: docker CLI, tools/imperial_state.py, Ollama API
📟 I/O: Redis: zcl:system:gpu:lock, zcl:agent:*:heartbeat
🛡️ INTEGRITY: Do not use shell=True. Container names from hard Allow-List. Anti-Injection.
"""
import os
import sys
import time
import json
import logging
import subprocess
import threading

# Add root folder to path to import imperial_state
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from tools.imperial_state import matrix
except ImportError:
    from imperial_state import matrix

try:
    import requests as _req
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# ── Configuration ────────────────────────────────────────────────────────────
OLLAMA_BASE_URL    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CHECK_INTERVAL     = 30      # Check frequency (seconds)
STALE_LOCK_LIMIT   = 300     # Lock is considered stale after 300s without a new HB
HEARTBEAT_LIMIT    = 120     # Max HB silence (seconds) before warning
OLLAMA_IDLE_CYCLES = 6       # Number of idle cycles (6 x 30s = 3 minutes) before killing zombie

# Mapping Agent ID -> Container Name (Hard ALLOW-LIST, anti-injection)
AGENT_TO_CONTAINER = {
    "01": "zcl_hound_a01",
    "02": "zcl_phantom_a02",
    "03": "zcl_social_a03",
    "04": "zcl_scholar_a04",
    "05": "zcl_dpo_evaluator",
    "06": "Zero_Cutloss_Syndicate",
    # "07": RETIRED 2026-06-10 — Absorbed into A06 Butler
    "08": "zcl_commander",
    "09": "zcl_immunity_a09",
    "10": "zcl_emf_collector",
    "11": "zcl_emf_analyzer",
    "12": "zcl_aeo_detective",
}

# ── Logging ──────────────────────────────────────────────────────────────────
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [WATCHDOG] %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "watchdog_guardian.log"), encoding="utf-8"),
    ]
)
log = logging.getLogger("watchdog")


class WatchdogGuardian:
    def __init__(self):
        self.matrix = matrix
        self._ollama_idle_counter = 0   # Count number of Ollama idle cycles (no lock)
        log.info("🔱 Watchdog Guardian v17.0 connected to Imperial State Matrix")

    # ── Telegram Alert ────────────────────────────────────────────────────────
    def _tele_alert(self, msg: str):
        """Push alert to Telegram queue via A06."""
        try:
            self.matrix.xadd("SYSTEM", "telegram:queue", {"payload": json.dumps({
                "type":        "ALERT",
                "report_text": msg,
                "chat_id":     os.getenv("TELEGRAM_CHAT_ID"),
                "signature":   "WATCHDOG",
                "ts":          int(time.time()),
            })}, maxlen=1000)
        except Exception as e:
            log.warning(f"Failed to send Telegram alert: {e}")

    # ── Docker Restart (Anti-Injection) ───────────────────────────────────────
    def _restart_container(self, container_name: str, reason: str):
        """Restart container via docker CLI — container_name is always from Allow-List."""
        # Guard: only allow container names in whitelist
        allowed = set(AGENT_TO_CONTAINER.values())
        if container_name not in allowed:
            log.error(f"SECURITY: rejected invalid container restart: '{container_name}'")
            return

        log.warning(f"🔄 RESTARTING {container_name} — Reason: {reason}")
        self._tele_alert(
            f"🚨 **WATCHDOG ALERT**\n"
            f"Restarting `{container_name}`\n"
            f"Reason: `{reason}`"
        )
        try:
            # Use list args (NO shell=True) -> immune to Command Injection
            subprocess.run(["docker", "restart", container_name], check=True, timeout=30)
            log.info(f"✅ Restart successful: {container_name}")
            return True
        except Exception as e:
            log.error(f"❌ Restart failed {container_name}: {e}")
            return False

    # ── GPU Lock Parser ───────────────────────────────────────────────────────
    def _parse_gpu_lock(self) -> tuple[str | None, int]:
        """
        Read and parse key `zcl:system:gpu:lock`.
        New Format: "A04:1712620800"  →  (agent_id_str "04", held_since_unix)
        Return (None, 0) if no lock.
        """
        try:
            raw = self.matrix.redis.get("zcl:system:gpu:lock")
            if not raw:
                return None, 0
            val = raw.decode() if isinstance(raw, bytes) else str(raw)
            # Format: "A04:1712620800"
            parts = val.split(":")
            if len(parts) >= 2:
                agent_str = parts[0].lstrip("A")  # "04"
                held_ts   = int(parts[-1])
                return agent_str, held_ts
        except Exception:
            pass
        return None, 0

    # ── Ollama Zombie Killer ───────────────────────────────────────────────────
    def _check_ollama_zombie(self, gpu_lock_active: bool):
        """
        If no agent holds gpu:lock continuously >= OLLAMA_IDLE_CYCLES cycles,
        check if Ollama still has loaded models. If so -> Zombie -> Force unload.
        """
        if not _HAS_REQUESTS:
            return

        if gpu_lock_active:
            self._ollama_idle_counter = 0   # Reset when an agent is using GPU
            return

        self._ollama_idle_counter += 1
        log.debug(f"Ollama idle_counter = {self._ollama_idle_counter}/{OLLAMA_IDLE_CYCLES}")

        if self._ollama_idle_counter < OLLAMA_IDLE_CYCLES:
            return

        # Sufficient idle cycles -> check api/ps
        try:
            ps_resp = _req.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=5)
            if ps_resp.status_code != 200:
                return
            models = ps_resp.json().get("models", [])
            if not models:
                self._ollama_idle_counter = 0
                return

            # Model still loaded while no one holds lock -> ZOMBIE!
            log.critical(
                f"🧟 OLLAMA ZOMBIE DETECTED! {len(models)} model(s) loaded "
                f"but no agent holds gpu:lock in {OLLAMA_IDLE_CYCLES} cycles."
            )
            killed = []
            for m in models:
                model_name = m.get("name", "")
                if not model_name:
                    continue
                try:
                    resp = _req.post(
                        f"{OLLAMA_BASE_URL}/api/generate",
                        json={"model": model_name, "keep_alive": 0},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        killed.append(model_name)
                        log.info(f"💀 Force-unloaded zombie model: {model_name}")
                    else:
                        log.error(f"Unload {model_name} failed with status {resp.status_code}")
                except Exception as e:
                    log.error(f"Failed to unload {model_name}: {e}")

            if killed:
                self._tele_alert(
                    f"🧟 **WATCHDOG: Ollama Zombie Exterminated!**\n"
                    f"Forcefully unloaded {len(killed)} model(s) occupying VRAM:\n"
                    + "\n".join(f"• `{m}`" for m in killed)
                    + f"\nVRAM has been freed."
                )
            # Reset counter after killing
            self._ollama_idle_counter = -10  # Cooldown ~5 minutes before checking again

        except Exception as e:
            log.error(f"Error checking Ollama: {e}")

    # ── Main Monitor Cycle ────────────────────────────────────────────────────
    def monitor_cycle(self):
        now = int(time.time())

        # ── 1. GPU LOCK: Detect Deadlock ─────────────────────────────────
        agent_id, held_ts = self._parse_gpu_lock()
        gpu_lock_active   = agent_id is not None

        if gpu_lock_active and held_ts:
            held_duration = now - held_ts
            log.debug(f"GPU Lock: A{agent_id} held {held_duration}s")

            if held_duration > STALE_LOCK_LIMIT and agent_id in AGENT_TO_CONTAINER:
                # Check heartbeat of that agent
                last_hb = self.matrix.get(f"A{agent_id}", "heartbeat")
                hb_ts = 0
                if isinstance(last_hb, dict):
                    hb_ts = last_hb.get("timestamp_unix") or last_hb.get("ts") or 0
                elif last_hb:
                    try:
                        hb_ts = int(last_hb)
                    except (ValueError, TypeError):
                        pass

                hb_silence = (now - int(hb_ts)) if hb_ts else 9999
                if hb_silence > STALE_LOCK_LIMIT:
                    log.critical(
                        f"GPU DEADLOCK! A{agent_id} holds lock {held_duration}s, "
                        f"HB silent {hb_silence}s — Restarting!"
                    )
                    success = self._restart_container(
                        AGENT_TO_CONTAINER[agent_id],
                        f"GPU Deadlock: held lock {held_duration}s, HB silence {hb_silence}s"
                    )
                    # Delete lock after successful restart
                    if success:
                        try:
                            self.matrix.redis.delete("zcl:system:gpu:lock")
                        except Exception:
                            pass

        # ── 2. OLLAMA ZOMBIE KILLER ──────────────────────────────────────────
        self._check_ollama_zombie(gpu_lock_active)

        # ── 3. HEARTBEAT OF CRITICAL AGENTS ───────────────────────────────
        CRITICAL_AGENTS = {"01", "03", "04", "06", "09", "10", "11", "12"}
        for aid, cname in AGENT_TO_CONTAINER.items():
            if aid == "09":
                continue  # Do not indict myself

            last_hb = self.matrix.get(f"A{aid}", "heartbeat")
            hb_ts = 0
            if last_hb:
                if isinstance(last_hb, dict):
                    hb_ts = last_hb.get("timestamp_unix") or last_hb.get("ts") or 0
                else:
                    try:
                        hb_ts = int(last_hb)
                    except (ValueError, TypeError):
                        pass

            silence = (now - int(hb_ts)) if hb_ts else 999999

            if aid in CRITICAL_AGENTS and silence > HEARTBEAT_LIMIT * 3:
                log.warning(
                    f"⚠️ Agent A{aid} ({cname}) silent {silence}s "
                    f"— exceeded threshold {HEARTBEAT_LIMIT * 3}s"
                )
                # Alert via Telegram (automatic restart only when exceeding maximum threshold)
                if silence > HEARTBEAT_LIMIT * 10:
                    self._restart_container(cname, f"Heartbeat silence {silence}s")

    # ── Run Loop ──────────────────────────────────────────────────────────────
    def run(self):
        log.info("🔱 Watchdog Guardian loop started. Interval: %ds", CHECK_INTERVAL)
        log.info(f"📡 Ollama: {OLLAMA_BASE_URL} | Zombie threshold: {OLLAMA_IDLE_CYCLES}×{CHECK_INTERVAL}s")
        while True:
            try:
                self.monitor_cycle()
            except Exception as e:
                log.error(f"Error in monitor cycle: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    guardian = WatchdogGuardian()
    guardian.run()
