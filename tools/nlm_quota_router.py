"""
🧬 DNA: v16.7 (Sovereign Purity & Quota Shield)
🏢 UNIT: NLM_QUOTA_ROUTER
🛠️ ROLE: GLOBAL_QUOTA_ORCHESTRATOR
📖 DESC: Global Quota Management v76.6. Integrated Punishment Engine.
🔗 CALLS: imperial_state.py, redis_matrix.py
📟 I/O: Redis: zcl:QUOTA:*, logs/route_report.log
🧠 SOUL: agents/logic/soul/quota_logic.soul
🛡️ INTEGRITY: Organic Ecosystem - Immutable
"""
import os
import time
import logging
import random
from pathlib import Path
from datetime import datetime, timezone
try:
    from tools.imperial_state import matrix
except ImportError:
    from imperial_state import matrix

log = logging.getLogger("nlm_quota_router")

# ── 1. DYNAMIC KEY LOADER ─────────────────────────────────────────────────────
def _load_keys(prefix: str):
    keys = []
    # DNA v16.6: Detect both KEY and KEY_N (Numbered keys)
    env_keys = sorted([k for k in os.environ.keys() if k.startswith(prefix)])
    for k in env_keys:
        v = os.environ[k].strip()
        if v: keys.append(v)
    
    # Fallback for unnumbered keys
    root_key = os.getenv(prefix.rstrip("_"))
    if root_key and root_key not in keys:
        keys.append(root_key.strip())
    return keys

# ── 2. FULL MATRIX CONFIG (DNA v76.6) ────────────────────────────────────────
CONFIG_MAP = {
    "gemini-3.1-pro-preview":        {"rpm": 25,   "rpd": 250,    "tpm": 2000000},
    "gemini-3-flash-preview":       {"rpm": 1000, "rpd": 10000,  "tpm": 2000000},
    "gemini-3.1-flash-lite-preview": {"rpm": 4000, "rpd": 150000, "tpm": 4000000},
    "gemini-2.5-pro":               {"rpm": 5,    "rpd": 50,     "tpm": 100000},
    "gemini-flash-latest":          {"rpm": 15,   "rpd": 1500,   "tpm": 1000000},
    "qwen-3-235b-a22b-instruct-2507": {"rpm": 30,  "rpd": 14400,  "tpm": 30000},
    "qwen/qwen3-32b":                 {"rpm": 60,  "rpd": 6000,   "tpm": 500000},
    "qwen/qwen3.5-397b-a17b":       {"rpm": 5,    "rpd": 500,    "tpm": 260000},
    "qwen/qwen3.5-122b-a10b":       {"rpm": 10,   "rpd": 1000,   "tpm": 100000},
    "qwen/qwen3.5-35b-a3b":         {"rpm": 60,   "rpd": 1000,   "tpm": 1000000},
    "nvidia/nemotron-3-nano-30b-a3b": {"rpm": 100, "rpd": 20000,  "tpm": 2000000},
    # 🔱 OpenRouter Free Tier (v85.2 Cloud-Free Sovereign)
    "deepseek/deepseek-r1:free":                 {"rpm": 200,  "rpd": 2000,  "tpm": 1000000},
    "nvidia/nemotron-3-super-120b-a12b:free":    {"rpm": 200,  "rpd": 2000,  "tpm": 1000000},
    "nvidia/nemotron-3-nano-30b-a3b:free":       {"rpm": 200,  "rpd": 2000,  "tpm": 1000000},
    "openai/gpt-oss-120b:free":                  {"rpm": 200,  "rpd": 2000,  "tpm": 1000000},
    "qwen/qwen3-next-80b-a3b-instruct:free":     {"rpm": 200,  "rpd": 2000,  "tpm": 1000000},
    "qwen/qwen3-coder:free":                      {"rpm": 200,  "rpd": 2000,  "tpm": 1000000},
    "qwen/qwen3-coder-flash":                     {"rpm": 999,   "rpd": 9999,  "tpm": 10000000},
    "qwen/qwen3-coder-next":                      {"rpm": 999,   "rpd": 9999,  "tpm": 10000000},
    "arcee-ai/trinity-large-preview:free":         {"rpm": 200,  "rpd": 2000,  "tpm": 1000000},
    "nousresearch/hermes-3-llama-3.1-405b:free":   {"rpm": 200,  "rpd": 2000,  "tpm": 1000000},
    "google/gemma-4-31b-it:free":                  {"rpm": 200,  "rpd": 2000,  "tpm": 1000000},
    "qwen/qwen3.6-plus":                         {"rpm": 100,  "rpd": 2000,  "tpm": 1000000},
    "qwen/qwen3.5-flash-02-23":                  {"rpm": 100,  "rpd": 10000, "tpm": 2000000},
    "deepseek-v4-pro":                           {"rpm": 100,  "rpd": 2000,  "tpm": 1000000},
    "deepseek-v4-flash":                         {"rpm": 100,  "rpd": 10000, "tpm": 2000000},
}

