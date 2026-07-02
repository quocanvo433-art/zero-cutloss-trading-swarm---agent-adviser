"""
🧬 DNA: v16.7 (Sovereign Purity) [DNA Header]
🏢 UNIT: ENGRAM_HELPER
🛠️ ROLE: KNOWLEDGE_ORCHESTRATOR
📖 DESC: Four operational functions for knowledge orchestration (Genesis/Boost Distill & Ingest).
          Merged elite algorithms from engram_a04, engram_genesis, chroma_ingest_a04, chroma_ingest_genesis into a single unit.
          4-stage Pipeline: Grid Coverage → Hallucination Taxonomy →
          Lesson Dedup → Quality Backfill (Boost) or
          Auto-Label → Result-Grid → Time-Diversity → Backfill (Genesis).
🔗 CALLS: tools/imperial_state.py, tools/llm_router.py
📟 I/O: dpo_lab/engrams/a04/, ChromaDB: zcl_a04_*_patterns
🛡️ INTEGRITY: Data-Distillation, Geometric-Grid-Coverage, Dual-Memory-Sync.
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from collections import defaultdict
from typing import List, Dict
from datetime import datetime, timezone
from dotenv import load_dotenv

# ── Load Context ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env")

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
CHROMA_HOST = os.getenv("CHROMA_HOST", "chroma")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
BATCH_SIZE = 10

log = logging.getLogger("ENGRAM_HELPER")

# ══════════════════════════════════════════════════════════════════════════════
# WEIGHT CONFIGURATION (Geometric Logic)
# ══════════════════════════════════════════════════════════════════════════════

WYCKOFF_PHASES = {
    "A":  {"label": "Stopping Previous Trend",  "weight": 0.8},
    "B":  {"label": "Building Cause — TRADING FORBIDDEN", "weight": 0.7},
    "C":  {"label": "Spring/Upthrust — PRIME OPPORTUNITY", "weight": 1.5},
    "D":  {"label": "Trend Confirmation",        "weight": 1.2},
    "E":  {"label": "Trend Extension",           "weight": 1.0},
    "DIST_A": {"label": "Stop Uptrend",          "weight": 0.8},
    "DIST_B": {"label": "Distribution Cause",    "weight": 0.7},
    "DIST_C": {"label": "UTAD — BULL TRAP",       "weight": 1.5},
    "DIST_D": {"label": "Distribution Confirm",  "weight": 1.2},
    "DIST_E": {"label": "Markdown — PRICE DUMP",    "weight": 1.0},
    "UNKNOWN": {"label": "Undefined",        "weight": 0.5},
}

ELLIOTT_WAVES = {
    "W1": {"label": "Impulse W1 — beginning",     "weight": 1.0},
    "W2": {"label": "Corrective W2 — TRAP",       "weight": 1.3},
    "W3": {"label": "Impulse W3 — STRONGEST",    "weight": 1.5},
    "W4": {"label": "Corrective W4 — complex",  "weight": 1.2},
    "W5": {"label": "Impulse W5 — EXHAUSTION",    "weight": 1.3},
    "A":  {"label": "Corrective A",              "weight": 1.0},
    "B":  {"label": "Corrective B — BULL TRAP",   "weight": 1.2},
    "C":  {"label": "Corrective C — CRITICAL DROP",   "weight": 1.0},
    "UNKNOWN": {"label": "Undefined",        "weight": 0.5},
}

# Classification of hallucination traps (Boosting): teaching model WHERE and WHY it went wrong
HALL_CATEGORIES = {
    "indicator_misuse":    ["RSI", "MACD", "BB Width", "Bollinger", "overbought"],
    "volume_neglect":      ["volume", "volume size", "diminishing volume", "volume confirmation"],
    "phase_confusion":     ["Phase C Distribution", "UTAD", "Upthrust Against"],
    "wave_completion":     ["5-wave completion", "wave 5", "completed"],
    "sentiment_override":  ["emotional sentiment", "risen significantly", "already priced in"],
}

# Result categorization (Genesis): price fluctuations after N candles
RESULT_BUCKETS = {
    "STRONG_BULL": 2.0,   # Increase ≥5%
    "MILD_BULL":   1.5,   # Increase 2-5%
    "SIDEWAYS":    1.0,   # < 2%
    "MILD_BEAR":   1.5,   # Decrease 2-5%
    "STRONG_BEAR": 2.0,   # Decrease ≥5%
}


# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES (Utility Functions)
# ══════════════════════════════════════════════════════════════════════════════

def _load_jsonl(filepath: Path) -> list:
    """Read JSONL file, supports both line-by-line format and Queen's pretty JSON stream."""
    records = []
    if not filepath.exists():
        return records
        
    try:
        # First try line-by-line
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        
        # If no records found, try to parse the entire content as stream or list
        if not records:
            with open(filepath, encoding="utf-8") as f:
                content = f.read().strip()
            
            if not content:
                return records
                
            import json
            decoder = json.JSONDecoder()
            idx = 0
            while idx < len(content):
                while idx < len(content) and content[idx].isspace():
                    idx += 1
                if idx >= len(content):
                    break
                try:
                    obj, end_idx = decoder.raw_decode(content[idx:])
                    records.append(obj)
                    idx += end_idx
                except json.JSONDecodeError:
                    idx += 1
                            
    except Exception as e:
        log.warning(f"Error reading data {filepath.name}: {e}")
        
    return records


