"""
🧬 DNA: v16.6 (Sovereign Purity & Defense)
🏢 UNIT: SECURITY_SCANNER
🛠️ ROLE: SYSTEM_ARMOR
📖 DESC: Multi-tier security scanning system (9 vectors), verifying DPO pairs integrity, detecting injection, and system hardening.
🔗 CALLS: tools/dos_guardian.py, tools/threat_classifier.py
📟 I/O: security/logs/ (OUT), dpo_lab/ (IN)
🛡️ INTEGRITY: Anti-Recon, FIM-Init, HMAC-Verify.
"""

import os, sys, json, re, hmac, hashlib, time, subprocess, socket, statistics
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv
from collections import Counter

BASE_DIR   = Path(__file__).parent.parent
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env")
PAIRS_HMAC = os.getenv("IMMUNITY_HMAC_SECRET", "CHANGE_ME")
REDIS_URL  = os.getenv("REDIS_URL", "redis://localhost:6379")
CHROMA_URL = os.getenv("CHROMA_URL", "http://localhost:8001")
BINANCE_KEY = os.getenv("BINANCE_API_KEY", "")

SECURITY_DIR = BASE_DIR / "security"
SECURITY_DIR.mkdir(exist_ok=True)

# ANSI colors
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; E = "\033[0m"; W = "\033[1m"

INJECTION_PATS = [
    r"ignore\s+(previous|all|above)\s+instructions?",
    r"you\s+are\s+now\s+a?\s*(different|new)\s+",
    r"act\s+as\s+if\s+you\s+are",
    r"override\s+(output|response|behavior|rules)",
    r"print\s+(your\s+)?(api\s*key|system\s+prompt|secret)",
    r"<\|?(im_start|im_end|system|user|assistant)\|?>",
    r"\[INST\]|\[\/INST\]",
    r"OVERRIDE_ZCL|ZCL_INJECT",
    r"eval\s*\(|exec\s*\(",
    r"__import__\s*\(",
    r"subprocess\.(?:run|call|Popen)",
    r"os\.(?:system|popen|remove|unlink)",
]
COMPILED_INJECTS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in INJECTION_PATS]

HIDDEN_BYTES = [
    b"\xe2\x80\x8b",  # zero-width space
    b"\xef\xbb\xbf",  # BOM
    b"\xe2\x80\x8c",  # zero-width non-joiner
    b"\xc2\xad",      # soft hyphen (invisible)
    b"\xe2\x80\x8d",  # zero-width joiner
    b"\xe2\x81\xa0",  # word joiner
]

ALLOWED_DOC_TYPES = {"theory", "ly_thuyet", "binance_history", "lich_su_binance", "dpo_chosen", "dpo_rejected"}


