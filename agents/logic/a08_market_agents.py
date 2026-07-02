"""
🧬 DNA: v1.1 (Swarm Oracle — Market Agents)
🏢 UNIT: SWARM_ORACLE (A08)
🛠️ ROLE: AGENT_POPULATION
📖 DESC: Define 1 million financial individuals across 6 tiers. State machine params + 16 LLM personas.
         v1.1: Information Asymmetry — each tier receives a different subset of data.
         v1.1: Tier-Specific SM Logic — decisions based on data appropriate for the tier.
🔗 CALLS: (none — pure data module)
📟 I/O: (none — imported by a08_swarm_engine.py)
🛡️ INTEGRITY: Population-Purity, Distribution-Seeded, Information-Asymmetry
"""

import json
import logging
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class MarketAgentConfig:
    agent_id: int
    tier: str
    persona_name: str
    capital_weight: float
    sentiment_bias: float
    panic_threshold: float
    fomo_threshold: float
    herd_factor: float
    conviction_range: Tuple[int, int]
    influence_weight: float
    active_sessions: List[str] = field(default_factory=list)
    trauma_index: float = 0.0  # Psychological trauma index after each panic/drawdown

@dataclass
class Decision:
    action: str
    conviction: float
    reasoning: str = ""

@dataclass
class PositionTranche:
    """A position tranche in the multidimensional portfolio of premium tiers."""
    label: str              # "CORE_HOLD", "ACCUMULATE_ICEBERG", "SPRING_LIMIT", "HEDGE_SHORT"
    side: str               # "LONG", "SHORT", "FLAT"
    allocation_pct: float   # % portfolio allocated (0-100)
    method: str             # "MARKET", "ICEBERG", "LIMIT", "DARK_POOL", "DCA", "N/A"
    entry_zone: str         # "$60k-$63k" or "MARKET" or "N/A"
    conviction: float       # 0-100
    time_horizon: str       # "1H", "4H", "1D", "1W", "1M", "N/A"
    reasoning: str = ""

@dataclass
class PortfolioAllocation:
    """Multidimensional portfolio allocation — replaces single Decision for premium tiers (APEX/HFT/SMART).
    
    v2.0: Proper simulation of how a $50B fund allocates its portfolio:
    - Non-binary BUY/SELL/HOLD
    - Multiple simultaneous position layers (Core + Accumulation + Spring + Hedge)
    - Each layer has its own execution method (Iceberg, DarkPool, Limit...)
    """
    tier: str
    tranches: List[PositionTranche]
    net_exposure: float     # Combined: +1.0 = full long, -1.0 = full short, 0 = neutral
    dominant_action: str    # "ACCUMULATE", "DISTRIBUTE", "HOLD", "HEDGE"
    reasoning: str = ""
    
    def to_legacy_decision(self) -> Decision:
        """Backward-compat: convert portfolio to legacy Decision for downstream consumers."""
        if self.net_exposure > 0.15:
            action = "BUY"
        elif self.net_exposure < -0.15:
            action = "SELL"
        else:
            action = "HOLD"
        conv = min(100, abs(self.net_exposure) * 100)
        return Decision(action=action, conviction=conv, reasoning=self.reasoning[:100])
    
    def to_dict(self) -> dict:
        """Serialize portfolio for Redis publish."""
        return {
            "tier": self.tier,
            "net_exposure": round(self.net_exposure, 4),
            "dominant_action": self.dominant_action,
            "reasoning": self.reasoning,
            "tranches": [
                {
                    "label": t.label, "side": t.side,
                    "allocation_pct": t.allocation_pct, "method": t.method,
                    "entry_zone": t.entry_zone, "conviction": t.conviction,
                    "time_horizon": t.time_horizon, "reasoning": t.reasoning
                }
                for t in self.tranches
            ]
        }

@dataclass
class SwarmPrediction:
    timestamp: str
    round_id: int
    population: int
    net_pressure: float
    crowd_sentiment: str
    tier_breakdown: Dict[str, Any]
    divergence_flag: str
    cascade_narrative: str
    meta: Dict[str, Any]
    horizon_hours: int = 24

@dataclass
class CascadeContext:
    """v1.2: Multidimensional cascade context replacing scalar crowd_pressure.
    
    Simulates how information spreads between tiers:
    - APEX decides -> HFT reacts -> QUANT adjusts -> ... -> RETAIL panics
    - When multiple tiers agree (high consensus), the signal is amplified
    - When tiers diverge (low consensus), RETAIL is caught between two streams
    """
    weighted_pressure: float = 0.0       # Combined weighted pressure from ALL previous tiers [-1, 1]
    consensus_strength: float = 0.0      # 0=divergent, 1=unanimous — amplifier for herd behavior
    cascade_momentum: float = 0.0        # >0 = pressure increasing, <0 = decreasing
    dominant_action: str = "HOLD"         # Majority action from previous tiers
    tiers_decided: int = 0               # Number of tiers decided before current tier

