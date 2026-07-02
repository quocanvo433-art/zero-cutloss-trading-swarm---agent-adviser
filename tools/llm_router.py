"""
🧬 DNA: v16.6 (Sovereign Purity - Cloud-Free Maximal Routing) [DNA Header]
🏢 UNIT: LLM_ORCHESTRATOR
🛠️ ROLE: BRAIN_ROUTER
📖 DESC: Core brain of LLM orchestrator v85.2 Cloud-Free Sovereign. Iron discipline.
🔗 CALLS: tools/nlm_quota_router.py, tools/imperial_state.py
📟 I/O: Redis: matrix (SYSTEM:genesis_turn, SYSTEM:boost_turn)
🛡️ INTEGRITY: Routing-Purity, Cloud-Free-Sovereign, Temperature-Control.
"""
import os
import json
import time
import re
import hashlib
import requests
import atexit
try:
    from tools.imperial_state import matrix
except ImportError:
    from imperial_state import matrix
from pathlib import Path

from datetime import datetime as _dt, timedelta as _timedelta
from dotenv import load_dotenv
import logging

# 🔱 MILITARY LOGGING CONFIGURATION 🔱
log = logging.getLogger("LLM_ROUTER")

# 🔱 NEW WEAPON: GOOGLE GENAI SDK (v18.4) 🔱
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# ── 1. SOVEREIGN MATRIX CONSTANTS (STRICT STATIC LOCK) ───────────────
# [🔱 AUDIT LLM_CONFIG.JSON - v85.2 Cloud-Free Sovereign]

# Common breathing interval for ALGO tier (Deep analysis) — "Continuous Scraping, Synchronous Thinking"
ALGO_CYCLE_INTERVAL_SEC = 3600  # Synchronize whole Swarm every 60 minutes

# ── GEMINI (BACKUP ONLY — NOT USED IN MAIN ROUTING) ──
M31_PRO   = "gemini-3.1-pro-preview"
M31_FLASH = "gemini-3-flash-preview"
M31_LITE  = "gemini-3.1-flash-lite-preview"
M25_PRO   = "gemini-2.5-pro"
M25_FLASH = "gemini-flash-latest"
M25_LITE  = "gemini-flash-lite-latest"

# ── CEREBRAS (4 free keys) ──
MC_235B   = "qwen-3-235b-a22b-instruct-2507"

# ── GROQ (4 free keys) ──
MG_32B    = "qwen/qwen3-32b"
GRQ_GPT_120B = "openai/gpt-oss-120b"
GRQ_LLAMA_70B = "llama-3.3-70b-versatile"
GRQ_GPT_20B = "openai/gpt-oss-20b"
GRQ_LLAMA_17B = "meta-llama/llama-4-scout-17b-16e-instruct"

# ── OPENROUTER FREE TIER (1 key — maximize cloud computing) ──
MOR_Q36P  = "moonshotai/kimi-k2.6:free"                       # A05, MASTER, ENGRAM, FALLBACK
MOR_NEM   = "google/gemma-3-27b-it:free"        # A03 news scraping (Placeholder)
MOR_NANO  = "meta-llama/llama-3.3-70b-instruct:free"         # A03 news scraping fallback (Placeholder)
MOR_GPT   = "openai/gpt-oss-120b:free"                     # A11, A12, Session
MOR_QNXT  = "qwen/qwen3-next-80b-a3b-instruct:free"        # Genesis backup
MOR_MINI  = "tencent/hy3-preview:free" 
MOR_CODER = "google/gemma-3-12b-it:free"                        # ClawCode Coder (480B A35B, Agentic Coding 262K ctx)
MOR_TRINITY = "arcee-ai/trinity-large-thinking:free" 
MOR_MINIMAX_25_FREE = "minimax/minimax-m2.5:free"
MOR_LAGUNA_M1_FREE = "poolside/laguna-m.1:free"
MOR_DEEPSEEK_V4_FLASH_FREE = "deepseek/deepseek-v4-flash:free"
MOR_HERMES_405B = "nousresearch/hermes-3-llama-3.1-405b:free"   # C01/C04 heavy reasoning
MOR_GEMMA4_31B  = "google/gemma-4-31b-it:free"                  # C01/C04 format-strict
MOR_NEMOTRON120 = "nvidia/nemotron-3-super-120b-a12b:free"       # C01/C04 fallback
MOR_QWEN3_CODER_FREE = "qwen/qwen3-coder:free"                  # C02/C03 Cloud escalation
MOR_DOLPHIN_24B_FREE = "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
MOR_OPENAI_GPT_20B_FREE = "openai/gpt-oss-20b:free"
MOR_NEMO_12B_FREE = "nvidia/nemotron-nano-12b-v2-vl:free"
MOR_NEMO_30B_FREE = "nvidia/nemotron-3-nano-30b-a3b:free"
MOR_GLM_45_FREE = "z-ai/glm-4.5-air:free"
MOR_DEEPSEEK_R1_FREE = "openai/gpt-oss-120b:free" # Replaced deprecated model
MOR_LLAMA3_8B_FREE = "meta-llama/llama-3.1-8b-instruct:free"
MOR_KIMI = "moonshotai/kimi-k2.6:free"
MOR_NEMOTRON_ULTRA_FREE = "nvidia/nemotron-3-ultra-550b-a55b:free"  # 550B (55B active) — Heavy reasoning
MOR_NEX_N2_PRO_FREE = "nex-agi/nex-n2-pro:free"                    # Nex AGI N2 Pro — Reasoning

# ── OPENROUTER PAID TIER ──
MOR_Q35P_PAID = "qwen/qwen3.6-plus"                       # OpenRouter credit control
MOR_Q3MAX_THINK = "qwen/qwen3.6-plus"                     # OpenRouter credit control

# ── OPENROUTER LIGHTWEIGHT PAID TIER (cheap) ──
MOR_DEEPSEEK_FLASH  = "deepseek/deepseek-v4-flash"                           # A10/A03 news scraping — anti-hallucination

# ── QWEN DASHSCOPE NATIVE — Round-Robin 49 Models (49M Free Tokens) ──
# Endpoint: https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions
# Auth: QWEN_API_KEY from .env | 1M free tokens per model | Expires 07/29/2026

QWEN_CRAWL_POOL = [
    # Flash/Plus/Turbo (1M tokens per model — Scraping speed)
    "qwen3.7-plus", "qwen3.7-plus-2026-05-26", "deepseek-v4-flash",
    "qwen3.6-flash", "qwen3.6-flash-2026-04-16",
    "qwen3.5-flash", "qwen3.5-flash-2026-02-23",
    "qwen3-coder-flash", "qwen-flash",
    "qwen3.6-35b-a3b", "qwen3.5-35b-a3b", "qwen3.6-27b", "qwen3.5-27b",
    "qwen3-32b", "qwen3-30b-a3b", "qwen3-30b-a3b-instruct-2507",
    "qwen2.5-72b-instruct", "qwen2.5-32b-instruct",
    "qwen3-next-80b-a3b-thinking", "qwen3-next-80b-a3b-instruct",
    "qwen3.5-122b-a10b", "qwen3-235b-a22b",
    # Demoted from Algo Pool (older models)
    "qwen3-235b-a22b-thinking-2507", "qwen3-235b-a22b-instruct-2507",
    "qwq-plus", "qwen-plus",
]

QWEN_ALGO_POOL = [
    # Flagship reasoning models
    "qwen3.7-plus", "qwen3.7-plus-2026-05-26", "deepseek-v4-flash",
]

QWEN_SUPREME_POOL = [
    # Flagship reasoning models for Supreme node A05 only
    "qwen3.7-max-2026-06-08", "qwen3.7-max", "qwen3.7-max-preview", "qwen3.7-max-2026-05-20", "qwen3.7-max-2026-05-17",
    "deepseek-v4-pro", "glm-5.1", "qwen3.7-plus", "qwen3.7-plus-2026-05-26", "deepseek-v4-flash",
]

# ── NVIDIA NIM FREE — 58 Models (integrate.api.nvidia.com) ──────────────────
# Endpoint: https://integrate.api.nvidia.com/v1/chat/completions
# Auth: NIM_API_KEY from .env | FREE tier

NIM_SUPREME_POOL = [
    "qwen/qwen3.5-397b-a17b",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "nvidia/nemotron-3-ultra-550b-a55b",
]

NIM_ALGO_POOL = [
    # === Tier S: Reasoning Engines (Best — runs BEFORE ALGO_PAID) ===
    "mistralai/mistral-large-3-675b-instruct-2512",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "minimaxai/minimax-m2.7",
    "z-ai/glm-5.1",
]

NIM_ALGO_SMART_POOL = [
    # === >=100B — Used when ALGO_PLUS quota is exhausted ===
    "stepfun-ai/step-3.7-flash",
    "mistralai/mistral-medium-3.5-128b",
    "mistralai/mistral-small-4-119b-2603",
    "meta/llama-4-maverick-17b-128e-instruct",
    "stepfun-ai/step-3.5-flash",
]

