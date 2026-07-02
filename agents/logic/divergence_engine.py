"""
🧬 DNA: v16.6 (Sovereign Purity & Signal Synthesis) [DNA Header]
🏢 UNIT: DIVERGENCE_ENGINE
🛠️ ROLE: SIGNAL_SYNTHESIZER
📖 DESC: Signal synthesis system (Divergence Engine). Analyzes the contradiction between Retail behavior (Crowd) and Elite Money Flow (Smart Money), triggered by A12.
🔗 CALLS: tools/imperial_state.py, agents/logic/a03_social_crawler.py, agents/logic/a10_signal_collector.py
📟 I/O: Redis: zcl:a05:divergence_stream, zcl:sentiment:latest, emf:signals:*
🛡️ INTEGRITY: Logic-Isolated, Score-Bounded, Evidence-Backed, Consensus-Driven.
"""

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))
import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Optional

from imperial_state import matrix

log = logging.getLogger("DIVERGENCE_ENGINE")
if not log.handlers:
    log.setLevel(logging.INFO)
    log.addHandler(logging.StreamHandler())

# ── Matrix Keys ───────────────────────────────────────────────────────────────
# Organic I/O v15.8 mapping
# A03: zcl:sentiment:latest => matrix.get("SENTIMENT", "latest")
# A10: emf:signals:scored   => matrix[xrevrange]("A10", "signals:scored")
# A11: emf:intent:report    => matrix[xrevrange]("A11", "intent:report")
# A12: aeo:reports          => matrix[xrevrange]("A12", "reports")
# OUTPUT: zcl:a05:divergence_stream => matrix[xadd]("A05", "divergence_stream")

DIVERGENCE_TTL      = 172800                        # 48 hours TTL (Session-based perpetual data)

# ── Action activation thresholds ────────────────────────────────────────────────
STORM_THRESHOLD_HIGH    = 55    # Divergence >= 55 → strong action (CANH_CHO / CHO_SPRING)
STORM_THRESHOLD_MEDIUM  = 35    # Divergence >= 35 → observe further
EXIT_CRITICAL_THRESHOLD = 65    # Divergence >= 65 during RIDING → exit immediately


# ==============================================================================
# PART 1 — READ 4-AGENT DATA (Matrixized)
# ==============================================================================

def _safe_matrix_get(agent_id: str, key: str) -> dict:
    """Reads Matrix key to dict, does not raise exception."""
    try:
        data = matrix.get(agent_id, key)
        if isinstance(data, (str, bytes)):
            return json.loads(data)
        elif isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _safe_json_field(json_str, field: str, default: str = "") -> str:
    """Parses a JSON string and retrieves field, returns default if error occurs."""
    if not json_str or json_str == "{}":
        return default
    try:
        obj = json.loads(json_str) if isinstance(json_str, str) else json_str
        return obj.get(field, default)
    except (json.JSONDecodeError, AttributeError):
        return default


def _evaluate_dict_quality(d: dict) -> float:
    """Evaluates the quality of a data block to select the best noise-resistant block."""
    if not d: return -999.0
    q = 0.0
    str_val = str(d)
    if "NO_DATA" in str_val or "Disconnected" in str_val or "Mất kết nối" in str_val: q -= 50
    
    # HingeEBM v6.5.1 bonus
    if "algo_core" in d and "narrative_lens" in d:
        q += 500.0
        
    try:
        if "confidence" in d: q += float(d["confidence"]) * 20
        if "composite_score" in d: q += abs(float(d.get("composite_score",0))) / 2.0
        if "aeo_score" in d: q += float(d.get("aeo_score",0)) * 20
        
        ac = d.get("algo_core", {})
        met = ac.get("expert_metrics", {})
        if "confidence" in ac: q += float(ac["confidence"]) * 20
        if "confidence" in met: q += float(met["confidence"]) * 20
        if "composite_score" in met: q += abs(float(met.get("composite_score",0))) / 2.0
    except: pass
    
    q += len(d) * 2 # Prioritize blocks with more data fields
    return q

def _safe_matrix_stream_latest(agent_id: str, stream_key: str, source_filter: str = None) -> dict:
    """Reads the 10 most recent messages from Matrix Stream and selects the HIGHEST QUALITY block.
    Supports both 'payload' and 'envelope' fields (Grand Surgery Trinity Envelope).
    """
    try:
        count = 20 if source_filter else 10
        msgs = matrix.xrevrange(agent_id, stream_key, count=count)
        best_data = {}
        best_q = -9999.0
        if msgs:
            for _, fields in msgs:
                if source_filter and fields.get("source") != source_filter:
                    continue
                
                # Try all possible JSON keys containing packet
                candidates = []
                for k in ["payload", "envelope", "signals"]:
                    raw = fields.get(k)
                    if raw and isinstance(raw, str):
                        try: candidates.append(json.loads(raw))
                        except json.JSONDecodeError: pass
                    elif raw and isinstance(raw, dict):
                        candidates.append(raw)
                
                # Fallback to direct fields reading
                d_fields = {}
                for k, v in fields.items():
                    if isinstance(v, str) and (v.strip().startswith('{') or v.strip().startswith('[')):
                        try: d_fields[k] = json.loads(v)
                        except: d_fields[k] = v
                    else:
                        d_fields[k] = v
                candidates.append(d_fields)
                
                for d in candidates:
                    q = _evaluate_dict_quality(d)
                    if q > best_q:
                        best_q = q
                        best_data = d
            return best_data
    except Exception:
        pass
    return {}

def _get_age_seconds(d: dict, fallback_hours: int = 48) -> int:
    """Calculates the age of the data compared to the current time."""
    if not d: return fallback_hours * 3600
    ts = d.get("timestamp") or d.get("ts") or d.get("timestamp_unix")
    if not ts: return fallback_hours * 3600
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e11: ts = ts / 1000 # convert ms to s
            return int(time.time() - ts)
        elif isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(time.time() - dt.timestamp())
    except:
        return fallback_hours * 3600

# ==============================================================================
# PART 1 — READ 4-AGENT DATA
# ==============================================================================