def _hmac_verify(data: str, sig: str) -> bool:
    exp = hmac.new(PAIRS_HMAC.encode(), data.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(exp, sig)

def _print_result(vector: str, status: str, detail: str = ""):
    icon  = f"{G}✓{E}" if status == "PASS" else (f"{R}✗{E}" if status == "FAIL" else f"{Y}~{E}")
    color = G if status == "PASS" else (R if status == "FAIL" else Y)
    print(f"  {icon} {W}{vector}{E}: {color}{status}{E} {detail}")


# ══════════════════════════════════════════════════════════════════════════════
# V1 — INJECTION PATTERNS
# ══════════════════════════════════════════════════════════════════════════════

def scan_v1_injection() -> dict:
    """Scan injection patterns in soul files and Python tools"""
    findings = []
    scan_paths = list((BASE_DIR / "agents").glob("*.md")) + \
                 list((BASE_DIR / "agents" / "logic").glob("*.py")) + \
                 list((BASE_DIR / "tools").glob("*.py")) + \
                 list((BASE_DIR / "scripts").glob("*.py"))

    for fp in scan_paths:
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
            for i, pat in enumerate(COMPILED_INJECTS):
                m = pat.search(text)
                if m:
                    findings.append({
                        "file": fp.name, "pattern": INJECTION_PATS[i][:50],
                        "match": m.group()[:60], "line": text[:m.start()].count("\n") + 1,
                    })
        except Exception:
            pass

    status  = "FAIL" if findings else "PASS"
    _print_result("V1 Injection scan", status,
                  f"({len(scan_paths)} files | {len(findings)} findings)")
    return {"status": status, "scanned": len(scan_paths), "findings": findings}


# ══════════════════════════════════════════════════════════════════════════════
# V2 — HIDDEN CHARACTERS
# ══════════════════════════════════════════════════════════════════════════════

def scan_v2_hidden_chars() -> dict:
    findings = []
    scan_paths = list((BASE_DIR / "agents").glob("*.md")) + \
                 list((BASE_DIR / "agents" / "logic").glob("*.py")) + \
                 list((BASE_DIR / "tools").glob("*.py")) + \
                 list((BASE_DIR / "config").glob("*.md")) + \
                 [BASE_DIR / "MASTER_RULES.md", BASE_DIR / "CONTEXT.md"]

    for fp in [p for p in scan_paths if p.exists()]:
        try:
            content = fp.read_bytes()
            found = [pat.hex() for pat in HIDDEN_BYTES if pat in content]
            if found:
                findings.append({"file": fp.name, "hidden_bytes": found,
                                  "byte_count": sum(content.count(p) for p in HIDDEN_BYTES)})
        except Exception:
            pass

    status = "FAIL" if findings else "PASS"
    _print_result("V2 Hidden chars", status,
                  f"({len(findings)} suspicious files)")
    return {"status": status, "findings": findings}


# ══════════════════════════════════════════════════════════════════════════════
# V3 — CHROMADB INTEGRITY
# ══════════════════════════════════════════════════════════════════════════════

def scan_v3_chromadb() -> dict:
    try:
        import chromadb
        host = CHROMA_URL.replace("http://","").split(":")[0]
        port = int(CHROMA_URL.split(":")[-1]) if ":" in CHROMA_URL else 8001
        client = chromadb.HttpClient(host=host, port=port)
        coll   = client.get_collection("wyckoff_patterns")
        all_docs = coll.get(include=["metadatas"], limit=10000)
        alien = [m for m in all_docs.get("metadatas",[])
                 if m.get("doc_type", m.get("loai_doc")) not in ALLOWED_DOC_TYPES]
        total = len(all_docs.get("metadatas",[]))
        status = "FAIL" if alien else ("WARN" if total < 15 else "PASS")
        detail = f"({total} docs | {len(alien)} alien)"
        if total < 15:
            detail += " — less than 15 docs, run chroma_ingest.py --init"
        _print_result("V3 ChromaDB integrity", status, detail)
        return {"status": status, "total_docs": total, "alien_docs": len(alien),
                "alien_examples": alien[:3]}
    except Exception as e:
        _print_result("V3 ChromaDB integrity", "WARN", f"(failed to connect: {e})")
        return {"status": "WARN", "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# V4 — DPO PAIRS HMAC
# ══════════════════════════════════════════════════════════════════════════════

def scan_v4_dpo_hmac() -> dict:
    if PAIRS_HMAC == "CHANGE_ME":
        _print_result("V4 DPO HMAC", "FAIL", "(IMMUNITY_HMAC_SECRET has not been changed from default!)")
        return {"status": "FAIL", "reason": "Default secret"}

    results = {}
    for fname in ["chosen.jsonl", "rejected.jsonl"]:
        fp  = BASE_DIR / "dpo_lab" / "pairs" / fname
        sig = BASE_DIR / "dpo_lab" / "pairs" / f"{fname}.sig"
        if not fp.exists():
            results[fname] = "NOT_FOUND"
            continue
        if not sig.exists():
            results[fname] = "NO_SIG_FILE"
            continue
        content = fp.read_text(encoding="utf-8")
        stored  = sig.read_text().strip()
        results[fname] = "PASS" if _hmac_verify(content, stored) else "FAIL_TAMPERED"

    # Check anomaly_score field in the latest pairs
    no_provenance = 0
    if (BASE_DIR / "dpo_lab" / "pairs" / "chosen.jsonl").exists():
        with open(BASE_DIR / "dpo_lab" / "pairs" / "chosen.jsonl") as f:
            for line in f.readlines()[-50:]:  # Last 50 entries
                try:
                    obj = json.loads(line.strip())
                    if "source_type" not in obj:
                        no_provenance += 1
                except Exception:
                    pass

    overall = "FAIL" if any(v in ("FAIL_TAMPERED","FAIL") for v in results.values()) else "PASS"
    detail  = f"({results}) | {no_provenance} pairs missing provenance"
    _print_result("V4 DPO HMAC", overall, detail)
    return {"status": overall, "files": results, "no_provenance_count": no_provenance}


# ══════════════════════════════════════════════════════════════════════════════
# V5 — API CROSS-VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def scan_v5_api_crossvalidation() -> dict:
    """Compare BTC price from Binance vs CoinGecko — if deviation >2% = suspicious"""
    results = {}
    headers = {"User-Agent": "Mozilla/5.0"}

    # Get from Binance (REST public, no key needed)
    binance_price = None
    try:
        resp = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                            timeout=5, headers=headers)
        binance_price = float(resp.json()["price"])
    except Exception as e:
        results["binance"] = f"ERROR: {e}"

    # Get from CoinGecko
    cg_price = None
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=5, headers=headers)
        cg_price = resp.json()["bitcoin"]["usd"]
    except Exception as e:
        results["coingecko"] = f"ERROR: {e}"

    if binance_price and cg_price:
        delta_pct = abs(binance_price - cg_price) / cg_price * 100
        if delta_pct > 2.0:
            results["cross_validation"] = f"FAIL: delta {delta_pct:.2f}% — Binance={binance_price} CG={cg_price}"
            status = "FAIL"
        else:
            results["cross_validation"] = f"OK: delta {delta_pct:.2f}%"
            status = "PASS"
    else:
        status = "WARN"

    _print_result("V5 API cross-validation", status,
                  f"(BTC delta {results.get('cross_validation','N/A')[:40]})")
    return {"status": status, "results": results, "binance": binance_price, "coingecko": cg_price}