NIM_CRAWL_POOL = [
    # === Flash/Speed / Safety / Omni ===
    "qwen/qwen3.5-122b-a10b",
    "nvidia/nemotron-3.5-content-safety",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "mistralai/mistral-nemotron",
    "google/gemma-3n-e4b-it",
    "google/gemma-3n-e2b-it",
    "qwen/qwen3-coder-480b-a35b-instruct",
    # === 30-70B ===
    "bytedance/seed-oss-36b-instruct",
    "Abacus.AI/dracarys-llama-3.1-70b-instruct",
    "microsoft/phi-4-multimodal-instruct",
]

def _qwen_round_robin_wheel(pool: list, pool_key: str) -> list:
    """Creates a round-robin wheel — each call starts from the next model.
    Redis atomic counter ensures 11 agents are evenly distributed."""
    try:
        if matrix.client.get("zcl:system:quota:qwen:exhausted"):
            return []
    except:
        pass
    try:
        idx = int(matrix.incr("SYSTEM", f"qwen:rr:{pool_key}") or 1) - 1
    except:
        idx = 0
    n = len(pool)
    return [("QWEN", pool[(idx + i) % n]) for i in range(n)]

def _nim_round_robin_wheel(pool: list, pool_key: str) -> list:
    """NIM round-robin — same logic as Qwen but provider='NIM'.
    Redis atomic counter `nim:rr:{pool_key}` ensures 11 agents are evenly distributed."""
    try:
        if matrix.client.get("zcl:system:quota:nim:exhausted"):
            return []
    except:
        pass
    try:
        idx = int(matrix.incr("SYSTEM", f"nim:rr:{pool_key}") or 1) - 1
    except:
        idx = 0
    n = len(pool)
    return [("NIM", pool[(idx + i) % n]) for i in range(n)]

def _build_smart_free_wheel() -> list:
    """DRY: Group OR free + Groq wheel — shared for SMART + SMART_FLASH.
    Exclude nemotron-30b (poor news filtering). Exclude nemotron-120b (low quality)."""
    wheel = [
        ("OR", MOR_NEMOTRON_ULTRA_FREE),
        ("OR", MOR_NEX_N2_PRO_FREE),
        ("OR", MOR_HERMES_405B),
        ("OR", MOR_GPT),
        ("OR", MOR_TRINITY),
    ]
    try:
        num_groq = get_tracker(MG_32B).num_keys if get_tracker else 1
    except:
        num_groq = 1
    for _ in range(max(1, num_groq)):
        wheel.extend([
            ("GROQ", GRQ_GPT_120B),
            ("GROQ", GRQ_LLAMA_70B),
            ("GROQ", GRQ_GPT_20B),
        ])
    return wheel

def _call_algo(prompt: str, agent_id: str, label: str, temp: float, tier: str = "ALGO"):
    """Unified dispatch ALGO function — 3 tiers.
    - ALGO:        NIM Tier S (11) → Qwen ALGO (6) = 17 FREE models
    - SMART:       NIM Smart (10 >=100B) → OR free → Groq → Qwen ALGO = ~25 FREE
    - SMART_FLASH: NIM Crawl (35 >=14B) → OR free → Groq → Qwen ALGO = ~50 FREE
    Returns result text or None/ERROR.
    PAID fallback (OpenRouter/V4 Flash) is handled by CALLER."""
    
    aid_upper = str(agent_id).upper()
    if aid_upper.startswith(("A05", "05")):
        tier = "SUPREME"
        
    if tier == "SUPREME":
        # Supreme Node A05 only: QWEN_SUPREME_POOL + NIM_SUPREME_POOL + NIM_ALGO_POOL
        wheel = _qwen_round_robin_wheel(QWEN_SUPREME_POOL, "supreme")
        wheel.extend(_nim_round_robin_wheel(NIM_SUPREME_POOL, "supreme_nim"))
        wheel.extend(_nim_round_robin_wheel(NIM_ALGO_POOL, "algo"))
        wheel.append(("OR", MOR_KIMI))
        wheel.append(("OR", MOR_MINIMAX_25_FREE))
        return _execute_progress_array(wheel, prompt, agent_id, label, temp)

    if tier == "ALGO":
        # Tier S: Qwen ALGO → NIM best (prevents NIM timeouts)
        wheel = _qwen_round_robin_wheel(QWEN_ALGO_POOL, "algo")
        wheel.extend(_nim_round_robin_wheel(NIM_ALGO_POOL, "algo"))
        wheel.extend(_nim_round_robin_wheel(NIM_ALGO_SMART_POOL, "smart"))
        wheel.append(("OR", MOR_NEMOTRON_ULTRA_FREE))
        wheel.append(("OR", MOR_HERMES_405B))
        wheel.append(("OR", MOR_GLM_45_FREE))
        return _execute_progress_array(wheel, prompt, agent_id, label, temp)
    
    elif tier == "SMART":
        # NIM Smart (>=100B) → OR free → Groq → Qwen ALGO
        wheel = _nim_round_robin_wheel(NIM_ALGO_SMART_POOL, "smart")
        wheel.extend(_build_smart_free_wheel())
        wheel.extend(_qwen_round_robin_wheel(QWEN_ALGO_POOL, "algo"))
        return _execute_progress_array(wheel, prompt, agent_id, label, temp)
    
    elif tier == "SMART_FLASH":
        # NIM Flash (>=14B) → OR free → Groq → Qwen ALGO
        wheel = _nim_round_robin_wheel(NIM_CRAWL_POOL, "crawl_flash")
        wheel.extend(_build_smart_free_wheel())
        wheel.extend(_qwen_round_robin_wheel(QWEN_ALGO_POOL, "algo"))
        return _execute_progress_array(wheel, prompt, agent_id, label, temp)
    
    elif tier == "SWARM":
        # A08 SURVIVAL TIER — optimal speed + reliability, max 7 slots
        # Priority: OR free (stable) → NIM flash → Groq (backup if key active)
        wheel = [
            # OR free — most stable, ~5-10s
            ("OR", MOR_HERMES_405B),
            ("OR", MOR_GPT),
            ("OR", MOR_DEEPSEEK_R1_FREE),
            ("OR", MOR_TRINITY),
            # NIM flash small — fast if quota remains
            ("NIM", "meta/llama-4-maverick-17b-128e-instruct"),
            ("NIM", "mistralai/mistral-nemotron"),
            # Groq backup (if key recovers)
            ("GROQ", GRQ_LLAMA_70B),
        ]
        return _execute_progress_array(wheel, prompt, agent_id, label, temp)

# ── 2. INITIALIZATION ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env")

try:
    try:
        from tools.nlm_quota_router import QuotaTracker, is_rate_limit
    except ImportError:
        from nlm_quota_router import QuotaTracker, is_rate_limit
    def get_tracker(model_id): return QuotaTracker(model_id)
except ImportError as e:
    import logging
    logging.getLogger("LLM_ROUTER").error(f"FATAL: Missing tracker module! {e}")
    get_tracker = is_rate_limit = None

# ── 2.5 LOCAL OLLAMA HELPER (Unified Single-Model GPU Queue v2.0 - DISABLED) ──

def _call_ollama_fair(model: str, prompt: str, agent_id: str, label: str, temp: float) -> str:
    """Single-Compartment Architecture: 1 Model — 1 GPU — 1 Turn. Keep Alive 30s to save VRAM."""
    # Local Ollama bypassed completely (Cloud-Only requested)
    return "ERROR: LOCAL_OLLAMA_DISABLED"

# ── 2.7 SEMANTIC CACHE — Smart Shield (MD5 Hash + Redis TTL) ────────────
_SEMANTIC_CACHE_TTL = 7200  # 2 hours — identical prompt in 2h returns cache
_CACHE_SKIP_MODES = {"GENESIS", "MASTER", "ENGRAM", "BOOSTING", "REALTIME"}

# ── 2.7.1 REGEX FILTER — Strip <thinking> Tags (Phase 0 Grand Surgery) ──────
# Multi-tier filter: Supports nested tags, unclosed tags, and casing/whitespace variations.
_FULL_THINK_RE = re.compile(r'<(think(?:ing)?)\b[^>]*?>(?:(?!<(?:think(?:ing)?)\b[^>]*?>).)*?</\1>', re.DOTALL | re.IGNORECASE)
_UNCLOSED_THINK_RE = re.compile(r'<(think(?:ing)?)\b[^>]*?>.*$', re.DOTALL | re.IGNORECASE)
_STRAY_THINK_RE = re.compile(r'</(think(?:ing)?)\b[^>]*?>', re.IGNORECASE)

def _strip_thinking_tags(text: str) -> str:
    """Removes all <thinking>...</thinking> and <think>...</think> tags from LLM output.
    This is a MANDATORY step before caching or parsing JSON.
    🛡️ Sovereign Mechanism: Handles nested tags (10 levels), unclosed tags (greedy strip), and tag case variations."""
    if not text:
        return text
    
    # 1. Clear complete tag pairs (inside out, supporting nesting)
    result = text
    for _ in range(10):
        new_result = _FULL_THINK_RE.sub('', result)
        if new_result == result:
            break
        result = new_result
    
    # 2. Clear unclosed open tags (scanning to the end of string - Anti-Truncated Output)
    result = _UNCLOSED_THINK_RE.sub('', result)
    
    # 3. Clear stray closing tags
    result = _STRAY_THINK_RE.sub('', result)
    
    return result.strip()