def _trigram_jaccard(text_a: str, text_b: str) -> float:
    """Trigram Jaccard similarity — lightweight, fast, sufficient for lesson deduplication."""
    def trigrams(text: str) -> set:
        words = text.lower().split()
        if len(words) < 3:
            return set(words)
        return set(tuple(words[i:i + 3]) for i in range(len(words) - 2))
    tg_a, tg_b = trigrams(text_a), trigrams(text_b)
    if not tg_a or not tg_b:
        return 0.0
    return len(tg_a & tg_b) / len(tg_a | tg_b)








# ══════════════════════════════════════════════════════════════════════════════
# CLASS CHÍNH — A04 ENGRAM ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

class A04EngramHelper:
    """
    Four operational functions for Agent 04 knowledge orchestration (v17.6 HD).

    Boosting (Theoretical learning — prevent errors, accelerate when correct):
      distill_boost_pairs()    → 4 Phases: Grid → Hallucination → Dedup → Backfill
      ingest_boost_to_chroma() → Semantic 3-Layer: Pattern + Signals + Lesson

    Genesis (Coin habit learning — compression duration, bounce magnitude):
      distill_genesis_pairs()    → Auto-Label → Result-Grid → Time-Diversity
      ingest_genesis_to_chroma() → Semantic 3-Layer: Pattern + Ground Truth + Context
    """

    COLLECTIONS = {
        "boost":   "zcl_a04_blinding_patterns",
        "genesis": "zcl_a04_genesis_patterns",
    }

    def __init__(self):
        self.engram_base = BASE_DIR / "dpo_lab" / "engrams" / "A04"
        self.engram_base.mkdir(parents=True, exist_ok=True)
        self._chroma_client = None

    @property
    def chroma(self):
        if self._chroma_client is None:
            try:
                import chromadb
                host = CHROMA_HOST if "chroma" in CHROMA_HOST else "chroma"
                self._chroma_client = chromadb.HttpClient(host=host, port=CHROMA_PORT)
            except Exception as e:
                log.debug(f"ChromaDB unavailable: {e}")
                return None
        return self._chroma_client

    def get_collection(self, mode: str):
        """Return corresponding ChromaDB collection (genesis or boosting)."""
        if self.chroma is None:
            return None
        col_name = self.COLLECTIONS.get(mode, "zcl_a04_blinding_patterns")
        return self.chroma.get_or_create_collection(
            name=col_name,
            metadata={"description": f"A04 {mode} patterns", "hnsw:space": "cosine"},
        )

    # ══════════════════════════════════════════════════════════════════════════
    # FUNCTION 1: DISTIL BOOST (1000 → 150) — Essence from engram_a04.py
    # ══════════════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════════════
    # FUNCTION 2: DISTIL GENESIS (1000 → 150) — Essence from engram_genesis.py
    # ══════════════════════════════════════════════════════════════════════════






    
    def _clean_jsonl_response(self, text: str) -> str:
        """Laser Clean: Supports both JSONL (one object per line) AND Static JSON (pretty-print)"""
        if not text: return ""
        text = text.strip()
        
        # 1. Try parsing the entire text block (for LLM returning a large pretty-print Object)
        try:
            # If parsed successfully, it is pure JSON (1 object or 1 list)
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return '\n'.join([json.dumps(obj, ensure_ascii=False) for obj in parsed])
            elif isinstance(parsed, dict):
                return json.dumps(parsed, ensure_ascii=False)
        except Exception:
            pass

        # 2. Handle Markdown Code block extraction if present
        code_block = re.search(r"```(?:json|jsonl)?\n?(.*?)\n?```", text, re.DOTALL)
        if code_block:
            clean_text = code_block.group(1).strip()
            try:
                parsed = json.loads(clean_text)
                if isinstance(parsed, list):
                    return '\n'.join([json.dumps(obj, ensure_ascii=False) for obj in parsed])
                elif isinstance(parsed, dict):
                    return json.dumps(parsed, ensure_ascii=False)
            except Exception:
                pass
        
        # 3. Fallback: If JSONL is contaminated with outer text, attempt structural mapping
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                lines.append(line)
        
        return '\n'.join(lines)
    
    def distill_genesis_pairs(self, input_file: Path, target: int = 40) -> Path:
        """
        DNA v23.2: REAL TIME HEAT - 10 pairs -> elite engram.
        ⚠️ MASTER DIRECTIVE: Distillation requires Deep Intelligence
        thus MANDATORY to use Gemini PRO (via brain_mode='A04_ENGRAM').
        Flash only used for superficial Genesis Scan.
        """
        from imperial_state import matrix
        from llm_router import router_api_call
        from genesis_v17_prompt import GENESIS_SPEC_V17
        from imperial_brain import brain
        
        output_dir = self.engram_base / "genesis"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        ckpt_key = f'a04:genesis:checkpoint:{input_file.stem}'
        
        # DNA v24.0: Load disk checkpoint to survive Redis flush
        checkpoint_file = output_dir / "distill_checkpoints.json"
        disk_checkpoints = {}
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    disk_checkpoints = json.load(f)
            except Exception as e:
                log.error(f"Error reading {checkpoint_file.name}: {e}")
                
        redis_val = int(matrix.get('SYSTEM', ckpt_key) or 0)
        disk_val = disk_checkpoints.get(ckpt_key, 0)
        start_line = max(redis_val, disk_val)
        
        # Auto-heal Redis if disk is ahead
        if start_line > redis_val:
            matrix.set('SYSTEM', ckpt_key, start_line)
        
        all_pairs = _load_jsonl(input_file)
        if len(all_pairs) < start_line + 10:
             log.info(f'[A04] Not enough new pairs (Currently have {len(all_pairs)-start_line}). Waiting...')
             return None
             
        pairs_subset = all_pairs[start_line : start_line + 10]
        
        # 1. Prepare 100-candle context
        context_data = []
        for p in pairs_subset:
             meta = p.get('_meta', {})
             context_data.append(f"Time: {meta.get('human_time')} | Wyckoff: {meta.get('wyckoff_phase')} | Result: {p.get('output','')[:100]}")
        
        # 2. Check cycle to activate Master Lattice (4 Gemini 2.5 Pro : 1 Gemini 3.1 Pro Master)
        cycle = int(matrix.get('SYSTEM', 'a04:engram:cycle') or 0)
        is_master_turn = (cycle == 4) 
        
        master_context = ""
        if is_master_turn:
            log.info(f"🧬 [MASTER_LATTICE] Gemini 3.1 Pro turn. Loading context of last 10 files...")
            last_files = self._get_last_10_engrams()
            context_lessons = []
            for lf in last_files:
                context_lessons.extend(_load_jsonl(lf))
            
            # Get summary of the last 100-160 lessons as legacy context
            summary = []
            for l in context_lessons[:150]:
                summary.append(f"TS: {l.get('_meta', {}).get('ts')} | Phase: {l.get('context', {}).get('wyckoff_phase', 'N/A')} | Insight: {l.get('output', '')[:100]}")
            master_context = "--- MASTER LATTICE LEGACY MECHANISM (LAST 10 FILES) ---\n" + "\n".join(summary)

        # 3. Invoke Gemini 2.5/3.1 (Router automatically rotates based on brain_mode)
        prompt = f"{GENESIS_SPEC_V17}\n\n"
        if master_context:
            prompt += f"{master_context}\n\n"
            prompt += "🔥 SUPER TASK (MASTER LATTICE — TECHNICAL AUTOPSY):\n"
            prompt += "You are not just a summarizer, you are a TECHNICAL AUDITING MASTER. With 150-160 genetic lessons from the past and 10 new pairs, conduct a DEEP LOGICAL INQUEST:\n"
            prompt += "1. Identify the 'Structural Nexus': The point where Elliott/Wyckoff rules are broken or MM performs the most sophisticated 'Managed Move'.\n"
            prompt += "2. Consolidate 'First Principles': Do not describe price; describe the LAW governing large capital flows behind multi-frame phase shifts.\n"
            prompt += "3. Extract 'Master Engrams' containing 'Root Knowledge' — quantity depends on quality, NOT MANDATORILY FIXED.\n"
            prompt += "⚠️ SUPREME REQUIREMENT: ONLY RETURN RAW JSONL. NO MARKDOWN, NO EXPLANATIONS, NO INTRODUCTORY TEXT. ONE JSON OBJECT PER LINE.\n"
        else:
            prompt += "🔥 ELITE DISTILLATION TASK:\n"
            prompt += "You receive 10 raw candle data pairs. Your task is to SYNTHESIZE and DISTILL them into elite lessons (Engrams) — quantity depends on quality.\n"
            prompt += "1. No copy-paste: Identify the general capital pattern (MM Intent) within these 10 candles.\n"
            prompt += "2. Hunt the Hunter: Pay special attention to liquidity sweeps and Wick Sweep areas to point out 'Ambush' locations for Master.\n"
            prompt += "3. Extract lessons (Engrams) in standard JSONL format — quantity depends on data quality.\n"
            prompt += "⚠️ SUPREME REQUIREMENT: ONLY RETURN RAW JSONL. ONE JSON OBJECT PER LINE. NO MARKDOWN. NO VERBOSE TEXT.\n"
            prompt += "Example doc_id: EN_BTC_1509984000\n"
        
        prompt += "INPUT DATA:\n"
            
        prompt += '\n'.join(context_data[:10])
        
        log.info(f'[A04] Calling LLM (Cycle:{cycle}) to distill 10 pairs for {input_file.name}...')
        response_raw = router_api_call(prompt, agent_id='A04', brain_mode='A04_MASTER' if is_master_turn else 'A04_ENGRAM', est_tokens=4500)
        
        # Post-process response to clean it
        response_clean = self._clean_jsonl_response(response_raw)
        
        if response_clean and 'ERROR' not in response_clean:
            # 4. Write real Engram file
            ts_now = int(time.time())
            if is_master_turn:
                output_file = output_dir / f'master_lattice_{input_file.stem}_{ts_now}.jsonl'
                log.info(f"💎 [MASTER_LATTICE_SECURED] Saved {len(response_clean.splitlines())} master insights to {output_file.name}")
            else:
                output_file = output_dir / f'engrams_{input_file.stem}_{ts_now}.jsonl'
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(response_clean)
            
            # 5. Advance Checkpoint & Cycle
            new_line = start_line + 10
            matrix.set('SYSTEM', ckpt_key, new_line)
            
            # Save checkpoints to disk
            disk_checkpoints[ckpt_key] = new_line
            try:
                with open(checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump(disk_checkpoints, f, indent=2)
            except Exception as e:
                log.error(f"Error writing {checkpoint_file.name}: {e}")
                
            next_cycle = (cycle + 1) % 5
            matrix.set('SYSTEM', 'a04:engram:cycle', next_cycle)
            
            log.info(f'[A04] Distillation complete. Checkpoint -> {new_line} | Cycle -> {next_cycle}')
            return output_file
        else:
            log.error(f'[A04] LLM Call failed: {response_raw}')
            return None

    def _get_last_10_engrams(self) -> List[Path]:
        """Get the 10 most recent engrams/master files for Master Synthesis context."""
        base = self.engram_base / 'genesis'
        files = sorted(base.glob('*.jsonl'), key=lambda x: x.stat().st_mtime, reverse=True)
        return files[:10]

    def synthesize_master_lattice(self):
        """Master turn (Turn 5): Gemini 3.1 Pro distills the 10 most recent files per v17.0."""
        from llm_router import router_api_call
        from genesis_v17_prompt import GENESIS_SPEC_V17
        
        last_files = self._get_last_10_engrams()
        if not last_files:
            return
        
        all_lessons = []
        for f in last_files:
            all_lessons.extend(_load_jsonl(f))
            
        summary_lines = []
        for l in all_lessons[:160]:
             did = l.get('doc_id', 'N/A')
             phase = l.get('context', {}).get('wyckoff_phase', 'N/A')
             insight = l.get('meta_insight', '')[:150]
             summary_lines.append(f'ID: {did} | Wyckoff: {phase} | Insight: {insight}')
             
        context_str = '\n'.join(summary_lines)
        
        full_prompt = f"{GENESIS_SPEC_V17}\n\n"
        full_prompt += f"--- MASTER LATTICE LEGACY MECHANISM (LAST 10 FILES) ---\n{context_str}\n\n"
        full_prompt += "🔥 MASTER LATTICE TASK (GLOBAL SYNTHESIS):\n"
        full_prompt += "Perform a 'GENETIC AUDIT' across all 160 lessons. Your task is to extract 'MASTER PRINCIPLES' regarding multi-frame convergence/phase shift and MM manipulative behavior — quantity depends on quality, NOT MANDATORILY FIXED.\n"
        full_prompt += "Do not simply repeat Wyckoff or Elliott; reveal the CORE NATURE of price dynamics distilled from analyzing thousands of hours of data.\n"
        full_prompt += "🎯 'HAWK HUNTS EAGLE' TACTIC (Hunt the Hunter): Clearly distinguish where the Elite distributes bait, thereby mapping out a stealth entry point (safe Limit Order) to ambush, and an ABSOLUTE stop-loss point outside the Wick Sweep Zone.\n"
        full_prompt += "⚠️ DEATH REQUIREMENT: ONLY RETURN RAW JSONL. NO MARKDOWN, NO EXPLANATIONS. EACH LINE MUST BE A SINGLE JSON OBJECT.\n"
        
        log.info(f"🧬 [MASTER_LATTICE] Synthesizing knowledge from {len(last_files)} files...")
        # DNA v17.1: Use brain_mode='A04_MASTER' for Router to summon Gemini 3.1 Pro (Max Elite)
        resp = router_api_call(full_prompt, agent_id='A04', brain_mode='A04_MASTER', est_tokens=8000)
        
        clean_resp = self._clean_jsonl_response(resp)
        if clean_resp:
            output_file = self.engram_base / "genesis" / "master_lattice_global.jsonl"
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(clean_resp + "\n")
            log.info(f"💎 [MASTER_LATTICE_GLOBAL] Stored new master knowledge in the system.")

    # ══════════════════════════════════════════════════════════════════════════
    # HÀM 3: VECTOR INGESTION & 2-WAY TRACKING (v17.6)
    # ══════════════════════════════════════════════════════════════════════════

    def store_a04_lesson(self, crypto_symbol: str, content: dict, mode: str, metadata: dict = None):
        """Real-Time Ingest API for Boosting/Genesis."""
        if mode not in self.COLLECTIONS:
            log.warning(f"[A04_ENGRAM] store_a04_lesson: mode '{mode}' is invalid.")
            return
            
        # ── FIXED PHYSICAL DATA LOSS ISSUE ──
        # Prioritize writing JSONL file first, preventing block if ChromaDB is off
        try:
            import glob, json, datetime
            save_dir = BASE_DIR / "dpo_lab" / "A04" / ("genesis" if mode == 'genesis' else 'boosting')
            save_dir.mkdir(parents=True, exist_ok=True)
            safe_coin = crypto_symbol.replace('/', '_')
            
            if mode == 'genesis':
                latest_file = str(save_dir / f"pairs_{safe_coin}_active.jsonl")
            else:
                pattern = str(save_dir / f"pairs_{safe_coin}_*.jsonl")
                files = glob.glob(pattern)
                latest_file = None
                max_num = 0
                for f in files:
                    try:
                        num_part = f.split(f"pairs_{safe_coin}_")[1].replace(".jsonl", "")
                        if num_part.isdigit():
                            if int(num_part) > max_num:
                                max_num = int(num_part)
                                latest_file = f
                    except Exception: pass
                
                if not latest_file:
                    max_num = 1
                    latest_file = str(save_dir / f"pairs_{safe_coin}_1.jsonl")
                
                # CHUNKING LIMIT: Check if current file reached 1000 lines to transition to a new file
                try:
                    if Path(latest_file).exists():
                        size_kb = Path(latest_file).stat().st_size / 1024
                        # Assuming 1 record ~ 1.5KB, 1000 records ~ 1500KB
                        if size_kb >= 1500:
                            max_num += 1
                            latest_file = str(save_dir / f"pairs_{safe_coin}_{max_num}.jsonl")
                            log.info(f"🔄 [A04_ENGRAM] Old file reached ~1500KB. Splitting and moving to chunk: {Path(latest_file).name}")
                except Exception as e:
                    log.warning(f"Error checking size of file {latest_file}: {e}")
                
            # Ensure JSON satisfies standards for other systems to read (distill schema protection)
            if "_meta" not in content:
                content["_meta"] = {
                    "mode": mode,
                    "coin_symbol": crypto_symbol,
                    "ts": int(time.time()),
                    "human_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                if metadata:
                    content["_meta"].update(metadata)
            if "source" not in content:
                content["source"] = f"a04_{mode}"
                
            with open(latest_file, "a", encoding="utf-8") as file_out:
                file_out.write(json.dumps(content, ensure_ascii=False) + "\n")
            log.info(f"📦 [A04_ENGRAM] Appended pairs to physical data: {Path(latest_file).name}")
        except Exception as e:
            log.error(f"❌ [A04_ENGRAM] Error saving DPO File: {e}")


    # ══════════════════════════════════════════════════════════════════════════
    # HÀM 4: HIGH-DENSITY RECALL (140K TOKENS)
    # ══════════════════════════════════════════════════════════════════════════

    def recall_knowledge_deep(self, query: str, ticker: str, target_genesis_tokens: int = 20000, target_boost_tokens: int = 20000) -> str:
        """
        High-density knowledge recall. Retrieve max 20K tokens per branch (40K total).
        Average engram text ~250 tokens -> requires ~80 engrams for 20k tokens.
        """
        # Normalize Ticker: Convert 'BTC_USDT' to 'BTC/USDT' to match Chroma Metadata
        if ticker and ticker != "UNKNOWN":
            ticker = ticker.replace("_", "/")

        # Technical dictionary attached for LLM to understand abbreviations:
        glossary = (
            "--- EMPIRE STANDARD WYCKOFF & ELLIOTT DICTIONARY ---\\n"
            "This knowledge data represents lessons accumulated from super-intelligent AI, use it to inspect T0.\\n"
            "WYCKOFF: PHASE_A (Stop trend), PHASE_B (Horizontal accumulation/Trading forbidden), PHASE_C (Spring/Upthrust/Opportunity), PHASE_D (Trend confirmation), PHASE_E (Expansion).\\n"
            "ELLIOTT: W1, W3, W5 (Impulse waves), W2, W4 (Corrective waves), Sideways (Flat range).\\n"
            "----------------------------------------------\\n"
        )
        
        result_text = glossary + "\n"
        
        # 1. Original Historical Knowledge Block
        result_text += (
            "\n=== ORIGINAL HISTORICAL KNOWLEDGE (GENESIS ETHOS) ===\n"
            f"Below is actual historical data that HAS OCCURRED for {ticker}.\n"
            "You must ingest historical loops following this MANDATORY LOGICAL CHAIN:\n"
            "[TECHNICAL SIGNALS] -> [FOOTPRINTS OF ELITE / COMPOSITE MAN] -> [SUBSEQUENT PRICE CONSEQUENCE]\n\n"
            "<genesis_data>\n"
        )
        
        genesis_col = self.get_collection("genesis")
        if genesis_col is not None and genesis_col.count() > 0:
            where_clause = {"coin_symbol": ticker} if (ticker and ticker != "UNKNOWN") else None
            gen_res = genesis_col.query(
                query_texts=[query],
                n_results=min(80, genesis_col.count()), 
                where=where_clause
            )
            if gen_res and gen_res.get("documents") and gen_res["documents"][0]:
                for doc in gen_res["documents"][0]:
                    result_text += f"- [🔱 GENESIS] {doc}\n"
            else:
                result_text += "(SYSTEM: NO RELEVANT GENESIS KNOWLEDGE FOR THIS CONTEXT)\n"
        else:
            result_text += "(SYSTEM: NO GENESIS DATA IN CHROMADB OR CHROMA IS OFFLINE)\n"
        
        result_text += "</genesis_data>\n"
            
        # 2. Boosting Nuances Block
        result_text += (
            "\n=== HALLUCINATION IMMUNITY LESSONS (BOOSTING ELITE) ===\n"
            "Below are diagnostic studies dissection of your past errors or random guesses.\n"
            "You must contemplate this knowledge following a RIGOROUS THINKING CHAIN:\n"
            "[TECHNICAL SIGNALS] -> [SCHOLASTIC LOGICAL ELIMINATION OF HALLUCINATIONS] -> [PROBING ELITE'S TRUE INTENT] -> [CONSEQUENCE AND LESSON]\n\n"
            "<boosting_data>\n"
        )
        
        boost_col = self.get_collection("boost")
        if boost_col is not None and boost_col.count() > 0:
            where_clause = {"coin_symbol": ticker} if (ticker and ticker != "UNKNOWN") else None
            boo_res = boost_col.query(
                query_texts=[query],
                n_results=min(80, boost_col.count()),
                where=where_clause
            )
            if boo_res and boo_res.get("documents") and boo_res["documents"][0]:
                for doc in boo_res["documents"][0]:
                    result_text += f"- [🔱 BOOST] {doc}\n"
            else:
                result_text += "(SYSTEM: NO RELEVANT BOOSTING KNOWLEDGE FOR THIS CONTEXT)\n"
        else:
            result_text += "(SYSTEM: NO BOOSTING DATA IN CHROMADB OR CHROMA IS OFFLINE)\n"
        
        result_text += "</boosting_data>\n"
        
        return result_text

    # ══════════════════════════════════════════════════════════════════════════
    # ADDITIONAL FUNCTION: FINANCIAL HOLMES ALGORITHMIC BLOCK (V2.3)
    # ══════════════════════════════════════════════════════════════════════════
    
    def _extract_holmes_meta(self, rec: dict, is_ancestor: bool = False) -> dict:
        """Laser extract pure Metadata for Holmes Jaccard."""
        if is_ancestor:
            doc_id = rec.get("doc_id", rec.get("id", "UNKNOWN"))
            lesson = rec.get("lesson", rec.get("_lesson", rec.get("holmes_principle", "")))
            cm_phase = rec.get("cm_phase", "UNKNOWN").upper()
            wyckoff = str(rec.get("wyckoff", rec.get("context", {}).get("wyckoff_phase", "UNKNOWN"))).upper()
            signals_raw = rec.get("main_signals", rec.get("signals", ""))
            return {"doc_id": doc_id, "wyckoff": wyckoff, "cm_phase": cm_phase, "lesson": lesson, "signals_raw": signals_raw, "raw": rec}

        verdict = rec.get("verdict", {}) if isinstance(rec.get("verdict"), dict) else {}
        wyckoff = str(rec.get("wyckoff_phase", verdict.get("wyckoff_phase", "UNKNOWN"))).strip().upper()
        if wyckoff not in WYCKOFF_PHASES: wyckoff = "UNKNOWN"
        cm_phase = str(rec.get("cm_phase", "UNKNOWN")).strip().upper()
        
        quality = float(rec.get("quality_score", 0.5))
        hall_detected = bool(rec.get("hallucination_detected", verdict.get("hallucination_detected", False)))
        
        w_score = WYCKOFF_PHASES.get(wyckoff, {}).get("weight", 0.5) / 1.5 
        composite = (quality * 0.4) + (w_score * 0.4)
        if hall_detected: composite += 0.2

        lesson = verdict.get("lesson_for_9b", rec.get("chosen", ""))
        signals_raw = str(rec.get("vsa_scores", "")) + " " + str(rec.get("cm_confirmed", ""))

        return {
            "composite": round(composite, 4), "wyckoff": wyckoff, "cm_phase": cm_phase,
            "hall_detected": hall_detected, "lesson": lesson, "signals_raw": signals_raw, "raw": rec
        }

    def _holmes_jaccard_cross_check(self, cand: dict, anc: dict) -> float:
        """Holmes Cross-Check (Jaccard > 75% Multi-Axis)"""
        w_sim = 1.0 if cand['wyckoff'] == anc['wyckoff'] else 0.0
        cm_sim = 1.0 if cand['cm_phase'] == anc['cm_phase'] else 0.0
        sig_sim = _trigram_jaccard(cand.get('signals_raw', ''), anc.get('signals_raw', ''))
        les_sim = _trigram_jaccard(cand.get('lesson', ''), anc.get('lesson', ''))
        return (w_sim * 0.3) + (cm_sim * 0.2) + (sig_sim * 0.25) + (les_sim * 0.25)

    def distill_boost_pairs_holmes(self, input_file: Path) -> Path:
        """
        Holmes Distillation Pipeline: Jaccard scanning against Queen's repository.
        Fusing new Variant into "Family" instead of blindly filling Matrix.
        """
        from llm_router import router_api_call
        from datetime import datetime
        pairs = _load_jsonl(input_file)
        dt_str = datetime.now().strftime('%H%M%S_%d%m%y')
        out_file = self.engram_base / "boosting" / f"engram_boosting_holmes_{dt_str}.jsonl"
        if not pairs: return out_file

        log.info(f"🔍 [HOLMES] Analyzing {len(pairs)} raw records from {input_file.name}")
        candidates = []
        for p in pairs:
            meta = self._extract_holmes_meta(p, is_ancestor=False)
            if meta["composite"] >= 0.5:
                candidates.append(meta)

        ancestors_meta = []
        boosting_dir = self.engram_base / "boosting"
        anc_files = list(boosting_dir.glob("engrams_of_the_Queen_*.jsonl")) + list(boosting_dir.glob("engrams_*.jsonl"))
        
        # Take up to 1000 closest ancestors for matching performance (avoid OOM)
        count_anc = 0
        for af in sorted(anc_files, key=lambda x: x.stat().st_mtime, reverse=True):
            if count_anc > 1000: break
            for ar in _load_jsonl(af):
                if count_anc > 1000: break
                ancestors_meta.append(self._extract_holmes_meta(ar, is_ancestor=True))
                count_anc += 1

        families = defaultdict(list)
        novel_candidates = []
        redundant_count = 0

        for cand in candidates:
            if not ancestors_meta:
                novel_candidates.append(cand)
                continue
            max_sim = 0.0
            best_anc = None
            for anc in ancestors_meta:
                sim = self._holmes_jaccard_cross_check(cand, anc)
                if sim > max_sim:
                    max_sim = sim
                    best_anc = anc
            
            if max_sim >= 0.78:
                 redundant_count += 1
            elif max_sim >= 0.40:
                 families[best_anc['doc_id']].append(cand)
            else:
                 novel_candidates.append(cand)

        log.info(f"⚖️ [HOLMES LOGIC] Redundant (Discarded): {redundant_count} | Variant Families (Merged): {len(families)} | Novel (Breakthrough): {len(novel_candidates)}")

        new_engrams = []
        for anc_id, variants in list(families.items())[:10]: # Limit 10 calls to save API cost
            anc_record = next((a for a in ancestors_meta if a['doc_id'] == anc_id), None)
            if not anc_record: continue

            prompt = (
                "As the 'Financial Sherlock Holmes', my system has stored this Core Lesson (Ancestor):\n"
                f"--- ANCESTOR ---\n{anc_record['lesson'][:200]}\nWyckoff: {anc_record['wyckoff']}\nPhase: {anc_record['cm_phase']}\n\n"
                "I just discovered NEW VARIANTS (closely related to core, but branching at profit-taking):\n"
                f"--- VARIANTS ---\n{ [v['lesson'][:150] for v in variants][:3] }\n\n"
                "=== EMPIRE 4D KINEMATICS ALGORITHMS ===\n"
                "- KAR (Absorption Ratio): Iceberg wall footprint.\n"
                "- PEI (Path Efficiency): Level 2 Bot controlling trend status.\n"
                "- MNR (Micro-Noise): Liquidity hunting ground (Stop-hunt).\n"
                "- CA (Capitulation): Peak panic zone (FOMO/Panic).\n"
                "🔥 WAY OF THE NINJA: Distill them! Return exactly 1 JSON Object containing:\n"
                '{"main_signals": "Core signals including 4D algorithms", "fake_variants": "Manipulative traps MM sets to invalidate variants", "holmes_principle": "Universal rule covering both Ancestor and Variant"}\n'
            )
            resp = router_api_call(prompt, agent_id='A04', brain_mode='A04_ENGRAM', est_tokens=800)
            clean_json = self._clean_jsonl_response(resp)
            try:
                if clean_json:
                    merged = json.loads(clean_json)
                    merged['doc_id'] = f"ENG_BOOST_VAR_{int(time.time()*1000)}"
                    merged['type'] = 'holmes_family_fusion'
                    new_engrams.append(merged)
            except Exception as e: log.error(f"[HOLMES] Error decoding JSON Family: {e}. Raw: {clean_json[:200]}...")

        if novel_candidates:
             chunk = [n['lesson'][:200] for n in novel_candidates[:5]]
             prompt = (
                "As the cash-flow Sherlock Holmes! Here are BRAND NEW EXERCISES (Blind Spots) never seen before:\n"
                f"{chunk}\n\n"
                "=== EMPIRE 4D KINEMATICS ALGORITHMS ===\n"
                "- KAR (Absorption Ratio): Iceberg wall footprint.\n"
                "- PEI (Path Efficiency): Level 2 Bot controlling trend status.\n"
                "- MNR (Micro-Noise): Liquidity hunting ground (Stop-hunt).\n"
                "- CA (Capitulation): Peak panic zone (FOMO/Panic).\n"
                "🔥 WAY OF THE NINJA: Decode the Blind Spot! Generate 1 JSON Object:\n"
                '{"main_signals": "4D Kinematics identification signals", "fake_variants": "Traps (if any)", "holmes_principle": "Nature of the new manipulation algorithm"}\n'
             )
             resp = router_api_call(prompt, agent_id='A04', brain_mode='A04_ENGRAM', est_tokens=800)
             clean_json = self._clean_jsonl_response(resp)
             try:
                 if clean_json:
                     merged = json.loads(clean_json)
                     merged['doc_id'] = f"ENG_BOOST_NOV_{int(time.time()*1000)}"
                     merged['type'] = 'holmes_novel_creation'
                     new_engrams.append(merged)
             except Exception as e: log.error(f"[HOLMES] Error decoding JSON Novel: {e}. Raw: {clean_json[:200]}...")

        if new_engrams:
             with open(out_file, 'w', encoding='utf-8') as f:
                 for eg in new_engrams:
                     f.write(json.dumps(eg, ensure_ascii=False) + "\n")
             log.info(f"💎 [HOLMES LOGIC] Successfully consolidated {len(new_engrams)} core elite lessons into {out_file.name}")
             return out_file
        return None