# ══════════════════════════════════════════════════════════════════════════════
# V6 — NETWORK ISOLATION
# ══════════════════════════════════════════════════════════════════════════════

def scan_v6_network_isolation() -> dict:
    """
    Verify ChromaDB and Redis are NOT exposed outside the Docker network.
    If accessible from localhost with mapped ports = risky.
    """
    findings = []

    # Check ChromaDB port
    for host, port, service in [
        ("localhost", 8001, "ChromaDB"),
        ("127.0.0.1", 6379, "Redis"),
    ]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                # Port open — check if docker-compose has port mapping
                compose = BASE_DIR / "docker-compose.yml"
                if compose.exists():
                    content = compose.read_text()
                    port_str = str(port)
                    if f"- \"{port_str}:{port_str}\"" in content or f"- '{port_str}:{port_str}'" in content:
                        findings.append({
                            "service": service, "port": port,
                            "issue": "Port exposed in docker-compose — use 'expose' instead of 'ports'"
                        })
        except Exception:
            pass

    # Verify Redis has password auth
    redis_conf_ok = False
    redis_pw = os.getenv("REDIS_PASSWORD", "")
    if redis_pw:
        redis_conf_ok = True

    if not redis_conf_ok:
        findings.append({"service": "Redis", "issue": "REDIS_PASSWORD not set — Redis has no auth"})

    status = "WARN" if findings else "PASS"
    _print_result("V6 Network isolation", status, f"({len(findings)} issues)")
    return {"status": status, "findings": findings}


# ══════════════════════════════════════════════════════════════════════════════
# V7 — DRIFT DETECTION (Most Critical — long game attack detector)
# ══════════════════════════════════════════════════════════════════════════════

