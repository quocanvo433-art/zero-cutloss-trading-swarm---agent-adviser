"""
🧬 DNA: v16.7 (Sovereign Purity & Biological Inspector)
🏢 UNIT: PURITY_CHECK
🛠️ ROLE: ARCHITECTURAL_SENTINEL
📖 DESC: Empire Purity Verification System. Scans all source code to ensure 100% of files have DNA Headers and match TOOL_REGISTRY.md.
🔗 CALLS: TOOL_REGISTRY.md, agents/, tools/, scripts/
📟 I/O: Console Report, logs/purity_audit.log
🛡️ INTEGRITY: Registry-Consistency, Genetic-Mapping, Law-Enforcement.
"""

import os
import re
import sys
import logging
import ast
import traceback
import shutil
from pathlib import Path

# --- Configuration ---
BASE_DIR = Path(__file__).parent.parent
REGISTRY_FILE = BASE_DIR / "TOOL_REGISTRY.md"
TARGET_DIRS = ["agents", "tools", "scripts", "agentic"]
# DNA v113.0: Redirect logs to an internal directory to avoid Permission errors on logs/
LOG_DIR = BASE_DIR / "logs_purity"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "purity_audit.log"
CYCLE_FILE = LOG_DIR / ".purity_cycle"
CHECKPOINT_DIR = BASE_DIR / ".checkpoint_green"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("PURITY_GUARD")