def _validate_cacheable(response: str) -> bool:
    """Checks if the response is worth caching.
    Anti-Poisoned-Cache: Only cache when response contains valid JSON or meaningful text.
    Returns False if response is empty, error, or broken JSON."""
    if not response or str(response).startswith("ERROR:"):
        return False
    # If response contains signs of JSON -> validate it can be parsed
    stripped = response.strip()
    if '{' in stripped:
        start = stripped.find('{')
        end = stripped.rfind('}') + 1
        if start != -1 and end > start:
            try:
                json.loads(stripped[start:end])
                return True  # Valid JSON -> cache
            except (json.JSONDecodeError, ValueError):
                log.warning(f"[🛡️ ANTI_POISON] Response contains corrupted JSON — DO NOT CACHE!")
                return False  # Corrupted JSON -> DO NOT cache (prevent Poisoned Cache)
    # Plain text (no JSON) — cache if long enough
    return len(stripped) > 50

def _semantic_cache_key(prompt: str, agent_id: str) -> str:
    """Creates cache key from MD5(prompt + agent_root). Agent root = first 2 digits (A03_P1 -> 03)."""
    agent_root = "".join(filter(str.isdigit, str(agent_id).upper()))[:2]
    digest = hashlib.md5((prompt + agent_root).encode("utf-8", errors="ignore")).hexdigest()
    return f"scache:{agent_root}:{digest}"

def _semantic_cache_get(prompt: str, agent_id: str) -> str | None:
    """Returns cached response if exists, None if cache miss."""
    try:
        key = _semantic_cache_key(prompt, agent_id)
        cached = matrix.client.get(f"zcl:system:{key}")
        if cached:
            val = cached.decode("utf-8") if isinstance(cached, bytes) else str(cached)
            if val and not val.startswith("ERROR:"):
                return val
    except Exception:
        pass
    return None

def _semantic_cache_set(prompt: str, agent_id: str, response: str):
    """Saves response to cache with TTL 2h.
    🛡️ Phase 0 Grand Surgery: Strip <thinking> tags + validate JSON before caching."""
    try:
        if not response or str(response).startswith("ERROR:"):
            return  # Do not cache error results
        # 🔱 PHASE 0: Strip thinking tags before caching
        clean_response = _strip_thinking_tags(response)
        # 🔱 PHASE 0: Validate — only cache when response is clean and valid
        if not _validate_cacheable(clean_response):
            return  # Anti-Poisoned Semantic Cache
        key = _semantic_cache_key(prompt, agent_id)
        matrix.client.setex(f"zcl:system:{key}", _SEMANTIC_CACHE_TTL, clean_response)
    except Exception:
        pass

def _evaluate_smart_diff(prompt: str, agent_id: str) -> tuple[str, str | None]:
    """Checks if the new prompt has a CORE difference compared to the previous Paid call.
    Returns Tuple: (Decision Type, Old Result if available)
    - "CACHE": >= 96% -> Reuse the exact old result.
    - "FLASH": 80% - 96% -> Perform lightweight update using Flash.
    - "PLUS": < 80% -> Trigger completely new call."""
    try:
        import difflib
        last_prompt_key = f"zcl:system:last_prompt:{agent_id}"
        last_result_key = f"zcl:system:last_result:{agent_id}"
        
        last_prompt_bytes = matrix.client.get(last_prompt_key)
        if not last_prompt_bytes: return "PLUS", None
            
        last_prompt = last_prompt_bytes.decode("utf-8") if isinstance(last_prompt_bytes, bytes) else str(last_prompt_bytes)
        if not last_prompt: return "PLUS", None
 
        last_res_bytes = matrix.client.get(last_result_key)
        last_res = None
        if last_res_bytes:
            val = last_res_bytes.decode("utf-8") if isinstance(last_res_bytes, bytes) else str(last_res_bytes)
            if val and not val.startswith("ERROR:"):
                last_res = val
                
        if not last_res: return "PLUS", None
        
        # 1. Quick length comparison (Mismatch > 20% indicates significant new data added)
        len_cur, len_old = len(prompt), len(last_prompt)
        if len_old == 0: return "PLUS", None
        if abs(len_cur - len_old) / max(len_old, 1) > 0.20:
            return "PLUS", None
            
        # 2. Quick Ratio Algorithm
        ratio = difflib.SequenceMatcher(None, prompt, last_prompt).quick_ratio()
        
        if ratio >= 0.96:
            return "CACHE", last_res
        elif ratio >= 0.80:
            return "FLASH", last_res
        else:
            return "PLUS", None
            
    except Exception as e:
        log.warning(f"🔱 [SMART_DIFF_ERROR] {e}")
    return "PLUS", None

def _save_last_state(prompt: str, agent_id: str, response: str):
    """Stores the last code state to check Smart Diff (TTL 4h)
    🛡️ Phase 0: Strip thinking tags + validate before saving."""
    try:
        if not response or str(response).startswith("ERROR:"): return
        # 🔱 PHASE 0: Strip thinking tags
        clean_response = _strip_thinking_tags(response)
        if not _validate_cacheable(clean_response): return
        matrix.client.setex(f"zcl:system:last_prompt:{agent_id}", 14400, prompt)
        matrix.client.setex(f"zcl:system:last_result:{agent_id}", 14400, clean_response)
    except: pass


# ═══════════════════════════════════════════════════════════════════════════
# 🔱 GOLDEN CALL CACHE — LEVERAGE EVERY LIVE CALL
# "API might fail, but codebase utilizes rare successful live calls"
# ═══════════════════════════════════════════════════════════════════════════
_GOLDEN_CACHE_TTL = 6 * 3600  # 6h — preserve valuable LLM results