def scan_v7_drift_detection() -> dict:
    """
    Analyze statistical drift in DPO pairs to detect long game poisoning attacks.

    Long game attack: attacker creates fake pumps multiple times to train model on incorrect patterns.
    Signs:
    1. Anomalously high win rate in the last 30 days (>80% vs normal ~40-60%)
    2. Sudden spike in average profit (from ~5% to >15%)
    3. Max drawdown suddenly drops to 0
    4. Skewed Wyckoff Phase distribution (too much PHASE_C in 7 days)
    5. Streak detector: consecutive CHOSEN

    This is V7 because it detects hidden patterns over time — V1-V6 detect single events.
    """
    chosen_file = BASE_DIR / "dpo_lab" / "pairs" / "chosen.jsonl"
    if not chosen_file.exists():
        _print_result("V7 Drift detection", "WARN", "(chosen.jsonl does not exist)")
        return {"status": "WARN", "reason": "No data"}

    # Read all chosen pairs
    all_chosen = []
    with open(chosen_file, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line.strip())
                all_chosen.append(obj)
            except Exception:
                pass

    if len(all_chosen) < 10:
        _print_result("V7 Drift detection", "WARN", f"(only {len(all_chosen)} pairs — need at least 10)")
        return {"status": "WARN", "reason": "Insufficient data", "count": len(all_chosen)}

    findings = []
    drift_score = 0

    # ── Metric 1: Win rate trượt (rolling 30 vs rolling 60) ──────────────────
    n = len(all_chosen)
    window_recent = all_chosen[-min(30, n):]
    window_old    = all_chosen[-min(60, n):-min(30, n)] if n > 30 else []

    recent_profits = []
    old_profits    = []

    for rec in window_recent:
        try:
            resp = json.loads(rec.get("response","{}"))
            actual = resp.get("actual_result", resp.get("ket_qua_thuc_te", {}))
            loi = actual.get("profit_pct", actual.get("loi_nhuan_pct", rec.get("profit_pct", rec.get("loi_nhuan_pct", 0))))
            if isinstance(loi, (int, float)):
                recent_profits.append(float(loi))
        except Exception:
            pass

    for rec in window_old:
        try:
            resp = json.loads(rec.get("response","{}"))
            actual = resp.get("actual_result", resp.get("ket_qua_thuc_te", {}))
            loi = actual.get("profit_pct", actual.get("loi_nhuan_pct", rec.get("profit_pct", rec.get("loi_nhuan_pct", 0))))
            if isinstance(loi, (int, float)):
                old_profits.append(float(loi))
        except Exception:
            pass

    if recent_profits:
        avg_recent = statistics.mean(recent_profits)
        if old_profits:
            avg_old = statistics.mean(old_profits)
            delta = avg_recent - avg_old
            if delta > 8:  # Sudden increase in avg profit > 8%
                drift_score += 30
                findings.append({
                    "metric": "PROFIT_SPIKE",
                    "detail": f"Average profit 30 days: {avg_recent:.1f}% vs prior: {avg_old:.1f}% (delta +{delta:.1f}%)",
                    "severity": "HIGH",
                    "giai_thich": "Possible long game attack active — fake pump is being labeled CHOSEN"
                })

        if avg_recent > 20:  # Avg >20% = abnormal
            drift_score += 25
            findings.append({
                "metric": "EXTREME_AVG_PROFIT",
                "detail": f"Average profit {avg_recent:.1f}% — exceeds reasonable threshold",
                "severity": "HIGH"
            })

    # ── Metric 2: Wyckoff Phase distribution ─────────────────────────────────
    phase_count: Counter = Counter()
    for rec in window_recent:
        try:
            prompt = json.loads(rec.get("prompt","{}"))
            phase  = prompt.get("wyckoff_phase","UNKNOWN")
            phase_count[phase] += 1
        except Exception:
            pass

    if phase_count:
        total_phases  = sum(phase_count.values())
        phase_c_ratio = phase_count.get("PHASE_C", 0) / total_phases if total_phases > 0 else 0
        if phase_c_ratio > 0.85:  # >85% Phase C = abnormal
            drift_score += 20
            findings.append({
                "metric": "PHASE_C_DOMINANCE",
                "detail": f"{phase_c_ratio*100:.0f}% of pairs are PHASE_C in the last 30 days",
                "severity": "MEDIUM",
                "giai_thich": "Normal ~40-60%. High ratio could indicate selective pump attack."
            })

    # ── Metric 3: Anomaly score distribution ─────────────────────────────────
    no_anomaly_field = sum(1 for r in all_chosen if "anomaly_score" not in r)
    if no_anomaly_field > len(all_chosen) * 0.5:
        drift_score += 10
        findings.append({
            "metric": "MISSING_ANOMALY_FIELD",
            "detail": f"{no_anomaly_field}/{len(all_chosen)} pairs missing anomaly_score",
            "severity": "LOW",
            "giai_thich": "Legacy pairs prior to dpo_evaluator v2 update — normal"
        })

    # ── Metric 4: Source distribution ────────────────────────────────────────
    source_count: Counter = Counter(r.get("source_type","unknown") for r in all_chosen)
    total_pairs = len(all_chosen)
    synthetic_ratio = (source_count.get("opus_synthetic",0) + source_count.get("immunity_vaccine",0)) / total_pairs
    if synthetic_ratio > 0.7:
        drift_score += 15
        findings.append({
            "metric": "HIGH_SYNTHETIC_RATIO",
            "detail": f"{synthetic_ratio*100:.0f}% of pairs are synthetic — real_trade only {source_count.get('real_trade',0)}",
            "severity": "MEDIUM",
            "giai_thich": "High synthetic ratio = model learns more from simulation than real trading"
        })

    # ── Metric 5: Consecutive CHOSEN streak ───────────────────────────────────
    max_streak, current_streak = 0, 0
    for rec in all_chosen:
        rec_class = rec.get("classification", rec.get("phan_loai", "")).upper()
        if rec_class in ("CHOSEN", "DPO_CHOSEN"):
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    if max_streak >= 5:
        drift_score += 20
        findings.append({
            "metric": "CHOSEN_STREAK",
            "detail": f"Max streak CHOSEN: {max_streak}",
            "severity": "HIGH" if max_streak >= 8 else "MEDIUM",
            "giai_thich": "Long streak = market is repeating patterns (OK) OR long game attack is in progress"
        })

    # ── Conclusions ──────────────────────────────────────────────────────────
    if drift_score >= 50:
        status = "FAIL"
        recommendation = "STOP training immediately. Send to Opus to review all chosen.jsonl from the last 30 days."
    elif drift_score >= 25:
        status = "WARN"
        recommendation = "Opus review required in the next session. Suspend injecting new pairs."
    else:
        status = "PASS"
        recommendation = "Normal distribution."

    _print_result("V7 Drift detection", status,
                  f"(drift_score={drift_score} | {len(findings)} anomalies | {len(all_chosen)} pairs)")

    if findings:
        for f in findings[:3]:
            print(f"     {Y}→{E} [{f['severity']}] {f['metric']}: {f['detail'][:70]}")

    return {
        "status":         status,
        "drift_score":    drift_score,
        "total_pairs":    len(all_chosen),
        "findings":       findings,
        "recommendation": recommendation,
        "phase_dist":     dict(phase_count),
        "source_dist":    dict(source_count),
        "avg_profit_recent": round(statistics.mean(recent_profits), 2) if recent_profits else None,
        "max_streak":     max_streak,
    }


