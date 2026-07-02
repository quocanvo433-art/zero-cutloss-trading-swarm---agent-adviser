"""
🧬 DNA: v1.2 (Swarm Oracle Engine)
🏢 UNIT: SWARM_ORACLE (A08)
🛠️ ROLE: MARKET_SIMULATOR
📖 DESC: Simulate 1 million financial individuals via Sequential Cascade. 16 LLM calls + 999,984 state machines.
         v1.1: Information Asymmetry — each tier receives different data via TIER_VISIBLE_FIELDS.
         v1.2: Agent-Agent Cascade — CascadeContext replaces scalar crowd_pressure.
              Consensus/momentum amplify RETAIL herd, dampen APEX contrarian.
🔗 CALLS: tools/llm_router.py, tools/imperial_state.py, a08_market_agents.py
📟 I/O: Redis: zcl:a08:swarm_prediction, zcl:a08:tier_breakdown, zcl:a08:heartbeat
🛡️ INTEGRITY: Cascade-Purity, State-Machine-First, Information-Asymmetry, Agent-Interaction
"""

import sys
import json
import time
import re
import logging
import threading
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))
sys.path.insert(0, str(BASE_DIR / "agents" / "logic"))

try:
    from llm_router import _call_algo, ALGO_CYCLE_INTERVAL_SEC
    from imperial_state import matrix
except ImportError:
    # Fallback/Mock for local testing if not fully integrated
    ALGO_CYCLE_INTERVAL_SEC = 3600
    def _call_algo(prompt: str, agent_id: str, label: str, temp: float, tier: str = "ALGO") -> str:
        return '{"action": "HOLD", "conviction": 0, "reasoning": "mock"}'
    class MockMatrix:
        def __init__(self):
            self.client = self
        def get(self, ns, key): return None
        def set(self, ns, key, val, ex=None): pass
        def xrevrange(self, stream, key, count=1): return []
        def hget(self, key, field): return None
        def lpush(self, key, val): pass
        def ltrim(self, key, start, stop): pass
        def expire(self, key, ttl): pass
    matrix = MockMatrix()