def _doc_a03_retail() -> dict:
    """
    Reads A03: retail sentiment from Streams (EMF:signals:raw).
    v3.0: Implant Psycho-Kinematic Sensors (MPI/HDR/CWG/DTA) for override.
    """
    # DNA v17.0: Scan Stream signals:raw to find the most recent message of A03
    d = {}
    try:
        msgs = matrix.xrevrange("EMF", "signals:raw", count=100)
        for _, fields in msgs:
            if fields.get("source") == "A03":
                payload = fields.get("signals")
                if isinstance(payload, (str, bytes)):
                    d = json.loads(payload)
                else:
                    d = payload or {}
                break
    except Exception as e:
        log.error(f"Error reading A03 from Stream: {e}")

    algo_core = d.get("algo_core", {})
    narrative_lens = d.get("narrative_lens", {})
    
    if algo_core:
        fear_greed = algo_core.get("fear_greed")
        if fear_greed is None:
            fomo = algo_core.get("fomo_index", 0)
            fear_greed = int((fomo * 50) + 50)
        fear_greed_source = algo_core.get("fear_greed_source", "alternative.me")
        mm_score = algo_core.get("mm_score", 0)
        xu_huong = narrative_lens.get("topic_dominant", "TRUNG_TINH")
        
        thong_tin = narrative_lens.get("summary", "[NO_DATA]")
        dien_giai = narrative_lens.get("topic_dominant", "[NO_DATA]")
        nhan_xet = narrative_lens.get("story", "[NO_DATA]")
        narratives = []
        media_consensus = 0
    else:
        xu_huong = d.get("xu_huong_dam_dong", d.get("xu_huong_thi_truong", d.get("xu_huong", "TRUNG_TINH")))
        mm_score  = d.get("mm_fingerprint", {}).get("score_sau_elite",
                    d.get("mm_fingerprint", {}).get("score", 0))
        if isinstance(mm_score, dict): mm_score = mm_score.get("score", 0)
        fear_greed = d.get("fear_greed", {}).get("gia_tri", 50)
        if isinstance(fear_greed, dict): fear_greed = fear_greed.get("gia_tri", 50)
        fear_greed_source = d.get("fear_greed_source", "alternative.me")
        
        narratives = d.get("tai_chinh_narrative", {}).get("narrative_noi_bat", [])
        media_consensus = d.get("tai_chinh_narrative", {}).get("do_dong_thuan_media_pct", 0)
        thong_tin = d.get("Thong_Tin_Du_Lieu", "[NO_DATA] Psychology Expert A03 is sampling analysis or has not completed startup.")
        dien_giai = d.get("Dien_Giai_Ly_Thuyet", "[NO_DATA] Waiting for A03 to complete interpretation.")
        nhan_xet = d.get("Nhan_Xet_Chuyen_Gia", "[NO_DATA] Lost connection to A03, using Fallback Rule-based.")
    
    # Classify Retail state (Classical)
    if xu_huong in ("FOMO_CUC_DO",) or fear_greed >= 80:
        retail_state = "EXTREME_FOMO"
        retail_score = 90
    elif xu_huong in ("THAM_LAM_CUC_DO", "THAM_LAM") or fear_greed >= 65:
        retail_state = "FOMO"
        retail_score = 65
    elif xu_huong in ("SO_HAI_CUC_DO", "CHAN_NAN_TUI_CUC") or fear_greed <= 20:
        retail_state = "EXTREME_PANIC"
        retail_score = 10
    elif xu_huong in ("SO_HAI", "BAN_THAO_HOANG_LOAN") or fear_greed <= 35:
        retail_state = "PANIC"
        retail_score = 25
    else:
        retail_state = "NEUTRAL"
        retail_score = 50
    
    # ── 16D TENSOR Layer 4: Psycho-Kinematic Override ─────────────────────
    psycho = {}
    psycho_verdict = "NEUTRAL"
    try:
        psycho = _safe_matrix_get("PSYCHO", "sensors")
    except Exception:
        pass

    if psycho:
        mpi_zscore = psycho.get("mpi_zscore", 0)
        hdr_value  = psycho.get("hdr_value", 0)
        cwg_value  = psycho.get("cwg_value", 0)
        dta_value  = psycho.get("dta_value", 0)
        psycho_verdict = psycho.get("psycho_verdict", "NEUTRAL")

        # CAPITULATION: MPI integrates extreme pain + HDR finished boiling the frog
        if mpi_zscore > 3.0 and hdr_value > 5:
            retail_state = "EXTREME_PANIC"
            retail_score = 5      # Maximum Spring Reversal
            psycho_verdict = "CAPITULATION_BUY_SIGNAL"
            log.info(f"[DIVERGENCE] PSYCHO OVERRIDE → CAPITULATION (MPI={mpi_zscore:.1f} HDR={hdr_value:.1f})")

        # GRINDER: CWG explosion = meat grinder is operating → FLAT
        elif cwg_value > 15:
            retail_state = "GRINDER_FLAT"
            retail_score = 50     # Neutral — do not trade
            psycho_verdict = "GRINDER_FLAT"
            log.info(f"[DIVERGENCE] PSYCHO OVERRIDE → GRINDER (CWG={cwg_value:.1f})")

        # DEAD CAT: DTA fake bounce → be careful
        elif dta_value > 3.0:
            if retail_state == "NEUTRAL":
                retail_state = "DEAD_CAT_TRAP"
                retail_score = 35
            psycho_verdict = "DEAD_CAT_SHORT"
            log.info(f"[DIVERGENCE] PSYCHO OVERRIDE → DEAD_CAT (DTA={dta_value:.1f})")

        # EUPHORIA: Near peak
        elif mpi_zscore < -2.0:
            if retail_state in ("FOMO", "EXTREME_FOMO"):
                retail_score = min(retail_score + 10, 100)
            psycho_verdict = "EUPHORIA_WARNING"
    
    return {
        "retail_state":     retail_state,
        "retail_score":     retail_score,
        "mm_fingerprint":   mm_score,
        "fear_greed":       fear_greed,
        "fear_greed_source": fear_greed_source,
        "positioning_greed": algo_core.get("positioning_greed", d.get("positioning_greed", 50)),
        "xu_huong_raw":     xu_huong,
        "narratives":       narratives,
        "media_consensus":  media_consensus,
        "tpmi":             algo_core.get("tpmi", d.get("tpmi", {})),
        # 16D Tensor fields
        "psycho_verdict":   psycho_verdict,
        "psycho_raw":       psycho,
        "Thong_Tin_Du_Lieu": thong_tin,
        "Dien_Giai_Ly_Thuyet": dien_giai,
        "Nhan_Xet_Chuyen_Gia": nhan_xet,
        "_age_seconds":     _get_age_seconds(d),
        "full_snapshot":    d
    }


def _doc_a10_emf() -> dict:
    """
    Reads A10: Dark Pool / Options / On-chain flow.
    v3.0: Implant Macro-Flow Sensors (GLS/REP/SHD/CRA) for override.
    """
    # [BUG FIX OPUS] PREFIX_MAP: "A10" does not exist → fallback zcl:misc.
    # Real key is zcl:emf:signals:scored → use prefix "EMF"
    # [BUG FIX OPUS] Real key is zcl:emf:signals:scored → use prefix "EMF"
    d = _safe_matrix_stream_latest("EMF", "signals:scored")
    
    algo_core = d.get("algo_core", {})
    metrics = algo_core.get("expert_metrics", {})
    narrative_lens = d.get("narrative_lens", {})
    
    if algo_core:
        alert_level = metrics.get("alert_level", "LOW")
        flow_direction = metrics.get("flow_direction", "NEUTRAL")
        composite_score = float(metrics.get("composite_score", 0))
        cross_asset = metrics.get("cross_asset_confirmed", False)
        chu_ky = metrics.get("chu_ky", "NGAN")
        
        thong_tin = narrative_lens.get("summary", "[NO_DATA]")
        dien_giai = narrative_lens.get("a10_story", "[NO_DATA]")
        nhan_xet = narrative_lens.get("elite_action", "[NO_DATA]")
    else:
        meta = d.get("metadata", {})
        alert_level    = meta.get("alert_level", d.get("alert_level", "LOW"))
        
        confidence_data = meta.get("confidence", d.get("confidence", {}))
        if isinstance(confidence_data, str):
            try: confidence_data = json.loads(confidence_data)
            except: confidence_data = {}
            
        flow_direction = confidence_data.get("label", "NEUTRAL")
        try:
            composite_score = float(confidence_data.get("score", d.get("composite_score", 0))) * 100
        except (ValueError, TypeError):
            composite_score = 0
            
        cross_asset = d.get("cross_asset_confirmed", False)
        chu_ky = d.get("chu_ky", "NGAN")
        
        thong_tin = _safe_json_field(d.get("macro_narrative", "{}"), "Thong_Tin_Du_Lieu", "[NO_DATA]")
        dien_giai = _safe_json_field(d.get("macro_narrative", "{}"), "Dien_Giai_Ly_Thuyet", "[NO_DATA]")
        nhan_xet = _safe_json_field(d.get("macro_narrative", "{}"), "Nhan_Xet_Chuyen_Gia", "[NO_DATA]")
    
    # Elite intensity threshold (Classical)
    if flow_direction in ("ACCUMULATE", "STRONG_ACCUMULATE") or composite_score > 60:
        elite_flow = "ACCUMULATE"
        elite_power = min(100, 50 + composite_score * 0.5)
    elif flow_direction in ("DISTRIBUTE", "STRONG_DISTRIBUTE") or composite_score < -60:
        elite_flow = "DISTRIBUTE"
        elite_power = min(100, 50 + abs(composite_score) * 0.5)
    elif flow_direction in ("HEDGE",) or alert_level in ("HIGH", "CRITICAL"):
        elite_flow = "HEDGE"
        elite_power = 70
    else:
        elite_flow = "NEUTRAL"
        elite_power = 30
    
    # ── 16D TENSOR Layer 2: Macro-Flow Override ──────────────────────────
    psycho = {}
    macro = {}
    macro_verdict = "NORMAL"
    try:
        macro = _safe_matrix_get("MACRO", "sensors")
    except Exception:
        pass

    if macro:
        gls_zscore = macro.get("gls_zscore", 0)
        shd_value  = macro.get("shd_value", 0)
        cra_zscore = macro.get("cra_zscore", 0)
        rep_trend  = macro.get("rep_trend_5d", 0)
        macro_verdict = macro.get("macro_verdict", "NORMAL")

        # SHD > 0.3: Elite is silently buying crash insurance
        if shd_value > 0.3:
            if elite_flow != "DISTRIBUTE":
                elite_flow = "HEDGE"
            alert_level = "HIGH"
            elite_power = max(elite_power, 75)
            log.info(f"[DIVERGENCE] MACRO OVERRIDE → SHD={shd_value:.2f} (Elite hedging)")

        # CRA < -2: Credit broken → CRISIS
        if cra_zscore < -2:
            alert_level = "CRITICAL"
            if elite_flow == "NEUTRAL":
                elite_flow = "DISTRIBUTE"
            elite_power = max(elite_power, 85)
            macro_verdict = "CREDIT_CRISIS"
            log.info(f"[DIVERGENCE] MACRO OVERRIDE → CRA={cra_zscore:.1f} (Credit crisis)")

        # GLS > 2: Liquidity locked — institutional water valve
        if gls_zscore > 2.0:
            if elite_flow == "ACCUMULATE":
                elite_power = max(30, elite_power - 20)  # Reduce accumulation power
            macro_verdict = "LIQUIDITY_SQUEEZED"
            log.info(f"[DIVERGENCE] MACRO OVERRIDE → GLS={gls_zscore:.1f} (Liquidity locked)")

        # REP strong negative trend: Real economy decline
        if rep_trend < -5:
            macro_verdict = "REAL_ECONOMY_DECLINE"
    
    return {
        "elite_flow":       elite_flow,
        "elite_power":      round(elite_power, 1),
        "alert_level":      alert_level,
        "composite_score":  composite_score,
        "cross_asset":      cross_asset,
        "chu_ky":           chu_ky,
        # 16D Tensor fields
        "macro_verdict":    macro_verdict,
        "macro_raw":        macro,
        "Thong_Tin_Du_Lieu": thong_tin,
        "Dien_Giai_Ly_Thuyet": dien_giai,
        "Nhan_Xet_Chuyen_Gia": nhan_xet,
        "_age_seconds":     _get_age_seconds(d),
        "full_snapshot":    d
    }