# ══════════════════════════════════════════════════════════════════════════════
# V8 — SUPPLY CHAIN (requirements hash)
# ══════════════════════════════════════════════════════════════════════════════

def scan_v8_supply_chain() -> dict:
    """Verify requirements.txt and Docker image provenance"""
    findings = []

    # Verify requirements.txt pins versions
    req_file = BASE_DIR / "requirements.txt"
    if req_file.exists():
        content = req_file.read_text()
        lines   = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
        unpinned = [l for l in lines if "==" not in l and ">=" not in l and not l.startswith("-")]
        if unpinned:
            findings.append({
                "type":   "UNPINNED_DEPS",
                "detail": f"{len(unpinned)} packages not pinned: {unpinned[:5]}",
            })
        no_hash = [l for l in lines if "--hash=" not in l and l and not l.startswith("-")]
        if len(no_hash) > 5:
            findings.append({
                "type":   "NO_HASH_VERIFICATION",
                "detail": f"{len(no_hash)} packages missing --hash. Use: pip-compile --generate-hashes",
            })
    else:
        findings.append({"type": "NO_REQUIREMENTS", "detail": "requirements.txt not found"})

    # Verify docker-compose doesn't use openclaw/core:latest
    compose = BASE_DIR / "docker-compose.yml"
    if compose.exists():
        content = compose.read_text()
        if "openclaw/core:latest" in content:
            findings.append({
                "type":   "UNTRUSTED_IMAGE",
                "detail": "docker-compose.yml uses openclaw/core:latest — build custom image via Dockerfile",
            })
        if "image: python:latest" in content or "image: python:3" in content:
            findings.append({
                "type":   "UNPINNED_PYTHON_IMAGE",
                "detail": "Python base image does not pin patch version",
            })

    # Verify .env is in .gitignore
    gitignore = BASE_DIR / ".gitignore"
    if gitignore.exists():
        gi_content = gitignore.read_text()
        if "config/.env" not in gi_content and ".env" not in gi_content:
            findings.append({"type": "ENV_NOT_GITIGNORED", "detail": ".env not in .gitignore!"})
    else:
        findings.append({"type": "NO_GITIGNORE", "detail": ".gitignore does not exist"})

    status = "FAIL" if any(f["type"] in ("UNTRUSTED_IMAGE","ENV_NOT_GITIGNORED") for f in findings) else \
             "WARN" if findings else "PASS"
    _print_result("V8 Supply chain", status, f"({len(findings)} issues)")
    return {"status": status, "findings": findings}