# ── 3. CORE GLOBAL TRACKER (DNA v16.6) ───────────────────────────────────────
class QuotaTracker:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.keys = []
        self._set_keys_and_limits()
        self.num_keys = len(self.keys)

    def _set_keys_and_limits(self):
        if "gemini" in self.model_id:
            self.keys = _load_keys("GEMINI_API_KEY")
        elif "qwen-3-235b" in self.model_id:
            self.keys = _load_keys("CEREBRAS_API_KEY")
        elif "qwen3-32b" in self.model_id and ":free" not in self.model_id:
            self.keys = _load_keys("GROQ_API_KEY")
        elif "deepseek" in self.model_id:
            self.keys = _load_keys("DEEPSEEK_API_KEY")
        elif ":free" in self.model_id or "nemotron" in self.model_id or "gpt-oss" in self.model_id:
            # All :free + nemotron/gpt-oss models -> OpenRouter
            self.keys = _load_keys("OPENROUTER_API_KEY")
        elif "qwen" in self.model_id or "kimi" in self.model_id:
            self.keys = _load_keys("OPENROUTER_API_KEY")
            
        self.limits = CONFIG_MAP.get(self.model_id, {"rpm": 1, "rpd": 10})

    def _get_registry(self) -> dict:
        try:
            reg = matrix.get("QUOTA", f"{self.model_id}:registry")
        except Exception as e:
            log.error(f"[QUOTA] Redis get error: {e}")
            reg = None
        if not reg or not isinstance(reg, dict):
            reg = self._build_empty_registry()
        return self._reset_daily(reg)

    def _save_registry(self, registry: dict):
        try:
            matrix.set("QUOTA", f"{self.model_id}:registry", registry, ttl=90000)
        except Exception as e:
            log.error(f"[QUOTA] Redis set error: {e}")

    def _build_empty_registry(self) -> dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        reg = {"_date": today}
        for i in range(self.num_keys):
            # Initialize err_count = 0 to track violations
            reg[str(i)] = {"rpd_used": 0, "locked_until": 0, "err_count": 0}
        return reg

    def _reset_daily(self, registry: dict) -> dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if registry.get("_date") != today: return self._build_empty_registry()
        return registry

    def get_key(self) -> tuple:
        """Get available key (Sovereign Array)"""
        if self.num_keys == 0: return None, -1
        registry = self._get_registry()
        sequence = list(range(self.num_keys))
        random.shuffle(sequence)
        now = time.time()
        
        for idx in sequence:
            info = registry.get(str(idx), {})
            if now < info.get("locked_until", 0): continue
            if info.get("rpd_used", 0) >= self.limits["rpd"]: continue
            return self.keys[idx], idx
        return None, -1

    def get_key_by_index(self, key_idx: int) -> tuple:
        """Get exact key by index (Genesis Cycle)"""
        if self.num_keys == 0: return None, -1
        idx = key_idx % self.num_keys
        registry = self._get_registry()
        info = registry.get(str(idx), {})
        now = time.time()
        
        if now < info.get("locked_until", 0): return None, -1
        if info.get("rpd_used", 0) >= self.limits["rpd"]: return None, -1
        return self.keys[idx], idx

    def record_usage(self, idx: int, success: bool):
        """API Punishment System (5m/1d) - Iron Discipline"""
        if idx < 0: return
        client = matrix.client
        if not client: return
        
        lock_key = f"lock:quota:{self.model_id}:{idx}"
        try:
            with client.lock(lock_key, timeout=5):
                reg = self._get_registry()
                info = reg.get(str(idx), {})
                now = time.time()
                
                if success:
                    info["rpd_used"] = info.get("rpd_used", 0) + 1
                    info["err_count"] = 0 # reset blacklist
                else:
                    errs = info.get("err_count", 0) + 1
                    info["err_count"] = errs
                    
                    if errs == 1:
                        lock_time = 10  # 10 seconds so the next round can call cloud again
                        info["locked_until"] = now + lock_time
                        self._log_route_report("WARNING", f"Key[{idx}] failed 1st time -> Locked 10s.")
                    else:
                        lock_time = 60  # 60 seconds to recover TPM/RPM Quota instead of 1 day ban
                        info["locked_until"] = now + lock_time
                        self._log_route_report("CRITICAL", f"Key[{idx}] failed 2nd+ time -> Waiting for 60s Quota recovery.")
                
                reg[str(idx)] = info
                self._save_registry(reg)
        except Exception as e:
            log.error(f"[QUOTA] Lock record_usage error: {e}")

    def _log_route_report(self, level: str, msg: str):
        """Punishment Log: Armored (Sovereign Order v183.0)"""
        pass

    def all_exhausted(self, caller: str = "UNK") -> bool:
        """Check if all keys in Array are blocked (Locked/RPD)"""
        if self.num_keys == 0: return True
        registry = self._get_registry()
        now = time.time()
        for i in range(self.num_keys):
            info = registry.get(str(i), {})
            if now >= info.get("locked_until", 0) and info.get("rpd_used", 0) < self.limits["rpd"]:
                return False
        return True

    def get_wait_time(self) -> int:
        """Compute minimum wait seconds for an available key"""
        if self.num_keys == 0: return 3600
        registry = self._get_registry()
        now = time.time()
        wait_times = []
        for i in range(self.num_keys):
            info = registry.get(str(i), {})
            if info.get("rpd_used", 0) >= self.limits["rpd"]:
                # If exhausted for the day, wait until 00:01 UTC tomorrow (simplified)
                wait_times.append(3600) 
            else:
                wait_times.append(max(0, int(info.get("locked_until", 0) - now)))
        return min(wait_times) if wait_times else 60

    def get_status(self) -> dict:
        """Return quota status report for dashboard/logs"""
        registry = self._get_registry()
        return {
            "model": self.model_id,
            "num_keys": self.num_keys,
            "registry": registry,
            "limits": self.limits
        }

# ── 4. GLOBAL ACCESS LAYER ───────────────────────────────────────────────────
def get_tracker(model_id: str) -> QuotaTracker:
    return QuotaTracker(model_id)

def is_rate_limit(resp) -> bool:
    if hasattr(resp, 'status_code') and resp.status_code in {429, 503}: return True
    body = (resp.text if hasattr(resp, 'text') else str(resp)).lower()
    return any(s in body for s in ["rate_limit", "quota_exceeded", "too_many_requests"])

# 🔱 PRE-INSTANTIATED ROUTERS (For A04_BOOSTING/GENESIS)
groq_router     = QuotaTracker("qwen/qwen3-32b")
cerebras_router = QuotaTracker("qwen-3-235b-a22b-instruct-2507")
gemini_router   = QuotaTracker("gemini-3.1-pro-preview")