def _doc_a11_intent() -> dict:
    """
    Reads A11: Elite upcoming scenarios.
    """
    # [BUG FIX OPUS] Real key is zcl:emf:intent:report → use prefix "EMF"
    d = _safe_matrix_stream_latest("EMF", "intent:report")
    
    algo_core = d.get("algo_core", {})
    metrics = algo_core.get("expert_metrics", {})
    narrative_lens = d.get("narrative_lens", {})
    
    if algo_core:
        # Completely resolve nested extraction error of A11
        report_data = metrics.get("report", {})
        if isinstance(report_data, str):
            try: report_data = json.loads(report_data)
            except: report_data = {}
            
        intent_data = report_data.get("intent", {})
        if isinstance(intent_data, str):
            try: intent_data = json.loads(intent_data)
            except: intent_data = {}
            
        scenario_data = report_data.get("scenario", {})
        if isinstance(scenario_data, str):
            try: scenario_data = json.loads(scenario_data)
            except: scenario_data = {}

        scenario_type = algo_core.get("scenario_type", scenario_data.get("type", "WATCH"))
        confidence = algo_core.get("scenario_confidence", scenario_data.get("confidence", 0.0))
        timeframe = scenario_data.get("estimated_timeframe", None)
        exit_triggers = scenario_data.get("exit_triggers", [])
        hedge_active = intent_data.get("hedge_active", False)
        label = intent_data.get("label", "NEUTRAL")
        
        thong_tin = narrative_lens.get("summary", "[NO_DATA]")
        dien_giai = narrative_lens.get("llm_reasoning", "[NO_DATA]")
        nhan_xet = narrative_lens.get("a11_story", "[NO_DATA]")
    else:
        meta = d.get("metadata", {})
        report_data = meta.get("report", d)
        
        raw_scenario = report_data.get("scenario", "{}")
        raw_intent   = report_data.get("intent", "{}")
        
        scenario    = json.loads(raw_scenario) if isinstance(raw_scenario, str) else (raw_scenario or {})
        intent_data = json.loads(raw_intent) if isinstance(raw_intent, str) else (raw_intent or {})
        
        scenario_type = scenario.get("type", "WATCH") if isinstance(scenario, dict) else "WATCH"
        confidence    = scenario.get("confidence", 0.0) if isinstance(scenario, dict) else 0.0
        timeframe     = scenario.get("estimated_timeframe", None) if isinstance(scenario, dict) else None
        exit_triggers = scenario.get("exit_triggers", []) if isinstance(scenario, dict) else []
        hedge_active  = intent_data.get("hedge_active", False) if isinstance(intent_data, dict) else False
        label         = intent_data.get("label", "NEUTRAL") if isinstance(intent_data, dict) else "NEUTRAL"
        
        thong_tin = _safe_json_field(d.get("macro_narrative", "{}"), "Thong_Tin_Du_Lieu", "[NO_DATA]")
        dien_giai = _safe_json_field(d.get("macro_narrative", "{}"), "Dien_Giai_Ly_Thuyet", "[NO_DATA]")
        nhan_xet = _safe_json_field(d.get("macro_narrative", "{}"), "Nhan_Xet_Chuyen_Gia", "[NO_DATA]")
        
    # Parse timeframe into estimated hours
    hours_range = _parse_timeframe_to_hours(timeframe)
    
    return {
        "elite_intent":     scenario_type,     # BOOM_INCOMING | CRISIS_INCOMING | EXIT_POINT | WATCH
        "confidence":       confidence,        # 0.0 - 1.0
        "timeframe_raw":    timeframe,         # "4-12 tuần" etc.
        "storm_window_h":   hours_range,       # (min_h, max_h) estimated
        "exit_triggers":    exit_triggers,
        "hedge_active":     hedge_active,
        "label":            label,
        "Thong_Tin_Du_Lieu": thong_tin,
        "Dien_Giai_Ly_Thuyet": dien_giai,
        "Nhan_Xet_Chuyen_Gia": nhan_xet,
        "_age_seconds":     _get_age_seconds(d),
        "full_snapshot":    d
    }


