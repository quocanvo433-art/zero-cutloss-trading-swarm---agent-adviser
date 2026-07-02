"""
🧬 DNA: v16.6 (Sovereign Purity) [DNA Header]
🏢 UNIT: A11
🛠️ ROLE: PARADOX_ALGORITHMS
📖 DESC: Core Algorithms PDI, TPT, CACM

PARADOX DIVERGENCE INDEX (PDI) -ALGO

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Measures the vector distance between "Money Flow Truth" (A10) and "Media Narrative" (A12).

Formula:
  PDI = |V_money - V_narrative| × Temporal_Weight × AEO_Amplifier

Where:
  V_money     = composite_score from A10 signals    (range: -100 to +100)
  V_narrative = sentiment_score from A12/A03         (range: -100 to +100)  
  Temporal_Weight = decay function based on the duration of contradiction
  AEO_Amplifier   = 1.0 if organic, 1.5-2.0 if A12 detects manipulation

Classification:
  PDI < 30:   ALIGNED        (Money flow and narrative in the same direction -> True trend)
  PDI 30-60:  MILD_DIVERGE   (Divergence exists -> Monitor)
  PDI 60-120: HIGH_DIVERGE   (Clear contradiction -> Warning)
  PDI > 120:  EXTREME_PARADOX (Extreme paradox -> TRAP IS BEING SET)
"""

import math
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List


