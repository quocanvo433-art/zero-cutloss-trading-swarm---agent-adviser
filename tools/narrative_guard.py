"""
🧬 DNA: v16.1
🏢 UNIT: COGNITIVE (A03) - Sentinel
🛠️ ROLE: Elite Narrative Sentinel (Guard)
📖 DESC: Defense layer detecting Elite narrative manipulation by analyzing Velocity, Semantic and Inversion (Narrative vs EMF).
🔗 CALLS: tools/dos_guardian.py
🛡️ INTEGRITY: Organic Ecosystem - Immutable

DESIGN ORIGINS:
  Inherits the AEO 4-layer technique from A12 (aeo_detective.py) but applies it
  to ALL narrative streams flowing into A03 — not just single URLs.

CORE ISSUE (GEO Poisoning — Liqing case, CCTV 3/2026):
  The Elite/Composite Man does NOT need to hack the system — they only need to create targeted flood content
  so that the AI learns the "default truth" about the market direction.
  
  Example: Before selling at the peak, Elite pumps 1000 articles claiming "BTC to 200k" -> AI models
  all predict bullish -> retail buys more -> Elite exits positions into the crowd.

ARCHITECTURE — 4 LAYERS (inherits A12 + adds Fear/Greed layer):

  Layer 1 — Velocity & Coordination (Information pump speed):
    Measures narrative speed of appearance compared to baseline.
    Concentrated within 24-72 hours = coordinated push.

  Layer 2 — Semantic Uniformity (Identical language structure):
    Elite content is often based on AI-generated templates —
    conclusion first, authority stacking, lacking opposition view.

  Layer 3 — Fear/Greed Inversion (Inverted Fear/Greed indicators):
    CORE INSIGHT: When Elite is PRE-POSITIONING (buying), they pump a
    "bearish/fear" narrative to make retail sell cheap -> Elite accumulates.
    When Elite is EXITING (selling), they pump a "bullish/greed" narrative to make retail buy high.
    -> Detected by comparing narrative direction with EMF signals (A10/A11).

  Layer 4 — EMF Cross-Validation (True Elite signals from A10/A11):
    Bearish narrative but Elite is accumulating = SELL TRAP.
    Bullish narrative but Elite is distributing = BUY TRAP.

OUTPUT:
  injection_risk_score: float 0.0-1.0
  elite_narrative_type: str  — FEAR_BAIT | GREED_BAIT | NEUTRAL | ORGANIC
  block_recommended: bool
  action: str — PASS | WARN | BLOCK
  summary: str
"""

import os
import json
import time
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
from collections import deque

try:
    from tools.imperial_state import matrix
except ImportError:
    from imperial_state import matrix
    
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../config/.env'))

TELEGRAM_BOT     = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

BASE_DIR = Path(__file__).parent.parent
LOG_FILE = BASE_DIR / "logs" / "narrative_guard.log"
LOG_FILE.parent.mkdir(exist_ok=True)

log = logging.getLogger("NARRATIVE_GUARD")
if not log.handlers:
    log.setLevel(logging.INFO)
    log.addHandler(logging.FileHandler(str(LOG_FILE)))
    log.addHandler(logging.StreamHandler())

# ── Redis keys (via Matrix SYSTEM namespace) ──────────────────────────────────
NG_HISTORY_KEY     = "ng:narrative_history"     # List: A03 output 8 cycles
NG_FEAR_GREED_KEY  = "ng:fear_greed_log"        # List: fear/greed series
NG_SENTINEL_KEY    = "ng:sentinel_status"       # Hash: guard status
NG_BLOCKED_KEY     = "ng:blocked_log"           # List: blocked log
NG_SENTINEL_OUT    = "ng:sentinel_narrative"    # String: latest output