def _doc_a12_aeo() -> dict:
    """
    Reads A12: AI/Media manipulation verdict.
    v4.0: Add Priority 0 to read AEO:last_report KV (Grand Surgery Trinity Envelope).
    """
    d = {}
    llm_triptych = {}
    
    # ── Priority 0: Read AEO:last_report KV (HingeEBM Packet) ───────────────
    try:
        kv_raw = matrix.get("AEO", "last_report")
        if kv_raw:
            kv = json.loads(kv_raw) if isinstance(kv_raw, str) else kv_raw
            # Extract if matching HingeEBM schema
            if "algo_core" in kv:
                d = kv
            else:
                trinity = (kv or {}).get("trinity", {})
                if isinstance(trinity, str): trinity = json.loads(trinity)
                if trinity and "algo_core" in trinity: d = trinity
    except Exception as e_kv:
        pass
    
    # ── Priority 1: Read from reports_stream ────────────────
    if not d:
        try:
            report_data = _safe_matrix_stream_latest("A12", "reports_stream")
            if report_data:
                d = report_data
        except Exception:
            pass

    algo_core = d.get("algo_core", {})
    metrics = algo_core.get("expert_metrics", {})
    narrative_lens = d.get("narrative_lens", {})

    if algo_core:
        aeo_label = algo_core.get("verdict", "ORGANIC")
        aeo_score = algo_core.get("aeo_score", 0.0)
        financial = algo_core.get("financial_aeo_confirmed", False)
        beneficiary = narrative_lens.get("beneficiary", "")
        payload = narrative_lens.get("payload_hypothesis", "")
        
        # Override triptych
        llm_triptych = {
            "Thong_Tin_Du_Lieu": narrative_lens.get("summary", "[NO_DATA]"),
            "Dien_Giai_Ly_Thuyet": narrative_lens.get("payload_hypothesis", "[NO_DATA]"),
            "Nhan_Xet_Chuyen_Gia": narrative_lens.get("a12_story", "[NO_DATA]")
        }
    else:
        # Fallback 2: Legacy parsing
        if not d:
            try:
                raw = matrix.get("A12", "brain_b")
                if isinstance(raw, str): d = json.loads(raw)
                elif isinstance(raw, dict): d = raw
                if d and d.get("mode") == "BRAIN_B_DIAGNOSTIC":
                    fin = d.get("financial_aeo_confirmed", False)
                    src = d.get("confirmation_sources", 0)
                    llm_triptych = {
                        "Thong_Tin_Du_Lieu": f"Detected Diagnostic signal: Data matches {src} sources.",
                        "Dien_Giai_Ly_Thuyet": f"Fallback BRAIN_B: Financial AEO Confirmed = {fin}.",
                        "Nhan_Xet_Chuyen_Gia": "The underlying money flow is being examined, waiting for LLM to process further."
                    }
            except: pass

        if not d:
            try:
                raw = matrix.get("A12", "brain_a")
                if isinstance(raw, str): d = json.loads(raw)
                elif isinstance(raw, dict): d = raw
                if d and d.get("mode") == "BRAIN_A_CONTEXT":
                    vel = d.get("velocity_score", 0)
                    plat = d.get("active_platforms", 0)
                    sig = d.get("strongest_signal", "N/A")
                    llm_triptych = {
                        "Thong_Tin_Du_Lieu": f"Media appeared on {plat} platforms with propagation velocity {vel:.2f}.",
                        "Dien_Giai_Ly_Thuyet": f"Fallback BRAIN_A: Network signal is reflecting {sig[:50]}.",
                        "Nhan_Xet_Chuyen_Gia": "Monitoring media surface, waiting for A12 to analyze underlying Motivation (Brain B)."
                    }
            except: pass
            
        verdict    = d.get("verdict", {})
        aeo_label  = verdict.get("label", d.get("narrative_verdict", "ORGANIC"))
        aeo_score  = verdict.get("aeo_score", d.get("aeo_score", 0))
        financial  = verdict.get("financial_aeo_confirmed", d.get("financial_aeo_confirmed", False))
        beneficiary = verdict.get("beneficiary", "")
        payload    = verdict.get("payload_hypothesis", "")

    # AI/LLM manipulation intensity (Classical)
    if aeo_label == "MANUFACTURED" or financial:
        aeo_active = True
        aeo_power  = min(100, int(aeo_score * 100))
    elif aeo_label in ("HIGH_AEO", "SUSPICIOUS"):
        aeo_active = True
        aeo_power  = int(aeo_score * 80)
    else:
        aeo_active = False
        aeo_power  = int(aeo_score * 50)
    
    # ── 16D TENSOR Layer 3: Narrative-Pipeline Override ───────────────────
    nps = {}
    narrative_verdict = "ORGANIC"
    try:
        nps = _safe_matrix_get("NARRATIVE", "sensors")
    except Exception:
        pass

    if nps:
        cad_zscore = nps.get("cad_zscore", 0)
        ecs_value  = nps.get("ecs_value", 0)
        dar_value  = nps.get("dar_value", 0)
        npa_delta  = nps.get("npa_delta", 0)
        narrative_verdict = nps.get("narrative_verdict", "ORGANIC")

        # CAD > 2: Press hype but price does not budge → MANUFACTURED
        if cad_zscore > 2.0:
            aeo_label = "MANUFACTURED"
            financial = True
            aeo_active = True
            aeo_power = max(aeo_power, 95)
            narrative_verdict = "MANUFACTURED_DIVERGENCE"
            log.info(f"[DIVERGENCE] NPS OVERRIDE → CAD={cad_zscore:.1f} (Media is lying)")

        # ECS spike: Paid PR campaign — increase AEO power
        if ecs_value > 3.0:
            aeo_power = min(100, aeo_power + 20)
            if not aeo_active:
                aeo_active = True
                aeo_label = "SUSPICIOUS"
            narrative_verdict = "COORDINATED_PR"
            log.info(f"[DIVERGENCE] NPS OVERRIDE → ECS={ecs_value:.1f} (Paid campaign)")

        # DAR > 1.5: Empty Bluster — media is more than reality
        if dar_value > 1.5:
            aeo_power = min(100, aeo_power + 10)
            if narrative_verdict == "ORGANIC":
                narrative_verdict = "AMPLIFIED"
            log.info(f"[DIVERGENCE] NPS OVERRIDE → DAR={dar_value:.1f} (Amplified story)")

        # NPA delta dương mạnh: Đang bẻ lái Pipeline
        if npa_delta > 2.0:
            narrative_verdict = "PIPELINE_HIJACKED"
    
    return {
        "aeo_label":     aeo_label,
        "aeo_score":     aeo_score,
        "aeo_power":     aeo_power,
        "aeo_active":    aeo_active,
        "financial_aeo": financial,
        "beneficiary":   beneficiary,
        "payload":       payload,
        # 16D Tensor fields
        "narrative_verdict": narrative_verdict,
        "narrative_raw":     nps,
        # [BUG FIX OPUS] Triptych read from reports_stream.llm_analysis, fallback brain_b, fallback [NO_DATA]
        "Thong_Tin_Du_Lieu": llm_triptych.get("Thong_Tin_Du_Lieu", d.get("Thong_Tin_Du_Lieu", "[NO_DATA] Detective A12 is accessing Media/Narrative system.")),
        "Dien_Giai_Ly_Thuyet": llm_triptych.get("Dien_Giai_Ly_Thuyet", d.get("Dien_Giai_Ly_Thuyet", "[NO_DATA] Waiting for A12 diagnostics.")),
        "Nhan_Xet_Chuyen_Gia": llm_triptych.get("Nhan_Xet_Chuyen_Gia", d.get("Nhan_Xet_Chuyen_Gia", "[NO_DATA] Lost connection to A12.")),
        "full_snapshot":    llm_triptych if llm_triptych else d
    }

def _doc_a04_realtime() -> dict:
    """Reads T0 Behavior Cipher data from A04.
    v4.0: Unwrap Trinity sub-key (Grand Surgery format: {"trinity": {...}}).
    """
    d = _safe_matrix_stream_latest("A05", "t0_stream", source_filter="A04")
    
    algo_core = d.get("algo_core", {})
    metrics = algo_core.get("expert_metrics", {})
    narrative_lens = d.get("narrative_lens", {})
    
    if algo_core:
        thong_tin = narrative_lens.get("hoc_gia_tuan", "[NO_DATA]")
        dien_giai = narrative_lens.get("reality_check", "[NO_DATA]")
        nhan_xet = narrative_lens.get("a04_story", "[NO_DATA]")
        
        wyckoff = metrics.get("wyckoff", "")
        elliott = metrics.get("elliott", "")
        vsa_label = algo_core.get("vsa_label", "")
        kinematics = metrics.get("kinematics", {})
        trinity = d # use full packet for snapshot
    else:
        # Legacy
        trinity = d.get("trinity", {})
        if isinstance(trinity, str):
            try: trinity = json.loads(trinity)
            except: trinity = {}
        meta = d.get("metadata", {})
        if isinstance(meta, str):
            try: meta = json.loads(meta)
            except: meta = {}
        
        thong_tin = trinity.get("Thong_Tin_Du_Lieu", d.get("Thong_Tin_Du_Lieu", "[NO_DATA] Price Action Expert A04 is analyzing Wyckoff structure."))
        dien_giai = trinity.get("Dien_Giai_Ly_Thuyet", d.get("Dien_Giai_Ly_Thuyet", "[NO_DATA] Waiting for A04 to sync charts."))
        nhan_xet = trinity.get("Nhan_Xet_Chuyen_Gia", d.get("Nhan_Xet_Chuyen_Gia", "[NO_DATA] Lost connection to A04."))
        
        wyckoff = meta.get("wyckoff", "")
        elliott = meta.get("elliott", "")
        vsa_label = meta.get("vsa_label", "")
        kinematics = meta.get("kinematics", {})
        
    return {
        "Thong_Tin_Du_Lieu": thong_tin,
        "Dien_Giai_Ly_Thuyet": dien_giai,
        "Nhan_Xet_Chuyen_Gia": nhan_xet,
        "wyckoff": wyckoff,
        "elliott": elliott,
        "vsa_label": vsa_label,
        "kinematics": kinematics,
        "full_snapshot": trinity if trinity else d
    }


def _doc_a07_apex() -> dict:
    """
    Reads A07: Apex Crisis Detonator Index & Asset Restructuring.
    """
    d = {}
    try:
        raw = matrix.get("A07", "latest_decision")
        if raw:
            d = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        log.error(f"Error reading A07 from Redis: {e}")

    algo_core = d.get("algo_core", {})
    narrative_lens = d.get("narrative_lens", {})

    if algo_core:
        thong_tin = narrative_lens.get("summary", "[NO_DATA]")
        dien_giai = narrative_lens.get("r_g_divergence_threat", "[NO_DATA]")
        nhan_xet = narrative_lens.get("strategic_advice", "[NO_DATA]")
    else:
        thong_tin = "[NO_DATA] Elite-Apex Expert A07 is collecting underlying macro data."
        dien_giai = "[NO_DATA]"
        nhan_xet = "[NO_DATA]"

    return {
        "Thong_Tin_Du_Lieu": thong_tin,
        "Dien_Giai_Ly_Thuyet": dien_giai,
        "Nhan_Xet_Chuyen_Gia": nhan_xet,
        "full_snapshot": d
    }


def _parse_timeframe_to_hours(timeframe: Optional[str]) -> tuple:
    """Parses timeframe string '4-12 weeks' into (min_hours, max_hours)."""
    if not timeframe:
        return (None, None)
    
    import re
    # Find number of days
    m = re.search(r'(\d+)-(\d+)\s*(tuần|week|ngày|day|tháng|month)', timeframe, re.I)
    if not m:
        # Try 1 number
        m = re.search(r'(\d+)\s*(tuần|week|ngày|day|tháng|month)', timeframe, re.I)
        if not m:
            return (None, None)
        n1, n2 = int(m.group(1)), int(m.group(1)) * 2
        unit = m.group(2).lower()
    else:
        n1, n2 = int(m.group(1)), int(m.group(2))
        unit = m.group(3).lower()
    
    multiplier = 168 if 'tuần' in unit or 'week' in unit else (
                 24  if 'ngày' in unit or 'day' in unit else
                 720                                          # month
    )
    return (n1 * multiplier, n2 * multiplier)


# ==============================================================================
# PART 2 — CALCULATE DIVERGENCE SCORE
# ==============================================================================