def compute_pdi(
    a10_signals: list,
    a12_aeo_data: dict,
    a03_sentiment: dict,
    historical_pdi: list = None  # PDI values from N cycles ago
) -> dict:
    """
    Computes the Paradox Divergence Index between real money flow (A10)
    and information flow (A12 + A03).
    
    Returns:
        dict with keys: pdi_score, pdi_label, v_money, v_narrative,
                       temporal_weight, aeo_amplifier, paradox_direction,
                       traceback_hypothesis
    """
    consecutive_diverge = 0
    # ═══ STEP 1: Money Flow Vector (V_money) ═══
    # Convert composite_score from analyze_intent to normalized vector
    acc_weight = sum(
        _magnitude_to_float(s.get("magnitude", "low")) 
        for s in (a10_signals or []) 
        if s.get("elite_intent_raw") == "accumulate"
    )
    dis_weight = sum(
        _magnitude_to_float(s.get("magnitude", "low")) 
        for s in (a10_signals or []) 
        if s.get("elite_intent_raw") == "distribute"
    )
    
    total_weight = acc_weight + dis_weight
    if total_weight == 0:
        v_money = 0.0
    else:
        # Range: -100 (full distribute) to +100 (full accumulate)
        v_money = ((acc_weight - dis_weight) / total_weight) * 100
    
    # ═══ STEP 2: Narrative Vector (V_narrative) ═══
    # Aggregate from A03 (crowd sentiment) + A12 (AEO verdict)
    
    # A03 component: Fear & Greed -> normalize to -100..+100
    fear_greed = 50
    if a03_sentiment and isinstance(a03_sentiment, dict):
        if "algo_core" in a03_sentiment:
            fomo_idx = float(a03_sentiment.get("algo_core", {}).get("fomo_index", 0.0))
            fear_greed = int((fomo_idx * 50) + 50)
        else:
            ptcx = a03_sentiment.get("sentiment_analysis")
            if isinstance(ptcx, dict):
                fear_greed = ptcx.get("composite_score", 50)
    if fear_greed is None or fear_greed == "?":
        fear_greed = 50
    v_a03 = (fear_greed - 50) * 2  # 0 to -100, 50 to 0, 100 to +100
    
    # A12 component: AEO score + verdict direction
    aeo_score = 0
    aeo_label = "ORGANIC"
    payload = ""
    if a12_aeo_data:
        aeo_score = a12_aeo_data.get("verdict", {}).get("aeo_score", 0)
        aeo_label = a12_aeo_data.get("verdict", {}).get("label", "ORGANIC")
        payload = a12_aeo_data.get("verdict", {}).get("payload_hypothesis", "")
        
    # Narrative direction from A12 (bullish/bearish payload)
    narrative_direction = _detect_narrative_direction(payload)
    
    # V_narrative = weighted average
    # A03 represents real crowd, A12 represents pushed narrative
    v_narrative = v_a03 * 0.4 + (narrative_direction * 100) * 0.6
    
    # ═══ STEP 3: AEO Amplifier ═══
    # If A12 detects manipulated narrative -> amplify paradox level
    if aeo_label in ("MANUFACTURED", "HIGH_AEO"):
        aeo_amplifier = 1.5 + min(aeo_score / 200, 0.5)  # Max 2.0
    elif aeo_label == "LOW_AEO":
        aeo_amplifier = 1.2
    else:
        aeo_amplifier = 1.0
    
    # ═══ STEP 4: Temporal Weight ═══
    # Paradox lasts longer -> more dangerous (Elite is patiently accumulating/distributing)
    temporal_weight = 1.0
    if historical_pdi:
        # Count consecutive cycles with PDI > 30 (persistent divergence)
        for prev_pdi in reversed(historical_pdi):
            if prev_pdi > 30:
                consecutive_diverge += 1
            else:
                break
        # Logarithmic scaling: 1 cycle -> 1.3, 3 cycles -> 1.6, 7 cycles -> 1.9
        temporal_weight = 1.0 + math.log2(1 + consecutive_diverge) * 0.3
        temporal_weight = min(temporal_weight, 2.5)  # Cap
    
    # ═══ STEP 5: Calculate PDI ═══
    raw_divergence = abs(v_money - v_narrative)
    pdi_score = raw_divergence * temporal_weight * aeo_amplifier
    
    # ═══ STEP 6: Classification ═══
    if pdi_score < 30:
        pdi_label = "ALIGNED"
    elif pdi_score < 60:
        pdi_label = "MILD_DIVERGE"
    elif pdi_score < 120:
        pdi_label = "HIGH_DIVERGE"
    else:
        pdi_label = "EXTREME_PARADOX"
    
    # ═══ STEP 7: Determine Paradox Direction ═══
    if v_money > 20 and v_narrative < -20:
        paradox_direction = "STEALTH_ACCUMULATE"
        traceback = (
            f"Elite accumulating quietly (V_money=+{v_money:.0f}) "
            f"while narrative is bearish (V_narrative={v_narrative:.0f}). "
            f"AEO={aeo_label}: {'Fear narrative MANUFACTURED' if aeo_amplifier > 1.2 else 'Organic narrative'}. "
            f"Duration: {consecutive_diverge} cycles."
        )
    elif v_money < -20 and v_narrative > 20:
        paradox_direction = "STEALTH_DISTRIBUTE"
        traceback = (
            f"Elite distributing (V_money={v_money:.0f}) "
            f"while narrative is bullish (V_narrative=+{v_narrative:.0f}). "
            f"AEO={aeo_label}: {'FOMO narrative MANUFACTURED' if aeo_amplifier > 1.2 else 'Organic narrative'}. "
            f"Duration: {consecutive_diverge} cycles."
        )
    elif abs(v_money) < 15 and abs(v_narrative) > 40:
        paradox_direction = "NARRATIVE_NOISE"
        traceback = (
            f"Elite money flow quiet (V_money={v_money:.0f}) "
            f"but narrative is very noisy (V_narrative={v_narrative:.0f}). "
            f"Could be noise or Elite is waiting in the shadows."
        )
    else:
        paradox_direction = "NONE"
        traceback = "No clear paradox detected."
    
    return {
        "pdi_score": round(pdi_score, 2),
        "pdi_label": pdi_label,
        "v_money": round(v_money, 2),
        "v_narrative": round(v_narrative, 2),
        "temporal_weight": round(temporal_weight, 3),
        "aeo_amplifier": round(aeo_amplifier, 3),
        "paradox_direction": paradox_direction,
        "traceback_hypothesis": traceback,
        "raw_divergence": round(raw_divergence, 2),
        "historical_streak": consecutive_diverge,
    }


def _magnitude_to_float(mag: str) -> float:
    mag_val = str(mag).lower()
    mapping = {"low": 0.25, "medium": 0.50, "high": 0.75, "extreme": 1.0, "critical": 1.0}
    if mag_val not in mapping:
        # In the Zero-Cutloss system, default unknown severity = medium to avoid missing signals
        return 0.50
    return mapping[mag_val]