from a08_market_agents import (
    init_population, agent_decide_sm, aggregate_tier, detect_divergence,
    compute_cascade_context, CascadeContext,
    Decision, SwarmPrediction, TIER_CONFIG, LLM_PERSONAS, TIER_VISIBLE_FIELDS,
    PositionTranche, PortfolioAllocation,
    apex_portfolio_sm, hft_portfolio_sm, smart_portfolio_sm
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("A08_ENGINE")

TIER_ORDER = ["APEX", "HFT", "QUANT", "PASSIVE", "SMART_CONTRARIAN", "SMART_VALUE", "SEMI_SMART", "RETAIL_FOMO", "RETAIL_FUD", "RETAIL_LEVERAGE"]

def read_market_state() -> dict:
    state = {
        "price": 0.0,
        "change_24h": 0.0,
        "volume_24h": 0.0,
        "funding_rate": 0.0,
        "open_interest": 0.0,
        "fear_greed": 50,
        "mm_score": 0.0,
        "elite_flow": "NEUTRAL",
        "intent_summary": "No clear intent"
    }
    try:
        def _safe_parse(raw):
            if raw is None: return {}
            if isinstance(raw, dict): return raw
            try: return json.loads(raw)
            except: return {}

        def _safe_float(val, default=0.0):
            try: return float(val) if val is not None else default
            except: return default

        def _safe_int(val, default=0):
            try: return int(val) if val is not None else default
            except: return default

        # ── 1. PRICE + 24H DATA: A01 Hound realtime ─────────────────────
        try:
            a01_raw = matrix.get("a01", "realtime")
            if a01_raw:
                a01 = _safe_parse(a01_raw)
                state["price"] = _safe_float(a01.get("current_price", a01.get("gia_hien_tai", 0.0)))
                state["change_24h"] = _safe_float(a01.get("change_24h_pct", a01.get("bien_dong_24h_pct", 0.0)))
                state["volume_24h"] = _safe_float(a01.get("volume_24h_usdt", a01.get("khoi_luong_24h_usdt", 0.0)))
                oi_raw = a01.get("open_interest", {})
                state["open_interest"] = _safe_float(oi_raw.get("current_oi", oi_raw.get("oi_hien_tai", 0.0))) if isinstance(oi_raw, dict) else _safe_float(oi_raw)
                fr_raw = a01.get("ty_le_long_short", {})
                state["funding_rate"] = _safe_float(fr_raw.get("ls_ratio", fr_raw.get("ti_le_ls", 0.0))) if isinstance(fr_raw, dict) else _safe_float(fr_raw)
            else:
                # Fallback: HASH zcl:system:latest_prices
                price_raw = matrix.client.hget("zcl:system:latest_prices", "BTC/USDT")
                if price_raw:
                    price_data = _safe_parse(price_raw)
                    state["price"] = _safe_float(price_data.get("price", price_data.get("gia", 0.0)))
                    state["open_interest"] = _safe_float(price_data.get("oi", 0.0))
        except Exception as e_price:
            log.debug(f"[A08] Price read error: {e_price}")

        # ── 2. SENTIMENT: STRING key zcl:sentiment:latest ──
        # Tách fear_greed (Alt.me sentiment) và positioning_greed (Binance L/S)
        sentiment_raw = matrix.get("sentiment", "latest")
        sentiment = _safe_parse(sentiment_raw)
        algo_core = sentiment.get("algo_core", {})
        if algo_core:
            # Ưu tiên fear_greed trực tiếp từ A03 (không derive từ fomo_index)
            fg_direct = algo_core.get("fear_greed")
            if fg_direct is not None:
                state["fear_greed"] = _safe_int(fg_direct, 50)
            else:
                # Fallback: derive từ fomo_index (legacy)
                fomo = _safe_float(algo_core.get("fomo_index", 0.0))
                state["fear_greed"] = int((fomo * 50) + 50)
            
            # Positioning greed (Binance L/S) — tín hiệu riêng biệt
            pos_greed = algo_core.get("positioning_greed")
            state["positioning_greed"] = _safe_int(pos_greed, 50) if pos_greed is not None else None
            state["fg_source"] = algo_core.get("fear_greed_source", "derived")
            
            state["mm_score"] = _safe_float(algo_core.get("mm_score", 0.0))
        else:
            # Fallback Trinity cũ
            state["fear_greed"] = _safe_int(
                sentiment.get("fear_greed", sentiment.get("fear_greed_index", sentiment.get("chi_so_tham_lam", 50))), 50
            )
            state["positioning_greed"] = None
            state["fg_source"] = "legacy"
            mm_data = sentiment.get("mm_fingerprint", {})
            if isinstance(mm_data, dict):
                state["mm_score"] = _safe_float(mm_data.get("score_after_elite", mm_data.get("score_sau_elite", mm_data.get("score", 0.0))))
            else:
                state["mm_score"] = 0.0
        
        # Derive elite_flow from mm_score (A03 Chronicle):
        #   mm_score > 30 -> Elite distributing (DISTRIBUTE)
        #   mm_score < 10 -> Elite accumulating silently -> ACCUMULATE
        #   10–30 -> NEUTRAL
        mm = state["mm_score"]
        if mm > 30.0:
            state["elite_flow"] = "DISTRIBUTE"  # UTAD trap / distribution top
        elif mm < 10.0 and mm > 0:
            state["elite_flow"] = "ACCUMULATE"  # Accumulating silently "silence week"
        elif fomo > 0.3:
            state["elite_flow"] = "DISTRIBUTE"
        elif fomo < -0.3:
            state["elite_flow"] = "ACCUMULATE"

        # ── 3. EMF SIGNALS: STREAM zcl:emf:signals:scored ──
        try:
            emf_entries = matrix.xrevrange("EMF", "signals:scored", count=1)
            if emf_entries:
                _, entry_data = emf_entries[0]
                if isinstance(entry_data, dict):
                    # Extract confidence field containing elite flow label directly
                    raw_conf = entry_data.get(b"confidence", entry_data.get("confidence"))
                    if raw_conf:
                        if isinstance(raw_conf, bytes): raw_conf = raw_conf.decode("utf-8", errors="replace")
                        conf_dict = _safe_parse(raw_conf)
                        elite = conf_dict.get("label")
                        if elite:
                            state["elite_flow"] = str(elite)
                    else:
                        # Fallback: Extract from payload field
                        raw_payload = entry_data.get(b"payload", entry_data.get("payload"))
                        if raw_payload:
                            if isinstance(raw_payload, bytes): raw_payload = raw_payload.decode("utf-8", errors="replace")
                            payload_dict = _safe_parse(raw_payload)
                            elite = payload_dict.get("algo_core", {}).get("expert_metrics", {}).get("flow_direction")
                            if elite:
                                state["elite_flow"] = str(elite)
        except Exception as e_emf:
            log.debug(f"[A08] EMF scored read error: {e_emf}")

        # ── 4. EMF INTENT: STREAM zcl:emf:intent:report ──
        try:
            intent_entries = matrix.xrevrange("EMF", "intent:report", count=1)
            if intent_entries:
                _, entry_data = intent_entries[0]
                if isinstance(entry_data, dict):
                    # Extract from payload field (contains JSON string of intent)
                    raw_payload = entry_data.get(b"payload", entry_data.get("payload"))
                    if raw_payload:
                        if isinstance(raw_payload, bytes): raw_payload = raw_payload.decode("utf-8", errors="replace")
                        payload_dict = _safe_parse(raw_payload)
                        summary = payload_dict.get("narrative_lens", {}).get("summary", "")
                        if summary:
                            state["intent_summary"] = str(summary)[:300]
                            
                            # Extract elite intent label from A11 and assign to elite_flow
                            if "|" in summary:
                                parts = summary.split("|")
                                if len(parts) >= 2:
                                    elite_lbl = parts[1].strip().upper().replace("_DATA_RECENTLY", "")
                                    if elite_lbl in ("ACCUMULATE", "DISTRIBUTE", "NEUTRAL", "HEDGE"):
                                        state["elite_flow"] = elite_lbl
                                        
                        # Fallback: Direct access to A11 nested JSON structure
                        report_data = payload_dict.get("algo_core", {}).get("expert_metrics", {}).get("report", {})
                        if report_data:
                            if isinstance(report_data, str):
                                try: report_data = json.loads(report_data)
                                except: report_data = {}
                            intent_data = report_data.get("intent", {})
                            if isinstance(intent_data, str):
                                try: intent_data = json.loads(intent_data)
                                except: intent_data = {}
                            elite = intent_data.get("label")
                            if elite:
                                elite_str = str(elite).upper().replace("_DATA_RECENTLY", "")
                                if elite_str in ("ACCUMULATE", "DISTRIBUTE", "NEUTRAL", "HEDGE"):
                                    state["elite_flow"] = elite_str
        except Exception as e_intent:
            log.debug(f"[A08] EMF intent read error: {e_intent}")

        # ── 5. APEX ONLY: Chronicle insight từ A05 + Divergence narrative ──
        try:
            compiled_raw = matrix.get("A05", "compiled_insight")
            compiled = _safe_parse(compiled_raw)
            state["chronicle_insight"] = str(compiled)[:500] if compiled else ""
        except Exception:
            state["chronicle_insight"] = ""

        try:
            div_entries = matrix.xrevrange("A05", "divergence_stream", count=1)
            if div_entries:
                _, entry_data = div_entries[0]
                if isinstance(entry_data, dict):
                    narr = entry_data.get(b"narrative", entry_data.get("narrative", ""))
                    if isinstance(narr, bytes): narr = narr.decode("utf-8", errors="replace")
                    state["divergence_narrative"] = str(narr)[:300]
            else:
                state["divergence_narrative"] = ""
        except Exception:
            state["divergence_narrative"] = ""

        # ── 6. 1-MONTH KNOWLEDGE COMPRESSION ANCHORS ──
        from pathlib import Path
        anchor_dir = Path(__file__).resolve().parent.parent.parent / "agentic" / "knowledge"
        
        anchor_maps = {
            "macro_flow_anchor": "a10_macro_flow_anchor.md",
            "intent_anchor": "a11_intent_anchor.md",
            "quant_anchor": "a04_longterm_flow_analysis.md",
            "psycho_anchor": "a03_longterm_flow_analysis.md",
            "narrative_anchor": "a12_narrative_anchor.md"
        }
        
        for key, filename in anchor_maps.items():
            filepath = anchor_dir / filename
            if filepath.exists():
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Limit to ~3000 chars per anchor to save context window
                        state[key] = content[:3000] + ("\n...[TRUNCATED]" if len(content) > 3000 else "")
                except Exception as e_anchor:
                    log.debug(f"[A08] Failed to read anchor {filename}: {e_anchor}")
                    state[key] = ""
            else:
                state[key] = ""

        # ── 7. REAL-TIME A04 STATE (quant_realtime) ──
        state["quant_realtime"] = ""
        try:
            a04_raw = matrix.get("A04", "latest")
            if a04_raw:
                a04_latest = _safe_parse(a04_raw)
                algo = a04_latest.get("algo_core", {})
                narrative = a04_latest.get("narrative_lens", {})
                metrics = algo.get("expert_metrics", {})
                
                # Extract derivatives information & quantize liquidation bait
                fut = metrics.get("futures", {})
                suff = metrics.get("sufficiency_report", {})
                
                suff_str = ""
                if suff:
                    suff_str = (
                        f"    Bottom Maturity Score: {suff.get('bottom_maturity_score', 0.0):.4f}\n"
                        f"    Top Maturity Score: {suff.get('top_maturity_score', 0.0):.4f}\n"
                        f"    OI Flush Ratio: {suff.get('oi_flush_ratio_pct', 100.0):.2f}%\n"
                        f"    Absorption (Bottom/Top): {suff.get('abs_rate_bottom', 0.0):.4f} / {suff.get('abs_rate_top', 0.0):.4f}\n"
                        f"    POC Trapped Price: ${suff.get('poc_price', 0.0):,.2f}"
                    )
                else:
                    suff_str = "    Sufficiency metrics: N/A"

                is_a04_fallback = metrics.get("is_fallback", False)
                if not is_a04_fallback:
                    state["quant_realtime"] = (
                        f"A04 REALTIME WYCKOFF & VSA REPORT (Updated: {algo.get('ts', '?')}):\n"
                        f"  Spot Wyckoff Phase: {algo.get('wyckoff_phase', 'UNKNOWN')} | Spot VSA Label: {algo.get('vsa_label', 'UNKNOWN')}\n"
                        f"  Futures Wyckoff Phase: {fut.get('wyckoff_phase', 'UNKNOWN')} | Futures VSA Label: {fut.get('vsa_label', 'UNKNOWN')}\n"
                        f"  Elliott Wave: {metrics.get('elliott', 'UNKNOWN')}\n"
                        f"  Liquidity Sufficiency:\n{suff_str}\n"
                        f"  Reality Check: {narrative.get('reality_check', 'N/A')}\n"
                        f"  Recent Milestones (1D): {metrics.get('milestone_ngay', 'N/A')}\n"
                        f"  Recent Milestones (1H): {metrics.get('milestone_gio', 'N/A')}"
                    )
        except Exception as e_realtime:
            log.debug(f"[A08] Failed to read real-time A04 state: {e_realtime}")

        # ── 8. REAL-TIME A03 STATE (psycho_realtime) ──
        state["psycho_realtime"] = ""
        try:
            a03_raw = matrix.get("SENTIMENT", "latest") or matrix.get("sentiment", "latest")
            if a03_raw:
                a03_latest = _safe_parse(a03_raw)
                algo = a03_latest.get("algo_core", {})
                narrative = a03_latest.get("narrative_lens", {})
                metrics = algo.get("expert_metrics", {})
                is_a03_fallback = metrics.get("is_fallback", False)
                if not is_a03_fallback:
                    state["psycho_realtime"] = (
                        f"A03 REALTIME SENTIMENT & PSYCHO REPORT (Updated: {algo.get('ts', '?')}):\n"
                        f"  MM Score: {algo.get('mm_score', 0.0):.1f} | Fomo Index: {algo.get('fomo_index', 0.0):.2f}\n"
                        f"  Sentiment Summary: {narrative.get('summary', 'N/A')}\n"
                        f"  Expert Verdict: {narrative.get('story', 'N/A')[:1000]}"
                    )
        except Exception as e_realtime:
            log.debug(f"[A08] Failed to read real-time A03 state: {e_realtime}")

        # ── 9. REAL-TIME A10 STATE (macro_realtime) ──
        state["macro_realtime"] = ""
        try:
            a10_raw = matrix.get("A10", "latest_macro_narrative")
            if a10_raw:
                a10_latest = _safe_parse(a10_raw)
                algo = a10_latest.get("algo_core", {})
                narrative = a10_latest.get("narrative_lens", {})
                metrics = algo.get("expert_metrics", {})
                is_a10_fallback = metrics.get("is_fallback", False)
                if not is_a10_fallback:
                    state["macro_realtime"] = (
                        f"A10 REALTIME MACRO FLOW REPORT (Updated: {algo.get('ts', '?')}):\n"
                        f"  Smart Money Inflow: {algo.get('smart_money_flow', 0.0):,.0f} | Alert Level: {algo.get('alert_level', 0)}\n"
                        f"  Macro Summary: {narrative.get('summary', 'N/A')}\n"
                        f"  Elite Action: {narrative.get('elite_action', 'N/A')}\n"
                        f"  Macro Flow: {narrative.get('a10_story', 'N/A')[:1000]}"
                    )
        except Exception as e_realtime:
            log.debug(f"[A08] Failed to read real-time A10 state: {e_realtime}")

        # ── 10. REAL-TIME A11 STATE (intent_realtime) ──
        state["intent_realtime"] = ""
        try:
            a11_raw = matrix.get("A11", "intent")
            if a11_raw:
                a11_latest = _safe_parse(a11_raw)
                algo = a11_latest.get("algo_core", {})
                narrative = a11_latest.get("narrative_lens", {})
                metrics = algo.get("expert_metrics", {})
                is_a11_fallback = metrics.get("is_fallback", False)
                if not is_a11_fallback:
                    state["intent_realtime"] = (
                        f"A11 REALTIME INTENT & ANOMALY REPORT (Updated: {algo.get('ts', '?')}):\n"
                        f"  Composite Score: {algo.get('composite_score', 0.0):.2f} | Scenario: {algo.get('scenario_type', 'N/A')} (Confidence: {algo.get('scenario_confidence', 0.0):.2f})\n"
                        f"  Intent Summary: {narrative.get('summary', 'N/A')}\n"
                        f"  System Coherence: {metrics.get('coherence_score', 0.0):.3f} | PDI Label: {metrics.get('pdi_label', 'N/A')}\n"
                        f"  Story Analysis: {narrative.get('a11_story', 'N/A')[:1000]}"
                    )
        except Exception as e_realtime:
            log.debug(f"[A08] Failed to read real-time A11 state: {e_realtime}")

        # ── 11. REAL-TIME A12 STATE (narrative_realtime) ──
        state["narrative_realtime"] = ""
        try:
            a12_raw = matrix.get("AEO", "last_report")
            if a12_raw:
                a12_latest = _safe_parse(a12_raw)
                algo = a12_latest.get("algo_core", {})
                narrative = a12_latest.get("narrative_lens", {})
                metrics = algo.get("expert_metrics", {})
                is_a12_fallback = metrics.get("is_fallback", False)
                if not is_a12_fallback:
                    state["narrative_realtime"] = (
                        f"A12 REALTIME NARRATIVE & STATE REPORT (Updated: {algo.get('ts', '?')}):\n"
                        f"  AEO Score: {algo.get('aeo_score', 0.0):.3f} | Verdict: {algo.get('verdict', 'ORGANIC')} (Confidence: {algo.get('confidence', 0.0):.2f})\n"
                        f"  Financial AEO Confirmed: {algo.get('financial_aeo_confirmed', False)}\n"
                        f"  Narrative Summary: {narrative.get('summary', 'N/A')}\n"
                        f"  Payload Hypothesis: {narrative.get('payload_hypothesis', 'N/A')} | Beneficiary: {narrative.get('beneficiary', 'N/A')}\n"
                        f"  Narrative Analysis: {narrative.get('a12_story', 'N/A')[:1000]}"
                    )
        except Exception as e_realtime:
            log.debug(f"[A08] Failed to read real-time A12 state: {e_realtime}")

        pos = state.get('positioning_greed')
        pos_str = f"Pos={pos}" if pos is not None else "Pos=N/A"
        log.info(f"[A08] Market state: BTC=${state['price']:,.0f} | F&G={state['fear_greed']}({state.get('fg_source','?')}) | {pos_str} | MM={state['mm_score']} | Flow={state['elite_flow']}")

    except Exception as e:
        log.warning(f"Error reading market state, using defaults: {e}")
    return state

def get_current_session() -> str:
    hour = datetime.now(timezone.utc).hour
    if 0 <= hour < 8:
        return "ASIA"
    elif 8 <= hour < 16:
        return "EU"
    else:
        return "US"

def build_market_prompt(market_state: dict, persona: dict, previous_decisions: dict) -> str:
    """Build prompt with Information Asymmetry: each tier only receives appropriate data subset."""
    tier = persona.get("tier", "RETAIL")
    visible_fields = TIER_VISIBLE_FIELDS.get(tier, ["price", "change_24h"])
    
    prompt = f"[SYSTEM] {persona.get('system_prompt', '')}\n\n[MARKET DATA AVAILABLE TO YOU]\n"
    
    # Inject only fields visible to this tier
    field_labels = {
        "price": f"Price: ${market_state.get('price', 0)}",
        "change_24h": f"24h Change: {market_state.get('change_24h', 0)}%",
        "volume_24h": f"Volume 24h: ${market_state.get('volume_24h', 0):,.0f}",
        "funding_rate": f"Funding Rate: {market_state.get('funding_rate', 0)}",
        "open_interest": f"Open Interest: ${market_state.get('open_interest', 0):,.0f}",
        "fear_greed": f"Fear & Greed Index: {market_state.get('fear_greed', 50)}/100",
        "elite_flow": f"Institutional Flow: {market_state.get('elite_flow', 'N/A')}",
        "intent_summary": f"Market Narrative: {market_state.get('intent_summary', 'N/A')}",
        "chronicle_insight": f"Long-term Analysis (Agent Council): {market_state.get('chronicle_insight', 'N/A')}",
        "divergence_narrative": f"Inter-Agent Divergence: {market_state.get('divergence_narrative', 'N/A')}",
        "quant_realtime": f"Real-time A04 Quant Report:\n{market_state.get('quant_realtime', 'N/A')}",
        "macro_realtime": f"Real-time A10 Macro Flow Report:\n{market_state.get('macro_realtime', 'N/A')}",
        "intent_realtime": f"Real-time A11 Intent & Anomaly Report:\n{market_state.get('intent_realtime', 'N/A')}",
        "psycho_realtime": f"Real-time A03 Sentiment & Psycho Report:\n{market_state.get('psycho_realtime', 'N/A')}",
        "narrative_realtime": f"Real-time A12 Narrative & State Report:\n{market_state.get('narrative_realtime', 'N/A')}",
    }
    
    for field in visible_fields:
        # Ignore anchors here, they will be rendered in a separate block
        if field in field_labels and market_state.get(field) and not field.endswith("_anchor"):
            prompt += f"  {field_labels[field]}\n"

    # Inject Long-term Memory Anchors (1-Month Compression)
    anchors_to_inject = [f for f in visible_fields if f.endswith("_anchor") and market_state.get(f)]
    if anchors_to_inject:
        prompt += "\n[LONG-TERM MEMORY (1-MONTH KNOWLEDGE COMPRESSION)]\n"
        for anchor_field in anchors_to_inject:
            anchor_name = anchor_field.replace("_anchor", "").replace("_", " ").upper()
            prompt += f"--- {anchor_name} MEMORY ---\n{market_state[anchor_field]}\n\n"
    
    # APEX + SMART receive previous tier decisions
    if tier in ("APEX", "SMART_CONTRARIAN", "SMART_VALUE", "SEMI_SMART", "QUANT"):
        prompt += "[PREVIOUS TIER DECISIONS]\n"
        for t, dec in previous_decisions.items():
            prompt += f"{t}: {dec['action']} (conviction: {dec['conviction']}) — {dec['reasoning']}\n"
        if not previous_decisions:
            prompt += "None (You are the first to act).\n"
    # RETAIL does not see decisions of other tiers
    elif tier in ("RETAIL_FOMO", "RETAIL_FUD", "RETAIL_LEVERAGE"):
        prompt += "\n[NOTE] You have no access to institutional or smart money positioning.\n"
    
    if tier == "APEX":
        prompt += (
            "\n[YOUR PORTFOLIO ALLOCATION]\n"
            "You manage a $50B fund. You MUST distribute capital across MULTIPLE simultaneous positions.\n"
            "Return JSON ONLY:\n"
            '{\"dominant_action\": \"ACCUMULATE|DISTRIBUTE|HOLD|HEDGE\",'
            ' \"tranches\": ['
            '{\"label\": \"name\", \"side\": \"LONG|SHORT|FLAT\", \"allocation_pct\": 0-100, '
            '\"method\": \"MARKET|ICEBERG|LIMIT|DARK_POOL|DCA\", '
            '\"entry_zone\": \"$XXk-$XXk\", \"conviction\": 0-100, '
            '\"time_horizon\": \"1H|4H|1D|1W|1M\"}'
            ', ...], \"reasoning\": \"max 150 words\"}\n'
            "RULES: Total allocation_pct MUST = 100. NEVER go 100% one direction. Always hedge + reserve.\n"
            "Conviction > 90 is EXTREMELY RARE. You are a predator, not a gambler."
        )
    else:
        prompt += "\n[YOUR DECISION]\nReturn JSON only: {\"action\": \"BUY/SELL/HOLD\", \"conviction\": 0-100, \"reasoning\": \"max 100 words\"}"
    return prompt

def parse_llm_response(raw: str) -> Decision:
    try:
        match = re.search(r'\{.*\}', raw.replace('\n', ''), re.IGNORECASE | re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return Decision(
                action=str(data.get("action", "HOLD")).upper(),
                conviction=float(data.get("conviction", 0)),
                reasoning=str(data.get("reasoning", ""))
            )
    except Exception as e:
        log.error(f"Failed to parse LLM response: {e}")
    return Decision("HOLD", 0, "PARSE_ERROR")

def parse_portfolio_response(raw: str) -> PortfolioAllocation:
    """Parse LLM response into PortfolioAllocation. Fallback to Decision if legacy format."""
    try:
        match = re.search(r'\{.*\}', raw.replace('\n', ''), re.IGNORECASE | re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            
            # Check if new portfolio format
            if "tranches" in data and isinstance(data["tranches"], list):
                tranches = []
                for t in data["tranches"]:
                    tranches.append(PositionTranche(
                        label=str(t.get("label", "UNKNOWN")),
                        side=str(t.get("side", "FLAT")).upper(),
                        allocation_pct=float(t.get("allocation_pct", 0)),
                        method=str(t.get("method", "MARKET")),
                        entry_zone=str(t.get("entry_zone", "MARKET")),
                        conviction=float(t.get("conviction", 0)),
                        time_horizon=str(t.get("time_horizon", "1D")),
                        reasoning=str(t.get("reasoning", ""))
                    ))
                
                # Calculate net exposure
                net = sum(
                    (t.allocation_pct / 100.0 if t.side == "LONG" else
                     -t.allocation_pct / 100.0 if t.side == "SHORT" else 0.0)
                    for t in tranches
                )
                
                return PortfolioAllocation(
                    tier="APEX",
                    tranches=tranches,
                    net_exposure=round(net, 4),
                    dominant_action=str(data.get("dominant_action", "HOLD")).upper(),
                    reasoning=str(data.get("reasoning", ""))
                )
            
            # Fallback: legacy Decision format -> wrap into simple portfolio
            action = str(data.get("action", "HOLD")).upper()
            conv = float(data.get("conviction", 0))
            reasoning = str(data.get("reasoning", ""))
            side = "LONG" if action == "BUY" else ("SHORT" if action == "SELL" else "FLAT")
            net = conv / 100.0 if side == "LONG" else (-conv / 100.0 if side == "SHORT" else 0.0)
            
            return PortfolioAllocation(
                tier="APEX",
                tranches=[PositionTranche(
                    label="LLM_SINGLE", side=side, allocation_pct=conv,
                    method="MARKET", entry_zone="MARKET",
                    conviction=conv, time_horizon="1D", reasoning=reasoning
                )],
                net_exposure=round(net, 4),
                dominant_action=action,
                reasoning=reasoning
            )
    except Exception as e:
        log.error(f"Failed to parse portfolio response: {e}")
    
    # Total failure -> return neutral portfolio
    return PortfolioAllocation(
        tier="APEX", tranches=[
            PositionTranche("PARSE_ERROR", "FLAT", 100, "N/A", "N/A", 0, "N/A", "PARSE_ERROR")
        ],
        net_exposure=0.0, dominant_action="HOLD", reasoning="PARSE_ERROR"
    )

# ── Margin Simulation Config ──
PERSONA_LEVERAGE = {
    "RETAIL_LEVERAGE": 20.0,
    "RETAIL_FOMO": 10.0,
    "RETAIL_FUD": 3.0,
    "HFT_LONG_BOT": 5.0,
    "HFT_SHORT_BOT": 5.0,
    "SMART_SWING": 3.0,
    "SEMI_SMART": 5.0,
    "SMART_CONTRARIAN": 3.0,
    "SMART_VALUE": 1.0,
}

GLOBAL_TIER_RESULTS = {}
GLOBAL_PREVIOUS_DECISIONS = {}
IS_POSITIONS_INITIALIZED = False

def calculate_liquidation_price(side: str, entry_price: float, leverage: float) -> float:
    if leverage <= 1.0 or entry_price <= 0:
        return 0.0
    maintenance_margin = 0.05  # 5% mandatory maintenance margin
    if side == "LONG":
        return entry_price * (1.0 - (1.0 / leverage) + maintenance_margin)
    elif side == "SHORT":
        return entry_price * (1.0 + (1.0 / leverage) - maintenance_margin)
    return 0.0

def init_agent_positions(population: list):
    for agent in population:
        agent.position_size = 0.0
        agent.entry_price = 0.0
        agent.liq_price = 0.0
        agent.leverage = PERSONA_LEVERAGE.get(agent.persona_name, 1.0)
        agent.position_side = "HOLD"
        agent.trauma_index = 0.0
        agent.pyramid_count = 0

def simulate_liquidations(population: list, current_price: float) -> float:
    """Check and execute leveraged liquidations first. Returns forced_pressure [-1.0, 1.0]."""
    if current_price <= 0:
        return 0.0
        
    forced_buy_weight = 0.0
    forced_sell_weight = 0.0
    total_capital = sum(a.capital_weight for a in population)
    
    for agent in population:
        if not hasattr(agent, 'position_side') or agent.position_side == "HOLD" or agent.position_size == 0:
            continue
            
        # Check liquidation based on dynamic liq_price
        if agent.position_side == "LONG":
            if getattr(agent, 'liq_price', 0) > 0 and current_price <= agent.liq_price:
                # Forced liquidation selloff
                forced_sell_weight += agent.position_size * agent.capital_weight * agent.leverage
                agent.position_side = "HOLD"
                agent.position_size = 0.0
                agent.entry_price = 0.0
                agent.liq_price = 0.0
                agent.pyramid_count = 0
                agent.trauma_index = 1.0  # Severe PTSD
                log.warning(f"[LIQUIDATION] Agent {agent.agent_id} ({agent.persona_name}) LONG liquidated at ${current_price:.2f} (Liq Price: ${agent.liq_price:.2f})")
                
        elif agent.position_side == "SHORT":
            if getattr(agent, 'liq_price', 0) > 0 and current_price >= agent.liq_price:
                # Forced buyback
                forced_buy_weight += agent.position_size * agent.capital_weight * agent.leverage
                agent.position_side = "HOLD"
                agent.position_size = 0.0
                agent.entry_price = 0.0
                agent.liq_price = 0.0
                agent.pyramid_count = 0
                agent.trauma_index = 1.0
                log.warning(f"[LIQUIDATION] Agent {agent.agent_id} ({agent.persona_name}) SHORT liquidated at ${current_price:.2f} (Liq Price: ${agent.liq_price:.2f})")

    if total_capital > 0:
        forced_pressure = (forced_buy_weight - forced_sell_weight) / total_capital
        return min(1.0, max(-1.0, forced_pressure))
    return 0.0

def update_agent_positions(agent: any, decision: Decision, current_price: float):
    if current_price <= 0:
        return
    action = decision.action.upper()
    weight = decision.conviction / 100.0
    added_size = weight * 0.5  # Size multiplier for each addition
    
    if action == "BUY":
        if agent.position_side == "SHORT":
            agent.position_side = "HOLD"
            agent.position_size = 0.0
            agent.entry_price = 0.0
            agent.liq_price = 0.0
            agent.pyramid_count = 0
            
        if agent.position_side == "LONG":
            # Add to position (Pyramiding) when in profit and not exceeding 3 additions
            if hasattr(agent, 'entry_price') and agent.entry_price > 0 and current_price > agent.entry_price and getattr(agent, 'pyramid_count', 0) < 3:
                total_size = agent.position_size + added_size
                agent.entry_price = ((agent.position_size * agent.entry_price) + (added_size * current_price)) / total_size
                agent.position_size = total_size
                agent.pyramid_count = getattr(agent, 'pyramid_count', 0) + 1
        else:
            agent.position_side = "LONG"
            agent.entry_price = current_price
            agent.position_size = weight
            agent.pyramid_count = 0
            
        agent.liq_price = calculate_liquidation_price("LONG", agent.entry_price, agent.leverage)
        
    elif action == "SELL":
        if agent.position_side == "LONG":
            agent.position_side = "HOLD"
            agent.position_size = 0.0
            agent.entry_price = 0.0
            agent.liq_price = 0.0
            agent.pyramid_count = 0
            
        if agent.position_side == "SHORT":
            # Add to position (Pyramiding) when in profit (price dropping)
            if hasattr(agent, 'entry_price') and agent.entry_price > 0 and current_price < agent.entry_price and getattr(agent, 'pyramid_count', 0) < 3:
                total_size = agent.position_size + added_size
                agent.entry_price = ((agent.position_size * agent.entry_price) + (added_size * current_price)) / total_size
                agent.position_size = total_size
                agent.pyramid_count = getattr(agent, 'pyramid_count', 0) + 1
        else:
            agent.position_side = "SHORT"
            agent.entry_price = current_price
            agent.position_size = weight
            agent.pyramid_count = 0
            
        agent.liq_price = calculate_liquidation_price("SHORT", agent.entry_price, agent.leverage)

def decay_trauma(population: list):
    for agent in population:
        if hasattr(agent, 'trauma_index') and agent.trauma_index > 0:
            agent.trauma_index = max(0.0, agent.trauma_index - 0.05)


def run_cascade_round(population: list, market_state: dict, minutes_elapsed: int = 0) -> SwarmPrediction:
    global GLOBAL_TIER_RESULTS, GLOBAL_PREVIOUS_DECISIONS, IS_POSITIONS_INITIALIZED
    
    session = get_current_session()
    current_price = market_state.get("price") or 0.0
    
    if not IS_POSITIONS_INITIALIZED:
        init_agent_positions(population)
        IS_POSITIONS_INITIALIZED = True
        
    # 1. Run leverage liquidation simulation first
    forced_pressure = simulate_liquidations(population, current_price)
    
    # 2. Asymmetric cycle decomposition (Multi-Timescale)
    # HFT: always runs (every minute)
    # QUANT: runs every 15 minutes
    # APEX, PASSIVE, SMART, RETAIL: runs every 60 minutes
    tiers_to_run = ["HFT"]
    if minutes_elapsed % 15 == 0:
        tiers_to_run.append("QUANT")
    if minutes_elapsed % 60 == 0:
        tiers_to_run.extend(["APEX", "PASSIVE", "SMART_CONTRARIAN", "SMART_VALUE", "SEMI_SMART", "RETAIL_FOMO", "RETAIL_FUD", "RETAIL_LEVERAGE"])
        decay_trauma(population)  # Recovery from trauma every hour
        
    round_id = int(time.time())
    ts = datetime.now(timezone.utc).isoformat()
    llm_calls = 0
    llm_successes = 0
    
    # v2.0: Portfolio storage for cross-tier communication
    apex_portfolio = None
    
    LLM_ELIGIBLE_TIERS = {"APEX"}
    
    for tier in TIER_ORDER:
        # If tier is not in the run list for this cycle, keep the previous result
        if tier not in tiers_to_run:
            if tier not in GLOBAL_TIER_RESULTS:
                # Initialize default if no legacy data exists
                GLOBAL_TIER_RESULTS[tier] = {"buy_pct": 0.0, "sell_pct": 0.0, "hold_pct": 1.0, "net": 0.0, "normalized_net": 0.0, "population": 0}
            continue
            
        tier_agents = [a for a in population if a.tier == tier and session in a.active_sessions]
        if not tier_agents:
            continue
            
        # Calculate CascadeContext based on existing GLOBAL_TIER_RESULTS
        cascade = compute_cascade_context(GLOBAL_TIER_RESULTS, tier)
        
        # Add forced_pressure from liquidation to weighted_pressure for HFT/QUANT reaction
        if tier in ("HFT", "QUANT"):
            cascade.weighted_pressure = min(1.0, max(-1.0, cascade.weighted_pressure + forced_pressure * 0.5))
            
        # Operate State Machine
        sm_decisions = []
        for a in tier_agents:
            dec = agent_decide_sm(a, market_state, cascade)
            update_agent_positions(a, dec, current_price)
            sm_decisions.append(dec)
            
        tier_capital_weight = TIER_CONFIG[tier]["capital_weight"]
        agg_result = aggregate_tier(sm_decisions, tier_capital_weight)
        
        # Run LLM for APEX
        best_llm_decision = None
        llm_status = "SM_ONLY"
        
        if tier in LLM_ELIGIBLE_TIERS:
            tier_personas = [p for p in LLM_PERSONAS if p["tier"] == tier]
            
            for p in tier_personas:
                llm_calls += 1
                try:
                    prompt = build_market_prompt(market_state, p, GLOBAL_PREVIOUS_DECISIONS)
                    raw_resp = _call_algo(prompt=prompt, agent_id=f"A08_{p['id']}", label="SWARM_SIM", temp=0.7, tier="SWARM")
                    if raw_resp and raw_resp not in ("ERROR", "None", ""):
                        if tier == "APEX":
                            # v2.0: Parse as PortfolioAllocation
                            llm_portfolio = parse_portfolio_response(raw_resp)
                            if llm_portfolio.dominant_action != "HOLD" or abs(llm_portfolio.net_exposure) > 0.05:
                                llm_successes += 1
                                apex_portfolio = llm_portfolio
                                # Convert to legacy for backward compat
                                llm_dec = llm_portfolio.to_legacy_decision()
                                if not best_llm_decision or llm_dec.conviction > best_llm_decision.conviction:
                                    best_llm_decision = llm_dec
                                log.info(f"[APEX LLM] Portfolio: {llm_portfolio.dominant_action} net={llm_portfolio.net_exposure:+.3f} tranches={len(llm_portfolio.tranches)}")
                        else:
                            llm_dec = parse_llm_response(raw_resp)
                            if llm_dec.action != "HOLD" or llm_dec.conviction > 0:
                                llm_successes += 1
                                if not best_llm_decision or llm_dec.conviction > best_llm_decision.conviction:
                                    best_llm_decision = llm_dec
                    else:
                        log.warning(f"LLM returned empty/error for {p['id']}")
                except Exception as e:
                    log.error(f"LLM call failed for persona {p['id']}: {e}")
            
            llm_status = f"LLM_{best_llm_decision.action}" if best_llm_decision else "LLM_FAIL→SM"
            
        if best_llm_decision:
            GLOBAL_PREVIOUS_DECISIONS[tier] = {
                "action": best_llm_decision.action,
                "conviction": best_llm_decision.conviction,
                "reasoning": best_llm_decision.reasoning
            }
            # Update position for APEX based on LLM decision
            for a in tier_agents:
                update_agent_positions(a, best_llm_decision, current_price)
                
            if best_llm_decision.conviction > 80:
                if best_llm_decision.action == "BUY":
                    agg_result["net"] = tier_capital_weight
                    agg_result["normalized_net"] = 1.0
                    agg_result["buy_pct"], agg_result["sell_pct"], agg_result["hold_pct"] = 1.0, 0.0, 0.0
                elif best_llm_decision.action == "SELL":
                    agg_result["net"] = -tier_capital_weight
                    agg_result["normalized_net"] = -1.0
                    agg_result["buy_pct"], agg_result["sell_pct"], agg_result["hold_pct"] = 0.0, 1.0, 0.0
                else:
                    agg_result["net"] = 0.0
                    agg_result["normalized_net"] = 0.0
                    agg_result["buy_pct"], agg_result["sell_pct"], agg_result["hold_pct"] = 0.0, 0.0, 1.0
        else:
            dominant = "BUY" if agg_result["buy_pct"] > agg_result["sell_pct"] else ("SELL" if agg_result["sell_pct"] > agg_result["buy_pct"] else "HOLD")
            conv_sm = max(agg_result.get("buy_pct", 0), agg_result.get("sell_pct", 0), agg_result.get("hold_pct", 0)) * 100
            GLOBAL_PREVIOUS_DECISIONS[tier] = {
                "action": dominant,
                "conviction": round(conv_sm, 1),
                "reasoning": f"SM consensus ({len(tier_agents):,} agents)"
            }
            
        GLOBAL_TIER_RESULTS[tier] = agg_result
        
        # ── v2.0: Portfolio Allocation for APEX/HFT/SMART ──
        portfolio = None
        if tier == "APEX":
            if best_llm_decision is None:
                # LLM fail -> use SM Portfolio (more comprehensive than legacy SM)
                portfolio = apex_portfolio_sm(market_state, cascade)
                log.info(f"[APEX] Portfolio SM: {portfolio.dominant_action} net={portfolio.net_exposure:+.3f}")
            else:
                # LLM success -> parsed above
                portfolio = apex_portfolio  # Set by LLM parse above
                if portfolio is None:
                    portfolio = apex_portfolio_sm(market_state, cascade)
            
            # Override agg_result with portfolio legacy decision
            legacy = portfolio.to_legacy_decision()
            if abs(portfolio.net_exposure) > 0.05:  # Only override if portfolio has a clear decision
                norm_net = portfolio.net_exposure
                agg_result["normalized_net"] = norm_net
                agg_result["net"] = norm_net * tier_capital_weight
                agg_result["buy_pct"] = max(0, norm_net)
                agg_result["sell_pct"] = max(0, -norm_net)
                agg_result["hold_pct"] = max(0, 1.0 - abs(norm_net))
            
            apex_portfolio = portfolio
            GLOBAL_TIER_RESULTS[tier] = agg_result
            GLOBAL_TIER_RESULTS[tier]["portfolio"] = portfolio.to_dict()
            
            GLOBAL_PREVIOUS_DECISIONS[tier] = {
                "action": legacy.action,
                "conviction": legacy.conviction,
                "reasoning": portfolio.reasoning[:200]
            }
            
        elif tier == "HFT":
            portfolio = hft_portfolio_sm(market_state, cascade)
            GLOBAL_TIER_RESULTS[tier]["portfolio"] = portfolio.to_dict()
            
        elif tier in ("SMART_CONTRARIAN", "SMART_VALUE", "SEMI_SMART") and apex_portfolio is not None:
            portfolio = smart_portfolio_sm(market_state, cascade, apex_portfolio)
            # Override SMART SM results with pilot fish logic
            legacy = portfolio.to_legacy_decision()
            if abs(portfolio.net_exposure) > 0.05:
                norm_net = portfolio.net_exposure
                agg_result["normalized_net"] = norm_net
                agg_result["net"] = norm_net * tier_capital_weight
                agg_result["buy_pct"] = max(0, norm_net)
                agg_result["sell_pct"] = max(0, -norm_net)
                agg_result["hold_pct"] = max(0, 1.0 - abs(norm_net))
                GLOBAL_TIER_RESULTS[tier] = agg_result
            GLOBAL_TIER_RESULTS[tier]["portfolio"] = portfolio.to_dict()
        
        log.info(f"Tier {tier} (Run): {len(tier_agents):,} agents | net={agg_result['net']:.3f} | {llm_status} | cascade=[wp={cascade.weighted_pressure:.3f} cs={cascade.consensus_strength:.2f}]")

    divergence = detect_divergence(GLOBAL_TIER_RESULTS)
    
    # Combined net pressure including pressure from forced liquidations (forced_pressure)
    decided_nets = sum(res["net"] for res in GLOBAL_TIER_RESULTS.values() if "net" in res)
    net_pressure = min(1.0, max(-1.0, decided_nets + forced_pressure * 0.3))
    
    if net_pressure > 0.3:
        crowd_sentiment = "BULLISH"
    elif net_pressure < -0.3:
        crowd_sentiment = "BEARISH"
    else:
        crowd_sentiment = "NEUTRAL"
        
    cascade_narrative = (
        f"Market session {session}. Net pressure at {net_pressure:.2f} ({crowd_sentiment}). "
        f"Forced Liq Pressure: {forced_pressure:+.3f}. Divergence: {divergence}."
    )
    
    # Write dynamic liquidation allocation map to Redis
    publish_liquidation_migration_map(population)
    
    return SwarmPrediction(
        timestamp=ts,
        round_id=round_id,
        population=len([a for a in population if session in a.active_sessions]),
        net_pressure=net_pressure,
        crowd_sentiment=crowd_sentiment,
        tier_breakdown=GLOBAL_TIER_RESULTS.copy(),
        divergence_flag=divergence,
        cascade_narrative=cascade_narrative,
        meta={"session": session, "llm_calls": llm_calls, "llm_successes": llm_successes, 
              "mode": f"HYBRID(APEX_LLM+SM)" if llm_successes > 0 else "PURE_SM",
              "forced_liq_pressure": round(forced_pressure, 4),
              "engine_version": "v2.5"}
    )

def publish_liquidation_migration_map(population: list):
    map_data = {"long_liq_clusters": {}, "short_liq_clusters": {}}
    for agent in population:
        if not hasattr(agent, 'position_side') or agent.position_side == "HOLD" or getattr(agent, 'liq_price', 0) <= 0:
            continue
        # Round to nearest $100 price bin
        price_bin = int(round(agent.liq_price / 100) * 100)
        # weight = size * capital_weight * leverage
        weight = agent.position_size * agent.capital_weight * agent.leverage
        
        cluster = "long_liq_clusters" if agent.position_side == "LONG" else "short_liq_clusters"
        map_data[cluster][price_bin] = map_data[cluster].get(price_bin, 0.0) + weight
        
    try:
        matrix.set("A08", "liquidation_migration_map", json.dumps(map_data), ex=3600)
        log.info(f"[A08] Published Liquidation Migration Map: {len(map_data['long_liq_clusters'])} long bins, {len(map_data['short_liq_clusters'])} short bins")
    except Exception as e:
        log.error(f"[A08] Failed to publish liquidation migration map to Redis: {e}")

def publish_prediction(prediction: SwarmPrediction):
    try:
        ts = datetime.now(timezone.utc).isoformat()
        pred_json = json.dumps(asdict(prediction), ensure_ascii=False)
        
        # 1. SET latest — backward-compatible, dùng cho divergence_engine đọc nhanh
        matrix.set("A08", "swarm_prediction", pred_json, ex=21600)  # 6 hours
        matrix.set("A08", "tier_breakdown", json.dumps(prediction.tier_breakdown), ex=21600)
        
        # v2.0: Publish portfolio breakdowns for APEX/HFT/SMART
        portfolio_data = {}
        for tier_name, tier_data in prediction.tier_breakdown.items():
            if "portfolio" in tier_data:
                portfolio_data[tier_name] = tier_data["portfolio"]
        if portfolio_data:
            matrix.set("A08", "portfolio_breakdown", json.dumps(portfolio_data, ensure_ascii=False), ex=21600)
        
        matrix.set("A08", "heartbeat", json.dumps({"ts": ts, "status": "ALIVE"}), ex=300)
        
        # 2. LIST history — store 5 most recent predictions, TTL 6 hours
        history_key = "zcl:a08:prediction_history"
        try:
            r = matrix.client  # Direct Redis client
            r.lpush(history_key, pred_json)
            r.ltrim(history_key, 0, 4)  # Keep 5 most recent entries
            r.expire(history_key, 21600)  # TTL 6 hours
        except Exception as e_hist:
            log.warning(f"Failed to push prediction history: {e_hist}")
        
        log.info(f"Published prediction {prediction.round_id} - Net Pressure: {prediction.net_pressure:.3f}")
        
        # Skip sending Telegram per instructions (permanently disabled A08 reports)
        log.info("[A08] Skip sending Telegram per instructions (permanently disabled A08 reports)")
        
        try:
            from agent_session_logger import log_agent_snapshot
            # Rich snapshot: sufficient data for backtesting + regime detection
            tier_summary_lines = []
            for tier, td in prediction.tier_breakdown.items():
                tier_summary_lines.append(
                    f"{tier}: B={td.get('buy_pct',0)*100:.1f}% S={td.get('sell_pct',0)*100:.1f}% "
                    f"H={td.get('hold_pct',0)*100:.1f}% Net={td.get('normalized_net',0):+.3f}"
                )
            log_agent_snapshot(
                agent_id="A08",
                prompt=(
                    f"[MARKET_STATE] Round={prediction.round_id} | Session={prediction.meta.get('session','?')} | "
                    f"Mode={prediction.meta.get('mode','?')} | LLM={prediction.meta.get('llm_successes',0)}/{prediction.meta.get('llm_calls',0)}"
                ),
                response=(
                    f"Net={prediction.net_pressure:+.4f} | Div={prediction.divergence_flag} | "
                    f"Crowd={prediction.crowd_sentiment}\n" +
                    "\n".join(tier_summary_lines) + "\n" +
                    f"Narrative: {prediction.cascade_narrative}"
                ),
                metadata={
                    "net_pressure": prediction.net_pressure,
                    "divergence_flag": prediction.divergence_flag,
                    "crowd_sentiment": prediction.crowd_sentiment,
                    "population": prediction.population,
                    "mode": prediction.meta.get("mode", "?"),
                    "session": prediction.meta.get("session", "?"),
                    "llm_calls": prediction.meta.get("llm_calls", 0),
                    "llm_successes": prediction.meta.get("llm_successes", 0),
                    "tier_nets": {
                        tier: round(td.get("normalized_net", 0), 4)
                        for tier, td in prediction.tier_breakdown.items()
                    }
                }
            )
        except Exception as e:
            log.warning(f"Failed to log A08 snapshot: {e}")

        # ── JSONL Timeline Archive ──
        try:
            from pathlib import Path
            timeline_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "a08_timeline"
            timeline_dir.mkdir(parents=True, exist_ok=True)
            # 1 file/day — easy to rotate
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            timeline_file = timeline_dir / f"timeline_{date_str}.jsonl"
            timeline_entry = {
                "ts": ts,
                "round_id": prediction.round_id,
                "session": prediction.meta.get("session", "?"),
                "net_pressure": round(prediction.net_pressure, 5),
                "crowd_sentiment": prediction.crowd_sentiment,
                "divergence_flag": prediction.divergence_flag,
                "mode": prediction.meta.get("mode", "?"),
                "tier_nets": {
                    tier: round(td.get("normalized_net", 0), 4)
                    for tier, td in prediction.tier_breakdown.items()
                },
                "tier_buy_pct": {
                    tier: round(td.get("buy_pct", 0), 3)
                    for tier, td in prediction.tier_breakdown.items()
                },
                "tier_sell_pct": {
                    tier: round(td.get("sell_pct", 0), 3)
                    for tier, td in prediction.tier_breakdown.items()
                },
            }
            with open(timeline_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(timeline_entry, ensure_ascii=False) + "\n")
            log.info(f"[A08] Timeline archived -> {timeline_file.name} ({timeline_entry['net_pressure']:+.4f})")
        except Exception as e_tl:
            log.debug(f"[A08] Timeline write skipped: {e_tl}")
            
    except Exception as e:
        log.error(f"Failed to publish prediction: {e}")


def _heartbeat_loop():
    while True:
        try:
            ts = datetime.now(timezone.utc).isoformat()
            matrix.set("A08", "heartbeat", json.dumps({"ts": ts, "status": "ALIVE"}), ex=300)
        except Exception:
            pass
        time.sleep(60)

if __name__ == "__main__":
    log.info("A08 Swarm Oracle Engine starting...")
    population = init_population()
    
    hb_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    hb_thread.start()
    
    minutes_counter = 0
    # Main engine cycle reduced to 60 seconds (1 minute) for HFT activity
    # For backward compatibility with ALGO_CYCLE_INTERVAL_SEC when testing,
    # we set the default run cycle to 60s
    CYCLE_INTERVAL_SEC = 60 
    
    while True:
        start_t = time.time()
        market_state = read_market_state()
        
        # Run asynchronous cascade round
        prediction = run_cascade_round(population, market_state, minutes_elapsed=minutes_counter)
        publish_prediction(prediction)
        
        comp_time = time.time() - start_t
        log.info(f"Summary Min {minutes_counter}: Net {prediction.net_pressure:.3f} | Forced Liq: {prediction.meta.get('forced_liq_pressure',0):+.3f} | Time: {comp_time:.2f}s")
        
        minutes_counter += 1
        time.sleep(CYCLE_INTERVAL_SEC)