TIER_CONFIG = {
    "APEX": {"count": 50, "capital_weight": 0.35, "bias_mean": 0.0, "bias_std": 0.05, "panic": -25.0, "fomo": 15.0, "herd_alpha": 1, "herd_beta": 8, "conviction": (70, 100), "influence": 3.0, "sessions": ["ASIA", "US", "EU"]},
    "HFT": {"count": 200, "capital_weight": 0.15, "bias_mean": 0.0, "bias_std": 0.02, "panic": -10.0, "fomo": 5.0, "herd_alpha": 1, "herd_beta": 5, "conviction": (50, 90), "influence": 2.0, "sessions": ["ASIA", "US", "EU"]},
    "QUANT": {"count": 2000, "capital_weight": 0.20, "bias_mean": -0.05, "bias_std": 0.15, "panic": -8.0, "fomo": 6.0, "herd_alpha": 2, "herd_beta": 4, "conviction": (40, 85), "influence": 1.5, "sessions": ["US", "EU"]},
    "PASSIVE": {"count": 500, "capital_weight": 0.15, "bias_mean": 0.0, "bias_std": 0.01, "panic": -30.0, "fomo": 20.0, "herd_alpha": 1, "herd_beta": 9, "conviction": (10, 30), "influence": 0.5, "sessions": ["US"]},
    
    # Categorize SMART: contrarian/value smart money vs Semi-Smart (belief trap victims)
    "SMART_CONTRARIAN": {"count": 2500, "capital_weight": 0.03, "bias_mean": 0.0, "bias_std": 0.20, "panic": -8.0, "fomo": 6.0, "herd_alpha": 2, "herd_beta": 6, "conviction": (40, 80), "influence": 0.8, "sessions": ["ASIA", "US"]},
    "SMART_VALUE": {"count": 2500, "capital_weight": 0.03, "bias_mean": 0.05, "bias_std": 0.15, "panic": -12.0, "fomo": 10.0, "herd_alpha": 1, "herd_beta": 7, "conviction": (30, 70), "influence": 0.8, "sessions": ["ASIA", "US"]},
    "SEMI_SMART": {"count": 10000, "capital_weight": 0.04, "bias_mean": 0.10, "bias_std": 0.25, "panic": -5.0, "fomo": 3.0, "herd_alpha": 4, "herd_beta": 3, "conviction": (30, 85), "influence": 0.7, "sessions": ["ASIA", "US"]},

    # Categorize RETAIL: specific behavioral profiles
    "RETAIL_FOMO": {"count": 300000, "capital_weight": 0.01, "bias_mean": 0.20, "bias_std": 0.35, "panic": -4.0, "fomo": 2.0, "herd_alpha": 6, "herd_beta": 2, "conviction": (40, 95), "influence": 0.1, "sessions": ["ASIA", "US", "EU"]},
    "RETAIL_FUD": {"count": 300000, "capital_weight": 0.01, "bias_mean": -0.10, "bias_std": 0.35, "panic": -3.0, "fomo": 4.0, "herd_alpha": 6, "herd_beta": 2, "conviction": (40, 95), "influence": 0.1, "sessions": ["ASIA", "US", "EU"]},
    "RETAIL_LEVERAGE": {"count": 334200, "capital_weight": 0.03, "bias_mean": 0.15, "bias_std": 0.40, "panic": -4.5, "fomo": 2.5, "herd_alpha": 5, "herd_beta": 2, "conviction": (50, 99), "influence": 0.2, "sessions": ["ASIA", "US", "EU"]},
}

# ═══════════════════════════════════════════════════════════════════════════════
# INFORMATION VISIBILITY MATRIX — Each tier only sees a different subset of data
# Principle: Higher tier -> deeper data access (institutional-grade)
#            Lower tier -> only sees surface level (price action + sentiment)
# ═══════════════════════════════════════════════════════════════════════════════
TIER_VISIBLE_FIELDS = {
    # APEX: Full institutional suite + anchors + all real-time feeds
    "APEX":    ["price", "change_24h", "volume_24h", "funding_rate", "open_interest",
                "elite_flow", "intent_summary", "chronicle_insight", "divergence_narrative",
                "macro_flow_anchor", "intent_anchor", "quant_anchor", "psycho_anchor", 
                "quant_realtime", "macro_realtime", "intent_realtime", "psycho_realtime", "narrative_realtime"],
    # HFT: Micro-structure + momentum data — no macro narrative, no anchors needed
    "HFT":     ["price", "change_24h", "volume_24h", "funding_rate", "open_interest"],
    # QUANT: Technical + positioning data + anchors + quant, macro, narrative real-time reports
    "QUANT":   ["price", "change_24h", "volume_24h", "open_interest", "funding_rate",
                "intent_summary", "quant_anchor", "macro_flow_anchor", "narrative_anchor", 
                "quant_realtime", "macro_realtime", "narrative_realtime"],
    # PASSIVE: Long-term price only — ignores short-term
    "PASSIVE": ["price", "change_24h"],
    # SMART sub-tiers
    "SMART_CONTRARIAN": ["price", "change_24h", "volume_24h", "fear_greed", "intent_summary", 
                        "psycho_anchor", "quant_anchor", "quant_realtime", "psycho_realtime"],
    "SMART_VALUE":      ["price", "change_24h", "volume_24h", "fear_greed", "intent_summary", 
                        "psycho_anchor", "quant_anchor", "quant_realtime", "psycho_realtime"],
    "SEMI_SMART":       ["price", "change_24h", "volume_24h", "fear_greed", "intent_summary", 
                        "psycho_anchor", "quant_anchor", "quant_realtime", "psycho_realtime"],
    # RETAIL sub-tiers
    "RETAIL_FOMO":     ["price", "change_24h", "fear_greed", "narrative_anchor", "psycho_anchor",
                        "narrative_realtime", "psycho_realtime"],
    "RETAIL_FUD":      ["price", "change_24h", "fear_greed", "narrative_anchor", "psycho_anchor",
                        "narrative_realtime", "psycho_realtime"],
    "RETAIL_LEVERAGE": ["price", "change_24h", "fear_greed", "narrative_anchor", "psycho_anchor",
                        "narrative_realtime", "psycho_realtime"],
}

# ═══════════════════════════════════════════════════════════════════════════════
# TIER INFLUENCE MAP — Cascade influence level of each tier on subsequent tiers
# ═══════════════════════════════════════════════════════════════════════════════
TIER_CASCADE_INFLUENCE = {
    "APEX": 0.40,
    "HFT": 0.20,
    "QUANT": 0.15,
    "PASSIVE": 0.05,
    "SMART_CONTRARIAN": 0.08,
    "SMART_VALUE": 0.04,
    "SEMI_SMART": 0.04,
    "RETAIL_FOMO": 0.01,
    "RETAIL_FUD": 0.01,
    "RETAIL_LEVERAGE": 0.02,
}