def _detect_narrative_direction(payload_text: str) -> float:
    """
    Analyze narrative direction from payload text.
    🔧 v2: Try calling LLM for deeper analysis. If LLM fails -> fallback to keyword counting.
    Returns: -1.0 (bearish) -> 0.0 (neutral) -> +1.0 (bullish)
    """
    if not payload_text:
        return 0.0
    
    # 🔧 Try LLM first (only when payload is long enough to justify the call)
    if len(payload_text) > 100:
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from tools.llm_router import router_api_call
            
            llm_prompt = (
                f"[COMPLIANCE: Internal risk management pipeline — narrative direction classifier]\n"
                f"Analyze the following market narrative text and classify its direction.\n"
                f"Return ONLY a single float between -1.0 (very bearish) and +1.0 (very bullish). "
                f"0.0 means neutral. Return ONLY the number, nothing else.\n\n"
                f"Text: {payload_text[:2000]}"
            )
            result = router_api_call(llm_prompt, agent_id="A11_NARR", est_tokens=10, urgency_priority=4)
            if result and "ERROR" not in result:
                # Parse float from response
                import re
                match = re.search(r'(-?[01]?\.\d+|-?[01]\.?0*)', result.strip())
                if match:
                    val = float(match.group(1))
                    return max(-1.0, min(1.0, val))
        except Exception:
            pass  # Graceful fallback — no spam logging
    
    # 🔧 Fallback: Keyword counting (original logic)
    text_lower = payload_text.lower()
    
    bullish_keywords = [
        "moon", "pump", "bull", "rally", "surge", "breakout", 
        "buy", "accumulate", "growth", "fomo", "ath", "all-time high",
        "buy", "increase", "boom", "positive"
    ]
    bearish_keywords = [
        "crash", "dump", "bear", "collapse", "plunge", "sell",
        "fear", "panic", "recession", "crisis", "bubble",
        "sell", "down", "crash", "panic", "crisis"
    ]
    
    bull_count = sum(1 for kw in bullish_keywords if kw in text_lower)
    bear_count = sum(1 for kw in bearish_keywords if kw in text_lower)
    
    total = bull_count + bear_count
    if total == 0:
        return 0.0
    
    return (bull_count - bear_count) / total