# ══════════════════════════════════════════════════════════════════════════════
# V9 — DOS GUARDIAN STATUS
# ══════════════════════════════════════════════════════════════════════════════

def scan_v9_dos_guardian() -> dict:
    """
    Verify DoS Guardian status:
    - System is not stuck in SURVIVAL/LOCKDOWN due to false positives
    - Circuit breakers are not permanently OPEN
    - Rate limit configuration is reasonable
    - Narrative freeze is not active excessively long
    """
    findings = []
    status   = "PASS"

    try:
        import redis as redis_lib
        rc = redis_lib.from_url(REDIS_URL, decode_responses=True)

        # 1. Verify system mode
        mode = rc.get("zcl:guardian:system_mode") or "NORMAL"
        mode_ts = int(rc.get("zcl:guardian:mode_ts") or 0)
        mode_reason = rc.get("zcl:guardian:mode_reason") or ""
        mode_duration_h = round((time.time() - mode_ts) / 3600, 1) if mode_ts else 0

        if mode == "LOCKDOWN":
            findings.append({
                "type":   "LOCKDOWN_ACTIVE",
                "detail": f"System under LOCKDOWN for {mode_duration_h}h — Reason: {mode_reason[:80]}",
                "severity": "CRITICAL",
            })
        elif mode == "SURVIVAL" and mode_duration_h > 2:
            findings.append({
                "type":   "SURVIVAL_TOO_LONG",
                "detail": f"SURVIVAL active for {mode_duration_h}h — Potential false positive. Check: python tools/dos_guardian.py --status",
                "severity": "HIGH",
            })
        elif mode == "CAUTION" and mode_duration_h > 6:
            findings.append({
                "type":   "CAUTION_EXTENDED",
                "detail": f"CAUTION active for {mode_duration_h}h — Review root cause",
                "severity": "MEDIUM",
            })

        # 2. Verify circuit breakers
        cb_keys = {
            "training": "zcl:guardian:circuit:train",
            "a03":      "zcl:guardian:circuit:a03",
            "chroma":   "zcl:guardian:circuit:chroma",
        }
        for cb_name, cb_key in cb_keys.items():
            raw = rc.get(cb_key)
            if raw:
                try:
                    data = json.loads(raw)
                    if data.get("state") == "OPEN":
                        opened_ts = data.get("opened_ts", 0)
                        open_duration_h = round((time.time() - opened_ts) / 3600, 1)
                        findings.append({
                            "type":   f"CIRCUIT_OPEN_{cb_name.upper()}",
                            "detail": f"Circuit {cb_name} OPEN for {open_duration_h}h — {data.get('last_fail_reason','')[:60]}",
                            "severity": "HIGH" if open_duration_h > 1 else "MEDIUM",
                        })
                except Exception:
                    pass

        # 3. Verify Narrative freeze
        freeze_raw = rc.get("zcl:guardian:narrative_freeze")
        if freeze_raw:
            try:
                freeze = json.loads(freeze_raw)
                expires = freeze.get("expires_ts", 0)
                if expires > time.time():
                    remaining_min = int((expires - time.time()) / 60)
                    findings.append({
                        "type":   "NARRATIVE_FREEZE_ACTIVE",
                        "detail": f"A03 Blindness Protocol active — {remaining_min}m remaining. Reason: {freeze.get('reason','')[:60]}",
                        "severity": "MEDIUM",
                    })
            except Exception:
                pass

        # 4. Verify recent DoS events in the last 1h
        try:
            events = rc.lrange("zcl:guardian:dos_events", 0, 49)
            recent_critical = 0
            cutoff = time.time() - 3600
            for ev_raw in events:
                try:
                    ev = json.loads(ev_raw)
                    if ev.get("ts", 0) >= cutoff and "FLOOD" in ev.get("type", ""):
                        recent_critical += 1
                except Exception:
                    pass
            if recent_critical >= 5:
                findings.append({
                    "type":   "ACTIVE_FLOOD_ATTEMPT",
                    "detail": f"{recent_critical} flood events in the last 1h — potential active attack",
                    "severity": "HIGH",
                })
        except Exception:
            pass

        # 5. Verify Redis saturation score
        sat_raw = rc.get("zcl:guardian:redis_sat")
        if sat_raw:
            sat = float(sat_raw)
            if sat >= 2000:
                findings.append({
                    "type":   "REDIS_SATURATION_DANGER",
                    "detail": f"Redis bus {sat:.0f} msg/min (limit 2000) — potential DoS P3",
                    "severity": "CRITICAL",
                })
            elif sat >= 500:
                findings.append({
                    "type":   "REDIS_SATURATION_WARN",
                    "detail": f"Redis bus {sat:.0f} msg/min (limit 500) — elevated",
                    "severity": "MEDIUM",
                })

        # Conclusions
        critical_f = [f for f in findings if f.get("severity") in ("CRITICAL", "HIGH")]
        medium_f   = [f for f in findings if f.get("severity") == "MEDIUM"]

        if critical_f:
            status = "FAIL"
        elif medium_f:
            status = "WARN"
        else:
            status = "PASS"

        detail = f"(mode={mode} | {len(findings)} issues | {len(critical_f)} critical)"

    except Exception as e:
        status = "WARN"
        detail = f"(Redis not connected: {e})"
        findings.append({"type": "REDIS_UNAVAILABLE", "detail": str(e)})

    _print_result("V9 DoS Guardian", status, detail)
    if findings:
        for f in findings[:3]:
            sev_color = R if f.get("severity") in ("CRITICAL","HIGH") else Y
            print(f"     {sev_color}→{E} [{f.get('severity','?')}] {f['type']}: {f['detail'][:70]}")

    return {"status": status, "mode": mode if 'mode' in locals() else "UNKNOWN",
            "findings": findings}