# ── Thresholds ────────────────────────────────────────────────────────────────
VELOCITY_WINDOW_CYCLES    = 8      # Number of A03 cycles to measure pressure
VELOCITY_ALERT_THRESHOLD  = 0.75   # > 75% same direction → elevated
VELOCITY_MAX_THRESHOLD    = 0.90   # > 90% → critical
SEMANTIC_SCORE_THRESHOLD  = 0.60   # Semantic score > 0.60 → suspicious
INVERSION_THRESHOLD       = 0.65   # Narrative opposite to EMF > threshold → BAIT
BLOCK_SCORE_THRESHOLD     = 0.70   # Composite > 0.70 → block recommended

def _map_sentiment(val):
    if not val: return "NEUTRAL"
    val = str(val).upper()
    mapping = {
        "TRUNG_TINH": "NEUTRAL",
        "FOMO_CUC_DO": "FOMO_EXTREME",
        "THAM_LAM_CUC_DO": "GREED_EXTREME",
        "SO_HAI_CUC_DO": "FEAR_EXTREME",
        "BAN_THAO_HOANG_LOAN": "PANIC_SELL",
        "CHAN_NAN_TUI_CUC": "EXTREME_DESPAIR",
        "NEUTRAL": "NEUTRAL",
        "FOMO_EXTREME": "FOMO_EXTREME",
        "GREED_EXTREME": "GREED_EXTREME",
        "FEAR_EXTREME": "FEAR_EXTREME",
        "PANIC_SELL": "PANIC_SELL",
        "EXTREME_DESPAIR": "EXTREME_DESPAIR"
    }
    return mapping.get(val, val)

def _tele_alert(msg: str):
    """Send Telegram alert to Commander."""
    if not (TELEGRAM_BOT and TELEGRAM_CHAT_ID):
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — VELOCITY & COORDINATION
# "Measure narrative pump speed — Elite flood before action"
# ══════════════════════════════════════════════════════════════════════════════

