"""
🧬 DNA: v16.6 (Sovereign Purity & State Matrix)
🏢 UNIT: IMPERIAL_STATE
🛠️ ROLE: MATRIX_GOVERNOR
📖 DESC: Manage state and signal flow (Matrix) of the entire Empire via Redis. Support Pub/Sub, Streams, and synchronized Heartbeat.
🔗 CALLS: redis-py
📟 I/O: Redis: zcl:*, zcl:agent:*:heartbeat
🛡️ INTEGRITY: State-Consistency, Pulse-Synchronization, Atomic-Operations.
"""
import os
import json
import time
import logging
from typing import Optional, Any, Dict, List, Union
from pathlib import Path
import redis
from dotenv import load_dotenv
try:
    from redis_flow_logger import flow_logger
except ImportError:
    flow_logger = None

# ── 0. LOAD CONFIGURATION (DNA v16.6) ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env")

# ── 1. CONFIGURATION & LOGGER ────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://zcl_redis:6379")
REDIS_PASS = os.getenv("REDIS_PASSWORD", None)

logging.basicConfig(level=logging.INFO, format='[IMPERIAL_STATE] %(asctime)s %(message)s')
log = logging.getLogger("StateMatrix")

def setup_agent_logger(agent_id: str, logger_name: str) -> logging.Logger:
    import logging
    from logging.handlers import TimedRotatingFileHandler
    from pathlib import Path
    
    # ROOT/logs/
    _base = Path(__file__).resolve().parent.parent
    _log_dir = _base / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    
    _log_file = _log_dir / f"{agent_id.lower()}_run_2.log"
    
    # Create or get logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    # 24 hours circular log, backupCount=1 (1 day of history)
    try:
        fh = TimedRotatingFileHandler(str(_log_file), when="H", interval=24, backupCount=1, encoding="utf-8")
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(fh)
    except (PermissionError, FileNotFoundError):
        pass

    ch = logging.StreamHandler()
    formatter = logging.Formatter('[%(name)s] %(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    
    logger.addHandler(ch)
    return logger

# ── 2. DOMAIN DEFINITION (REGISTRY) ──────────────────────────────────────────
# Organize key prefixes to avoid chaos
PREFIX_MAP = {
    "SYSTEM":   "zcl:system",
    "QUOTA":    "zcl:quota",
    "DIEN_HONG": "zcl:dien_hong",
    "CAMPAIGN": "zcl:campaigns",
    "EVENT":    "zcl:events",
    "GUARDIAN":  "zcl:guardian",
    "EMF":       "zcl:emf",
    "MACRO":     "zcl:macro",
    "GEOPOLITICAL": "zcl:macro",
    "SENTIMENT": "zcl:sentiment",
    "AEO":       "zcl:aeo",
    "A01":       "zcl:a01",
    "A02":       "zcl:a02",
    "A03":       "zcl:a03",
    "A04":       "zcl:a04",
    "A05":       "zcl:a05",
    "A06":       "zcl:a06",
    "A07":       "zcl:a07",
    "A08":       "zcl:a08",
    "A09":       "zcl:a09",
    "A10":       "zcl:a10",
    "A11":       "zcl:a11",
    "A12":       "zcl:a12",
    "PSYCHO":    "zcl:psycho",
    "NARRATIVE": "zcl:narrative",
    "TEMP":      "zcl:tmp",
    # [CLAW_CODE_HOOK] Empire allocates distinct Domain for ClawCode 3-Agent OS
    "CLAW":      "zcl:claw",
}

class StateMatrix:
    """Unified state matrix for the entire swarm."""
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StateMatrix, cls).__new__(cls)
        return cls._instance

    @property
    def client(self):
        """Return Redis client, automatically initialize if absent or disconnected."""
        if self._client is None:
            self._init_redis()
        return self._client

    def _init_redis(self):
        try:
            # Use standard redis library to initialize
            self._client = redis.Redis.from_url(
                REDIS_URL, 
                password=REDIS_PASS, 
                decode_responses=True,
                socket_keepalive=True,
                retry_on_timeout=True
            )
            self._client.ping()
            log.info(f"Redis connected successfully: {REDIS_URL.split('@')[-1]}")
        except Exception as e:
            log.error(f"Redis Matrix connection error: {e}")
            self._client = None

    def _log_flow(self, action: str, key_type: str, key_name: str, summary: str = ""):
        """Internal helper to trace data flow for DNA v16.5."""
        if not self.client: return
        try:
            agent_id = os.getenv("AGENT_ID", "SWARM_CELL")
            prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
            full_key = f"{prefix}:{key_name}"
            flow_logger.log_flow(agent_id, action, full_key, summary)
        except:
            pass

    # ── LEVEL 1: BASIC GET / SET (UNIFIED PROTOCOL) ─────────────────────
    
    def set(self, key_type: str, key_name: str, value: Any, ttl: Optional[int] = None, **kwargs):
        """Save state to matrix. Supports both ttl and expire (alias)."""
        if not self.client: return
        
        # Handle 'expire' and 'ex' aliases for backward compatibility
        final_ttl = ttl or kwargs.get('expire') or kwargs.get('ex')
        
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        
        if isinstance(value, (dict, list)):
            val_str = json.dumps(value, ensure_ascii=False)
        else:
            val_str = str(value)
            
        try:
            self.client.set(full_key, val_str, ex=final_ttl)
            self._log_flow("SET", key_type, key_name, summary=str(val_str)[:100])
        except Exception as e:
            log.error(f"Matrix set '{full_key}' error: {e}")
            self._client = None # Reset for subsequent lazy initialization

    def get(self, key_type: str, key_name: str, default: Any = None) -> Any:
        """Read state (Auto-parse JSON)."""
        if not self.client: return default
        
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        
        try:
            v = self.client.get(full_key)
            if v is None: return default
            
            if isinstance(v, (str, bytes)):
                v_str = v.decode('utf-8') if isinstance(v, bytes) else v
                if (v_str.startswith('{') and v_str.endswith('}')) or (v_str.startswith('[') and v_str.endswith(']')):
                    try: return json.loads(v_str)
                    except: return v_str
            return v
        except Exception as e:
            log.error(f"Matrix get '{full_key}' error: {e}")
            self._client = None
            return default

    # ── LEVEL 2: HASH (FOR CAMPAIGNS & QUOTAS) ───────────────────────────────
    
    def hset(self, key_type: str, key_name: str, field: str, value: Any):
        if not self.client: return
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        
        val_str = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        try:
            self.client.hset(full_key, field, val_str)
            self._log_flow("HSET", key_type, f"{key_name}:{field}", summary=str(val_str)[:100])
        except Exception as e:
            log.error(f"Matrix hset '{full_key}' field '{field}' error: {e}")
            self._client = None

    def hget(self, key_type: str, key_name: str, field: str) -> Any:
        if not self.client: return None
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            raw = self.client.hget(full_key, field)
            if raw and isinstance(raw, (str, bytes)):
                v_str = raw.decode('utf-8') if isinstance(raw, bytes) else raw
                if (v_str.startswith('{') and v_str.endswith('}')) or (v_str.startswith('[') and v_str.endswith(']')):
                    try: return json.loads(v_str)
                    except: pass
                return v_str
            return raw
        except Exception as e:
            log.error(f"Matrix hget '{full_key}' field '{field}' error: {e}")
            self._client = None
            return None

    def hgetall(self, key_type: str, key_name: str) -> Dict[str, Any]:
        if not self.client: return {}
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            raw_dict = self.client.hgetall(full_key)
            result = {}
            for k, v in raw_dict.items():
                if v and isinstance(v, (str, bytes)):
                    v_str = v.decode('utf-8') if isinstance(v, bytes) else v
                    if (v_str.startswith('{') and v_str.endswith('}')) or (v_str.startswith('[') and v_str.endswith(']')):
                        try: result[k] = json.loads(v_str)
                        except: result[k] = v_str
                    else:
                        result[k] = v_str
                else:
                    result[k] = v
            return result
        except Exception as e:
            log.error(f"Matrix hgetall '{full_key}' error: {e}")
            self._client = None
            return {}

    def incr(self, key_type: str, key_name: str, amount: int = 1) -> int:
        """Increment Key value (Atomic)."""
        if not self.client: return 0
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            return self.client.incr(full_key, amount)
        except Exception as e:
            log.error(f"Matrix incr '{full_key}' error: {e}")
            self._client = None
            return 0

    def hdel(self, key_type: str, key_name: str, field: str):
        """Delete field from Hash."""
        if not self.client: return
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            self.client.hdel(full_key, field)
        except Exception as e:
            log.error(f"Matrix hdel '{full_key}' field '{field}' error: {e}")
            self._client = None

    def delete(self, key_type: str, key_name: str):
        """Delete Key."""
        if not self.client: return
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            self.client.delete(full_key)
        except Exception as e:
            log.error(f"Matrix delete '{full_key}' error: {e}")
            self._client = None

    # ── LEVEL 3: PUBSUB (MOUTH & EAR OF THE EMPIRE) ────────────────────────────
    
    def publish(self, channel: str, message: Any):
        """Publish signal to PubSub channel."""
        if not self.client: return
        
        full_channel = f"zcl:events:{channel}"
        msg_str = json.dumps(message, ensure_ascii=False) if isinstance(message, (dict, list)) else str(message)
        
        try:
            self.client.publish(full_channel, msg_str)
            self._log_flow("PUBLISH", "EVENT", channel, summary=str(msg_str)[:100])
        except Exception as e:
            log.error(f"Publish error {full_channel}: {e}")
            self._client = None

    def publish_heartbeat(self, agent_id: str, status: str = "ALIVE", metadata: Optional[Dict] = None):
        """Publish normalized heartbeat."""
        if isinstance(status, dict):
            metadata = status
            status = metadata.get("status", "ALIVE")

        payload = {
            "agent_id":      agent_id,
            "status":        status,
            "timestamp":     int(time.time()),
            **(metadata or {}),
        }
        self.publish(f"heartbeat:{agent_id}", payload)
        # Save to Redis with TTL for state tracking (Consolidated to Agent Namespace)
        self.set(agent_id, "heartbeat", payload, ttl=300)

    def subscribe(self, channels: List[str]):
        """Create PubSub object."""
        if not self.client: return None
        try:
            ps = self.client.pubsub()
            full_channels = [f"zcl:events:{c}" for c in channels]
            ps.subscribe(*full_channels)
            return ps
        except Exception as e:
            log.error(f"Matrix subscribe error: {e}")
            self._client = None
            return None

    # ── LEVEL 4: LISTS (FOR QUEUES & CHANGELOGS) ───────────────────────
    
    def lpush(self, key_type: str, key_name: str, value: Any, max_len: Optional[int] = None):
        if not self.client: return
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        msg_str = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        try:
            self.client.lpush(full_key, msg_str)
            if max_len: self.client.ltrim(full_key, 0, max_len - 1)
        except Exception as e:
            log.error(f"Matrix lpush '{full_key}' error: {e}")
            self._client = None

    def rpush(self, key_type: str, key_name: str, value: Any, max_len: Optional[int] = None):
        if not self.client: return
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        msg_str = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        try:
            self.client.rpush(full_key, msg_str)
            if max_len: self.client.ltrim(full_key, -max_len, -1)
        except Exception as e:
            log.error(f"Matrix rpush '{full_key}' error: {e}")
            self._client = None

    def lpop(self, key_type: str, key_name: str) -> Optional[Any]:
        if not self.client: return None
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            v = self.client.lpop(full_key)
            if v and isinstance(v, (str, bytes)):
                v_str = v.decode('utf-8') if isinstance(v, bytes) else v
                if (v_str.startswith('{') and v_str.endswith('}')) or (v_str.startswith('[') and v_str.endswith(']')):
                    try: return json.loads(v_str)
                    except: pass
                return v_str
            return v
        except Exception as e:
            log.error(f"Matrix lpop '{full_key}' error: {e}")
            self._client = None
            return None

    def rpop(self, key_type: str, key_name: str) -> Optional[Any]:
        if not self.client: return None
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            v = self.client.rpop(full_key)
            if v and isinstance(v, (str, bytes)):
                v_str = v.decode('utf-8') if isinstance(v, bytes) else v
                if (v_str.startswith('{') and v_str.endswith('}')) or (v_str.startswith('[') and v_str.endswith(']')):
                    try: return json.loads(v_str)
                    except: pass
                return v_str
            return v
        except Exception as e:
            log.error(f"Matrix rpop '{full_key}' error: {e}")
            self._client = None
            return None

    def blpop(self, key_type: str, key_name: str, timeout: int = 0) -> Optional[Any]:
        if not self.client: return None
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            res = self.client.blpop(full_key, timeout=timeout)
            if res:
                v = res[1]
                if v and isinstance(v, (str, bytes)):
                    v_str = v.decode('utf-8') if isinstance(v, bytes) else v
                    if (v_str.startswith('{') and v_str.endswith('}')) or (v_str.startswith('[') and v_str.endswith(']')):
                        try: return json.loads(v_str)
                        except: pass
                    return v_str
                return v
            return None
        except Exception as e:
            log.error(f"Matrix blpop '{full_key}' error: {e}")
            self._client = None
            return None

    def llen(self, key_type: str, key_name: str) -> int:
        if not self.client: return 0
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            return self.client.llen(full_key)
        except Exception as e:
            log.error(f"Matrix llen '{full_key}' error: {e}")
            self._client = None
            return 0
  
    def lrange(self, key_type: str, key_name: str, start: int, stop: int) -> List[Any]:
        if not self.client: return []
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            raw_list = self.client.lrange(full_key, start, stop)
            result = []
            for v in raw_list:
                if v and isinstance(v, (str, bytes)):
                    v_str = v.decode('utf-8') if isinstance(v, bytes) else v
                    if (v_str.startswith('{') and v_str.endswith('}')) or (v_str.startswith('[') and v_str.endswith(']')):
                        try: result.append(json.loads(v_str))
                        except: result.append(v_str)
                    else:
                        result.append(v_str)
                else:
                    result.append(v)
            return result
        except Exception as e:
            log.error(f"Matrix lrange '{full_key}' error: {e}")
            self._client = None
            return []

    # ── LEVEL 5: STREAMS (DNA v16.6) ──────────────────────────────────────────

    def xadd(self, key_type: str, key_name: str, fields: Dict[str, Any], maxlen: Optional[int] = None):
        if not self.client: return
        try:
            from packet_validator import safe_xadd
            return safe_xadd(self, key_type, key_name, fields, maxlen=maxlen)
        except Exception as e:
            prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
            full_key = f"{prefix}:{key_name}"
            log.error(f"Matrix xadd '{full_key}' error: {e}")
            self._client = None
            return None

    def xgroup_create(self, key_type: str, key_name: str, group_name: str, id: str = "$", mkstream: bool = False):
        if not self.client: return
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            self.client.xgroup_create(full_key, group_name, id=id, mkstream=mkstream)
        except redis.exceptions.ResponseError as e:
            if "already exists" not in str(e):
                log.error(f"Matrix xgroup_create '{full_key}' error: {e}")
        except Exception as e:
            log.error(f"Matrix xgroup_create '{full_key}' error: {e}")
            self._client = None

    def xreadgroup(self, key_type: str, key_name: str, group_name: str, consumer_name: str, count: int = 10, block: int = 0):
        if not self.client: return []
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            return self.client.xreadgroup(group_name, consumer_name, {full_key: ">"}, count=count, block=block)
        except Exception as e:
            log.error(f"Matrix xreadgroup '{full_key}' error: {e}")
            self._client = None
            return []

    def xread(self, key_type: str, key_name: str, last_id: str = "0", count: int = 100, block: Optional[int] = None):
        if not self.client: return []
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            return self.client.xread({full_key: last_id}, count=count, block=block)
        except Exception as e:
            log.error(f"Matrix xread '{full_key}' error: {e}")
            self._client = None
            return []

    def xack(self, key_type: str, key_name: str, group_name: str, *ids: str):
        if not self.client: return
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            self.client.xack(full_key, group_name, *ids)
        except Exception as e:
            log.error(f"Matrix xack '{full_key}' error: {e}")
            self._client = None
            
    def xrevrange(self, key_type: str, key_name: str, count: int = 100) -> List[Any]:
        if not self.client: return []
        prefix = PREFIX_MAP.get(key_type.upper(), "zcl:misc")
        full_key = f"{prefix}:{key_name}"
        try:
            return self.client.xrevrange(full_key, count=count)
        except Exception as e:
            log.error(f"Matrix xrevrange '{full_key}' error: {e}")
            self._client = None
            return []



# Initialize singleton instance
matrix = StateMatrix()

if __name__ == "__main__":
    print("--- Check Status Matrix v19.0 ---")
    matrix.set("TEMP", "test_key", {"status": "OK", "timestamp": time.time()}, ttl=10)
    val = matrix.get("TEMP", "test_key")
    print(f"Data read: {val}")
    matrix.publish("heartbeat:tester", {"agent": "Tester", "status": "Alive"})