def _tinh_divergence_score(a03: dict, a10: dict, a11: dict, a12: dict) -> dict:
    """
    Core algorithm: calculates the level of Elite vs Retail contradiction.

    Conflict Matrix:
    ┌──────────────────────────────────────────────────────┐
    │             ELITE ACCUMULATE  | ELITE DISTRIBUTE    │
    │ RETAIL FOMO:   Real Momentum  │  Peak TRAP (high)   │
    │ RETAIL PANIC:  Bottom Spring  │  Confirm downtrend  │
    │ RETAIL NEUTRAL: Stealth Accum │  Stealth Dist       │
    └──────────────────────────────────────────────────────┘

    AEO Amplification: if A12 detects a guided narrative
    → add to divergence score (Elite is using media to guide retail)
    """
    retail_state = a03["retail_state"]
    retail_score = a03["retail_score"]
    mm_fingerprint = a03["mm_fingerprint"]
    elite_flow   = a10["elite_flow"]
    elite_power  = a10["elite_power"]
    chu_ky       = a10.get("chu_ky", "NGAN")
    elite_intent = a11["elite_intent"]
    intent_conf  = a11["confidence"]
    aeo_active   = a12["aeo_active"]
    aeo_power    = a12["aeo_power"]
    financial_aeo = a12["financial_aeo"]
    
    # ── Step 1: Base divergence from Retail vs Elite flow ──────────────────────
    base_score = 0
    conflict_type = "UNKNOWN"
    
    if retail_state in ("EXTREME_FOMO", "FOMO"):
        if elite_flow == "DISTRIBUTE":
            # Peak TRAP: Retail buying crazy, Elite is dumping → maximum contradiction
            base_score = 80 if retail_state == "EXTREME_FOMO" else 65
            conflict_type = "TRAP_TOP"
        elif elite_flow == "ACCUMULATE":
            # Real Momentum: both in the same direction → low
            base_score = 25
            conflict_type = "MOMENTUM_REAL"
        elif elite_flow == "HEDGE":
            # Elite hedging while retail FOMO → dangerous
            base_score = 70
            conflict_type = "ELITE_HEDGING_RETAIL_FOMO"
        else:
            base_score = 40
            conflict_type = "FOMO_NO_ELITE_CONFIRM"
    
    elif retail_state in ("EXTREME_PANIC", "PANIC"):
        if elite_flow == "ACCUMULATE":
            # Spring: Retail panic, Elite accumulating → big opportunity
            base_score = 78 if retail_state == "EXTREME_PANIC" else 62
            conflict_type = "SPRING_REVERSAL"
        elif elite_flow == "DISTRIBUTE":
            # Real Downtrend: both decreasing → warning but no contradiction
            base_score = 30
            conflict_type = "CONFIRMED_DOWNTREND"
        elif elite_flow == "HEDGE":
            # Real Crisis: both hedging
            base_score = 85
            conflict_type = "CRISIS_CONFIRMED"
        else:
            base_score = 45
            conflict_type = "PANIC_WATCH"
    
    else:  # NEUTRAL
        if elite_flow == "ACCUMULATE":
            # Stealth Accumulation: Retail sleeping, Elite accumulating
            base_score = 55
            conflict_type = "STEALTH_ACCUMULATION"
        elif elite_flow == "DISTRIBUTE":
            # Stealth Distribution: Retail neutral, Elite dumping silently
            base_score = 60
            conflict_type = "STEALTH_DISTRIBUTION"
        elif elite_flow == "HEDGE":
            base_score = 65
            conflict_type = "ELITE_HEDGE_SILENT"
        else:
            base_score = 20
            conflict_type = "SIDEWAYS_WATCH"
    
    # ── Step 2: Adjust by Elite power intensity ─────────────────────────
    power_factor = elite_power / 100.0  # 0-1
    base_score   = round(base_score * (0.7 + 0.3 * power_factor), 1)
    
    # ── Step 3: Adjust by A11 Intent confirmation ──────────────────────
    intent_boost = 0
    if elite_intent == "BOOM_INCOMING" and elite_flow == "ACCUMULATE":
        intent_boost = 10 * intent_conf  # Max +10
    elif elite_intent == "CRISIS_INCOMING" and elite_flow in ("DISTRIBUTE", "HEDGE"):
        intent_boost = 15 * intent_conf  # Max +15
    elif elite_intent == "EXIT_POINT":
        intent_boost = 12 * intent_conf
    
    # ── Step 4: AEO amplifier ─────────────────────────────────────────────────
    # When media is guided + Elite is moving → add boost
    aeo_boost = 0
    if aeo_active and financial_aeo:
        # Financial AEO: media serves Elite trap → extremely dangerous
        aeo_boost = min(20, aeo_power * 0.2)
    elif aeo_active:
        aeo_boost = min(10, aeo_power * 0.1)
    
    # ── Step 5: MM Fingerprint amplifier (A03) ───────────────────────────────
    mm_boost = 0
    if mm_fingerprint >= 75 and elite_flow == "DISTRIBUTE":
        # Media is paving the way to dump, elite dumping → peak trap
        mm_boost = (mm_fingerprint - 70) * 0.4
    elif mm_fingerprint >= 60:
        mm_boost = (mm_fingerprint - 55) * 0.2
    
    # ── Step 6: Macro Gravity (Impact of LONG-TERM Cycle) ──────────────────
    macro_boost = 0
    if chu_ky == "DAI":
        # DAI cycle represents extremely strong momentum, long accumulated Divergence will compress tightly
        # Multiply +20% Divergence power coefficient for inflection points
        macro_boost = (base_score + intent_boost) * 0.20
        conflict_type = f"MACRO_SHIFT_{conflict_type}"
    
    # ── Step 7: Cognitive Dissonance Boost (Option C - Contradiction between emotion vs behavior) ──
    cd_boost = 0
    fg = a03.get("fear_greed", 50)
    pos_g = a03.get("positioning_greed")
    if pos_g is not None:
        try:
            fg_val = float(fg)
            pos_g_val = float(pos_g)
            if abs(fg_val - pos_g_val) > 30:
                cd_boost = min(15.0, abs(fg_val - pos_g_val) * 0.3)
                conflict_type = f"DISSONANCE_{conflict_type}"
        except:
            pass

    # ── Step 8: TPMI (Trend Perception Manipulation Index) Boost ─────────────
    tpmi_boost = 0
    tpmi = a03.get("tpmi", {})
    if isinstance(tpmi, dict):
        tpmi_threat = tpmi.get("threat_level", "LOW")
        if tpmi_threat == "EXTREME":
            tpmi_boost = 15.0
        elif tpmi_threat == "HIGH":
            tpmi_boost = 10.0
        elif tpmi_threat == "MEDIUM":
            tpmi_boost = 5.0

    final_score = min(100, max(0, base_score + intent_boost + aeo_boost + mm_boost + macro_boost + cd_boost + tpmi_boost))
    
    return {
        "divergence_score":  round(final_score, 1),
        "con_so_cuoi_cung":  f"{round(final_score, 1)}/100 {'[MACRO]' if chu_ky == 'DAI' else ''}",
        "base_score":        base_score,
        "intent_boost":      round(intent_boost, 1),
        "aeo_boost":         round(aeo_boost, 1),
        "mm_boost":          round(mm_boost, 1),
        "macro_boost":       round(macro_boost, 1),
        "cd_boost":          round(cd_boost, 1),
        "tpmi_boost":        round(tpmi_boost, 1),
        "conflict_type":     conflict_type,
    }



def _tinh_dominant_actor(a03: dict, a10: dict) -> str:
    """Who is controlling the game?"""
    retail_power = abs(a03["retail_score"] - 50)  # Deviation from neutral
    elite_power  = a10["elite_power"]
    
    if elite_power > retail_power + 20:
        return "ELITE"
    elif retail_power > elite_power + 20:
        return "RETAIL"
    return "BALANCED"