def extract_dna_header(file_path: Path) -> dict:
    """Extract information from DNA Header in Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(2000) # Only read the beginning to find the header
            
        header_match = re.search(r'"""\s*🧬 DNA:.*🏢 UNIT: (?P<unit>.*)\s*🛠️ ROLE: (?P<role>.*)\s*📖 DESC: (?P<desc>.*)', content, re.DOTALL)
        if header_match:
            return {
                "unit": header_match.group("unit").strip(),
                "role": header_match.group("role").strip(),
                "desc": header_match.group("desc").strip(),
                "status": "VALID"
            }
        
        # Try to find old or legacy format
        if "UNIT:" in content and "ROLE:" in content:
            return {"status": "LEGACY", "raw": "Found legacy markers but failed parse."}
            
        return {"status": "MISSING"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def parse_registry() -> set:
    """Read TOOL_REGISTRY.md and get the list of registered files."""
    registered_files = set()
    if not REGISTRY_FILE.exists():
        log.error(f"TOOL_REGISTRY.md does not exist at {REGISTRY_FILE}")
        return registered_files

    with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # DNA v117.9: First column only match to avoid Ghost File from path in column 3
    matches = re.findall(r'^\|\s*`(?P<filename>[^`]+\.py)`\s*\|', content, re.MULTILINE)
    for m in matches:
        registered_files.add(m)
        
    return registered_files

def run_audit():
    log.info("=== STARTING DNA PURITY INSPECTION (v16.6) ===")
    
    registry = parse_registry()
    log.info(f"Loaded {len(registry)} files from TOOL_REGISTRY.md")
    
    issues = []
    scanned_count = 0
    passed_count = 0
    
    for dname in TARGET_DIRS:
        dir_path = BASE_DIR / dname
        if not dir_path.exists():
            continue
            
        log.info(f"Scanning directory: {dname}/ (recursive)")
        # Scan all .py files in directory and subdirectories
        for fpath in dir_path.rglob("*.py"):
            if fpath.name == "__init__.py" or "__pycache__" in str(fpath):
                continue
                
            scanned_count += 1
            dna = extract_dna_header(fpath)
            
            # 1. Verify DNA Header
            if dna["status"] == "MISSING":
                issues.append(f"[DNA_MISSING] {dname}/{fpath.relative_to(dir_path)}")
            elif dna["status"] == "LEGACY":
                issues.append(f"[DNA_LEGACY] {dname}/{fpath.relative_to(dir_path)} (Need to upgrade to v16.6)")
            elif dna["status"] == "ERROR":
                issues.append(f"[READ_ERROR] {dname}/{fpath.relative_to(dir_path)}: {dna['error']}")
                
            # 1.5 Syntax Check (AST Linter Flow) - Early Warning Mechanism for AI
            try:
                with open(fpath, "r", encoding="utf-8") as rf:
                    ast.parse(rf.read(), filename=str(fpath))
            except SyntaxError as e:
                err_msg = f"[SYNTAX_ERROR] {dname}/{fpath.relative_to(dir_path)} | Error at line {e.lineno}: {e.msg}"
                issues.append(err_msg)
                dna["status"] = "SYNTAX_FATAL" # Force demotion
            except Exception as e:
                issues.append(f"[COMPILATION_ERROR] {dname}/{fpath.relative_to(dir_path)} | Error: {str(e)}")
            
            # 2. Check Registration (Registry)
            # Check by file name, or can check by relative path if tighter constraint is needed
            if fpath.name not in registry:
                issues.append(f"[NOT_REGISTERED] {dname}/{fpath.relative_to(dir_path)} (Missing in TOOL_REGISTRY.md)")
            else:
                registry.discard(fpath.name) # Mark as seen (discard does not error if already removed)
                if dna["status"] == "VALID":
                    passed_count += 1

    # 3. Check ghost files (in Registry but missing in reality)
    for ghost in registry:
        issues.append(f"[GHOST_FILE] {ghost} (Present in Registry but actual file not found in scanned dirs)")

    # --- FINAL REPORT ---
    log.info("-" * 40)
    log.info(f"AUDIT SUMMARY:")
    log.info(f"  - Scanned: {scanned_count} files")
    log.info(f"  - DNA Compliant: {passed_count} files")
    log.info(f"  - Violations: {len(issues)} errors")
    log.info("-" * 40)
    
    if issues:
        log.warning("VIOLATION LIST:")
        for issue in issues:
            log.warning(f"  - {issue}")
        log.error("System fails to meet 100% Sovereign Purity standard. Requires remediation or DNA headers immediately.")
        
        # Read cycle
        cycle = 1
        if CYCLE_FILE.exists():
            try:
                with open(CYCLE_FILE, "r") as f:
                    cycle = int(f.read().strip()) + 1
            except: pass
        
        with open(CYCLE_FILE, "w") as f:
            f.write(str(cycle))
            
        print("\n" + "X"*70)
        if cycle >= 4:
            print(f"💀 [STATELESS MODE TRIGGERED - CYCLE {cycle}/4] OUT OF CONTROL HALLUCINATIONS!")
            print("1. CODE WORK SUSPENDED: Your short-term memory is saturated, causing cascading errors.")
            print("2. CONTEXT FLUSH: Drop all current logical assumptions in your mind.")
            print("3. RESTORE CHECKPOINT (ROLLBACK): Run command to copy all agents, tools, scripts from .checkpoint_green/ back to root.")
            print("   -> Recommended command: cp -r .checkpoint_green/* .")
            print("4. AFTER RESTORATION: Re-read CODING_RULES.md. STOP SURFACE REASONING. Must delve deep into the NodeGraph before thinking.")
        else:
            print(f"🛑 [AI DIRECTIVE - PROTOCOL BREACH] CYCLE {cycle}/4 - WARNING!")
            print("1. REFLEXION: Carefully read AST (SYNTAX_ERROR) or Registry error messages above.")
            print("2. ANTI-SUPERFICIAL HALLUCINATION PROTOCOL: Are you guessing an internal function or import? MUST use grep_search or view_file to trace dependencies (F3 NodeGraph).")
            print("3. CHUNKING DATA: Errors arose from wide-ranging modifications? Step back, fix small blocks.")
            print("4. PATIENCE: This loop repeats until GREEN. [WARNING: Exceeding 4 iterations forces a Context Reboot].")
        print("X"*70 + "\n")
        
        sys.exit(1)
    else:
        log.info("✅ SYSTEM MEETS 100% SOVEREIGN PURITY STANDARD. ORGANIC INTEGRITY PRESERVED.")
        
        if CYCLE_FILE.exists():
            os.remove(CYCLE_FILE)
            
        # AUTO CHECKPOINT
        if CHECKPOINT_DIR.exists():
            shutil.rmtree(CHECKPOINT_DIR)
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        for dname in TARGET_DIRS:
            src = BASE_DIR / dname
            dst = CHECKPOINT_DIR / dname
            if src.exists():
                shutil.copytree(src, dst)
        
        # --- AI ORIENTATION CORE (PASSED LOOP) ---
        print("\n" + "="*70)
        print("🌟 [AI DIRECTIVE - ZERO CUTLOSS CLEARED] LINTER LOOP PASSED!")
        print("1. TRANSPARENCY: Codebase guarantees syntax integrity (AST Passed) & DNA structure.")
        print(f"2. HISTORICAL ANCHOR (CHECKPOINT CREATED): All source code has been automatically backed up to {CHECKPOINT_DIR}.")
        print("   -> Always trust this anchor if you face future hallucinations.")
        print("3. PRAGMATIC TESTING: Verify correctness via real tests (e.g., --limit 1) before considering the task done.")
        print("4. REPORT SUBMISSION: Update walkthrough.md concisely and smartly. NEVER BE VERBOSE.")
        print("="*70 + "\n")
        
        sys.exit(0)

if __name__ == "__main__":
    run_audit()