def _golden_cache_key(prompt: str, agent_id: str) -> str:
    """Creates golden cache key from MD5(prompt[:500] + agent_root)."""
    agent_root = "".join(filter(str.isdigit, str(agent_id).upper()))[:2]
    digest = hashlib.md5((prompt[:500] + agent_root).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"zcl:llm:golden:{agent_root}:{digest}"

def _golden_cache_set(prompt: str, agent_id: str, response: str):
    """🏆 Saves successful LLM results to Golden Cache (TTL 6h).
    Every rare live API call -> cache it -> reuse when 429 occurs."""
    try:
        if not response or str(response).startswith("ERROR:"): return
        clean = _strip_thinking_tags(response)
        if not _validate_cacheable(clean): return
        key = _golden_cache_key(prompt, agent_id)
        matrix.client.setex(key, _GOLDEN_CACHE_TTL, clean)
        # Store an "any" key to quickly find the latest response of the agent
        agent_root = "".join(filter(str.isdigit, str(agent_id).upper()))[:2]
        matrix.client.setex(f"zcl:llm:golden:{agent_root}:_latest", _GOLDEN_CACHE_TTL, clean)
    except Exception:
        pass

def _golden_cache_get(prompt: str, agent_id: str) -> str | None:
    """🏆 Retrieves response from Golden Cache (exact match)."""
    try:
        key = _golden_cache_key(prompt, agent_id)
        cached = matrix.client.get(key)
        if cached:
            val = cached.decode("utf-8") if isinstance(cached, bytes) else str(cached)
            if val and not val.startswith("ERROR:"):
                return val
    except Exception:
        pass
    return None

def _golden_cache_get_any(agent_id: str) -> str | None:
    """🏆 Retrieves ANY latest response of the agent from Golden Cache.
    Last resort when exact match is missing."""
    try:
        agent_root = "".join(filter(str.isdigit, str(agent_id).upper()))[:2]
        cached = matrix.client.get(f"zcl:llm:golden:{agent_root}:_latest")
        if cached:
            val = cached.decode("utf-8") if isinstance(cached, bytes) else str(cached)
            if val and not val.startswith("ERROR:"):
                return val
    except Exception:
        pass
    return None

def _provider_fail_track(provider: str, error_text: str = ""):
    """Track consecutive failures per provider. Set exhausted flag after 3 fails.
    If QWEN returns FreeTierOnly error (exhausted monthly quota) -> lock 24h instead of 30 min."""
    try:
        prov_key = f"zcl:llm:provider:{provider.lower()}:fail_count"
        count = matrix.client.incr(prov_key)
        matrix.client.expire(prov_key, 1800)  # Reset after 30 min
        if count >= 3:
            exhaust_key = f"zcl:system:quota:{provider.lower()}:exhausted"
            # QWEN FreeTierOnly = exhausted monthly quota -> lock 24h, no useless retries
            is_monthly_exhausted = (provider == "QWEN" and "FreeTierOnly" in error_text)
            ttl = 86400 if is_monthly_exhausted else 1800
            ttl_label = "24 hours (monthly quota)" if is_monthly_exhausted else "30 minutes"
            matrix.client.setex(exhaust_key, ttl, "1")
            log.warning(f"[🔱 QUOTA_EXHAUST] Provider {provider} failed {count}x consecutively -> marked exhausted for {ttl_label}")
    except Exception:
        pass

def _provider_fail_reset(provider: str):
    """Reset fail count when provider succeeds."""
    try:
        matrix.client.delete(f"zcl:llm:provider:{provider.lower()}:fail_count")
        matrix.client.delete(f"zcl:system:quota:{provider.lower()}:exhausted")
    except Exception:
        pass

def _call_crawl_pipeline(prompt: str, agent_id: str, temp: float, aid: str) -> str:
    """4-Tier Scraping Pipeline: Token Blocker -> Free Tier -> Branching (Coder/Flash) -> Fallback (Infinite Cloud)"""
    est_tokens = len(prompt) // 3
    
    # Exceeds 20k Tokens -> Start Chunking mechanism to partition data instead of discarding
    if est_tokens > 20000:
        log.warning(f"[🔱 CRAWL_CHUNKING] Data payload of {est_tokens} tokens exceeds 20k limit! Launching DNA Chunking Engine...")
        
        try:
            from tools.chunking_engine import chunk_text, process_chunks_with_llm
        except ImportError:
            try: from chunking_engine import chunk_text, process_chunks_with_llm
            except: return "ERROR: MISSING_CHUNKING_ENGINE"
            
        # Split into chunks of ~5k tokens (within smooth running range of Qwen Flash/Free)
        chunks = chunk_text(prompt, chunk_size_tokens=5000, overlap_tokens=400)
        
        def _mini_recursive_call(chunk_raw_prompt: str) -> str:
            # Recursively call the CRAWL pipeline for this small chunk
            return _call_crawl_pipeline(chunk_raw_prompt, agent_id, temp, aid)
            
        # Template to append anti-hallucination instruction when model processes chunks
        ptmp = "{chunk_info}\n\n[SLICED CONTEXT]: You are processing a piece of a large document. Please execute the request (if any) or extract/observe following a seamless logic.\n\n{chunk_data}"
        
        merged_res = process_chunks_with_llm(
            chunks=chunks,
            prompt_template=ptmp,
            llm_call=_mini_recursive_call,
            merge_strategy="concatenate", # Concatenate to prevent data loss
            chunk_label="OVERLOAD_CRAWL",
            agent_name=aid
        )
        
        if merged_res and not str(merged_res).startswith("ERROR:"):
            _semantic_cache_set(prompt, aid, merged_res)
            return merged_res
            
        return "ERROR: CHUNKING_PIPELINE_FAILED"
        
    # Level 1: CRAWL_FREE loop (New Wheel Structure: 8 Models - Leverage Free Tier)
    free_wheel = []
    
    try:
        # Automatically fetch the number of existing API Keys (Gemini & Groq)
        num_gemini = get_tracker(M31_LITE).num_keys if get_tracker else 1
        num_groq = get_tracker(MG_32B).num_keys if get_tracker else 1
    except:
        num_gemini, num_groq = 3, 3 # Fallback if QuotaTracker crashes
        
    # 2 Wheel rounds looping N Keys
    for _ in range(max(1, num_gemini)): free_wheel.append(("GEMINI", M31_LITE))
    for _ in range(max(1, num_groq)): 
        free_wheel.append(("GROQ", MG_32B))
        free_wheel.append(("GROQ", GRQ_GPT_120B))
        free_wheel.append(("GROQ", GRQ_LLAMA_70B))
        free_wheel.append(("GROQ", GRQ_GPT_20B))
        free_wheel.append(("GROQ", GRQ_LLAMA_17B))
    
    # OpenRouter Wheel (Only preserve models >= 24B with quality — filter low-quality models to prevent "false success")
    free_wheel.extend([
        ("OR", MOR_QNXT),
        ("OR", MOR_DEEPSEEK_V4_FLASH_FREE),
        ("OR", MOR_LAGUNA_M1_FREE),
        ("OR", MOR_HERMES_405B),
        ("OR", MOR_NEMOTRON120),
        ("OR", MOR_DOLPHIN_24B_FREE),
        ("OR", MOR_OPENAI_GPT_20B_FREE),
        ("OR", MOR_GLM_45_FREE),
        ("OR", MOR_NANO),
        ("OR", MOR_GPT),
        ("OR", MOR_MINI),
        ("OR", MOR_GEMMA4_31B),
        ("OR", MOR_QWEN3_CODER_FREE),
        ("OR", MOR_KIMI),
    ])
    
    # Level 1.5: Qwen DashScope Round-Robin (11M tokens — End of wheel, after free providers)
    free_wheel.extend(_qwen_round_robin_wheel(QWEN_CRAWL_POOL, "crawl"))
    
    # Level 1.6: NIM FREE Round-Robin (35 models >= 14B — After Qwen quota exhausted)
    free_wheel.extend(_nim_round_robin_wheel(NIM_CRAWL_POOL, "crawl"))
    # Level 1.7: NIM SMART (10 models >= 100B — Final fallback before PAID)
    free_wheel.extend(_nim_round_robin_wheel(NIM_ALGO_SMART_POOL, "smart"))
    
    # Activate Wheel (Loop 3 times with 60s sleep if rate limited)
    free_retries = 0
    while free_retries < 3:
        res_free = _execute_progress_array(free_wheel, prompt, agent_id, f"[🔱 CRAWL_FREE_ROUND_{free_retries+1}]", temp)
        if res_free and not str(res_free).startswith("ERROR:"):
            _semantic_cache_set(prompt, aid, res_free)
            _save_last_state(prompt, aid, res_free)
            return res_free
            
        free_retries += 1
        if free_retries < 3:
            log.warning(f"[🔱 CRAWL_FREE] Round {free_retries} failed (Rate limit). Sleeping 60s to recover APIs before round {free_retries+1}...")
            import time
            time.sleep(60)
    
    # 🔱 [CLOUD-ONLY] Level 2: Fallback via cheap Paid API (Deepseek V4 Flash)
    log.warning(f"[🔱 CRAWL_FREE] Exhausted after 3 rounds. Falling back to Level 2 (PAID CRAWL): {MOR_DEEPSEEK_FLASH}")
    retries = 0
    while retries < 5:
        res_cloud, _, _ = execute_provider("DEEPSEEK", MOR_DEEPSEEK_FLASH, prompt, agent_id, "[🔱 CRAWL_CLOUD_INF]", temp)
        if res_cloud and not str(res_cloud).startswith("ERROR:"):
            _semantic_cache_set(prompt, aid, res_cloud)
            _save_last_state(prompt, aid, res_cloud)
            return res_cloud
        time.sleep(10)
        retries += 1
        
    log.error(f"[🔱 CRAWL_CLOUD_EXHAUSTED] {aid} Failed to fetch data. Falling back to STALE cache if available...")
    try:
        last_res_bytes = matrix.client.get(f"zcl:system:last_result:{aid}")
        if last_res_bytes:
            stale_res = last_res_bytes.decode("utf-8") if isinstance(last_res_bytes, bytes) else str(last_res_bytes)
            log.warning(f"[🛡️ CRAWL_STALE_RECOVERY] {aid} using stale data to prevent swarm collapse.")
            return stale_res
    except Exception as e:
        log.error(f"Failed to read stale cache for {aid}: {e}")
        
    return "ERROR: CRAWL_CLOUD_EXHAUSTED"


# ── 3. MATRIX PROCESS MODE (UNIT PROGRESS WHEEL) ───────────────────────

def router_api_call(prompt: str, agent_id: str = "A04", brain_mode: str = "NORMAL", est_tokens: int = 0, **kwargs) -> str:
    """Main dispatch orchestrator (DNA v85.3 Semantic Cache + Unleashed Plus)"""
    
    # 🔱 MATRIX BRIDGE: Standardize call mode from old code to satisfy new logic 🔱
    active_mode = brain_mode
    if "GENESIS" in brain_mode: active_mode = "GENESIS"
    if "ENGRAM" in brain_mode:  active_mode = "ENGRAM"
    if "MASTER" in brain_mode:  active_mode = "MASTER"
    if "BOOSTING" in brain_mode: active_mode = "BOOSTING"
    if "REALTIME" in brain_mode: active_mode = "REALTIME"

    # Get filtered temperature
    temp = _get_iron_discipline_temp(active_mode)
    aid = str(agent_id).upper()
    unit_num = "".join(filter(str.isdigit, aid)) # Get agent identifier number

    # ═══════════════════════════════════════════════════════════════════════
    # 🛡️ SEMANTIC CACHE — Smart Shield (0 Tokens, 0 API Calls) 🛡️
    # ═══════════════════════════════════════════════════════════════════════
    if active_mode not in _CACHE_SKIP_MODES:
        cached = _semantic_cache_get(prompt, aid)
        if cached:
            # Temporarily BYPASS cache by directive
            # log.info(f"[🛡️ CACHE_HIT] {aid} — Return cache (MD5 match, 0 API call, 0 token)")
            # return cached
            log.warning(f"Bypassing [🛡️ CACHE_HIT] for {aid} — FORCING LLM CALL!")
    
    # ════════════════════════════════════════════════════════════════════════
    # 🔱 PROCESS 1: GENESIS SCAN (Groq 4-Key + Qwen3-Next Backup) 🔱
    # ════════════════════════════════════════════════════════════════════════
    if active_mode == "GENESIS" or "GENESIS" in aid:
        total_turn = matrix.incr("SYSTEM", "genesis_turn")
        
        # Tier 1: Qwen3-Next 80B (OpenRouter - Top priority)
        res, _, _ = execute_provider("OR", MOR_QNXT, prompt, agent_id, "[🔱 GENESIS]", temp)
        if res and not str(res).startswith("ERROR:"):
            return res

        # Tier 2-5: Groq 32B (4 rotating keys - Fallback)
        groq_wheel = [
            ("GROQ", MG_32B, 0, "[🔱 GENESIS_BACKUP]"),
            ("GROQ", MG_32B, 1, "[🔱 GENESIS_BACKUP]"),
            ("GROQ", MG_32B, 2, "[🔱 GENESIS_BACKUP]"),
            ("GROQ", MG_32B, 3, "[🔱 GENESIS_BACKUP]"),
        ]
        for i in range(len(groq_wheel)):
            idx_wheel = (total_turn - 1 + i) % len(groq_wheel)
            prov, model, k_idx, label_site = groq_wheel[idx_wheel]
            res = _execute_target_slot(prov, model, k_idx, prompt, agent_id, label_site, temp, total_turn, allow_fallback=False)
            if res and not str(res).startswith("ERROR:"):
                return res
        
        return "ERROR: ALL_GENESIS_PROVIDERS_EXHAUSTED"

    # ════════════════════════════════════════════════════════════════════════
    # 🔱 PROCESS 2A: MASTER LATTICE (Qwen 3.5 Plus Paid -> Max Thinking) 🔱
    # ════════════════════════════════════════════════════════════════════════
    if active_mode == "MASTER" or aid.endswith("MASTER"):
        mode_label = "[🔱 MASTER]"
        _HOUR_LIMIT = 5
        _WINDOW = 3600
        _rl_key = f"quota:paid:{_dt.now().strftime('%Y%m%d_%H')}"
        _current_used = int(matrix.get("SYSTEM", _rl_key) or 0)
        
        if _current_used < _HOUR_LIMIT:
            res = _call_algo(prompt, agent_id, mode_label, temp, "ALGO")
            if res and not str(res).startswith("ERROR:"):
                matrix.incr("SYSTEM", _rl_key)
                matrix.client.expire(f"zcl:system:{_rl_key}", _WINDOW)
                return res
            log.warning(f"[🔱 MASTER] Plus failed — fallback MAX_THINKING")
        
        _rl_max_key = f"quota:max_think:{_dt.now().strftime('%Y%m%d_%H')}"
        _max_used = int(matrix.get("SYSTEM", _rl_max_key) or 0)
        
        if _max_used < 4:
            res_max = _call_algo(prompt, agent_id, f"{mode_label}_MAX", temp, "ALGO")
            if res_max and not str(res_max).startswith("ERROR:"):
                matrix.incr("SYSTEM", _rl_max_key)
                matrix.client.expire(f"zcl:system:{_rl_max_key}", _WINDOW)
                return res_max
        else:
            log.warning(f"{mode_label} Max Think Quota exhausted ({_max_used}/4).")
        
        # 🔱 [CLOUD-ONLY] NO local fallback — return ERROR to retry later
        return "ERROR: MASTER_ALL_CLOUD_EXHAUSTED"

    # ════════════════════════════════════════════════════════════════════════
    # 🔱 PROCESS 2B: ENGRAM DISTILL (Cloud Max Thinking Directly) 🔱
    # ════════════════════════════════════════════════════════════════════════
    if active_mode == "ENGRAM" or aid.endswith("ENGRAM"):
        mode_label = "[🔱 ENGRAM]"
        # 🔱 [CLOUD-ONLY] Skip Local, proceed straight to Cloud Max Thinking
        log.info(f"{mode_label} Cloud-Only mode — calling Max Thinking directly...")
        
        _WINDOW = 3600
        _rl_max_key = f"quota:max_think:{_dt.now().strftime('%Y%m%d_%H')}"
        _max_used = int(matrix.get("SYSTEM", _rl_max_key) or 0)
        
        if _max_used < 4:
            res_max = _call_algo(prompt, agent_id, f"{mode_label}_MAX_FALLBACK", temp, "ALGO")
            if res_max and not str(res_max).startswith("ERROR:"):
                matrix.incr("SYSTEM", _rl_max_key)
                matrix.client.expire(f"zcl:system:{_rl_max_key}", _WINDOW)
                return res_max
        else:
            log.warning(f"{mode_label} Max Think Quota exhausted ({_max_used}/4).")
            
        return "ERROR: ALL_ENGRAM_PROVIDERS_FAILED"

    # ════════════════════════════════════════════════════════════════════════
    # 🔱 PROCESS 3: BOOSTING (Cerebras 235B — 4-Key - DISABLED) 🔱
    # ════════════════════════════════════════════════════════════════════════
    if active_mode == "BOOSTING":
        log.warning("🔱 [BYPASS_CEREBRAS] Cerebras exhausted, returning empty by directive.")
        return "ERROR: CEREBRAS_EXHAUSTED"

    # ════════════════════════════════════════════════════════════════════════
    # 🔱 PROCESS 4: A04 REALTIME (Process stream immediately) 🔱
    # ════════════════════════════════════════════════════════════════════════
    if active_mode == "REALTIME":
        mode_label = "[🔱 A04_REALTIME]"
        _HOUR_WINDOW = 3600
        _rl_key = f"quota:realtime:{aid}:{_dt.now().strftime('%Y%m%d_%H')}"
        _used = int(matrix.get("SYSTEM", _rl_key) or 0)
        
        res = None
        # Use Qwen Plus for high sensitivity
        if _used < 15:
            res = _call_algo(prompt, agent_id, mode_label, temp, "ALGO")
            if res and not str(res).startswith("ERROR:"):
                matrix.incr("SYSTEM", _rl_key)
                matrix.client.expire(f"zcl:system:{_rl_key}", _HOUR_WINDOW)
                return res
        
        # 🔱 [CLOUD-ONLY] FALLBACK PAID: DeepSeek V4 Flash (Absolute Safety Net for REALTIME)
        log.warning(f"[🔱 REALTIME_EMERGENCY] Falling back to DeepSeek Paid for {aid}...")
        _flash_retries = 0
        while _flash_retries < 5:
            res_flash, _, _ = execute_provider("DEEPSEEK", MOR_DEEPSEEK_FLASH, prompt, agent_id, "[🔱 REALTIME_FLASH_FALLBACK]", temp)
            if res_flash and not str(res_flash).startswith("ERROR:"):
                _semantic_cache_set(prompt, aid, res_flash)
                _save_last_state(prompt, aid, res_flash)
                return res_flash
            _flash_retries += 1
            time.sleep(10)
            
        # 🔱 [CLOUD-ONLY] NO local fallback — return ERROR
        return "ERROR: REALTIME_ALL_CLOUD_EXHAUSTED"


    # ════════════════════════════════════════════════════════════════════════
    # 🔱 VECTOR PROCESS & CORE ALGORITHMS (A03, A05, A10, A11, A12) 🔱
    # ════════════════════════════════════════════════════════════════════════
    if ( (unit_num.startswith("03") or unit_num.startswith("3")) ) or \
       ( (unit_num.startswith("04") or unit_num.startswith("4")) and active_mode not in ["ENGRAM", "MASTER", "GENESIS", "BOOSTING", "REALTIME"] ) or \
       unit_num.startswith("05") or unit_num.startswith("5") or \
       unit_num.startswith("07") or unit_num.startswith("7") or \
       unit_num.startswith("10") or unit_num.startswith("11") or unit_num.startswith("12"):
       
        # Add LITE and DIAGNOSTIC to force using CRAWL flow (Free Models)
        is_scraping = any(tag in aid for tag in ["P1", "P2", "P3", "RESEARCH", "CRAWL", "SUMMARY", "12A", "LITE", "DIAGNOSTIC"])
        
        try:
            matrix.client.delete(f"zcl:system:last_algo_mode:{aid}")
        except Exception:
            pass
        
        # ── 1. IF SCRAPING STEP (P1, P2...) ──
        if is_scraping:
            return _call_crawl_pipeline(prompt, agent_id, temp, aid)
            
        # ── 2. ALGORITHM RESULT (Core) → Qwen 3.5 Plus (UNLEASHED — No Hard Quota) ──
        _HOUR_WINDOW = 3600
        _rl_16d_key = f"quota:16d:{aid}:{_dt.now().strftime('%Y%m%d_%H')}"
        _16d_used = int(matrix.get("SYSTEM", _rl_16d_key) or 0)
        
        # Get Current Limit
        agent_idx = "".join(filter(str.isdigit, str(aid)))[:2]
        _quota_limits = {
            "03": 1,
            "07": 2, # Plus Quota for A07
            "10": 1,
            "11": 2,
            "12": 2,  # [HingeEBM FIX] 1->2: Brain A (5K) + Brain B (15K) both need Plus
        }
        current_limit = _quota_limits.get(agent_idx, 1) # Default other agents = 1
        
        # 🛡️ SOVEREIGN BYPASS & INTELLECTUAL PROPERTY SAGA PULSE
        # 1. Judge A05 and Library A04: INVIOLABLE! Never degrade intelligence!
        # 2. Other commanders: Ensure "first LLM call of the hour" (_16d_used == 0) is always fresh Plus to submit 100% intelligence report to A05.
        if aid.startswith(("04", "05", "A04", "A05")) or _16d_used < current_limit:
            log.info(f"[👑 SOVEREIGN_CORE|QUOTA_AVAILABLE] {aid} active with Quota ({_16d_used}/{current_limit})! Proceeding straight to Plus core, preserving 100% intelligence!")
            diff_decision = "PLUS"
            last_res = None
        else:
            # 🛡️ SOURCE FILTER LAYER 1: FUZZY DIFF CACHE (Always call to determine drift)
            diff_decision, last_res = _evaluate_smart_diff(prompt, aid)
        
        # Bypass direct CACHE return (MD5 match/ >96%), force to FLASH so LLM still processes new data/updates reports instead of staying silent!
        if diff_decision == "CACHE":
            log.warning(f"[🛡️ SMART_DIFF_REUSE_BYPASS] {aid} data identical (>96%) BUT forced to use FLASH to update report, no skip!")
            diff_decision = "FLASH"
            
        if diff_decision == "FLASH":
            log.info(f"[🛡️ SMART_DIFF_UPDATE] {aid} data changed slightly (80-96%). Calling FLASH inheriting old Plus to save costs!")
            flash_prompt = f"""[SOVEREIGN COMMAND FOR YOU (OPTIMIZED UPDATE MODE)]
Below is the OLD REPORT (Core analysis) performed by the General (Plus level) a few minutes ago:
--- OLD REPORT START ---
{last_res}
--- OLD REPORT END ---

And below is the LATEST FIELD DATA JUST UPDATED:
--- NEW DATA START ---
{prompt}
--- NEW DATA END ---

YOUR TASK: The General is busy. Please review the New Data on his behalf. Proceed to EDIT / UPDATE the Old Report based on the new variables in the New Data. You MUST strictly preserve the output structure, style, and data formatting exactly as in the Old Report. Only adjust metrics or add/remove sentences if the timeline/data has changed. Act as a perfect maintainer. No further explanation needed."""
            
            # EXCLUSIVE LABEL FOR LOG INSPECTION: [🔱 ALGO_SMART_FLASH]
            res_flash = _call_algo(flash_prompt, agent_id, "[🔱 ALGO_SMART_FLASH]", temp, "SMART_FLASH")
            
            if res_flash and not str(res_flash).startswith("ERROR:"):
                # Save the ORIGINAL prompt as baseline for next Diff comparison
                _save_last_state(prompt, aid, res_flash)
                return res_flash
            else:
                log.warning(f"[🔱 ALGO_FLASH_UPDATE_ERROR] Flash Update via Free API failed -> Redirecting back to core Quota flow!")
                prompt = flash_prompt # Override original prompt with flash_prompt to use ALGO_PLUS/ALGO_FREE below

        # 🛡️ SOURCE FILTER LAYER 2: CORE QUOTA (Smart and balanced Plus limits for each Agent, Emperor A05 unrestricted)
        agent_idx = "".join(filter(str.isdigit, str(aid)))[:2]
        _quota_limits = {
            "03": 1,
            "07": 2, # Plus Quota for A07
            "10": 1,
            "11": 2,
            "12": 2,  # [HingeEBM FIX] 1->2: Brain A (5K) + Brain B (15K)
        }
        current_limit = _quota_limits.get(agent_idx, 1) # Default other agents = 1
        
        # ── EXCLUSIVE A12 FLOW ──
        # [HingeEBM FIX] A12A is now only 5K tokens (reduced from 100K) -> allowed to use Plus
        # Only scraping branches (CRAWL, LITE, DIAGNOSTIC) are forced free
        force_free = False
        if aid.startswith("A12") and aid not in ("A12B", "A12A"):
            force_free = True
            
        # ── EXCLUSIVE A10 FLOW (ONLY A10_FINAL ALLOWED TO USE ALGO_PLUS) ──
        if aid.startswith("A10") and aid != "A10_FINAL":
            force_free = True

        res_algo = None
        if force_free or (_16d_used >= current_limit and not aid.startswith(("04", "05", "A04", "A05"))):
            existing_cache = _semantic_cache_get(prompt, aid)
            if existing_cache:
                log.info(f"[🛡️ ALGO_CACHE_REUSE] {aid} already called {_16d_used}x/h — using Semantic Cache")
                return existing_cache
            
            if force_free:
                log.warning(f"[🔱 QUOTA_DOWNGRADE] {aid} restricted privileges — Pushed straight to ALGO_FREE cycle (Big Models)!")
            else:
                log.warning(f"[🔱 QUOTA_DOWNGRADE] {aid} exceeded quota {_16d_used} times/hour — Pushed to ALGO_FREE cycle (Big Models)!")
                
            res_algo = _call_algo(prompt, agent_id, "[🔱 ALGO_FREE]", temp, "SMART")
        else:
            # If within quota or Emperor A05 -> Call NIM Tier S + Qwen ALGO (FREE before PAID)
            res_algo = _call_algo(prompt, agent_id, "[🔱 ALGO_PLUS]", temp, "ALGO")
            if res_algo and not str(res_algo).startswith("ERROR:"):
                matrix.incr("SYSTEM", _rl_16d_key)
                matrix.client.expire(f"zcl:system:{_rl_16d_key}", _HOUR_WINDOW)
                _semantic_cache_set(prompt, aid, res_algo)  # 🛡️ Save pure cache (MD5)
                _save_last_state(prompt, aid, res_algo)     # 🛡️ Save Smart Cache for Ratio diff checking next time
                _golden_cache_set(prompt, aid, res_algo)    # 🔧 Golden Cache — leverage successful call
                try:
                    matrix.client.setex(f"zcl:system:last_algo_mode:{aid}", 60, "algo_plus")
                except Exception:
                    pass
                return res_algo
            else:
                log.warning(f"[🔱 ALGO_CLOUD_ERROR] Qwen Plus failed ({res_algo}). Running backup ALGO_FREE cycle...")
                res_algo = _call_algo(prompt, agent_id, "[🔱 ALGO_FREE_BACKUP]", temp, "SMART")

        # ── 3. FINAL TIER (ALGO_FREE OR ALGO_PLUS FAILED -> MAX THINK -> EMERGENCY FALLBACK) ──
        if not res_algo or str(res_algo).startswith("ERROR:"):
            if "_LITE" in str(aid):
                log.warning(f"[🔱 ALGO_RECOVERY_BLOCKED] Agent {aid} running in Lite Mode (fast read only). Max Think fallback is disabled!")
                return "ERROR: LITE_MODE_NO_MAX_THINK"
                
            _rl_max_key = f"quota:max_think:{_dt.now().strftime('%Y%m%d_%H')}"
            _max_used = int(matrix.get("SYSTEM", _rl_max_key) or 0)
            
            if _max_used < 4:
                log.warning(f"[🔱 ALGO_RECOVERY] Issue detected! Initiating Max Think recovery for {aid} ({_max_used}/4)")
                res_max = _call_algo(prompt, agent_id, "[🔱 ALGO_MAX_THINK]", temp, "ALGO")
                if res_max and not str(res_max).startswith("ERROR:"):
                    matrix.incr("SYSTEM", _rl_max_key)
                    matrix.client.expire(f"zcl:system:{_rl_max_key}", 3600)
                    return res_max
            else:
                log.warning(f"[🔱 ALGO_RECOVERY] Max Think Quota exhausted ({_max_used}/4). Skipping recovery.")
                
            # 🔱 [CLOUD-ONLY] FINAL FALLBACK TIER: DeepSeek V4 Flash (Cheap Paid — Absolute Safety Net)
            log.warning(f"[🔱 ALGO_EMERGENCY] Max Think exhausted. Falling back to DeepSeek V4 Flash for {aid}...")
            _flash_retries = 0
            while _flash_retries < 5:
                res_flash, _, _ = execute_provider("DEEPSEEK", MOR_DEEPSEEK_FLASH, prompt, agent_id, "[🔱 ALGO_FLASH_FALLBACK]", temp)
                if res_flash and not str(res_flash).startswith("ERROR:"):
                    _semantic_cache_set(prompt, aid, res_flash)
                    _save_last_state(prompt, aid, res_flash)
                    return res_flash
                _flash_retries += 1
                time.sleep(10)
            
            log.error(f"[🔱 ALGO_TOTAL_FAILURE] {aid} — DeepSeek Flash also exhausted. System fully depleted!")
            
            # 🔧 Golden Cache Fallback: Leverage previous successful calls
            golden = _golden_cache_get(prompt, aid)
            if golden:
                log.info(f"[🏆 GOLDEN_CACHE_HIT] {aid} — Using old LLM result (exact match) instead of returning ERROR!")
                return golden
            golden_any = _golden_cache_get_any(aid)
            if golden_any:
                log.info(f"[🏆 GOLDEN_CACHE_FUZZY] {aid} — Using latest LLM result (any) instead of returning ERROR!")
                return golden_any
            
            return "ERROR: ALGO_ALL_CLOUD_EXHAUSTED"
            
        return res_algo

        
    # A06 (Notification & Form Structure): Run through Crawl Pipeline (Cloud Free Wheel)
    if unit_num.startswith("06") or unit_num.startswith("6"):
        return _call_crawl_pipeline(prompt, agent_id, temp, aid)
        
    # A09 (Immunity): 🔱 [CLOUD-ONLY] Run through Crawl Pipeline Cloud
    if unit_num.startswith("09") or unit_num.startswith("9"):
        return _call_crawl_pipeline(prompt, agent_id, temp, aid)
    
    # ════════════════════════════════════════════════════════════════════════
    # 🔱 PROCESS 5: FINAL FALLBACK (Qwen 3.6 Plus) 🔱
    # ════════════════════════════════════════════════════════════════════════
    # Tier 1: OpenRouter Qwen 3.6 Plus (cloud safety net)
    res, tokens, dur = execute_provider("OR", MOR_Q36P, prompt, agent_id, "[🔱 FALLBACK]", temp)
    if res and not str(res).startswith("ERROR:"):
        _golden_cache_set(prompt, agent_id, res)  # 🔧 Golden Cache
        return res
    
    # Tier 2: Local Ollama Disabled (Cloud-Only mode by directive)
    log.warning(f"[🔱 LOCAL_BYPASS] Local Ollama fallback is disabled (Cloud-Only).")
    
    # 🔧 Final Golden Cache Fallback
    golden = _golden_cache_get(prompt, agent_id)
    if golden:
        log.info(f"[🏆 GOLDEN_CACHE_HIT] {agent_id} — Using old LLM result instead of returning ERROR!")
        return golden
    
    return "ERROR: ALL_MODELS_FAILED_OR_NO_KEY"

# ── 4. IRON DISCIPLINE: TEMPERATURE CONTROL (DNA v85.0) ─────────────────────────

def _get_iron_discipline_temp(mode: str) -> float:
    """Establishes Iron Discipline breathing rate for each Process"""
    if "GENESIS" in mode:  return 0.05  # 100% precise scan
    if "ENGRAM" in mode or "MASTER" in mode: return 0.10  # Discipline judgement
    if "BOOSTING" in mode: return 0.20  # Subtle DPO refinement 🔱
    return 0.0  # Default: Deterministic (Swarm Rule)

# ── 5. ARRAY EXECUTOR & SLOT COORDINATOR ─────────────────────────────────────

# ── 5.5 REFUSAL DETECTION v3 — Detects LLM Refusals (EN + VI + JSON-wrapped) ──
_REFUSAL_SIGNATURES = [
    # English
    "I need to decline", "I can't provide", "I cannot provide",
    "I'm not able to", "I must decline", "I can't assist with",
    "I cannot assist with", "prompt injection attempt",
    "I'm unable to generate", "I cannot generate",
    "not something I can do responsibly", "I can't do this",
    "against my guidelines", "I cannot fulfill", "I can't fulfill",
    "I appreciate the detailed setup", "What I Can Help With",
    "What I Cannot Do", "conspiracy-theory framework",
    # Vietnamese (Qwen/GLM style)
    "Tôi không thể thực hiện yêu cầu này", "không thể cung cấp",
    "không thể đưa ra khuyến nghị giao dịch", "Rủi ro tài chính nghiêm trọng",
    "Lý thuyết âm mưu về thị trường", "thiếu cơ sở khoa học",
    "đi ngược lại nguyên tắc", "từ chối thực hiện",
]

def _is_refusal(response: str) -> bool:
    """Detects LLM refusal instead of expected response.
    v3: Expanded to catch Qwen Vietnamese + JSON-wrapped refusal."""
    if not response or len(response) < 50:
        return False
    # Check first 1500 chars — Qwen wraps refusal deeper in JSON
    head = response[:1500].lower()
    for sig in _REFUSAL_SIGNATURES:
        if sig.lower() in head:
            return True
    return False

def _execute_progress_array(wheel: list, prompt: str, agent_id: str, label: str, temp: float) -> str:
    """Executes prioritized array (For Master/Fallback)
    🔧 v2: Track provider fail + golden cache set on success."""
    for provider, model_id in wheel:
        res, tokens, duration = execute_provider(provider, model_id, prompt, agent_id, label, temp)
        if res == "ERROR: NO_KEY_AVAILABLE":
            continue
        if res and not str(res).startswith("ERROR:"):
            # 🛡️ Refusal Shield: Detect model refusing to answer
            if _is_refusal(res):
                log.warning(f"{label} Provider {provider} (Model: {model_id}) REFUSED to answer. Skipping...")
                continue
            # 🔧 Golden Cache: Save successful result
            _golden_cache_set(prompt, agent_id, res)
            _provider_fail_reset(provider)
            return res
        # 🔧 Track provider failure
        _provider_fail_track(provider, error_text=str(res) if res else "")
        log.warning(f"{label} Provider {provider} (Model: {model_id}) failed. Switching to next slot...")
    return "ERROR: ALL_PROGRESS_SLOTS_FAILED"

def _execute_target_slot(prov, model, k_idx, prompt, agent_id, label, temp, slot, allow_fallback=True):
    """Orchestrates specific Slot in Array (Genesis Cycle)"""
    tracker = get_tracker(model)
    key, idx = tracker.get_key_by_index(k_idx) # Get Key 1 / Key 2
    
    if not key: return f"ERROR: SLOT_{slot}_LOCKED"
    
    # Execute API
    res, tokens, duration = execute_provider(prov, model, prompt, agent_id, label, temp, key, idx)
    
    # 🔱 BACKUP DEFENSE: If Cerebras fails -> Call OpenRouter 35B immediately
    if allow_fallback and (not res or str(res).startswith("ERROR:")) and prov == "CEREBRAS":
         res, tokens, duration = execute_provider("OR", MO_35B, prompt, agent_id, "[🔱 FALLBACK]", temp)
         
    return res or f"ERROR: SLOT_{slot}_FAILED"

# ── 6. PROVIDER HANDLERS (PROFESSIONAL GRADE - UNITY) ────────────────────────

def execute_provider(prov, model, prompt, agent_id, label, temp=0.1, key=None, idx=-1):
    """Multi-endpoint execution handler - Returns (Text, Tokens, Duration)"""
    if prov == "ollama":
        return "ERROR: LOCAL_OLLAMA_DISABLED", 0, 0

    if prov == "CEREBRAS":
        return "ERROR: CEREBRAS_DISABLED", 0, 0

    if not get_tracker: return "ERROR: NO_KEY_AVAILABLE", 0, 0
    
    # 🔱 QWEN DashScope: Bypass QuotaTracker — use QWEN_API_KEY directly
    if prov == "QWEN":
        try:
            if matrix.client.get("zcl:system:quota:qwen:exhausted"):
                return "ERROR: NO_KEY_AVAILABLE", 0, 0
        except: pass
        if not key:
            key = os.environ.get("QWEN_API_KEY", "")
            idx = -1  # Do not record_usage to QuotaTracker
        if not key: return "ERROR: NO_KEY_AVAILABLE", 0, 0
    elif prov == "NIM":
        # 🔱 NVIDIA NIM: Bypass QuotaTracker — use NIM_API_KEY directly
        try:
            if matrix.client.get("zcl:system:quota:nim:exhausted"):
                return "ERROR: NO_KEY_AVAILABLE", 0, 0
        except: pass
        if not key:
            key = os.environ.get("NIM_API_KEY", "")
            idx = -1  # Do not record_usage to QuotaTracker
        if not key: return "ERROR: NO_KEY_AVAILABLE", 0, 0
    else:
        tracker = get_tracker(model)
        is_claw = str(agent_id).startswith("claw_")
        
        # Get key (If not passed from Wheel/Slot)
        if not key:
            if is_claw and tracker.num_keys > 0:
                key = tracker.keys[0] # Bypass Quota, take the root key
                idx = -1 # Do not record_usage
                print(f"🔱 [CLAW_BYPASS] Imperial Privilege! Claw picks key directly bypassing Quota Tracker...", flush=True)
            else:
                key, idx = tracker.get_key()
                
        if not key: return "ERROR: NO_KEY_AVAILABLE", 0, 0
    
    headers = {"Content-Type": "application/json"}
    start = time.time()
    resp = None
    tokens = 0

    try:
        if prov == "GEMINI":
            if genai:
                try:
                    client = genai.Client(api_key=key)
                    # SDK v1.0 standard interface (Sovereign Order)
                    # Mapping model name: gemini-2.5-pro, gemini-3.1-pro-preview
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=temp)
                    )
                    text = response.text
                    tokens = response.usage_metadata.total_token_count
                    duration = time.time() - start
                    tracker.record_usage(idx, True)
                    _log_sovereign_victory(agent_id, model, label, "G", tokens, duration)
                    return text, tokens, duration
                except Exception as e:
                    print(f"🔱 [GEMINI_SDK_ERROR] SDK call error: {e}", flush=True)
                    _log_sovereign_failure(agent_id, model, label, "GEMINI", "SDK_EXCEPTION", str(e), time.time() - start)
                    if idx >= 0: tracker.record_usage(idx, False)
                    return None, 0, 0
            else:
                # Fallback: REST
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": temp}}
                resp = requests.post(url, headers=headers, json=payload, timeout=150)
                if resp and resp.status_code != 200:
                    print(f"🔱 [GEMINI_DEBUG] REST error: {resp.status_code} | Details: {resp.text}", flush=True)
        else:
            if prov == "CEREBRAS": url = "https://api.cerebras.ai/v1/chat/completions"
            elif prov == "GROQ":   url = "https://api.groq.com/openai/v1/chat/completions"
            elif prov == "DEEPSEEK":
                url = "https://api.deepseek.com/chat/completions"
                # Standardize model name for official Deepseek endpoint
                if "/" in model:
                    model = model.split("/")[-1]
            elif prov == "QWEN":
                # Qwen DashScope Native (OpenAI-compatible, 49 models round-robin)
                url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
            elif prov == "NIM":
                # NVIDIA NIM (OpenAI-compatible, 58 models FREE)
                url = "https://integrate.api.nvidia.com/v1/chat/completions"
            else:
                # OpenRouter (Sovereign Order v15.0)
                url = "https://openrouter.ai/api/v1/chat/completions"
            headers["Authorization"] = f"Bearer {key}"
            max_tok = 8192 if (agent_id and (str(agent_id).startswith(("05", "A05", "04", "A04")) or "supreme" in str(model).lower() or "max" in str(model).lower())) else 4096
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temp,
                "max_tokens": max_tok,
            }
            if prov == "NIM" and ("glm" in model.lower() or "minimax" in model.lower() or "step-3.7" in model.lower() or "kimi" in model.lower() or "397b" in model.lower() or "ultra-550b" in model.lower()):
                payload["reasoning_effort"] = "high"
            
            import concurrent.futures
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            conn_timeout = 10
            read_timeout = 180 if prov == "NIM" else 90
            future = executor.submit(lambda: requests.post(url, headers=headers, json=payload, timeout=(conn_timeout, read_timeout)))
            try:
                resp = future.result(timeout=read_timeout + 10)
            except concurrent.futures.TimeoutError:
                print(f"🔱 [{prov}_HARD_TIMEOUT] Model request timed out over 260s!", flush=True)
                try:
                    for _ in range(3):
                        matrix.xadd("SYSTEM", "telegram:queue", {"payload": json.dumps({
                            "type": "ROUTER_TIMEOUT",
                            "report_text": f"🚨🚨 [HARD TIMEOUT 160s] Model {model} (Provider {prov}) crashed due to timeout!",
                            "cycle": "ROUTER",
                            "ts": int(time.time()),
                        })}, maxlen=1000)
                        time.sleep(0.5)
                except Exception: pass
                resp = None
                raise Exception("HARD TIMEOUT 555s")
            except Exception as net_err:
                print(f"🔱 [{prov}_EXCEPTION] Error: {net_err}", flush=True)
                resp = None
            finally:
                executor.shutdown(wait=False)

        duration = time.time() - start

        if resp and resp.status_code == 200:
            res_json = resp.json()
            if prov == "GEMINI":
                text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                tokens = res_json.get("usageMetadata", {}).get("totalTokenCount", 0)
            else:
                choice_msg = res_json["choices"][0]["message"]
                content = choice_msg.get("content") or ""
                reasoning = choice_msg.get("reasoning_content") or ""
                if reasoning:
                    text = f"<thinking>\n{reasoning}\n</thinking>\n{content}"
                else:
                    text = content
                tokens = res_json.get("usage", {}).get("total_tokens", 0)
            
            if 'tracker' in dir() and tracker is not None:
                tracker.record_usage(idx, True) # Success
            
            # --- SNAPSHOT REDIS CNS FOR A03, A04, A05, A10, A11, A12 ---
            try:
                # Format agent name: 031:1 -> 03, or A11_P1 -> 11
                aid_clean = str(agent_id).split(':')[0].split('_')[0].upper()
                if aid_clean.startswith('A'):
                    aid_clean = aid_clean[1:]
                    
                if len(aid_clean) >= 3 and aid_clean.startswith(('0', '1')): 
                    aid_clean = aid_clean[:2]
                
                if aid_clean in ["03", "04", "05", "10", "11", "12"]:
                    from tools.imperial_state import matrix
                    matrix.set("SYSTEM", f"snapshot_llm:a{aid_clean.lower()}", text, ex=10800)
            except Exception as e:
                print(f"🔱 [SNAPSHOT_REDIS_ERROR] Fallback skip: {e}")
            # ---------------------------------------------------------------
            
            _log_sovereign_victory(agent_id, model, label, f"{prov[0]}", tokens, duration)
            return text, tokens, duration
        else:
            if resp is not None:
                err_msg = f"HTTP {resp.status_code}: {resp.text}"
                print(f"🔱 [{prov}_ERROR] Code: {resp.status_code} | Text: {resp.text}", flush=True)
                _log_sovereign_failure(agent_id, model, label, prov, resp.status_code, resp.text, duration)
                if idx >= 0 and 'tracker' in dir() and tracker is not None: tracker.record_usage(idx, False) # Failure
                
                # Fast-fail for QWEN DashScope exhaustion (monthly quota -> lock 24h)
                if prov == "QWEN" and (resp.status_code == 403 or "AllocationQuota.FreeTierOnly" in resp.text):
                    try:
                        matrix.client.setex("zcl:system:quota:qwen:exhausted", 86400, "1")
                        print("🔱 [QUOTA_SHIELD] Qwen DashScope free tier exhausted! Locked for 24h (monthly quota).", flush=True)
                    except: pass
                
                return f"ERROR: {err_msg}", 0, 0
            if idx >= 0 and 'tracker' in dir() and tracker is not None: tracker.record_usage(idx, False) # Failure
            
    except Exception as e:
        print(f"🔱 [{prov}_EXCEPTION] Error: {e}", flush=True)
        _log_sovereign_failure(agent_id, model, label, prov, "EXCEPTION", str(e), time.time() - start)
        if idx >= 0 and 'tracker' in dir() and tracker is not None: tracker.record_usage(idx, False)
        
        # Fast-fail for NIM timeouts
        if prov == "NIM":
            try:
                matrix.client.setex("zcl:system:quota:nim:exhausted", 300, "1")
                print("🔱 [QUOTA_SHIELD] NIM exception/timeout detected! Locked for 5 minutes.", flush=True)
            except: pass
            
    return "ERROR: NETWORK_OR_TIMEOUT", 0, 0