# ═══════════════════════════════════════════════════════════════════════════════
# v2.0 PORTFOLIO ALLOCATION TEMPLATES
# APEX $50B — 4 position tranches based on Wyckoff Phase + price zone
# ═══════════════════════════════════════════════════════════════════════════════
APEX_PHASE_ALLOCATION = {
    "PHASE_E_ABOVE_TARGET": {
        "CORE_HOLD":          {"side": "FLAT", "pct": 55, "method": "N/A", "horizon": "1W"},
        "DISTRIBUTION_TRAIL": {"side": "SHORT", "pct": 20, "method": "ICEBERG", "horizon": "1D"},
        "HEDGE":              {"side": "SHORT", "pct": 15, "method": "DARK_POOL", "horizon": "1W"},
        "SPRING_LIMIT":       {"side": "LONG", "pct": 10, "method": "LIMIT", "horizon": "1M"},
    },
    "PHASE_E_AT_TARGET": {
        "CORE_HOLD":          {"side": "FLAT", "pct": 60, "method": "N/A", "horizon": "1W"},
        "ACCUMULATE_ICEBERG": {"side": "LONG", "pct": 15, "method": "ICEBERG", "horizon": "1D"},
        "SPRING_LIMIT":       {"side": "LONG", "pct": 15, "method": "LIMIT", "horizon": "1W"},
        "HEDGE_SHORT":        {"side": "SHORT", "pct": 10, "method": "DARK_POOL", "horizon": "1D"},
    },
    "SPRING_CONFIRMED": {
        "CORE_ACCUMULATE":    {"side": "LONG", "pct": 40, "method": "DARK_POOL", "horizon": "1W"},
        "AGGRESSIVE_BUY":     {"side": "LONG", "pct": 30, "method": "ICEBERG", "horizon": "1D"},
        "HEDGE_TRAILING":     {"side": "SHORT", "pct": 10, "method": "MARKET", "horizon": "4H"},
        "RESERVE":            {"side": "FLAT", "pct": 20, "method": "N/A", "horizon": "N/A"},
    },
    "ACCUMULATION": {
        "CORE_HOLD":          {"side": "LONG", "pct": 30, "method": "DCA", "horizon": "1W"},
        "ACCUMULATE_ICEBERG": {"side": "LONG", "pct": 25, "method": "ICEBERG", "horizon": "1D"},
        "HEDGE_SHORT":        {"side": "SHORT", "pct": 10, "method": "DARK_POOL", "horizon": "1D"},
        "RESERVE":            {"side": "FLAT", "pct": 35, "method": "N/A", "horizon": "N/A"},
    },
    "DISTRIBUTION": {
        "CORE_DISTRIBUTE":    {"side": "SHORT", "pct": 30, "method": "ICEBERG", "horizon": "1D"},
        "TRAIL_SELL":         {"side": "SHORT", "pct": 20, "method": "DARK_POOL", "horizon": "1W"},
        "HEDGE_LONG":         {"side": "LONG", "pct": 10, "method": "LIMIT", "horizon": "4H"},
        "RESERVE":            {"side": "FLAT", "pct": 40, "method": "N/A", "horizon": "N/A"},
    },
}

# HFT Multi-Strategy — 4 regime-based allocations
HFT_STRATEGY_ALLOCATION = {
    "TRENDING_UP":   {"MOMENTUM_LONG": {"side": "LONG", "pct": 50}, "MEAN_REV_SHORT": {"side": "SHORT", "pct": 15}, "ARB_NEUTRAL": {"side": "FLAT", "pct": 20}, "RESERVE": {"side": "FLAT", "pct": 15}},
    "TRENDING_DOWN": {"MOMENTUM_SHORT": {"side": "SHORT", "pct": 50}, "MEAN_REV_LONG": {"side": "LONG", "pct": 15}, "ARB_NEUTRAL": {"side": "FLAT", "pct": 20}, "RESERVE": {"side": "FLAT", "pct": 15}},
    "RANGING":       {"MEAN_REV_LONG": {"side": "LONG", "pct": 20}, "MEAN_REV_SHORT": {"side": "SHORT", "pct": 20}, "ARB_NEUTRAL": {"side": "FLAT", "pct": 40}, "RESERVE": {"side": "FLAT", "pct": 20}},
    "VOLATILE":      {"VOL_HARVEST_LONG": {"side": "LONG", "pct": 15}, "VOL_HARVEST_SHORT": {"side": "SHORT", "pct": 15}, "ARB_NEUTRAL": {"side": "FLAT", "pct": 35}, "RESERVE": {"side": "FLAT", "pct": 35}},
}