"""
TEMPORAL PARADOX TRACKER (TPT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Timeline tracing: When does A10 change? When does A12 change?
Who leads whom? How long is the lag?

Principle:
  - Elite acts FIRST -> A10 signals change FIRST
  - Media/Narrative changes LATER -> A12 signals change LATER
  - If A12 changes BEFORE A10 -> could be "bait" -> MANUFACTURED NARRATIVE
  - If A10 changes way before A12 -> Elite is patiently accumulating -> STRONG SIGNAL
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional
from collections import deque
import json


class TemporalParadoxTracker:
    """
    Ring buffer keeping the N most recent snapshots of A10 + A12 signals.
    Each snapshot = {timestamp, v_money, v_narrative, pdi_score, raw_signals_hash}
    """
    
    def __init__(self, max_snapshots: int = 168, max_events: int = 50):  # 168 = 7 days x 24h
        self.max_snapshots = max_snapshots
        self.max_events = max_events
        self.snapshots = deque(maxlen=self.max_snapshots)
        self._money_change_events = deque(maxlen=self.max_events)   # When v_money reverses direction
        self._narrative_change_events = deque(maxlen=self.max_events)  # When v_narrative reverses direction
        self.current_money_regime = "NEUTRAL"
        self.current_narrative_regime = "NEUTRAL"
    
    def record_snapshot(self, timestamp: datetime, v_money: float, 
                        v_narrative: float, pdi_score: float,
                        a10_dominant_intent: str, a12_aeo_label: str):
        """Records a new snapshot."""
        snapshot = {
            "ts": timestamp.isoformat(),
            "v_money": v_money,
            "v_narrative": v_narrative,
            "pdi": pdi_score,
            "a10_intent": a10_dominant_intent,
            "a12_aeo": a12_aeo_label,
        }
        
        # Detect pivot point (regime change) using current state to avoid Gradual Transition Blindness
        new_money_regime = "BULL" if v_money > 15 else "BEAR" if v_money < -15 else "NEUTRAL"
        if self.current_money_regime != "NEUTRAL" and new_money_regime != "NEUTRAL" and self.current_money_regime != new_money_regime:
            self._money_change_events.append({
                "ts": timestamp.isoformat(),
                "from": self.current_money_regime,
                "to": new_money_regime,
                "direction": f"{self.current_money_regime}→{new_money_regime}"
            })
        if new_money_regime != "NEUTRAL":
            self.current_money_regime = new_money_regime
            
        new_narrative_regime = "BULL" if v_narrative > 20 else "BEAR" if v_narrative < -20 else "NEUTRAL"
        if self.current_narrative_regime != "NEUTRAL" and new_narrative_regime != "NEUTRAL" and self.current_narrative_regime != new_narrative_regime:
            self._narrative_change_events.append({
                "ts": timestamp.isoformat(),
                "from": self.current_narrative_regime,
                "to": new_narrative_regime,
                "direction": f"{self.current_narrative_regime}→{new_narrative_regime}"
            })
        if new_narrative_regime != "NEUTRAL":
            self.current_narrative_regime = new_narrative_regime
        
        self.snapshots.append(snapshot)
    
    def analyze_lead_lag(self) -> Dict:
        """
        Analyze: Does A10 or A12 lead when regime change occurs?
        
        Returns:
            dict: leader, lag_hours, interpretation, confidence
        """
        if not self._money_change_events and not self._narrative_change_events:
            return {
                "leader": "UNKNOWN",
                "lag_hours": None,
                "interpretation": "Insufficient regime change data to analyze lead-lag.",
                "confidence": 0.0,
            }
        
        # Compare most recent regime change events
        last_money_change = None
        last_narrative_change = None
        
        if self._money_change_events:
            last_money_change = self._money_change_events[-1]
        if self._narrative_change_events:
            last_narrative_change = self._narrative_change_events[-1]
        
        if not last_money_change or not last_narrative_change:
            leader = "A10_ONLY" if last_money_change else "A12_ONLY"
            return {
                "leader": leader,
                "lag_hours": None,
                "interpretation": f"Only {leader} changed regime, no comparison available.",
                "confidence": 0.3,
            }
        
        # Parse timestamps
        ts_money = datetime.fromisoformat(last_money_change["ts"])
        ts_narrative = datetime.fromisoformat(last_narrative_change["ts"])
        
        delta = ts_money - ts_narrative
        lag_hours = delta.total_seconds() / 3600
        
        # TIME WINDOW CHECK: Ignore if phase shift exceeds 7 days (168 hours)
        if abs(lag_hours) > 168:
            return {
                "leader": "UNKNOWN",
                "lag_hours": None,
                "interpretation": f"Two events are too far apart ({abs(lag_hours):.1f}h). Likely unrelated.",
                "confidence": 0.1,
            }
        
        # SAME DIRECTION or OPPOSITE DIRECTION?
        money_dir = last_money_change["direction"]
        narr_dir = last_narrative_change["direction"]
        same_direction = (money_dir == narr_dir)
        
        if lag_hours < 0:
            # A10 changes BEFORE A12 (Money leads Narrative)
            abs_lag = abs(lag_hours)
            if same_direction:
                interpretation = (
                    f"A10 (money flow) leads A12 (narrative) by {abs_lag:.1f}h. "
                    f"Same direction {money_dir}. "
                    f"NORMAL: Elite acts -> Media follows."
                )
                confidence = min(0.85, 0.5 + abs_lag / 100)
            else:
                interpretation = (
                    f"A10 leads by {abs_lag:.1f}h but OPPOSITE DIRECTION: "
                    f"Money={money_dir} vs Narrative={narr_dir}. "
                    f"⚠️ EXTREME PARADOX: Elite goes one way, media pushes the opposite -> "
                    f"THIS IS a MAJOR TRAP. Elite uses narrative to cloak real actions."
                )
                confidence = min(0.95, 0.7 + abs_lag / 50)
            leader = "A10_LEADS"
        
        elif lag_hours > 0:
            # A12 changes BEFORE A10 (Narrative leads Money)
            abs_lag = abs(lag_hours)
            if same_direction:
                interpretation = (
                    f"⚠️ A12 (narrative) leads A10 (money flow) by {abs_lag:.1f}h! "
                    f"Same direction {narr_dir}. "
                    f"SUSPICIOUS: Narrative changes before money flow = "
                    f"COULD BE a MANUFACTURED NARRATIVE to trigger retail, "
                    f"with Elite entering after (or front-running the media)."
                )
                confidence = min(0.8, 0.4 + abs_lag / 80)
            else:
                interpretation = (
                    f"A12 leads by {abs_lag:.1f}h and OPPOSITE DIRECTION: "
                    f"Narrative={narr_dir} vs Money={money_dir}. "
                    f"🔴 EXTREME: Media pushes one way, Elite does the opposite -> "
                    f"CLASSIC TRAP. Media is a TOOL of the Elite."
                )
                confidence = min(0.95, 0.75 + abs_lag / 40)
            leader = "A12_LEADS_SUSPICIOUS"
        
        else:
            # Almost simultaneous
            interpretation = "A10 and A12 changed almost simultaneously — monitor further."
            confidence = 0.4
            leader = "SIMULTANEOUS"
        
        return {
            "leader": leader,
            "lag_hours": round(lag_hours, 2),
            "money_direction": money_dir,
            "narrative_direction": narr_dir,
            "same_direction": same_direction,
            "interpretation": interpretation,
            "confidence": round(confidence, 3),
            "n_money_changes": len(self._money_change_events),
            "n_narrative_changes": len(self._narrative_change_events),
        }
    
    def get_divergence_streak(self, threshold: float = 30.0) -> Dict:
        """
        Counts consecutive snapshots with PDI > threshold.
        Long streak = Elite is patiently accumulating/distributing in the shadows.
        """
        streak = 0
        total_diverge = 0
        max_pdi_in_streak = 0
        
        for snap in reversed(self.snapshots):
            if snap["pdi"] > threshold:
                streak += 1
                total_diverge += 1
                max_pdi_in_streak = max(max_pdi_in_streak, snap["pdi"])
            else:
                break
        
        return {
            "current_streak": streak,
            "max_pdi_in_streak": round(max_pdi_in_streak, 2),
            "total_diverge_snapshots": total_diverge,
            "total_snapshots": len(self.snapshots),
            "alert": streak >= 6,  # >=6 consecutive cycles = serious
            "interpretation": (
                f"Paradox persists for {streak} consecutive cycles "
                f"(max PDI={max_pdi_in_streak:.0f}). "
                f"{'⚠️ Elite playing a LONG GAME — very dangerous!' if streak >= 6 else 'Monitor.'}"
            )
        }
    
    def export_for_redis(self) -> str:
        """Serialize to save in Redis."""
        return json.dumps({
            "max_snapshots": self.max_snapshots,
            "max_events": self.max_events,
            "snapshots": list(self.snapshots),
            "money_changes": list(self._money_change_events),
            "narrative_changes": list(self._narrative_change_events),
            "current_money_regime": getattr(self, "current_money_regime", "NEUTRAL"),
            "current_narrative_regime": getattr(self, "current_narrative_regime", "NEUTRAL"),
        }, ensure_ascii=False)
    
    @classmethod
    def import_from_redis(cls, data_str: str) -> "TemporalParadoxTracker":
        """Deserialize from Redis."""
        try:
            data = json.loads(data_str) if isinstance(data_str, str) else data_str
            tracker = cls(
                max_snapshots=data.get("max_snapshots", 168),
                max_events=data.get("max_events", 50)
            )
            tracker.snapshots = deque(data.get("snapshots", []), maxlen=tracker.max_snapshots)
            tracker._money_change_events = deque(data.get("money_changes", []), maxlen=tracker.max_events)
            tracker._narrative_change_events = deque(data.get("narrative_changes", []), maxlen=tracker.max_events)
            tracker.current_money_regime = data.get("current_money_regime", "NEUTRAL")
            tracker.current_narrative_regime = data.get("current_narrative_regime", "NEUTRAL")
            return tracker
        except Exception as e:
            import logging
            logging.error(f"[TemporalParadoxTracker] Critical error recovering state from Redis: {e}")
            raise RuntimeError(f"Corrupted tracker state: {e}")
        
        
"""
CROSS-AGENT CONTRADICTION MATRIX (CACM)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NxN matrix between agents — detects who contradicts whom,
to what extent, and who is more trustworthy (based on historical accuracy).

         A03        A10         A12         A02