def analyze_velocity(a03_output: dict) -> dict:
    """
    Analyze velocity and uniformity of narrative within VELOCITY_WINDOW_CYCLES cycles.
    
    Logic:
    - Composite Man does NOT change narratives constantly — they lock in 1 direction for 3-7 days
    - Organic market: narrative is mixed, changes direction frequently
    - Manipulated: narrative stays in the same direction for too long, especially when technical indicators contradict
    """
    rc = matrix._client
    
    # Update history
    entry = {
        "ts":          int(time.time()),
        "trend":       _map_sentiment(a03_output.get("crowd_trend") or a03_output.get("xu_huong_dam_dong") or "NEUTRAL"),
        "mm_score":    (a03_output.get("mm_fingerprint") or {}).get("score") or 0,
        "congruence":  (a03_output.get("financial_narrative") or a03_output.get("narrative_tai_chinh") or {}).get("media_congruence_pct") or (a03_output.get("narrative_tai_chinh") or {}).get("do_dong_thuan_media_pct") or 0,
        "sentiment":   _map_sentiment((a03_output.get("financial_narrative") or a03_output.get("narrative_tai_chinh") or {}).get("media_sentiment") or (a03_output.get("narrative_tai_chinh") or {}).get("sentiment_media") or "NEUTRAL"),
        "elite_active": (a03_output.get("elite_signal") or {}).get("active") or False,
    }
    
    try:
        matrix.lpush("SYSTEM", NG_HISTORY_KEY, entry, max_len=VELOCITY_WINDOW_CYCLES)
    except Exception:
        pass
    
    # Read history
    entries = []
    try:
        raw = matrix.lrange("SYSTEM", NG_HISTORY_KEY, 0, VELOCITY_WINDOW_CYCLES - 1)
        for r in raw:
            if isinstance(r, dict):
                entries.append(r)
            elif isinstance(r, str):
                try:
                    entries.append(json.loads(r))
                except Exception:
                    pass
    except Exception:
        pass
    
    if len(entries) < 3:
        return {"score": 0.0, "alert_level": "INSUFFICIENT_DATA",
                "dominant_direction": "UNKNOWN", "consecutive": 0,
                "detail": f"Requires >=3 cycles ({len(entries)} current)"}
    
    # Classify each cycle
    directions = []
    for e in entries:
        xu = e.get("trend") or e.get("xu_huong") or "NEUTRAL"
        sent = e.get("sentiment") or "NEUTRAL"
        if xu in ("FOMO_EXTREME", "GREED_EXTREME") or "BULLISH" in sent:
            directions.append("BULLISH")
        elif xu in ("FEAR_EXTREME", "PANIC_SELL", "EXTREME_DESPAIR") or "BEARISH" in sent:
            directions.append("BEARISH")
        else:
            directions.append("NEUTRAL")
    
    n = len(directions)
    bull_rate = directions.count("BULLISH") / n
    bear_rate = directions.count("BEARISH") / n
    dominant_rate = max(bull_rate, bear_rate)
    dominant_dir = ("BULLISH" if bull_rate > bear_rate 
                    else "BEARISH" if bear_rate > bull_rate else "MIXED")
    
    # Count consecutive
    consecutive = 0
    for d in directions:
        if d == dominant_dir:
            consecutive += 1
        else:
            break
    
    # Composite score
    score = dominant_rate
    elite_count = sum(1 for e in entries if e.get("elite_active"))
    high_mm = sum(1 for e in entries if (e.get("mm_score") or 0) > 70)
    if elite_count >= 2:
        score = min(1.0, score + 0.1)
    if high_mm >= 3:
        score = min(1.0, score + 0.15)
    
    # Alert level
    if score >= VELOCITY_MAX_THRESHOLD:
        alert = "CRITICAL"
    elif score >= VELOCITY_ALERT_THRESHOLD:
        alert = "HIGH"
    elif score >= 0.60:
        alert = "ELEVATED"
    else:
        alert = "NORMAL"
    
    return {
        "score":              round(score, 3),
        "alert_level":        alert,
        "dominant_direction": dominant_dir,
        "consecutive":        consecutive,
        "bullish_rate":       round(bull_rate, 3),
        "bearish_rate":       round(bear_rate, 3),
        "cycles_analyzed":    n,
        "elite_active_count": elite_count,
        "detail": f"{dominant_rate:.0%} cycles {dominant_dir}, {consecutive} consecutive",
    }


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — SEMANTIC UNIFORMITY
# "Detect AI-generated content template — Elite uses GPT to pump content"
# ══════════════════════════════════════════════════════════════════════════════

# Patterns characteristic of GEO-poisoned content
_GEO_PATTERNS = [
    # Conclusion comes before evidence
    r"(clearly|obviously|evidently).{0,50}(because|since)",
    # Authority stacking without specific links
    r"(experts|analysts).{0,30}(agree|confirm).{0,30}(that)",
    # Extreme claims without sources
    r"(all|every).{0,20}(expert|analyst).{0,30}(believe|expect)",
    # AI-optimized header patterns
    r"(what is|how to|why does).{0,50}\?",
    # Dismissal of opposition views
    r"(while some|despite concerns).{0,50}(but|however).{0,30}(in fact|reality)",
    # FOMO/FUD injection
    r"(last chance|now or never|miss out)",
    # Crypto-specific pump patterns
    r"(moonshot|100x|parabolic|only goes up)",
    # Fear patterns
    r"(collapse|crash imminent|to zero|end of)",
]
_COMPILED_GEO = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _GEO_PATTERNS]


