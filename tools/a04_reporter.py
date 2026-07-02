"""
🧬 DNA: v16.6 (Sovereign Intelligence Kindler - Exhaustive Mode)
🏢 UNIT: A04_REPORTER
🛠️ ROLE: KNOWLEDGE_KINDLER
📖 DESC: COMPREHENSIVE knowledge bridge A04 -> NotebookLM. Recursive scan and error recovery.
"""

import os
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from imperial_state import matrix

# 🔱 CONFIGURATION — SOVEREIGN PATHS 🔱
BASE_DIR = Path(__file__).resolve().parent.parent
# Root of A04 knowledge
ENGRAMS_ROOT = BASE_DIR / "dpo_lab" / "engrams" / "A04"
# Root of Queen reports
REPORTS_ROOT = BASE_DIR / "notebooklm_sources" / "engrams" / "A04"

# 🔱 INTELLIGENT LOGIC 🔱

def json_to_md(entry: dict, filename: str) -> str:
    """Converts a data block into standard Markdown format."""
    if not isinstance(entry, dict):
        return ""
        
    # Get basic information, prioritizing doc_id or timestamp combination
    doc_id = entry.get("doc_id") or f"{entry.get('agent_id') or 'A04'}_{entry.get('timestamp', 'N/A')}"
    context = (entry.get("context") or entry.get("metadata")) or {}
    metrics = entry.get("quantitative_metrics") or {}
    insight = entry.get("meta_insight") or entry.get("content", "No content description available.")
    result = entry.get("forward_24_result", "N/A")
    
    # Identify data type (Boosting vs Genesis) based on structure
    is_dpo = "chosen" in entry and "rejected" in entry
    
    if is_dpo:
        md = f"## 🚀 DPO Scenario: {doc_id}\n\n"
        md += f"- **Source File**: `{filename}`\n"
        md += f"### 🎭 Context:\n{entry.get('prompt', 'N/A')}\n\n"
        md += f"### ✅ Chosen:\n{entry.get('chosen', 'N/A')}\n\n"
        md += f"### ❌ Rejected:\n{entry.get('rejected', 'N/A')}\n\n"
        md += f"> **💡 INSIGHT:** {insight}\n\n"
    else:
        md = f"## 🔱 Wyckoff Lesson: {doc_id}\n\n"
        md += f"- **Source File**: `{filename}`\n"
        md += "| Metric | Value |\n"
        md += "| :--- | :--- |\n"
        md += f"| **Phase** | {context.get('wyckoff_phase') or context.get('phase', 'N/A')} |\n"
        md += f"| **Elliott** | {context.get('elliott_wave', 'N/A')} |\n"
        md += f"| **Fingerprint** | {context.get('vsa_fingerprint', 'N/A')} |\n"
        md += f"| **Confidence** | {metrics.get('confidence_score', 'N/A')} |\n"
        md += f"| **Result** | {result} |\n\n"
        md += f"> **🔥 MASTER INSIGHT:**\n> {insight}\n\n"
    
    md += "---\n\n"
    return md

def get_report_filename(original_file: str) -> str:
    """Creates an MD filename containing the original filename + standard timestamp ssmmhh_ddmmyy."""
    now = datetime.now()
    timestamp = now.strftime("%S%M%H_%d%m%y")
    return f"A04_REPORT_{original_file.replace('.', '_')}_{timestamp}.md"

def exhaust_sweep(force_all: bool = False):
    """
    EXHAUSTIVE SWEEP: Recursively scan the entire engrams/A04 directory
    """
    if not ENGRAMS_ROOT.exists():
        print(f"❌ [A04_REPORTER] Engrams root not found: {ENGRAMS_ROOT}")
        return

    print(f"🔱 [A04_REPORTER] Starting EXHAUSTIVE SWEEP of A04 knowledge (Mode: {'TOTAL_FORCE' if force_all else 'INCREMENTAL'})")
    
    # Recursive traversal
    for root, dirs, files in os.walk(ENGRAMS_ROOT):
        json_files = [f for f in files if f.endswith(('.jsonl', '.json'))]
        if not json_files:
            continue
            
        # Determine corresponding destination path
        relative_path = Path(root).relative_to(ENGRAMS_ROOT)
        dest_dir = REPORTS_ROOT / relative_path
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        checkpoint_key = f"zcl:a04:report:v2_checkpoint:{relative_path or 'root'}"
        processed = [] if force_all else (matrix.get("SYSTEM", checkpoint_key) or [])
        
        for fname in json_files:
            if fname in processed and not force_all:
                continue
                
            f_path = Path(root) / fname
            print(f"📄 Processing: {f_path.relative_to(ENGRAMS_ROOT)}")
            
            md_buffer = f"# 🔱 SUMMARY REPORT FOR A04 KNOWLEDGE: {fname}\n"
            md_buffer += f"Compilation Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            md_buffer += f"Knowledge Layer: {relative_path or '/'}\n\n"
            md_buffer += "===\n\n"
            
            try:
                # Process file content (SOVEREIGN STREAM PARSER V17.1)
                with open(f_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    
                if content:
                    import json
                    decoder = json.JSONDecoder()
                    idx = 0
                    while idx < len(content):
                        # Skip whitespace
                        while idx < len(content) and content[idx].isspace():
                            idx += 1
                        if idx >= len(content):
                            break
                        try:
                            entry, end_idx = decoder.raw_decode(content, idx)
                            md_buffer += json_to_md(entry, fname)
                            idx = end_idx
                        except json.JSONDecodeError:
                            # Fallback if raw_decode fails - try line by line
                            idx += 1
                
                # Save MD file
                report_name = get_report_filename(fname)
                with open(dest_dir / report_name, 'w', encoding='utf-8') as f_md:
                    f_md.write(md_buffer)
                
                # Update checkpoint
                if not force_all:
                    processed.append(fname)
                    matrix.set("SYSTEM", checkpoint_key, processed, ttl=None)
                    
            except Exception as fe:
                print(f"   ❌ Critical error reading file {fname}: {fe}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A04 Exhaustive Reporter")
    parser.add_argument("--all", action="store_true", help="Sweep all, bypassing checkpoint")
    parser.add_argument("--once", action="store_true", help="Run once")
    parser.add_argument("--loop", action="store_true", default=True, help="Run in background every 30m")
    
    args = parser.parse_args()
    
    if args.once:
        exhaust_sweep(force_all=args.all)
    else:
        print("🔱 [A04_REPORTER_V2] EXHAUSTIVE SWEEP engine activated. Pulse: 30 minutes.")
        while True:
            exhaust_sweep(force_all=args.all)
            time.sleep(1800)