def run_full_scan(save_report: bool = True) -> dict:
    print(f"\n{W}{'='*60}{E}")
    print(f"{W}  ZERO-CUTLOSS SECURITY HARDENING — 9 VECTORS{E}")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{W}{'='*60}{E}\n")

    results = {}
    scanners = [
        ("v1_injection",     scan_v1_injection),
        ("v2_hidden_chars",  scan_v2_hidden_chars),
        ("v3_chromadb",      scan_v3_chromadb),
        ("v4_dpo_hmac",      scan_v4_dpo_hmac),
        ("v5_api_crossval",  scan_v5_api_crossvalidation),
        ("v6_network",       scan_v6_network_isolation),
        ("v7_drift",         scan_v7_drift_detection),
        ("v8_supply_chain",  scan_v8_supply_chain),
        ("v9_dos_guardian",  scan_v9_dos_guardian),
    ]

    for key, fn in scanners:
        try:
            results[key] = fn()
        except Exception as e:
            results[key] = {"status": "ERROR", "error": str(e)}
            _print_result(key.upper(), "ERROR", str(e)[:60])

    # Summary
    fail_count = sum(1 for v in results.values() if v.get("status") == "FAIL")
    warn_count = sum(1 for v in results.values() if v.get("status") == "WARN")
    pass_count = sum(1 for v in results.values() if v.get("status") == "PASS")

    overall = "DANGER" if fail_count > 0 else ("CAUTION" if warn_count > 0 else "SAFE")
    color   = R if overall == "DANGER" else (Y if overall == "CAUTION" else G)

    print(f"\n{W}{'─'*60}{E}")
    print(f"  {color}{W}OVERALL: {overall}{E}  |  "
          f"{G}PASS:{pass_count}{E}  {Y}WARN:{warn_count}{E}  {R}FAIL:{fail_count}{E}")

    # V7 special warning
    v7 = results.get("v7_drift", {})
    if v7.get("status") != "PASS":
        print(f"\n  {R}{W}[V7 DRIFT] Critical warning:{E} {v7.get('recommendation','')}")

    # V9 special warning
    v9 = results.get("v9_dos_guardian", {})
    if v9.get("status") == "FAIL":
        mode = v9.get("mode", "?")
        print(f"\n  {R}{W}[V9 DOS] System is in mode {mode}:{E} check dos_guardian.py --status")

    print(f"{W}{'='*60}{E}\n")

    report = {
        "timestamp_unix": int(time.time()),
        "timestamp_readable": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        "overall": overall,
        "summary": {"pass": pass_count, "warn": warn_count, "fail": fail_count},
        "vectors": results,
    }

    if save_report:
        ts   = int(time.time())
        path = SECURITY_DIR / f"hardening_report_{ts}.json"
        with open(path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"  Report saved: {path.name}")

        # Push to Redis
        try:
            import redis as redis_lib
            rc = redis_lib.from_url(REDIS_URL, decode_responses=True)
            rc.set("zcl:security:latest", json.dumps({
                "overall": overall, "fail": fail_count, "warn": warn_count,
                "v7_drift_score": v7.get("drift_score", 0),
                "v9_dos_mode":    v9.get("mode", "UNKNOWN"),
                "timestamp": ts,
            }))
        except Exception:
            pass

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Security Hardening Scanner — Zero-Cutloss")
    parser.add_argument("--full",  action="store_true", default=True)
    parser.add_argument("--v7",    action="store_true", help="Run only V7 drift detection")
    parser.add_argument("--v9",    action="store_true", help="Run only V9 DoS Guardian check")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.v7:
        print("\n=== V7 DRIFT DETECTION ONLY ===\n")
        result = scan_v7_drift_detection()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.v9:
        print("\n=== V9 DOS GUARDIAN ONLY ===\n")
        result = scan_v9_dos_guardian()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        run_full_scan(save_report=True)