def _tinh_storm_window(a11: dict, divergence_score: float, conflict_type: str) -> dict:
    """
    Estimates the time window to a major event.

    Principle: Higher score + RISING trend = wave arrives sooner.
    HUNTING mode: When to enter?
    RIDING mode:  When to exit?
    """
    storm_h     = a11.get("storm_window_h", (None, None))
    elite_intent = a11.get("elite_intent", "WATCH")
    
    # If A11 already has timeframe estimate, prioritize using it
    if storm_h and storm_h[0] is not None:
        min_h, max_h = storm_h
        # Adjustment: high score -> shorten time
        intensity_factor = divergence_score / 100
        adjusted_min = max(6, int(min_h * (1.2 - intensity_factor * 0.4)))
        adjusted_max = int(max_h * (1.1 - intensity_factor * 0.2))
        return {
            "min_hours": adjusted_min,
            "max_hours": adjusted_max,
            "confidence": "HIGH" if a11.get("confidence", 0) > 0.65 else "MEDIUM",
            "source": "A11_confirmed",
        }
    
    # Fallback: estimate from conflict_type + score
    windows = {
        "TRAP_TOP":              (6,  48),
        "SPRING_REVERSAL":       (12, 72),
        "CRISIS_CONFIRMED":      (48, 336),   # 2-14 days
        "STEALTH_ACCUMULATION":  (72, 672),   # 3-28 days
        "STEALTH_DISTRIBUTION":  (48, 336),
        "ELITE_HEDGE_SILENT":    (48, 336),
        "MOMENTUM_REAL":         (None, None),
        "CONFIRMED_DOWNTREND":   (None, None),
    }
    
    range_h = windows.get(conflict_type, (None, None))
    if range_h[0] is None:
        return {"min_hours": None, "max_hours": None, "confidence": "LOW", "source": "fallback"}
    
    intensity_factor = divergence_score / 100
    adj_min = max(6, int(range_h[0] * (1.1 - intensity_factor * 0.3)))
    adj_max = int(range_h[1] * (1.0 - intensity_factor * 0.15))
    
    return {
        "min_hours": adj_min,
        "max_hours": adj_max,
        "confidence": "MEDIUM" if divergence_score > 60 else "LOW",
        "source": "rule_based",
    }


def _tinh_intensity_trend(current_score: float) -> str:
    # Get old Divergence from STREAM
    try:
        prev_list = matrix.xrevrange("A05", "divergence_stream", count=1)
        prev = json.loads(prev_list[0][1].get("payload") or "{}") if prev_list else None
    except Exception:
        prev = None
    if prev:
        prev_score = prev.get("divergence_score", current_score)
        delta = current_score - prev_score
        if delta >= 5:
            return "RISING"
        elif delta <= -5:
            return "FALLING"
    return "STABLE"


def _tinh_exit_critical(state: str, a10: dict, a11: dict, divergence_score: float) -> bool:
    """
    True if in RIDING state and there are CLEAR SIGNS to exit.
    Do not false trigger: only True when >=2 strong signals occur simultaneously.
    """
    if state != "RIDING":
        return False
    
    signals = 0
    
    # Signal 1: Elite is distributing heavily
    if a10["elite_flow"] == "DISTRIBUTE" and a10["elite_power"] > 60:
        signals += 1
    
    # Signal 2: A11 detects EXIT_POINT with high confidence
    if a11["elite_intent"] == "EXIT_POINT" and a11["confidence"] > 0.60:
        signals += 1
    
    # Signal 3: Divergence is at TRAP_TOP + RISING level
    if divergence_score >= EXIT_CRITICAL_THRESHOLD:
        signals += 1
    
    return signals >= 2


# ==============================================================================
# PART 3 — PUBLISH DIVERGENCE MATRIX
# ==============================================================================