# ── 7. LOGGING INTELLIGENCE (SOVEREIGN STANDARD) ─────────────────────────────

def _log_sovereign_victory(agent_id, model, label, turn, tokens, duration):
    """Orchestrator log: [Turn] [Agent] [Mode] [Model] [Token] [Time]"""
    try:
        # 🔱 MAPPED UNIT:CALLSITE (DNA v17.3)
        aid_str = str(agent_id).lower()
        if "claw_coordinator" in aid_str: unit_num = "C01"
        elif "claw_coder" in aid_str:     unit_num = "C02"
        elif "claw_verifier" in aid_str:  unit_num = "C03"
        elif "claw_logger" in aid_str:    unit_num = "C04"
        elif "coordinator" in aid_str: unit_num = "01"
        elif "coder" in aid_str:     unit_num = "02"
        elif "verifier" in aid_str:  unit_num = "03"
        else:
            unit_num = "".join(filter(str.isdigit, aid_str)) or "00"
            
        if len(unit_num) == 1: unit_num = "0" + unit_num
        
        # Map CallSite (1-2-3) depending on calling location
        call_site = "0"
        if "GENESIS" in label:   call_site = "1"
        elif "MASTER" in label or "ENGRAM" in label: call_site = "2"
        elif "BOOST" in label:    call_site = "3"
        elif "THREAD" in label or "LOCAL" in label:   call_site = "1"
        else:                     call_site = "1" 
        
        mapped_id = f"{unit_num}:{call_site}"
        
        log_dir = BASE_DIR / "logs" / "llm"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = _dt.now().strftime('%H:%M:%S')
        today = _dt.now().strftime('%Y-%m-%d')
        # Structure: [Turn: {turn}] [Agent: {mapped_id}] [Mode: {label}] [Model: {model}] [Token: {tokens}] [Time: {duration:.2f}s]
        entry = f"[{ts}] [Turn: {turn}] [Agent: {mapped_id}] [Mode: {label}] [Model: {model}] [Token: {tokens}] [Time: {duration:.2f}s]\n"
        with open(log_dir / f"{today}.log", "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e: 
        print(f"🔱 [LOG_TURN_ERROR] {e}", flush=True)

def _log_sovereign_failure(agent_id, model, label, prov, code, msg, duration):
    """Log failures to monitor performance issues (DNA v18.2)."""
    try:
        agent_raw = str(agent_id).lower()
        if "coordinator" in agent_raw or "os1" in agent_raw: prefix = "C01"
        elif "coder" in agent_raw or "os2" in agent_raw:     prefix = "C02"
        elif "verifier" in agent_raw or "os3" in agent_raw:  prefix = "C03"
        elif "logger" in agent_raw or "os4" in agent_raw:    prefix = "C04"
        else:
            unit_num = "".join(filter(str.isdigit, agent_raw)) or "00"
            if len(unit_num) == 1: unit_num = "0" + unit_num
            prefix = unit_num

        call_site = "0"
        if "GENESIS" in label:   call_site = "1"
        elif "MASTER" in label or "ENGRAM" in label: call_site = "2"
        elif "BOOST" in label:    call_site = "3"
        elif "THREAD" in label or "LOCAL" in label:   call_site = "1"
        else:                     call_site = "1"
        mapped_id = f"{prefix}:{call_site}"
        
        log_dir = BASE_DIR / "logs" / "llm"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = _dt.now().strftime('%H:%M:%S')
        today = _dt.now().strftime('%Y-%m-%d')
        safe_msg = str(msg).replace("\n", " ")[:150]
        entry = f"[{ts}] [Turn: ❌] [Agent: {mapped_id}] [Mode: {label}] [Model: {model}] [Prov: {prov}] [Code: {code}] [Error: {safe_msg}] [Time: {duration:.2f}s]\n"
        with open(log_dir / f"{today}.log", "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e: 
        print(f"🔱 [LOG_FAIL_ERROR] {e}", flush=True)