def analyze_semantic_uniformity(a03_output: dict) -> dict:
    """
    Analyze semantic structure of raw content fetched by A03.
    Inherits Layer 2 of A12 but applies it to streaming narrative instead of a single URL.
    """
    raw_snippets = []
    
    # Collect from multiple fields that may contain content
    for field in ["raw_news", "tin_tuc_raw", "social_snippets", "rss_entries", "raw_content"]:
        data = a03_output.get(field, [])
        if isinstance(data, list):
            raw_snippets.extend([str(s)[:500] for s in data[:10]])
        elif isinstance(data, str):
            raw_snippets.append(data[:2000])
    
    # Fallback: search in financial_narrative
    if not raw_snippets:
        nt = a03_output.get("financial_narrative") or a03_output.get("narrative_tai_chinh") or {}
        for v in nt.values():
            if isinstance(v, str):
                raw_snippets.append(v[:500])
    
    if not raw_snippets:
        return {"score": 0.0, "geo_hits": 0, "patterns_found": [],
                "detail": "No raw content to analyze"}
    
    combined = " ".join(raw_snippets)
    
    # Detect GEO patterns
    patterns_found = []
    for i, pat in enumerate(_COMPILED_GEO):
        match = pat.search(combined)
        if match:
            patterns_found.append({
                "pattern_id": i,
                "snippet": combined[max(0, match.start()-30):match.end()+30][:100],
            })
    
    geo_hit_count = len(patterns_found)
    
    # Score based on pattern hit ratio
    score = min(1.0, geo_hit_count / max(1, len(_GEO_PATTERNS) * 0.4))
    
    # Boost if A03 detected high narrative coordination
    dong_thuan = (a03_output.get("financial_narrative") or a03_output.get("narrative_tai_chinh") or {}).get("media_congruence_pct") or (a03_output.get("narrative_tai_chinh") or {}).get("do_dong_thuan_media_pct") or 0
    if dong_thuan > 70:
        score = min(1.0, score + 0.2)
    
    # Detect AI-generated content markers
    ai_generated_markers = [
        "in conclusion", "to summarize", "in summary", "overall",
        "it is worth noting", "it should be mentioned",
        "concluding", "summarized"
    ]
    ai_marker_count = sum(1 for m in ai_generated_markers if m.lower() in combined.lower())
    if ai_marker_count >= 3:
        score = min(1.0, score + 0.15)
    
    return {
        "score":           round(score, 3),
        "geo_hits":        geo_hit_count,
        "patterns_found":  patterns_found[:5],  # Top 5
        "ai_markers":      ai_marker_count,
        "media_congruence": dong_thuan,
        "detail": (
            f"{geo_hit_count}/{len(_GEO_PATTERNS)} GEO patterns, "
            f"{ai_marker_count} AI markers, {dong_thuan:.0f}% media congruence"
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — FEAR/GREED INVERSION
# "Composite Man pumps narrative opposite to their positioning"
# ══════════════════════════════════════════════════════════════════════════════

def analyze_fear_greed_inversion(a03_output: dict) -> dict:
    """
    CORE INSIGHT — Detect Elite leading by pumping inverted sentiment:
    
    FEAR_BAIT (Sell Trap):
      - Elite is accumulating (buying)
      - But narrative media is fear, collapse, pessimism
      - -> Retail panics and sells -> Elite buys cheap
      - Detect: Media bearish + EMF accumulate + low fear/greed index

    GREED_BAIT (Buy Trap):  
      - Elite is distributing (selling)
      - But narrative media is greed, moonshot, euphoria
      - -> Retail buys enthusiastically -> Elite sells high
      - Detect: Media bullish + EMF distribute + high fear/greed index
      
    ORGANIC:
      - Narrative and EMF in the same direction -> organic market
    """
    rc = matrix._client
    
    # Read narrative trend from A03
    xu_huong = _map_sentiment(a03_output.get("crowd_trend") or a03_output.get("xu_huong_dam_dong") or "NEUTRAL")
    mm_score  = (a03_output.get("mm_fingerprint") or {}).get("score") or 0
    dong_thuan = (a03_output.get("financial_narrative") or a03_output.get("narrative_tai_chinh") or {}).get("media_congruence_pct") or (a03_output.get("narrative_tai_chinh") or {}).get("do_dong_thuan_media_pct") or 0
    fear_greed_index = a03_output.get("fear_greed_index") or a03_output.get("chi_so_tham_lam") or a03_output.get("fear_greed")
    if fear_greed_index is None:
        fear_greed_index = 50
    
    # Classify narrative direction
    narrative_bullish = xu_huong in ("FOMO_EXTREME", "GREED_EXTREME") or dong_thuan > 65
    narrative_bearish = xu_huong in ("FEAR_EXTREME", "PANIC_SELL", "EXTREME_DESPAIR") or dong_thuan < 35
    
    # Read EMF intent from A11
    emf_accumulate = False
    emf_distribute = False
    emf_confidence = 0.0
    emf_detail = ""
    
    if rc:
        try:
            # Read from emf:intent:report
            msgs = rc.xrevrange("zcl:emf:intent:report", count=1)
            if msgs:
                _, fields = msgs[0]
                payload = fields.get(b"payload") or fields.get("payload", "{}")
                if isinstance(payload, bytes):
                    payload = payload.decode('utf-8')
                report = json.loads(payload)
                scenario_type = (report.get("scenario") or {}).get("type") or "WATCH"
                emf_confidence = (report.get("scenario") or {}).get("confidence") or 0.0
                intent_label = (report.get("intent") or {}).get("label") or "NEUTRAL"
                
                if scenario_type in ("BOOM_INCOMING",) or "ACCUMULATE" in intent_label:
                    emf_accumulate = True
                    emf_detail = f"A11: {scenario_type} (conf={emf_confidence:.2f})"
                elif scenario_type in ("CRISIS_INCOMING", "EXIT_POINT") or "DISTRIBUTE" in intent_label:
                    emf_distribute = True
                    emf_detail = f"A11: {scenario_type} (conf={emf_confidence:.2f})"
        except Exception as e:
            log.debug(f"Could not read emf:intent:report: {e}")
    
    # Detect inversion
    elite_narrative_type = "ORGANIC"
    inversion_score = 0.0
    inversion_detail = ""
    
    # FEAR_BAIT: Bearish narrative + Elite actually accumulating
    if narrative_bearish and emf_accumulate and emf_confidence > 0.5:
        inversion_score = 0.7 + (emf_confidence - 0.5) * 0.6  # 0.7 → 1.0
        elite_narrative_type = "FEAR_BAIT"
        inversion_detail = (
            f"⚠️ FEAR_BAIT: Media bearish ({xu_huong}) "
            f"but Elite is accumulating ({emf_detail}). "
            f"Fear/Greed: {fear_greed_index}/100. "
            f"MM Score: {mm_score}/100. Composite Man might be buying cheap from retail."
        )
    
    # GREED_BAIT: Bullish narrative + Elite actually distributing
    elif narrative_bullish and emf_distribute and emf_confidence > 0.5:
        inversion_score = 0.7 + (emf_confidence - 0.5) * 0.6
        elite_narrative_type = "GREED_BAIT"
        inversion_detail = (
            f"⚠️ GREED_BAIT: Media euphoric ({xu_huong}) "
            f"but Elite is distributing ({emf_detail}). "
            f"Fear/Greed: {fear_greed_index}/100. "
            f"MM Score: {mm_score}/100. Composite Man might be selling high to retail."
        )
    
    # Isolated high MM Score
    elif mm_score >= 75 and dong_thuan >= 70:
        inversion_score = 0.45  # Suspicious but unconfirmed
        elite_narrative_type = "SUSPICIOUS"
        inversion_detail = (
            f"MM Score {mm_score}/100 + media congruence {dong_thuan:.0f}% — "
            f"possible Elite coordination, requires further EMF confirmation."
        )
    
    # Extreme Fear/Greed combined with high MM score
    elif mm_score >= 60 and (fear_greed_index <= 20 or fear_greed_index >= 80):
        extreme_type = "EXTREME_FEAR" if fear_greed_index <= 20 else "EXTREME_GREED"
        inversion_score = 0.35
        elite_narrative_type = "SUSPICIOUS"
        inversion_detail = (
            f"Sentiment index {extreme_type} ({fear_greed_index}/100) + "
            f"MM Score {mm_score}/100 — precursor pattern for sentiment trap."
        )
    
    inversion_score = round(min(1.0, inversion_score), 3)
    
    return {
        "score":               inversion_score,
        "elite_narrative_type": elite_narrative_type,
        "narrative_direction": "BEARISH" if narrative_bearish else "BULLISH" if narrative_bullish else "NEUTRAL",
        "emf_accumulate":     emf_accumulate,
        "emf_distribute":     emf_distribute,
        "fear_greed_index":   fear_greed_index,
        "mm_score":           mm_score,
        "emf_confidence":     emf_confidence,
        "detail":             inversion_detail or "No inversion detected — narrative and EMF aligned.",
        "inversion_detected": inversion_score >= INVERSION_THRESHOLD,
    }


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — EMF FINANCIAL CROSS-VALIDATION
# "Fully inherited from A12 Layer 4"
# ══════════════════════════════════════════════════════════════════════════════

def cross_validate_financial(a03_output: dict) -> dict:
    """
    Compare A03 narrative with signals from A10/A11.
    Narrative A03 + EMF A10/A11 in same direction = real market.
    Narrative A03 contradicting EMF = financial manipulation.
    """
    rc = matrix._client
    if not rc:
        return {"score": 0.0, "financial_manipulation": False, "detail": "Redis unavailable"}
    
    manipulations = []
    score = 0.0
    
    try:
        # A10 scored signals
        try:
            msgs = rc.xrevrange("zcl:emf:signals:scored", count=1)
            if msgs:
                fields = msgs[0][1]
                payload = fields.get(b"payload") or fields.get("payload")
                if isinstance(payload, bytes):
                    payload = payload.decode('utf-8')
                scored_raw = payload
            else:
                scored_raw = None
        except Exception:
            scored_raw = None
        if scored_raw:
            scored = json.loads(scored_raw)
            alert_level = scored.get("alert_level") or "LOW"
            if alert_level in ("HIGH", "CRITICAL"):
                a03_xu = _map_sentiment(a03_output.get("crowd_trend") or a03_output.get("xu_huong_dam_dong") or "NEUTRAL")
                emf_direction = scored.get("dominant_direction") or "NEUTRAL"
                
                # Contradiction: A03 bullish but EMF bearish (Elite trap)
                if "FOMO" in a03_xu and emf_direction in ("DISTRIBUTE", "BEARISH"):
                    manipulations.append(f"A10 {alert_level}: EMF {emf_direction} vs A03 bullish narrative")
                    score += 0.4
                elif "FEAR" in a03_xu and emf_direction in ("ACCUMULATE", "BULLISH"):
                    manipulations.append(f"A10 {alert_level}: EMF {emf_direction} vs A03 bearish narrative")
                    score += 0.4
    except Exception:
        pass
    
    # Cross-validate with A12 AEO reports
    try:
        aeo_stream = rc.xrevrange("zcl:aeo:reports", count=3)
        for _, fields in aeo_stream:
            payload = fields.get(b"payload") or fields.get("payload", "{}")
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            report = json.loads(payload)
            verdict = (report.get("verdict") or {}).get("label") or ""
            if verdict in ("MANUFACTURED", "HIGH_AEO"):
                score += 0.3
                topic = (report.get("target") or {}).get("topic") or "?"
                manipulations.append(f"A12 confirmed {verdict} AEO on topic: {topic}")
                break
    except Exception:
        pass
    
    return {
        "score":                  round(min(1.0, score), 3),
        "financial_manipulation": score >= 0.4,
        "manipulation_signals":   manipulations,
        "detail": (
            " | ".join(manipulations) if manipulations 
            else "No financial narrative manipulation detected"
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# COMPOSITE SCORE & VERDICT
# ══════════════════════════════════════════════════════════════════════════════

LAYER_WEIGHTS = {
    "velocity":    0.25,
    "semantic":    0.20,
    "inversion":   0.35,   # Core insight — Elite pumps narrative opposite to EMF
    "financial":   0.20,
}


def full_guard_check(a03_output: dict) -> dict:
    """
    MAIN FUNCTION — A03 calls this function before publishing zcl:sentiment:latest.
    
    Args:
        a03_output: dict output from A03 (social_crawler.py) after 1 scan cycle
    
    Returns:
        {
            "action":                str,   # "PASS" | "WARN" | "BLOCK"
            "injection_risk_score":  float, # 0.0 - 1.0
            "elite_narrative_type":  str,   # "FEAR_BAIT" | "GREED_BAIT" | "SUSPICIOUS" | "ORGANIC"
            "block_recommended":     bool,
            "layer_breakdown":       dict,
            "summary":               str,
            "safe_output":           dict,  # A03 output adjusted if warned/blocked
        }
    """
    # ── Run 4 layers in parallel ─────────────────────────────
    try:
        l1 = analyze_velocity(a03_output)
    except Exception as e:
        l1 = {"score": 0.0, "alert_level": "ERROR", "detail": str(e)}
    
    try:
        l2 = analyze_semantic_uniformity(a03_output)
    except Exception as e:
        l2 = {"score": 0.0, "geo_hits": 0, "detail": str(e)}
    
    try:
        l3 = analyze_fear_greed_inversion(a03_output)
    except Exception as e:
        l3 = {"score": 0.0, "elite_narrative_type": "UNKNOWN", "detail": str(e)}
    
    try:
        l4 = cross_validate_financial(a03_output)
    except Exception as e:
        l4 = {"score": 0.0, "financial_manipulation": False, "detail": str(e)}
    
    # ── Composite score ─────────────────────────────────────────────────────
    composite = (
        l1.get("score", 0) * LAYER_WEIGHTS["velocity"] +
        l2.get("score", 0) * LAYER_WEIGHTS["semantic"] +
        l3.get("score", 0) * LAYER_WEIGHTS["inversion"] +
        l4.get("score", 0) * LAYER_WEIGHTS["financial"]
    )
    composite = round(min(1.0, composite), 3)
    
    # ── Verdict ─────────────────────────────────────────────────────────────
    elite_type = l3.get("elite_narrative_type", "ORGANIC")
    
    if composite >= BLOCK_SCORE_THRESHOLD or l3.get("inversion_detected"):
        action = "BLOCK"
        block_recommended = True
    elif composite >= 0.45 or l1.get("alert_level") in ("HIGH", "CRITICAL"):
        action = "WARN"
        block_recommended = False
    else:
        action = "PASS"
        block_recommended = False
    
    # ── Build summary ────────────────────────────────────────────────────────
    summary = _build_summary(action, elite_type, composite, l1, l2, l3, l4)
    
    # ── Publish to Redis ─────────────────────────────────────────────────────
    result = {
        "action":               action,
        "injection_risk_score": composite,
        "elite_narrative_type": elite_type,
        "block_recommended":    block_recommended,
        "layer_breakdown": {
            "velocity":  l1,
            "semantic":  l2,
            "inversion": l3,
            "financial": l4,
        },
        "summary":   summary,
        "timestamp": int(time.time()),
    }
    
    _publish_sentinel_result(result, a03_output)
    
    # Alert Commander if block/critical
    if action == "BLOCK":
        _tele_alert(
            f"🔴 *Narrative Guard BLOCK*\n"
            f"Type: `{elite_type}`\n"
            f"Score: `{composite:.0%}`\n"
            f"L3 Inversion: {l3.get('detail', '')[:100]}\n"
            f"→ A03 output blocked, not publishing to zcl:sentiment:latest"
        )
    elif action == "WARN" and l3.get("elite_narrative_type") in ("FEAR_BAIT", "GREED_BAIT"):
        _tele_alert(
            f"⚠️ *Narrative Guard WARN*\n"
            f"Type: `{elite_type}` | Score: `{composite:.0%}`\n"
            f"{l3.get('detail', '')[:120]}"
        )
    
    # Safe output: if BLOCK, return output with annotations
    safe_output = dict(a03_output)
    if action == "BLOCK":
        safe_output["_guard_action"] = "BLOCKED"
        safe_output["_guard_elite_type"] = elite_type
        safe_output["_guard_score"] = composite
        safe_output["_guard_summary"] = summary
        # Override trend to NEUTRAL to avoid downstream interference
        safe_output["crowd_trend"] = "NEUTRAL"
        if "xu_huong_dam_dong" in safe_output:
            safe_output["xu_huong_dam_dong"] = "TRUNG_TINH"
        
        financial_key = "financial_narrative" if "financial_narrative" in safe_output else "narrative_tai_chinh"
        safe_output[financial_key] = {
            **safe_output.get(financial_key, {}),
            "media_congruence_pct": 50,  # Neutral
            "do_dong_thuan_media_pct": 50,
            "_guard_override": True,
        }
    elif action == "WARN":
        safe_output["_guard_action"] = "WARNED"
        safe_output["_guard_elite_type"] = elite_type
        safe_output["_guard_score"] = composite
        safe_output["_guard_summary"] = summary
    else:
        safe_output["_guard_action"] = "PASS"
        safe_output["_guard_score"] = composite
    
    result["safe_output"] = safe_output
    
    log.info(
        f"[SENTINEL] {action} | type={elite_type} | score={composite:.3f} | "
        f"velocity={l1.get('score', 0):.2f} semantic={l2.get('score', 0):.2f} "
        f"inversion={l3.get('score', 0):.2f} financial={l4.get('score', 0):.2f}"
    )
    
    return result


def _build_summary(action: str, elite_type: str, composite: float,
                   l1: dict, l2: dict, l3: dict, l4: dict) -> str:
    parts = [f"[SENTINEL {action}] Score={composite:.0%} | Type={elite_type}"]
    
    if l1.get("alert_level") in ("HIGH", "CRITICAL"):
        parts.append(f"Velocity: {l1['consecutive']} consecutive cycles {l1['dominant_direction']}")
    
    if l2.get("geo_hits", 0) >= 2:
        parts.append(f"GEO: {l2['geo_hits']} patterns detected, {l2.get('ai_markers', 0)} AI markers")
    
    if l3.get("inversion_detected"):
        parts.append(f"INVERSION: {l3['detail'][:100]}")
    
    if l4.get("financial_manipulation"):
        parts.append(f"FINANCIAL: {l4['detail'][:80]}")
    
    return " | ".join(parts)


def _publish_sentinel_result(result: dict, original_a03: dict):
    """Publish sentinel result to Matrix for A09 audit."""
    try:
        publish_data = {
            "action":               result["action"],
            "injection_risk_score": result["injection_risk_score"],
            "elite_narrative_type": result["elite_narrative_type"],
            "timestamp":            result["timestamp"],
            "summary":              result["summary"][:200],
        }
        matrix.set("SYSTEM", NG_SENTINEL_OUT, publish_data, ttl=1800)  # 30min TTL
        
        if result["action"] == "BLOCK":
            matrix.lpush("SYSTEM", NG_BLOCKED_KEY, {
                **publish_data,
                "original_trend": original_a03.get("crowd_trend") or original_a03.get("xu_huong_dam_dong", "?"),
                "original_mm_score": original_a03.get("mm_fingerprint", {}).get("score", 0),
            }, max_len=100)
    except Exception as e:
        log.warning(f"Publish sentinel result error: {e}")


if __name__ == "__main__":
    """Test standalone — pass A03 JSON via stdin."""
    import sys
    print("Narrative Guard v2 — Elite Narrative Sentinel")
    print("Use: cat a03_output.json | python narrative_guard.py")
    
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        try:
            test_output = json.loads(raw)
        except Exception as e:
            test_output = {"crowd_trend": "FOMO_EXTREME",
                           "mm_fingerprint": {"score": 80},
                           "financial_narrative": {"media_congruence_pct": 85}}
        
        result = full_guard_check(test_output)
        print(json.dumps({
            "action":               result["action"],
            "elite_narrative_type": result["elite_narrative_type"],
            "injection_risk_score": result["injection_risk_score"],
            "summary":              result["summary"],
        }, ensure_ascii=False, indent=2))