def compute_and_publish(state: str = "HUNTING") -> dict:
    """
    Main entry point — called by A12 after each scan completes,
    or by A05 before decision making.

    Args:
        state: "HUNTING" or "RIDING" — current state of the vault

    Returns:
        DivergenceMatrix dict (also published to Redis)
    """
    a03 = _doc_a03_retail()
    a10 = _doc_a10_emf()
    a11 = _doc_a11_intent()
    a12 = _doc_a12_aeo()
    a04 = _doc_a04_realtime()
    a07 = _doc_a07_apex()
    
    # ── A08 Swarm Oracle (1M simulated individuals) ──
    a08 = {}
    try:
        a08_raw = matrix.get("A08", "swarm_prediction")
        if a08_raw:
            a08 = a08_raw if isinstance(a08_raw, dict) else json.loads(a08_raw)
        
        # Read 5 most recent predictions — A05 analyzes net_pressure trend
        try:
            history_raw = matrix.client.lrange("zcl:a08:prediction_history", 0, 4)
            if history_raw:
                history_parsed = []
                for h in history_raw:
                    try:
                        entry = json.loads(h)
                        history_parsed.append({
                            "ts": entry.get("timestamp", "?"),
                            "net_pressure": entry.get("net_pressure", 0),
                            "crowd_sentiment": entry.get("crowd_sentiment", "?"),
                            "divergence_flag": entry.get("divergence_flag", "?"),
                            "mode": entry.get("meta", {}).get("mode", "?")
                        })
                    except:
                        pass
                a08["prediction_history"] = history_parsed
        except Exception as e_hist:
            log.debug(f"[DIVERGENCE] A08 history read error: {e_hist}")
    except Exception as e_a08:
        log.debug(f"[DIVERGENCE] A08 Swarm Oracle read error: {e_a08}")
    
    # ── A08 Portfolio Breakdown v2.0 (Multi-tranche Allocation) ──
    try:
        port_raw = matrix.get("A08", "portfolio_breakdown")
        if port_raw:
            port_data = port_raw if isinstance(port_raw, dict) else json.loads(port_raw)
            a08["portfolio_breakdown"] = port_data
    except Exception as e_port:
        log.debug(f"[DIVERGENCE] A08 portfolio_breakdown read error: {e_port}")
    
    # ── Additive Confidence evaluation ──
    # Lao Cong indicator: 0 + 0.6 + 0.8 = 1.4 -> >80% (do not drag each other down)
    def _get_rel(d: dict) -> float:
        if d.get("_age_seconds", 99999) > 10800: return 0.0 # Exceeds 3 hours -> zero out
        s = 0.5
        if "confidence" in d: s = float(d["confidence"])
        elif "composite_score" in d: s = min(1.0, abs(float(d.get("composite_score",0)))/100.0)
        elif "aeo_power" in d: s = float(d.get("aeo_power",0))/100.0
        elif "retail_score" in d: s = abs(float(d.get("retail_score",50))-50)/50.0 + 0.3
        return max(0.2, s)

    r_a03 = _get_rel(a03)
    r_a10 = _get_rel(a10)
    r_a11 = _get_rel(a11)
    r_a12 = _get_rel(a12)
    sum_rel = r_a03 + r_a10 + r_a11 + r_a12
    
    # Conversion: 1.5 total power is enough to reach 100% confidence.
    data_confidence_pct = min(100, int((sum_rel / 1.5) * 100))
    missing_sources = []
    if r_a03 == 0: missing_sources.append("A03")
    if r_a10 == 0: missing_sources.append("A10")
    if r_a11 == 0: missing_sources.append("A11")
    if r_a12 == 0: missing_sources.append("A12")
    
    if data_confidence_pct >= 80:
        data_confidence = "HIGH"
    elif data_confidence_pct >= 50:
        data_confidence = "MEDIUM"
    else:
        data_confidence = "LOW"

    # ── Tính Divergence Score ─────────────────────────────────────────────────
    div = _tinh_divergence_score(a03, a10, a11, a12)
    score = float(div["divergence_score"])
    
    # ── PHASE 8: Divergence Score Half-Life Decay (§3.4 CONTEXT.md) ────────
    # If no new data is confirmed within 6h, decay score
    decay_applied = 0
    try:
        last_fresh_ts_raw = matrix.get("A05", "div_last_fresh_ts")
        has_fresh_data = any(
            d.get("_age_seconds", 99999) < 3600  # Data < 1h = fresh
            for d in [a03, a10, a11, a12]
            if isinstance(d, dict)
        )
        now_ts = int(time.time())
        
        if has_fresh_data:
            matrix.set("A05", "div_last_fresh_ts", str(now_ts), ttl=172800)
        elif last_fresh_ts_raw:
            last_fresh_ts = int(float(last_fresh_ts_raw))
            hours_since = (now_ts - last_fresh_ts) / 3600
            if hours_since > 6:
                decay = 0.95 ** (hours_since / 6)  # half-life ~80h
                old_score = score
                score = round(score * decay, 1)
                decay_applied = round((1 - decay) * 100, 1)
                log.warning(f"[DIVERGENCE] SCORE DECAY: {old_score:.1f}→{score:.1f} (-{decay_applied:.1f}%) | {hours_since:.1f}h since fresh data")
    except Exception as e_decay:
        log.debug(f"[DIVERGENCE] Score decay error (non-critical): {e_decay}")
    
    # ── PHASE 7: A05 Consumer Contract — Auto-Penalty Stale/Fallback ───────
    # Read Trinity Envelope is_fallback + stale_duration_hours from 4 agents
    # Apply penalty when any agent is in fallback or stale > 6h
    consumer_penalty = 0
    fallback_agents = []
    stale_agents = []
    try:
        for agent_key, label in [("SENTIMENT", "A03"), ("A10", "A10"), ("A11", "A11"), ("AEO", "A12")]:
            env_raw = matrix.get(agent_key, "latest" if agent_key == "A10" else ("intent" if agent_key == "A11" else ("last_report" if agent_key in ("AEO", "A12") else "latest")))
            if not env_raw:
                continue
            env = env_raw if isinstance(env_raw, dict) else {}
            if isinstance(env_raw, str):
                try:
                    env = json.loads(env_raw)
                except (json.JSONDecodeError, ValueError):
                    continue
            
            dq = env.get("data_quality", {})
            if dq.get("is_fallback"):
                fallback_agents.append(label)
                consumer_penalty += 0.05  # 5% per fallback agent
            if dq.get("stale_seconds", 0) > 21600:  # > 6h
                stale_agents.append(label)
                consumer_penalty += 0.08  # 8% per stale agent
        
        # Read stale_duration_hours specifically for A11 (Stale Escalation §3.5)
        a11_stale_h_raw = matrix.get("A11", "stale_duration_hours")
        if a11_stale_h_raw:
            a11_stale_h = float(a11_stale_h_raw)
            if a11_stale_h > 6:
                extra_penalty = min(0.3, a11_stale_h * 0.02)
                consumer_penalty += extra_penalty
                if "A11" not in stale_agents:
                    stale_agents.append("A11")
                log.warning(f"[DIVERGENCE] A11 STALE ESCALATION: {a11_stale_h:.1f}h → penalty +{extra_penalty:.0%}")
        
        if consumer_penalty > 0:
            consumer_penalty = min(consumer_penalty, 0.5)  # Cap 50% max penalty
            old_score = score
            score = round(score * (1 - consumer_penalty), 1)
            log.warning(f"[DIVERGENCE] CONSUMER CONTRACT PENALTY: {old_score:.1f}→{score:.1f} (-{consumer_penalty:.0%}) | Fallback:{fallback_agents} Stale:{stale_agents}")
    except Exception as e_consumer:
        log.debug(f"[DIVERGENCE] Consumer contract error (non-critical): {e_consumer}")
    
    # ── Additional analysis ─────────────────────────────────────────────────────
    intensity_trend = _tinh_intensity_trend(score)
    dominant_actor  = _tinh_dominant_actor(a03, a10)
    storm_window    = _tinh_storm_window(a11, score, div["conflict_type"])
    exit_critical   = _tinh_exit_critical(state, a10, a11, score)
    
    # ── Apply Graceful Degradation Penalty ──────────────────────────────────
    if data_confidence == "LOW":
        score = int(score * 0.7)  # Reduce power by 30%
        log.warning(f"[DIVERGENCE] DATA LOW CONFIDENCE {data_confidence_pct}% (Missing: {missing_sources}). Bóp score: {score}")
    elif data_confidence == "MEDIUM":
        score = int(score * 0.9)  # Reduce power by 10%
        log.warning(f"[DIVERGENCE] DATA MEDIUM CONFIDENCE {data_confidence_pct}% (Missing: {missing_sources}). Throttling score: {score}")
    else:
        log.info(f"[DIVERGENCE] DATA HIGH CONFIDENCE {data_confidence_pct}% - High quality data sources!")
        
    # ── Signal strength ───────────────────────────────────────────────────────
    if score >= 55:
        signal_strength = "STRONG"
    elif score >= 40:
        signal_strength = "MEDIUM"
    else:
        signal_strength = "WEAK"
    
    # ── Hunting recommendations ───────────────────────────────────────────────
    hunting_action = "WATCH"
    if state == "HUNTING":
        if score >= STORM_THRESHOLD_HIGH and div["conflict_type"] in (
            "SPRING_REVERSAL", "STEALTH_ACCUMULATION"
        ):
            hunting_action = "CANH_CHO_VAN_CO"
        elif score >= STORM_THRESHOLD_HIGH and div["conflict_type"] in (
            "TRAP_TOP", "ELITE_HEDGING_RETAIL_FOMO"
        ):
            hunting_action = "CHO_SPRING_SAU_TRAP"
        elif score >= STORM_THRESHOLD_MEDIUM:
            hunting_action = "QUAN_SAT_THEM"
        else:
            hunting_action = "TIEP_TUC_CHO"
    
    # ── Riding recommendations ────────────────────────────────────────────────
    riding_action = "HOLD"
    if state == "RIDING":
        if exit_critical:
            riding_action = "THOAT_NGAY"
        elif score >= 55 and a10["elite_flow"] == "DISTRIBUTE":
            riding_action = "CHOT_MOT_PHAN_T1"
        elif score >= 40 and intensity_trend == "RISING":
            riding_action = "GIAM_VIT_THE"
    
    # ── Helper function to filter LLM JSON ──────────────────────────────────────────
    def _extract_llm(snap: dict) -> str:
        if not isinstance(snap, dict): return ""
        # HingeEBM v6.5.1 Support
        if "narrative_lens" in snap and isinstance(snap["narrative_lens"], dict):
            snap = snap["narrative_lens"]
            
        exclude = {"Thong_Tin_Du_Lieu", "Dien_Giai_Ly_Thuyet", "full_snapshot", "_age_seconds", "psycho_raw", "macro_raw", "narrative_raw", "kinematics", "payload", "envelope", "summary"}
        res = []
        for k, v in snap.items():
            if k in exclude: continue
            # Get fields generated by LLM
            if isinstance(v, str) and len(v) > 15:
                res.append(f"[{k.upper()}]: {v}")
            elif isinstance(v, dict) and v:
                res.append(f"[{k.upper()}]: {json.dumps(v, ensure_ascii=False)}")
        return "\n".join(res)

    # ── Build DivergenceMatrix payload ───────────────────────────────────────
    matrix_payload = {
        "agent_id":           "DIVERGENCE_ENGINE",
        "timestamp_unix":     int(time.time()),
        "timestamp_readable": datetime.now(timezone.utc).isoformat(),
        "state":              state,
        
        # ── Core metrics ──
        "data_confidence":    f"{data_confidence} ({data_confidence_pct}%)",
        "missing_sources":    missing_sources,
        "divergence_score":   score,             # 0-100
        "intensity_trend":    intensity_trend,   # RISING | FALLING | STABLE
        "dominant_actor":     dominant_actor,    # ELITE | RETAIL | BALANCED
        "signal_strength":    signal_strength,   # STRONG | MEDIUM | WEAK
        "conflict_type":      div["conflict_type"],
        
        # ── Breakdown scores ──
        "score_breakdown": {
            "base":          div["base_score"],
            "intent_boost":  div["intent_boost"],
            "aeo_boost":     div["aeo_boost"],
            "mm_boost":      div["mm_boost"],
            "macro_boost":   div.get("macro_boost", 0),
            "cd_boost":      div.get("cd_boost", 0),
            "tpmi_boost":    div.get("tpmi_boost", 0),
        },
        
        # ── Conflict map (4 agent readings + 16D verdicts) ──
        "conflict_map": {
            "retail_sentiment":  a03["retail_state"],
            "retail_fear_greed": a03["fear_greed"],
            "retail_fear_greed_source": a03.get("fear_greed_source", "alternative.me"),
            "retail_positioning_greed": a03.get("positioning_greed", 50),
            "mm_fingerprint":    a03["mm_fingerprint"],
            "elite_flow":        a10["elite_flow"],
            "elite_power":       a10["elite_power"],
            "chu_ky_vi_mo":      a10.get("chu_ky", "NGAN"),
            "elite_intent":      a11["elite_intent"],
            "intent_confidence": a11["confidence"],
            "narrative_control": "AEO_ACTIVE" if a12["aeo_active"] else "ORGANIC",
            "financial_aeo":     a12["financial_aeo"],
            "aeo_beneficiary":   a12.get("beneficiary", ""),
            "tpmi":              a03.get("tpmi", {}),
            "con_so_cuoi_cung":  div.get("con_so_cuoi_cung", str(score)),
            # 16D Tensor verdicts
            "psycho_verdict":    a03.get("psycho_verdict", "NEUTRAL"),
            "macro_verdict":     a10.get("macro_verdict", "NORMAL"),
            "narrative_verdict": a12.get("narrative_verdict", "ORGANIC"),
        },
        
        # ── 16D Tensor raw sensor readings ──
        "tensor_16d": {
            "psycho":    a03.get("psycho_raw", {}),
            "macro":     a10.get("macro_raw", {}),
            "narrative": a12.get("narrative_raw", {}),
        },
        
        # ── Timing intelligence ──
        "storm_window": {
            "min_hours": storm_window["min_hours"],
            "max_hours": storm_window["max_hours"],
            "confidence": storm_window["confidence"],
            "source":     storm_window["source"],
            "human_readable": (
                f"{storm_window['min_hours']}-{storm_window['max_hours']}h"
                if storm_window["min_hours"] else "Unknown"
            ),
        },
        
        # ── Action recommendations ──
        "exit_critical":     exit_critical,
        "hunting_action":    hunting_action,
        "riding_action":     riding_action,
        
        # ── Evidence chain ──
        "evidence": {
            "a12_narratives_flagged": a12["payload"],
            "a11_exit_triggers":      a11.get("exit_triggers", [])[:3],
            "a03_media_narratives":   a03.get("narratives", [])[:3],
            "a10_cross_asset_confirmed": a10["cross_asset"],
        },

        # ── 6 Council of Elders Wisdome Collection (JSON) transmitted to Commander A05 ──
        "Bo_Lao_Tu_Van": {
            "A07_Apex": {
                "Thong_Tin_Du_Lieu": a07.get("Thong_Tin_Du_Lieu", ""),
                "Dien_Giai_Ly_Thuyet": a07.get("Dien_Giai_Ly_Thuyet", ""),
                "Nhan_Xet_Chuyen_Gia": _extract_llm(a07.get("full_snapshot", {}))
            },
            "A03_Psycho": {
                "Thong_Tin_Du_Lieu": a03.get("Thong_Tin_Du_Lieu", ""),
                "Dien_Giai_Ly_Thuyet": a03.get("Dien_Giai_Ly_Thuyet", ""),
                "Nhan_Xet_Chuyen_Gia": _extract_llm(a03.get("full_snapshot", {}))
            },
            "A04_PriceAction": {
                "Thong_Tin_Du_Lieu": a04.get("Thong_Tin_Du_Lieu", ""),
                "Dien_Giai_Ly_Thuyet": a04.get("Dien_Giai_Ly_Thuyet", ""),
                "Nhan_Xet_Chuyen_Gia": _extract_llm(a04.get("full_snapshot", {}))
            },
            "A10_MacroFlow": {
                "Thong_Tin_Du_Lieu": a10.get("Thong_Tin_Du_Lieu", ""),
                "Dien_Giai_Ly_Thuyet": a10.get("Dien_Giai_Ly_Thuyet", ""),
                "Nhan_Xet_Chuyen_Gia": _extract_llm(a10.get("full_snapshot", {}))
            },
            "A11_Intent": {
                "Thong_Tin_Du_Lieu": a11.get("Thong_Tin_Du_Lieu", ""),
                "Dien_Giai_Ly_Thuyet": a11.get("Dien_Giai_Ly_Thuyet", ""),
                "Nhan_Xet_Chuyen_Gia": _extract_llm(a11.get("full_snapshot", {}))
            },
            "A12_Media": {
                "Thong_Tin_Du_Lieu": a12.get("Thong_Tin_Du_Lieu", ""),
                "Dien_Giai_Ly_Thuyet": a12.get("Dien_Giai_Ly_Thuyet", ""),
                "Nhan_Xet_Chuyen_Gia": _extract_llm(a12.get("full_snapshot", {}))
            },
            "A08_SwarmOracle": {
                # ── Raw data ──
                "net_pressure": a08.get("net_pressure", 0),
                "crowd_sentiment": a08.get("crowd_sentiment", "NO_DATA"),
                "divergence_flag": a08.get("divergence_flag", "NO_DATA"),
                "cascade_narrative": a08.get("cascade_narrative", "[NO_DATA] A08 Swarm Oracle has not started."),
                "tier_breakdown": a08.get("tier_breakdown", {}),
                "prediction_history": a08.get("prediction_history", []),
                # ── Methodology metadata for A05 ──
                "methodology_note": (
                    "[A08 FIDELITY: ~62%] Simulating 1,000,000 financial individuals across 6 tiers. "
                    "STRONG: Sentiment & Crowd Behavior (~75%). WEAK: Tick-level microstructure & cross-asset macro. "
                    "CYCLE: 1h/round — insensitive to shocks < 1h. "
                    "STRONGEST SPOT: Detecting DIVERGENCE smart money vs retail (pattern accuracy ~75%)."
                ),
                "net_pressure_guide": (
                    "> +0.3: Strong FOMO → short-term peak warning | "
                    "+0.1 to +0.3: Slight buy bias | "
                    "-0.1 to +0.1: Hesitation — no action | "
                    "-0.1 to -0.3: Slight sell bias | "
                    "< -0.3: PANIC → contrarian signal to find bottom"
                ),
                "divergence_guide": (
                    "APEX_VS_RETAIL=TRAP_TOP(75%) | "
                    "RETAIL_VS_APEX=SPRING(70%) | "
                    "CONSENSUS_BULL=momentum(60%)/peak(40%) | "
                    "CONSENSUS_BEAR=capitulation | "
                    "MIXED=low_weight"
                )
            }
        },
        
        # ── Algorithm summary shorthand for A05 LLM (antihallucination) ──
        "algo_summary": {
            "A07": f"ACDI={a07.get('full_snapshot', {}).get('algo_core', {}).get('apex_crisis_detonator_index', '?')}|Cash={a07.get('full_snapshot', {}).get('algo_core', {}).get('elite_cash_allocation_ratio', '?')}",
            "A03": f"PSYCHO={a03.get('psycho_verdict','?')}|F&G={a03.get('fear_greed','?')}|MM={a03.get('mm_fingerprint','?')}|State={a03.get('retail_state','?')}",
            "A04": f"{a04.get('wyckoff','?')}|E:{a04.get('elliott','?')}|VSA:{a04.get('vsa_label','?')}|KAR={a04.get('kinematics',{}).get('KAR','?')}|MNR={a04.get('kinematics',{}).get('MNR','?')}|CA={a04.get('kinematics',{}).get('CA','?')}",
            "A10": f"MACRO={a10.get('macro_verdict','?')}|red={a10.get('red_count','?')}|Elite={a10.get('elite_flow','?')}|Power={a10.get('elite_power','?')}|Cycle={a10.get('chu_ky','?')}",
            "A11": f"Intent={a11.get('elite_intent','?')}|Conf={a11.get('confidence','?')}|Label={a11.get('label','?')}",
            "A12": f"AEO={a12.get('aeo_label','?')}|Score={a12.get('aeo_score','?')}|Financial={a12.get('financial_aeo','?')}|Verdict={a12.get('narrative_verdict','?')}",
            "A08": f"Swarm={a08.get('crowd_sentiment','?')}|Net={a08.get('net_pressure','?')}|Div={a08.get('divergence_flag','?')}|Pop={a08.get('population','?')}",
        },
        "algo_glossary": (
            "KAR=Kinematics Absorption Ratio (liquidity absorption ratio)|"
            "MNR=Micro Noise Ratio (micro noise ratio)|"
            "CA=Cumulative Action (cumulative action)|"
            "F&G=Fear & Greed Index (fear/greed index)|"
            "AEO=Artificial Editorial Operations (AI editorial manipulation)|"
            "MM=Market Maker Fingerprint (market maker fingerprint)|"
            "GEO=Geopolitical Risk Score|"
            "COT=Commitment of Traders|"
            "VSA=Volume Spread Analysis|"
            "PSYCHO=Psycho-Kinematic Verdict (psycho-kinematic verdict)|"
            "A08_NET=Net Pressure [-1→+1]: Aggregated behavior with capital weighting of 6 virtual trader tiers|"
            "A08_DIV=Divergence Flag: APEX_VS_RETAIL=peak trap, RETAIL_VS_APEX=bottom opportunity|"
            "A08_CASCADE=Propagation mechanism: APEX decides first with influence=3.0x, RETAIL affected last with 0.3x|"
            "A08_FIDELITY=~62% compared to reality: strong on crowd sentiment, weak on tick-by-tick microstructure"
        )
    }
    
    # ── Publish to Matrix ────────────────────────────────────────────────────
    try:
        # DNA v17.0: Push divergence blocks straight into XADD stream for A05 to XREAD
        matrix.xadd("A05", "divergence_stream", {"payload": json.dumps(matrix_payload, ensure_ascii=False)}, maxlen=5)
        log.info(
            f"[DIVERGENCE] Score={score:.0f} | {div['conflict_type']} | "
            f"Trend={intensity_trend} | Exit_critical={exit_critical}"
        )
    except Exception as e:
        log.error(f"Publish divergence matrix lỗi: {e}")
    
    return matrix_payload





def get_latest_matrix(state: str = "HUNTING") -> dict:
    """
    Reads the latest matrix from Matrix (no recomputation).
    """
    try:
        res = matrix.xrevrange("A05", "divergence_stream", count=1)
        if not res: 
            return compute_and_publish(state)
        _, fields = res[0]
        # Safely handle when payload can be bytes or decoded to str:
        raw_payload = fields.get(b"payload") or fields.get("payload", "{}")
        if isinstance(raw_payload, bytes):
            payload = raw_payload.decode('utf-8')
        else:
            payload = str(raw_payload)
        return json.loads(payload)
    except Exception as e:
        log.error(f"Error retrieving Divergence Stream: {e}")
        return compute_and_publish(state)