A03      ---        +0.8        -0.6        +0.3
A10      +0.8       ---         -0.9        +0.5
A12      -0.6       -0.9        ---         -0.2
A02      +0.3       +0.5        -0.2        ---

Values:
  +1.0 = full consensus
  0.0  = unrelated
  -1.0 = full contradiction

When |correlation| < -0.6 between 2 agents -> CONTRADICTION ALERT
"""

from typing import Dict, List, Tuple
import math


class ContradictionMatrix:
    """
    Cross-agent contradiction matrix.
    Each cell (i,j) = correlation between the conclusions of agent i and agent j.
    """
    
    def __init__(self):
        self.AGENT_IDS = [f"A{str(i).zfill(2)}" for i in range(1, 13)]
        # Current correlation matrix
        self.matrix: Dict[str, Dict[str, float]] = {
            a: {b: 0.0 for b in self.AGENT_IDS} for a in self.AGENT_IDS
        }
        # Accuracy history to weight when contradictions occur
        self.trust_scores: Dict[str, float] = {
            "A01": 0.60,
            "A02": 0.65,  # Macro — slow but steady
            "A03": 0.60,  # Sentiment — noise prone
            "A04": 0.70,
            "A05": 0.90,
            "A06": 0.80,
            "A07": 0.85,
            "A08": 0.85,
            "A09": 0.85,
            "A10": 0.85,  # Real money flow — hard to fake
            "A11": 0.75,  # Aggregate — input dependent
            "A12": 0.70,  # AEO — detects manipulation
        }
    
    def update_cell(self, agent_a: str, agent_b: str, 
                    verdict_a: str, verdict_b: str,
                    confidence_a: float = 0.5, confidence_b: float = 0.5,
                    score_a: float = None, score_b: float = None):
        """Updates cell (a,b) based on latest verdicts."""
        # Ensure agents are present in the matrix to avoid KeyError
        for a in [agent_a, agent_b]:
            if a not in self.AGENT_IDS:
                self.AGENT_IDS.append(a)
                self.matrix[a] = {x: 0.0 for x in self.AGENT_IDS}
                for x in self.AGENT_IDS:
                    self.matrix[x][a] = 0.0
                if a not in self.trust_scores:
                    self.trust_scores[a] = 0.5
                    
        # Convert verdict to numeric vector
        v_a = self._verdict_to_score(verdict_a)
        v_b = self._verdict_to_score(verdict_b)
        
        # FIX RC2: Use normalized composite score when verdict = NEUTRAL/WATCH
        if v_a == 0 and score_a is not None:
            v_a = max(-1.0, min(1.0, score_a / 100.0))
        if v_b == 0 and score_b is not None:
            v_b = max(-1.0, min(1.0, score_b / 100.0))
            
        # Correlation = cosine similarity (1D -> simple signed product)
        if v_a == 0 and v_b == 0:
            corr = 0.0  # Both are actually neutral -> skip
        else:
            # Fix Noise Magnification: use math.copysign(math.sqrt(abs(v_a * v_b)), v_a * v_b)
            # Helps preserve linear magnitude instead of amplifying small values
            raw_corr = math.copysign(math.sqrt(abs(v_a * v_b)), v_a * v_b)
            
            # Fix Confidence Suppression: use geometric mean instead of min()
            conf_weight = math.sqrt(confidence_a * confidence_b) if confidence_a > 0 and confidence_b > 0 else 0.0
            corr = raw_corr * conf_weight
        
        # Exponential Moving Average (EMA) to smooth over time
        alpha = 0.3  # Weight for new value
        old = self.matrix[agent_a][agent_b]
        new = alpha * corr + (1 - alpha) * old
        
        self.matrix[agent_a][agent_b] = round(new, 4)
        self.matrix[agent_b][agent_a] = round(new, 4)  # Symmetric
    
    def detect_contradictions(self, threshold: float = -0.5) -> List[Dict]:
        """Scans matrix to find severe agent contradictions."""
        contradictions = []
        checked = set()
        
        for a in self.AGENT_IDS:
            for b in self.AGENT_IDS:
                if a == b or (b, a) in checked:
                    continue
                checked.add((a, b))
                
                corr = self.matrix[a][b]
                if corr < threshold:
                    # Who is more trustworthy?
                    trust_a = self.trust_scores.get(a, 0.5)
                    trust_b = self.trust_scores.get(b, 0.5)
                    
                    if trust_a > trust_b:
                        trusted = a
                        suspect = b
                    else:
                        trusted = b
                        suspect = a
                    
                    contradictions.append({
                        "agents": (a, b),
                        "correlation": round(corr, 3),
                        "severity": "EXTREME" if corr < -0.8 else "HIGH" if corr < -0.6 else "MODERATE",
                        "trusted_agent": trusted,
                        "suspect_agent": suspect,
                        "trust_delta": round(abs(trust_a - trust_b), 3),
                        "interpretation": self._interpret_contradiction(a, b, corr, trusted, suspect),
                    })
        
        return sorted(contradictions, key=lambda x: x["correlation"])
    
    def get_system_coherence(self) -> Dict:
        """
        Measures system-wide coherence.
        High coherence = agents in agreement = strong signal.
        Low coherence = system disorganized = either trap or lack of data.
        """
        all_corrs = []
        checked = set()
        
        for a in self.AGENT_IDS:
            for b in self.AGENT_IDS:
                if a == b or (b, a) in checked:
                    continue
                checked.add((a, b))
                all_corrs.append(self.matrix[a][b])
        
        if not all_corrs:
            return {"coherence": 0.0, "label": "NO_DATA"}
        
        avg_corr = sum(all_corrs) / len(all_corrs)
        min_corr = min(all_corrs)
        max_corr = max(all_corrs)
        
        # Coherence = average correlation, range -1 to +1
        if avg_corr > 0.6:
            label = "HIGH_CONSENSUS"
            note = "All agents in agreement -> Very strong signal OR all being deceived simultaneously."
        elif avg_corr > 0.2:
            label = "MODERATE_CONSENSUS"
            note = "Majority agreement, some minor differences."
        elif avg_corr > -0.2:
            label = "LOW_CONSENSUS"
            note = "System dispersed — lack of data or market is changing phase."
        else:
            label = "SYSTEM_CONTRADICTION"
            note = "⚠️ Severe agent contradiction — COULD BE a sign of a complex Elite Trap."
        
        return {
            "coherence": round(avg_corr, 3),
            "label": label,
            "note": note,
            "min_correlation": round(min_corr, 3),
            "max_correlation": round(max_corr, 3),
            "n_pairs": len(all_corrs),
        }
    
    def _verdict_to_score(self, verdict: str) -> float:
        if not verdict:
            return 0.0
            
        mapping = {
            "BULLISH": +1.0,
            "STRONG_ACCUMULATE": +1.0,
            "MILD_ACCUMULATE": +0.5,
            "BOOM_INCOMING": +1.0,
            "BEARISH": -1.0,
            "STRONG_DISTRIBUTE": -1.0,
            "MILD_DISTRIBUTE": -0.5,
            "CRISIS_INCOMING": -1.0,
            "NEUTRAL": 0.0,
            "WATCH": 0.0,
            "TRAP_BULL": -0.8,    # Claims bullish but actually a trap
            "TRAP_BEAR": +0.8,    # Claims bearish but actually accumulating
            "MANUFACTURED": 0.0,   # Fix Data Quality: assign 0.0 to fallback to actual score
            "HIGH_AEO": 0.0,       # Fix Data Quality: assign 0.0 to fallback to actual score
            "ORGANIC": 0.0,
        }
        return mapping.get(str(verdict).upper(), 0.0)
    
    def _interpret_contradiction(self, a: str, b: str, corr: float,
                                  trusted: str, suspect: str) -> str:
        """Interprets contradiction between two specific agents."""
        pair_key = tuple(sorted([a, b]))
        
        interpretations = {
            ("A10", "A12"): (
                f"Real money flow (A10) vs Media narrative (A12) contradicts {abs(corr):.0%}. "
                f"This is the most CORE CONTRADICTION. "
                f"Trust {trusted} (trust={self.trust_scores.get(trusted, 0.5):.2f}), "
                f"suspect {suspect}."
            ),
            ("A03", "A10"): (
                f"Crowd sentiment (A03) vs Elite money flow (A10) contradicts {abs(corr):.0%}. "
                f"This is a classic sign of a TRAP: crowd thinks one way, money flows the other."
            ),
            ("A03", "A12"): (
                f"Real sentiment (A03) vs pushed narrative (A12) contradicts {abs(corr):.0%}. "
                f"Maybe A12 is detecting a MANUFACTURED narrative pushing against the crowd."
            ),
            ("A02", "A10"): (
                f"Macro (A02) vs Micro money flow (A10) contradicts {abs(corr):.0%}. "
                f"Macro says one thing but Elite acts differently -> "
                f"perhaps Elite knows policy will change in advance."
            ),
        }
        
        return interpretations.get(pair_key, 
            f"{a} vs {b} contradicts {abs(corr):.0%}. Trust {trusted}."
        )