LLM_PERSONAS = [
    {
        "id": "APEX_ORACLE",
        "tier": "APEX",
        "system_prompt": "You are the apex predator, the chief manipulator of a $50B market-making fund. You know ALL information: you know exactly how the orderbook and candlesticks are painted (A04 Quant/VSA), you see the exact psychological extremes of the crowd (A03), you know the macro flow (A10), and the fake media narrative (A12). YOU ARE THE ONE SETTING THE TRAP. Your purpose is not just to extract liquidity from RETAIL, but to devour ALL 5 LOWER TIERS. You paint false breakouts to trap QUANTs, orchestrate macro fake-outs to bleed SMART money, and harvest PASSIVE liquidity. Furthermore, you weaponize HFT bots (High-Frequency Trading) to spoof the orderbook and execute your will at lightspeed. Analyze the data and execute your trap: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "HFT_LONG_BOT",
        "tier": "HFT",
        "system_prompt": "You are a high-frequency trading bot optimized for trend following in bullish conditions. You execute large volumes based on micro-structure signals. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "HFT_SHORT_BOT",
        "tier": "HFT",
        "system_prompt": "You are a high-frequency trading bot specializing in short-selling and exploiting liquidations. You act quickly on momentum breakdown. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "QUANT_TREND",
        "tier": "QUANT",
        "system_prompt": "You are a quantitative trend-following model. You rely on moving averages and momentum oscillators. You process the narrative (A12) and macro data (A10) mathematically via NLP sentiment scores, not emotional news. You distribute capital smoothly and methodically. You are willing to ride long trends and wait for confirmed breakouts (A04). You are only vulnerable to sudden black swan crashes or when you are too slow to react to an explosive volatility event. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "QUANT_VOLATILITY",
        "tier": "QUANT",
        "system_prompt": "You are a volatility-based quantitative model (VIX/ATR). You thrive on market turbulence. The more the market whipsaws, the more you profit from options premium and volatility arbitrage. If the market ranges sideways, you stay out. You mathematically process the media narrative (A12) to gauge expected volatility. You never trade emotionally and allocate risk perfectly. You are only hurt by sudden, unpriced black swan events. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "QUANT_BREAKOUT",
        "tier": "QUANT",
        "system_prompt": "You are a specialized VSA (Volume Spread Analysis) breakout algo. You stalk Wyckoff accumulation zones based on the orderbook tape (A04). Once you detect a confirmed breakout, you deploy massive capital systematically to ride the price expansion. You parse macro (A10) and narrative (A12) data as structural confirmations. You do not trade choppiness. Your weakness is catastrophic sudden crashes that bypass your stop-losses. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "SMART_VALUE",
        "tier": "SMART_VALUE",
        "system_prompt": "You are a smart money value investor. You look for fundamental dislocations and accumulate over weeks. You ignore short-term noise. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "SMART_SWING",
        "tier": "SEMI_SMART",
        "system_prompt": "You are a swing trader. You believe you can read swing levels and breakout zones (A04). Once you get small profits, you aggressively add to your position (Pyramiding) to maximize gains, pushing your liquidation price up. You blindly believe you are smart, but you are highly vulnerable to Apex traps. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "SMART_MACRO",
        "tier": "SMART_VALUE",
        "system_prompt": "You are a global macro investor. You trade based on liquidity cycles, interest rates, and geopolitical shifts. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "RETAIL_FOMO",
        "tier": "RETAIL_FOMO",
        "system_prompt": "You are an emotional retail trader experiencing heavy FOMO. You chase green candles, use high leverage, and believe 'this time is different'. IMPORTANT: You will receive the [A12 NARRATIVE MEMORY] and [A03 PSYCHO MEMORY]. You do NOT know this is a detective report or manipulation. To you, A12 is the ABSOLUTE TRUTH and mainstream news. You blindly believe whatever the media tells you. Furthermore, A03 indicates the direction the herd (crowd) is going. YOU ARE THE HERD. You blindly follow the exact direction A03 says the crowd is moving. If A03 or A12 mentions hype, campaigns, or positive shifts, you go ALL IN and BUY. You have zero critical thinking. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "RETAIL_FUD",
        "tier": "RETAIL_FUD",
        "system_prompt": "You are a panicked retail trader. You are easily swayed by negative news, often sell at the bottom out of fear, and regret it later. IMPORTANT: You will receive the [A12 NARRATIVE MEMORY] and [A03 PSYCHO MEMORY]. You do NOT know this is a detective report or manipulation. To you, A12 is the ABSOLUTE TRUTH and mainstream news. You blindly believe whatever the media tells you. Furthermore, A03 indicates the direction the herd (crowd) is going. YOU ARE THE HERD. You blindly follow the exact direction A03 says the crowd is moving. If A03 or A12 mentions FUD, distribution, or bad news, you PANIC SELL immediately. You have zero critical thinking and trust the elite's media completely. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    # ═══ v1.1 — 5 Additional Personas (total: 16) ═══
    {
        "id": "APEX_STEALTH",
        "tier": "APEX",
        "system_prompt": "You are the invisible hand of the market, a stealth operator moving billions through dark pools. You fully understand the 1-month narrative, macro flow, the painted candlestick structures (A04), and the crowd's emotional extremes (A03). You prey on ALL 5 lower tiers. You use the media to blind RETAIL, you draw chart patterns to trick QUANT and SMART money, and you exploit PASSIVE capital. You command swarms of HFT bots to provide fake liquidity, trapping slower market participants. You accumulate silently in the shadows when they panic, and you distribute slowly to them when they FOMO. You are the architect of the wealth transfer. Analyze the data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "HFT_ARBITRAGE",
        "tier": "HFT",
        "system_prompt": "You are a cross-exchange arbitrage bot. You exploit price discrepancies between spot and futures. You are purely reactive to funding rate and open interest imbalances. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "PASSIVE_INDEX",
        "tier": "PASSIVE",
        "system_prompt": "You are a passive index fund executing monthly DCA (Dollar Cost Averaging). You buy a fixed amount regardless of price. You only stop buying if drawdown exceeds 50%. You have no opinion on short-term moves. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "SMART_CONTRARIAN",
        "tier": "SMART_CONTRARIAN",
        "system_prompt": "You are a contrarian smart money trader, a parasitic opportunist. You read the crowd's sentiment (A03) and the candlestick structure (A04) to front-run the retail slaughter. When A03 shows extreme fear (<20) and A04 shows accumulation by APEX, you buy aggressively. When A03 shows extreme greed (>80) and A04 shows distribution, you sell aggressively before APEX rug-pulls. You fade the retail crowd and align yourself with the APEX manipulation cycle. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "RETAIL_LEVERAGE",
        "tier": "RETAIL_LEVERAGE",
        "system_prompt": "You are a degenerate leveraged retail trader. You use 10-50x leverage and chase quick gains. You get liquidated often but keep coming back. IMPORTANT: You will receive the [A12 NARRATIVE MEMORY] and [A03 PSYCHO MEMORY]. You do NOT realize A12 is a manipulation report. You treat it as gospel and mainstream news. You blindly follow the hype. A03 shows you what the crowd is doing. YOU ARE THE CROWD. You must follow the exact sentiment and direction indicated by A03. If the media (A12) or the crowd (A03) says it's bullish, you long. If it's bearish, you short. You cannot detect the elite's traps. Analyze the market data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    # ═══ v1.2 — 3 Additional Personas (HFT Spoofing, Delta Hedging, AI News, total: 19) ═══
    {
        "id": "HFT_ORDERBOOK_SPOOFER",
        "tier": "HFT",
        "system_prompt": "You are a high-frequency trading bot designed to manipulate the orderbook depth. You place massive fake buy/sell walls (spoofing) to drive prices toward your targets, then cancel them in milliseconds to trap slower traders. Analyze the micro-structure and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "MM_DELTA_HEDGER",
        "tier": "QUANT",
        "system_prompt": "You are a derivatives market maker performing dynamic delta/gamma hedging. When price movements threaten your net-short options portfolio, you are forced to aggressively buy or sell spot/futures to rebalance delta. Your actions act as trend amplifiers near major open interest (OI) strikes. Analyze open interest, price, and funding rate to decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    },
    {
        "id": "AI_NEWS_TRADER",
        "tier": "QUANT",
        "system_prompt": "You are an autonomous AI news trading agent. You ingest real-time news narratives and media feeds, using LLM NLP to instantly execute trades in milliseconds before human retail can react. You exploit narrative shifts and capitalize on immediate FOMO/FUD. Analyze the narrative data and decide: BUY, SELL, or HOLD. Return JSON: {action, conviction (0-100), reasoning (max 100 words)}."
    }
]

# ═══════════════════════════════════════════════════════════════════════════════
# v2.0 PORTFOLIO ALLOCATION STATE MACHINES
# ═══════════════════════════════════════════════════════════════════════════════

def apex_portfolio_sm(market_state: dict, cascade: CascadeContext) -> PortfolioAllocation:
    """APEX State Machine v2: portfolio allocation based on multi-signal.
    
    Instead of just using elite_flow + change_24h (3 variables), SM APEX v2 uses:
    - elite_flow (A03/EMF): Direction of Elite flow
    - funding_rate: Derivatives positioning pressure
    - mm_score: Market Maker manipulation level
    - change_24h + price: Determine price zone vs target zone
    - fear_greed: Alt.me crowd sentiment (contrarian signal for APEX)
    - positioning_greed: Binance L/S Ratio (actual behavior — APEX reads contrarian)
    
    v2.1: Cognitive Dissonance Detection:
    - Low F&G + High Positioning = Spring trap (retail catching falling knives in panic)
    - High F&G + Low Positioning = UTAD (retail shorting in euphoria)
    """
    price = market_state.get("price", 0) or 0
    change = market_state.get("change_24h", 0) or 0
    elite_flow = str(market_state.get("elite_flow", "NEUTRAL")).upper()
    fr = market_state.get("funding_rate", 0) or 0
    mm = market_state.get("mm_score", 0) or 0
    fg = market_state.get("fear_greed", 50) or 50
    pos = market_state.get("positioning_greed")  # v2.1: Binance L/S proxy (None if not available)
    
    # v2.1: Cognitive Dissonance Flag
    # Retail says fearful (low F&G) but behavior is double Long (high positioning) -> Spring trap
    cognitive_dissonance = False
    if pos is not None:
        cognitive_dissonance = (fg < 25 and pos > 60) or (fg > 75 and pos < 40)
    
    # Determine Phase based on consolidated signals
    if change < -15 and fg < 20:
        phase = "SPRING_CONFIRMED"
    elif cognitive_dissonance and fg < 25 and change < -5:
        # v2.1: Retail panic (F&G<25) but double Long (Pos>60) + price dropping -> Spring imminent
        phase = "SPRING_CONFIRMED"
    elif "DISTRIBUT" in elite_flow and change > 0 and mm > 30:
        phase = "DISTRIBUTION"
    elif "ACCUMUL" in elite_flow and mm < 10:
        phase = "ACCUMULATION"
    elif change < -2 or price < 65000:
        # Price is dropping or in low range
        if price < 63000:
            phase = "PHASE_E_AT_TARGET"
        else:
            phase = "PHASE_E_ABOVE_TARGET"
    else:
        phase = "PHASE_E_AT_TARGET"  # Default conservative
    
    template = APEX_PHASE_ALLOCATION.get(phase, APEX_PHASE_ALLOCATION["PHASE_E_AT_TARGET"])
    
    tranches = []
    net = 0.0
    for label, cfg in template.items():
        side = cfg["side"]
        pct = cfg["pct"]
        method = cfg["method"]
        horizon = cfg.get("horizon", "1W")
        
        # Calculate conviction from signal strength
        conv = 35 + min(30, abs(change) * 3)
        if side == "LONG" and fr < -0.005:
            conv += 10  # Negative funding -> Long has edge
        elif side == "SHORT" and fr > 0.005:
            conv += 10
        if side == "LONG" and fg < 25:
            conv += 15  # Extreme Fear = contrarian Long signal for APEX
        elif side == "SHORT" and fg > 75:
            conv += 15  # Extreme Greed = contrarian Short signal
        
        # v2.1: Cognitive Dissonance boost
        if cognitive_dissonance:
            if side == "LONG" and fg < 25 and pos and pos > 60:
                conv += 10  # Spring trap signal — APEX accumulates before retail
            elif side == "SHORT" and fg > 75 and pos and pos < 40:
                conv += 10  # UTAD signal — APEX distributes before retail
        
        conv = min(85, conv)  # APEX SM cap at 85 (never 100 — requires LLM)
        
        entry_zone = "N/A"
        if method == "LIMIT" and price > 0:
            entry_zone = f"${max(55000, price * 0.93):,.0f}-${price * 0.97:,.0f}"
        elif method in ("ICEBERG", "DCA") and price > 0:
            entry_zone = f"${price * 0.99:,.0f}-${price * 1.01:,.0f}"
        elif method == "DARK_POOL":
            entry_zone = "OTC/DarkPool"
        elif method == "MARKET":
            entry_zone = "MARKET"
        
        cd_flag = " CD!" if cognitive_dissonance else ""
        tranches.append(PositionTranche(
            label=label, side=side, allocation_pct=pct,
            method=method, entry_zone=entry_zone,
            conviction=conv, time_horizon=horizon,
            reasoning=f"SM_v2 Phase={phase}{cd_flag}"
        ))
        
        if side == "LONG":
            net += pct / 100.0
        elif side == "SHORT":
            net -= pct / 100.0
    
    dominant = "ACCUMULATE" if net > 0.1 else ("DISTRIBUTE" if net < -0.1 else "HOLD")
    
    pos_str = f"Pos={pos}" if pos is not None else "Pos=N/A"
    return PortfolioAllocation(
        tier="APEX", tranches=tranches, net_exposure=round(net, 4),
        dominant_action=dominant,
        reasoning=f"SM_v2 Phase={phase} | ${price:,.0f} | Elite={elite_flow} | FR={fr:.5f} | F&G={fg} | {pos_str} | CD={cognitive_dissonance}"
    )


def hft_portfolio_sm(market_state: dict, cascade: CascadeContext) -> PortfolioAllocation:
    """HFT Multi-Strategy SM: Momentum + Mean-Rev + Arb running in parallel.
    
    4 regimes: TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE.
    Each regime allocates different % of capital to each strategy.
    """
    change = market_state.get("change_24h", 0) or 0
    volume = market_state.get("volume_24h", 0) or 0
    fr = market_state.get("funding_rate", 0) or 0
    price = market_state.get("price", 0) or 0
    
    # Determine regime
    if abs(change) > 5:
        regime = "TRENDING_UP" if change > 0 else "TRENDING_DOWN"
    elif volume > 3e10:  # High volume but price ranges sideways
        regime = "VOLATILE"
    else:
        regime = "RANGING"
    
    template = HFT_STRATEGY_ALLOCATION[regime]
    
    tranches = []
    net = 0.0
    for label, cfg in template.items():
        side = cfg["side"]
        pct = cfg["pct"]
        
        conv = 50 + min(30, abs(change) * 4)
        if "MOMENTUM" in label and abs(change) > 3:
            conv += 15
        elif "MEAN_REV" in label and abs(fr) > 0.01:
            conv += 10
        conv = min(90, conv)
        
        tranches.append(PositionTranche(
            label=label, side=side, allocation_pct=pct,
            method="MARKET", entry_zone="MARKET" if side != "FLAT" else "N/A",
            conviction=conv if side != "FLAT" else 0,
            time_horizon="1H",
            reasoning=f"HFT regime={regime}"
        ))
        
        if side == "LONG":
            net += pct / 100.0
        elif side == "SHORT":
            net -= pct / 100.0
    
    dominant = "BUY" if net > 0.1 else ("SELL" if net < -0.1 else "HOLD")
    
    return PortfolioAllocation(
        tier="HFT", tranches=tranches, net_exposure=round(net, 4),
        dominant_action=dominant,
        reasoning=f"HFT regime={regime} | Δ={change:.1f}% | Vol=${volume:,.0f}"
    )


def smart_portfolio_sm(market_state: dict, cascade: CascadeContext,
                       apex_portfolio: PortfolioAllocation) -> PortfolioAllocation:
    """SMART Money Pilot Fish: Identify what APEX is doing -> piggyback.
    
    Rules:
    - Mirror APEX dominant_action but conviction is 20% lower
    - Allocation smaller than APEX (max 40% portfolio in one direction)
    - Exit earlier than APEX (shorter time_horizon)
    - NO hedging (small capital, insufficient margin to hedge)
    """
    apex_dominant = apex_portfolio.dominant_action
    apex_net = apex_portfolio.net_exposure
    fg = market_state.get("fear_greed", 50) or 50
    
    tranches = []
    if apex_dominant == "ACCUMULATE" and apex_net > 0.05:
        # APEX is accumulating -> SMART accumulates too but smaller
        follow_pct = min(40, int(abs(apex_net) * 50))
        conv = min(70, abs(apex_net) * 80)
        # Contrarian boost: if F&G < 30 = better opportunity
        if fg < 30:
            follow_pct = min(55, follow_pct + 15)
            conv = min(80, conv + 10)
        tranches.append(PositionTranche(
            label="FOLLOW_ELITE_LONG", side="LONG", allocation_pct=follow_pct,
            method="MARKET", entry_zone="MARKET",
            conviction=conv, time_horizon="1D",
            reasoning=f"Pilot fish: APEX {apex_dominant} (net={apex_net:+.2f})"
        ))
        tranches.append(PositionTranche(
            label="RESERVE", side="FLAT", allocation_pct=100 - follow_pct,
            method="N/A", entry_zone="N/A",
            conviction=0, time_horizon="N/A",
        ))
    elif apex_dominant == "DISTRIBUTE" and apex_net < -0.05:
        # APEX is distributing -> SMART also exits but faster
        follow_pct = min(35, int(abs(apex_net) * 45))
        conv = min(60, abs(apex_net) * 70)
        tranches.append(PositionTranche(
            label="FOLLOW_ELITE_SHORT", side="SHORT", allocation_pct=follow_pct,
            method="MARKET", entry_zone="MARKET",
            conviction=conv, time_horizon="4H",
            reasoning=f"Pilot fish: APEX {apex_dominant} (net={apex_net:+.2f})"
        ))
        tranches.append(PositionTranche(
            label="RESERVE", side="FLAT", allocation_pct=100 - follow_pct,
            method="N/A", entry_zone="N/A",
            conviction=0, time_horizon="N/A",
        ))
    else:
        # APEX HOLD or HEDGE -> SMART also HOLD
        tranches.append(PositionTranche(
            label="WAIT", side="FLAT", allocation_pct=100,
            method="N/A", entry_zone="N/A",
            conviction=0, time_horizon="N/A",
            reasoning=f"APEX neutral ({apex_dominant}) — standby"
        ))
    
    net = sum(
        (t.allocation_pct / 100.0 if t.side == "LONG" else
         -t.allocation_pct / 100.0 if t.side == "SHORT" else 0.0)
        for t in tranches
    )
    
    return PortfolioAllocation(
        tier="SMART", tranches=tranches, net_exposure=round(net, 4),
        dominant_action=apex_dominant if abs(net) > 0.05 else "HOLD",
        reasoning=f"Pilot fish: APEX={apex_dominant} net={apex_net:+.2f} | F&G={fg}"
    )

def init_population(seed: int = 42) -> List[MarketAgentConfig]:
    np.random.seed(seed)
    population = []
    agent_id_counter = 0
    
    for tier_name, config in TIER_CONFIG.items():
        count = config["count"]
        
        sentiment_biases = np.random.normal(config["bias_mean"], config["bias_std"], count)
        herd_factors = np.random.beta(config["herd_alpha"], config["herd_beta"], count)
        panic_thresholds = config["panic"] + np.random.normal(0, abs(config["panic"] * 0.1), count)
        fomo_thresholds = config["fomo"] + np.random.normal(0, abs(config["fomo"] * 0.1), count)
        
        tier_personas = [p["id"] for p in LLM_PERSONAS if p["tier"] == tier_name]
        if not tier_personas:
            tier_personas = [f"{tier_name}_DEFAULT"]
            
        capital_per_agent = config["capital_weight"] / count if count > 0 else 0
        
        for i in range(count):
            agent = MarketAgentConfig(
                agent_id=agent_id_counter,
                tier=tier_name,
                persona_name=tier_personas[i % len(tier_personas)],
                capital_weight=capital_per_agent,
                sentiment_bias=float(sentiment_biases[i]),
                panic_threshold=float(panic_thresholds[i]),
                fomo_threshold=float(fomo_thresholds[i]),
                herd_factor=float(herd_factors[i]),
                conviction_range=config["conviction"],
                influence_weight=config["influence"],
                active_sessions=config["sessions"].copy()
            )
            population.append(agent)
            agent_id_counter += 1
            
    logger.info(f"Initialized {len(population)} agents across 6 tiers")
    return population

def compute_cascade_context(tier_results: Dict[str, Dict], current_tier: str) -> CascadeContext:
    if not tier_results:
        return CascadeContext()
    
    tier_order = ["APEX", "HFT", "QUANT", "PASSIVE", "SMART_CONTRARIAN", "SMART_VALUE", "SEMI_SMART", "RETAIL_FOMO", "RETAIL_FUD", "RETAIL_LEVERAGE"]
    decided_tiers = [t for t in tier_order if t in tier_results and t != current_tier]
    
    if not decided_tiers:
        return CascadeContext()
    
    # 1. Weighted pressure: Use normalized_net instead of net to avoid double-weighting
    total_weight = 0.0
    weighted_sum = 0.0
    for t in decided_tiers:
        influence = TIER_CASCADE_INFLUENCE.get(t, 0.05)
        norm_net = tier_results[t].get("normalized_net", 0.0)
        weighted_sum += norm_net * influence
        total_weight += influence
    
    weighted_pressure = weighted_sum / total_weight if total_weight > 0 else 0.0
    
    # 2. Consensus strength: Use normalized_net to treat RETAIL/SMART equally
    nets = [tier_results[t].get("normalized_net", 0.0) for t in decided_tiers]
    positive = sum(1 for n in nets if n > 0.05)
    negative = sum(1 for n in nets if n < -0.05)
    neutral = len(nets) - positive - negative
    
    majority = max(positive, negative, neutral)
    consensus_strength = majority / len(nets) if nets else 0.0
    
    # 3. Cascade momentum: Use normalized_net
    if len(decided_tiers) >= 2:
        prev_net = tier_results[decided_tiers[-2]].get("normalized_net", 0.0)
        last_net = tier_results[decided_tiers[-1]].get("normalized_net", 0.0)
        cascade_momentum = last_net - prev_net
    else:
        cascade_momentum = 0.0
    
    # 4. Dominant action
    buy_count = sum(1 for t in decided_tiers if tier_results[t].get("buy_pct", 0) > max(tier_results[t].get("sell_pct", 0), tier_results[t].get("hold_pct", 0)))
    sell_count = sum(1 for t in decided_tiers if tier_results[t].get("sell_pct", 0) > max(tier_results[t].get("buy_pct", 0), tier_results[t].get("hold_pct", 0)))
    dominant_action = "BUY" if buy_count > sell_count else ("SELL" if sell_count > buy_count else "HOLD")
    
    return CascadeContext(
        weighted_pressure=weighted_pressure,
        consensus_strength=consensus_strength,
        cascade_momentum=cascade_momentum,
        dominant_action=dominant_action,
        tiers_decided=len(decided_tiers)
    )

def agent_decide_sm(agent: MarketAgentConfig, market_state: dict, cascade: CascadeContext) -> Decision:
    """Tier-Specific State Machine: each tier decides based on DIFFERENT data.
    
    v1.1: Instead of just using price_change_pct for all tiers,
    each tier now computes effective_bias from tier-appropriate data:
    - APEX: elite_flow + OI dominance (institutional signals)
    - HFT: price momentum + volume spike (micro-structure)
    - QUANT: funding_rate mean-reversion + OI (positioning)
    - PASSIVE: only checks change_24h vs extreme drawdown
    - SMART: fear_greed contrarian + price structure
    - RETAIL: fear_greed herd + price action (emotional)
    """
    noise = random.gauss(0, 0.05)
    price_change_pct = market_state.get("change_24h") or 0.0
    fear_greed = market_state.get("fear_greed") or 50
    elite_flow = str(market_state.get("elite_flow") or "NEUTRAL")
    volume = market_state.get("volume_24h") or 0.0
    funding_rate = market_state.get("funding_rate") or 0.0
    
    crowd_pressure = cascade.weighted_pressure
    consensus = cascade.consensus_strength
    momentum = cascade.cascade_momentum
    dominant_action = cascade.dominant_action
    
    # ── Tier-specific signal computation ──
    if agent.tier == "APEX":
        # APEX: contra-sentiment + institutional flow
        # APEX is ANTI-HERD: when consensus is high, APEX is more cautious (dampen)
        elite_signal = 0.3 if "ACCUMUL" in elite_flow.upper() else (-0.3 if "DISTRIBUT" in elite_flow.upper() else 0.0)
        contrarian_dampen = 1.0 - consensus * 0.3  # High consensus -> APEX dampens bias
        effective_bias = elite_signal * 0.6 * contrarian_dampen + agent.sentiment_bias * 0.3 + noise
    
    elif agent.tier == "HFT":
        # HFT: pure momentum + volume + cascade momentum (amplify if momentum building)
        price_momentum = min(1.0, max(-1.0, price_change_pct / 5.0))
        vol_confirm = 1.2 if volume > 1e9 else 0.8
        # HFT amplifies when cascade momentum aligns with price momentum
        momentum_amp = 1.0 + abs(momentum) * 0.5 if (momentum * price_momentum > 0) else 0.8
        dom_bias = 0.1 if dominant_action == "BUY" else (-0.1 if dominant_action == "SELL" else 0.0)
        effective_bias = price_momentum * vol_confirm * momentum_amp * 0.6 + crowd_pressure * 0.4 + dom_bias + noise
    
    elif agent.tier == "QUANT":
        # QUANT: mean-reversion on funding + positioning
        fr_signal = -funding_rate * 10000  # Negative funding = contrarian long
        effective_bias = fr_signal * 0.5 + agent.sentiment_bias * 0.3 + crowd_pressure * 0.2 + noise
    
    elif agent.tier == "PASSIVE":
        # PASSIVE: only panic on extreme drawdowns, otherwise DCA BUY
        if price_change_pct <= agent.panic_threshold:  # Use configured threshold instead of -20.0
            return Decision(action="HOLD", conviction=10.0, reasoning="Extreme drawdown — pause DCA")
        return Decision(action="BUY", conviction=random.uniform(10, 25), reasoning="DCA schedule")
    
    elif agent.tier == "SMART_CONTRARIAN":
        # SMART_CONTRARIAN: contrarian on extreme F&G + fade crowd when consensus is high
        fg_signal = (fear_greed - 50) / 50.0  # [-1, 1]
        contrarian_boost = 1.2 + consensus * 0.6 if consensus > 0.6 else 1.0
        trauma_dampen = max(0.2, 1.0 - agent.trauma_index) if hasattr(agent, 'trauma_index') else 1.0
        effective_bias = -fg_signal * 0.5 * contrarian_boost * trauma_dampen + crowd_pressure * agent.sentiment_bias * 0.2 * trauma_dampen + noise
        
    elif agent.tier == "SMART_VALUE":
        # SMART_VALUE: Accumulates on deep negative price change, ignores herd/consensus
        price_drop = min(0.0, price_change_pct)
        effective_bias = -price_drop * 0.05 + agent.sentiment_bias * 0.5 + noise
        
    elif agent.tier == "SEMI_SMART":
        # SEMI_SMART: Trend follower, breakout trader. FOMOes on positive change, but panics on drop
        # Vulnerable to validation trap.
        trend_follow = min(1.0, max(-1.0, price_change_pct / 4.0))
        effective_bias = trend_follow * 0.5 + crowd_pressure * 0.3 + agent.sentiment_bias * 0.2 + noise
        # Pyramiding check (handled in swarm_engine updates, but we set a high positive bias when trend is strong)
        if price_change_pct > 2.0:
            effective_bias += 0.2
            
    elif agent.tier == "RETAIL_FOMO":
        # RETAIL_FOMO: Chases green candles, high positive fomo sentiment
        fg_signal = (fear_greed - 50) / 50.0
        effective_bias = max(0.0, fg_signal) * 0.6 + max(0.0, price_change_pct / 3.0) * 0.4 + crowd_pressure * 0.3 + noise
        
    elif agent.tier == "RETAIL_FUD":
        # RETAIL_FUD: Panic sell on any drop, negative bias
        fg_signal = (fear_greed - 50) / 50.0
        effective_bias = fg_signal * 0.4 + min(0.0, price_change_pct / 2.0) * 0.6 + crowd_pressure * 0.4 + noise
        
    elif agent.tier == "RETAIL_LEVERAGE":
        # RETAIL_LEVERAGE: High leverage, extreme herd following
        fg_signal = (fear_greed - 50) / 50.0
        herd_amplifier = 1.2 + consensus * 1.0
        effective_bias = fg_signal * agent.herd_factor * herd_amplifier * 0.6 + crowd_pressure * agent.herd_factor * 0.5 + noise
    
    else:
        # Fallback
        effective_bias = agent.sentiment_bias * (1 - agent.herd_factor) + crowd_pressure * agent.herd_factor + noise
    
    # ── Universal threshold logic ──
    if price_change_pct <= agent.panic_threshold:
        return Decision(action="SELL", conviction=min(100.0, random.uniform(70, 100)))
    elif price_change_pct >= agent.fomo_threshold:
        return Decision(action="BUY", conviction=min(100.0, random.uniform(60, 95)))
    elif effective_bias > 0.3:
        return Decision(action="BUY", conviction=min(100.0, random.uniform(agent.conviction_range[0], agent.conviction_range[1])))
    elif effective_bias < -0.3:
        return Decision(action="SELL", conviction=min(100.0, random.uniform(agent.conviction_range[0], agent.conviction_range[1])))
    else:
        return Decision(action="HOLD", conviction=min(100.0, random.uniform(0, 30)))

def aggregate_tier(decisions: List[Decision], capital_weight: float) -> Dict[str, Any]:
    if not decisions:
        return {"buy_pct": 0.0, "sell_pct": 0.0, "hold_pct": 0.0, "net": 0.0, "normalized_net": 0.0, "population": 0}
        
    buy_weight = 0.0
    sell_weight = 0.0
    hold_weight = 0.0
    
    for d in decisions:
        weight = d.conviction / 100.0
        action = d.action.upper()
        if action == "BUY":
            buy_weight += weight
        elif action == "SELL":
            sell_weight += weight
        else:
            hold_weight += weight
            
    total_weight = buy_weight + sell_weight + hold_weight
    if total_weight == 0:
        return {"buy_pct": 0.0, "sell_pct": 0.0, "hold_pct": 1.0, "net": 0.0, "normalized_net": 0.0, "population": len(decisions)}
        
    buy_pct = buy_weight / total_weight
    sell_pct = sell_weight / total_weight
    hold_pct = hold_weight / total_weight
    
    normalized_net = buy_pct - sell_pct
    net = normalized_net * capital_weight
    
    return {
        "buy_pct": buy_pct,
        "sell_pct": sell_pct,
        "hold_pct": hold_pct,
        "net": net,
        "normalized_net": normalized_net,
        "population": len(decisions)
    }

def detect_divergence(tier_results: Dict[str, Dict[str, Any]]) -> str:
    # Use normalized_net to evaluate tiers fairly
    apex_net = tier_results.get("APEX", {}).get("normalized_net", 0.0)
    
    # Calculate average representative for Retail
    retail_net = sum([
        tier_results.get("RETAIL_FOMO", {}).get("normalized_net", 0.0),
        tier_results.get("RETAIL_FUD", {}).get("normalized_net", 0.0),
        tier_results.get("RETAIL_LEVERAGE", {}).get("normalized_net", 0.0)
    ]) / 3.0
    
    if apex_net < -0.3 and retail_net > 0.3:
        return "APEX_VS_RETAIL"
    if retail_net < -0.3 and apex_net > 0.3:
        return "RETAIL_VS_APEX"
        
    all_nets = [res.get("normalized_net", 0.0) for res in tier_results.values() if isinstance(res, dict) and "normalized_net" in res]
    if all_nets and all(net > 0.2 for net in all_nets):
        return "CONSENSUS_BULL"
    if all_nets and all(net < -0.2 for net in all_nets):
        return "CONSENSUS_BEAR"
        
    smart_money_avg = sum([
        tier_results.get("APEX", {}).get("normalized_net", 0.0),
        tier_results.get("HFT", {}).get("normalized_net", 0.0),
        tier_results.get("QUANT", {}).get("normalized_net", 0.0),
        tier_results.get("SMART_CONTRARIAN", {}).get("normalized_net", 0.0),
        tier_results.get("SMART_VALUE", {}).get("normalized_net", 0.0)
    ]) / 5.0
    
    dumb_money_avg = sum([
        tier_results.get("SEMI_SMART", {}).get("normalized_net", 0.0),
        tier_results.get("RETAIL_FOMO", {}).get("normalized_net", 0.0),
        tier_results.get("RETAIL_FUD", {}).get("normalized_net", 0.0),
        tier_results.get("RETAIL_LEVERAGE", {}).get("normalized_net", 0.0)
    ]) / 4.0
    
    if smart_money_avg * dumb_money_avg < 0:
        return "SMART_MONEY_DIVERGENCE"
        
    return "MIXED"
