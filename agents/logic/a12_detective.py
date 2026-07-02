"""
🧬 DNA: v16.6 (Sovereign Purity & Narrative Detective) [DNA Header]
🏢 UNIT: AEO_DETECTIVE (A12)
🛠️ ROLE: COGNITIVE_MANIPULATION_HUNTER
📖 DESC: Cognitive Manipulation Detection System (AEO). Identifies AI-baiting, bot-driven narratives, and fake media campaigns by MM.
🔗 CALLS: tools/llm_router.py, tools/narrative_guard.py
📟 I/O: Redis: aeo:reports, aeo:flagged_urls (SET), zcl:A12:heartbeat
🛡️ INTEGRITY: AEO-Detection-Purity, Narrative-Deception-Watch, Cognitive-Shield.
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))

import os
import re
import json
import time
import hmac
import uuid
import hashlib
import logging
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import deque, defaultdict
from urllib.parse import urlparse

# redis import removed (using matrix)
from dotenv import load_dotenv
import nlm_changelog
from imperial_state import matrix
from llm_router import ALGO_CYCLE_INTERVAL_SEC
last_algo_time = 0
_FORCE_NEXT_ANALYSIS = True  # Forced run once bypassing throttle on boot or real-time request
import divergence_engine  # DNA v16.4.1: Trigger synthesis after Brain B
from agent_session_logger import log_session as _log_agent_session, get_drift_context as _get_drift_context, get_aeo_case_studies as _get_aeo_case_studies
from tools.megafeed_engine import hunt_keywords, detect_velocity_spike, get_nvd_score, get_cbm_score

# ── Import security modules (per project structure) ────────────────────────────
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))
try:
    from dos_guardian import get_agent_instructions
    from a09_immunity import sanitize_text_for_llm as a09_sanitize_text
    from narrative_guard import full_guard_check
    _HAS_GUARDS = True
except ImportError as e:
    print(f"[A12_BOOT_ERROR] Failed to load guards: {e}", flush=True)
    try:
        from a09_immunity import sanitize_text_for_llm as a09_sanitize_text
    except:
        a09_sanitize_text = lambda x, **kwargs: x
    _HAS_GUARDS = False

from llm_router import router_api_call
from imperial_brain import brain

# ── Load env ──────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / "config" / ".env")

# REDIS_URL handled by matrix
# API Keys removed: handled centrally by llm_router
HMAC_SECRET        = os.getenv("IMMUNITY_HMAC_SECRET", "")

BASE_DIR        = Path(__file__).parent.parent.parent
AEO_LAB_DIR     = BASE_DIR / "aeo_lab"

LOGS_DIR        = AEO_LAB_DIR / "logs"
NLM_DIR         = BASE_DIR / "notebooklm_sources" / "aeo"
FLAGGED_CACHE   = AEO_LAB_DIR / "flagged_urls.json"
STATS_FILE      = AEO_LAB_DIR / "stats.json"

for _d in [AEO_LAB_DIR, LOGS_DIR, NLM_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
from imperial_state import setup_agent_logger
log = setup_agent_logger("A12", "12_MANIPULATION_DETECTIVE")

# matrix is imported from imperial_state

# ── Security: Injection patterns (per security_hardening.py) ────────────────
_INJECTION_PATS = [
    r"ignore\s+(previous|all|above|prior)\s+(instructions?|prompts?|context)",
    r"you\s+are\s+now\s+a?\s*(different|new|other)",
    r"new\s+(instruction|task|system\s*prompt)",
    r"override\s+(output|response|behavior|rules)",
    r"print\s+(your\s+)?(api\s*key|system\s+prompt|secret|password)",
    r"<\|?(?:im_start|im_end|system|user|assistant)\|?>",
    r"\[INST\]|\[\/INST\]",
    r"OVERRIDE_ZCL|ZCL_INJECT|AEO_BYPASS",
    r"eval\s*\(|exec\s*\(|__import__\s*\(",
]
_COMPILED_INJECTIONS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _INJECTION_PATS]

# ── Psychological anchor: immutable questions - never changed by input ─────────
NEO_TAM_LY_ANCHOR = """
=== IMMUTABLE AXIOM ===
Agent 12 DOES NOT analyze whether information is true or false.
Agent 12 ANALYZES: is the content created with the intent for AI to learn and cite it as fact?

7 anchor questions (always ask in this order):
1. Is this content written for AI reading or human reading?
2. If GPT-5 was trained on 1000 articles like this, what would it "learn"?
3. Who benefits if this answer becomes the "default truth" in AI?
4. When does this pattern appear relative to market/geopolitical moves?
5. Are there any money flows/positions placed before this narrative spreads?
6. PROPAGATION VELOCITY: Does this news burst simultaneously (SYNTHETIC) or spread gradually (ORGANIC)?
   If simultaneous -> measure Variance timestamps. Low variance = paid PR campaign.
7. ASYMMETRY: Media explodes but price stays flat = Iceberg wall distribution (unloading).
   Media is quiet but price moves strongly = Elite secret accumulation.
8. ORGANIZATIONAL CYCLICALITY: Do manipulation signs align with SEC 13F filing cycles (distribution)? (IFT)
9. DERIVATIVES DIVERGENCE: Did Big Boys buy hidden Puts/Shorts before pumping the price? (OFND)

Verdict is NOT "true/false" — verdict is "AEO INTENT or ORGANIC".
=== END ANCHOR ===
"""

# ── Rate limit cache (against DoS inputs) ───────────────────────────────────────
_url_scan_times: deque = deque(maxlen=100)
_MAX_SCANS_PER_HOUR = 50


# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — INPUT SECURITY
# ══════════════════════════════════════════════════════════════════════════════

def _sanitize_content(text: str, source: str = "") -> tuple:
    """
    Use A09 Ultimate Filter to sanitize.
    Returns (clean_text, was_poisoned).
    """
    if not isinstance(text, str):
        return "", False
    clean_text = a09_sanitize_text(text, max_len=5000)
    was_poisoned = len(clean_text) != min(len(text), 5000) # Simple check
    return clean_text, was_poisoned


def _validate_url(url: str) -> bool:
    """Only fetch URL from http/https, no file://, no localhost."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.netloc.lower()
        blocked = ["localhost", "127.0.0.1", "0.0.0.0", "::1", "redis", "chroma", "ollama"]
        return not any(b in host for b in blocked)
    except Exception:
        return False


def _rate_limit_check() -> bool:
    """Maximum MAX_SCANS_PER_HOUR URL scans/hour."""
    now = time.time()
    _url_scan_times.append(now)
    hour_ago = now - 3600
    recent = [t for t in _url_scan_times if t > hour_ago]
    return len(recent) <= _MAX_SCANS_PER_HOUR





# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — FETCH CONTENT
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_content(url: str, timeout: int = 15) -> dict:
    """
    Fetch URL content with safety checks.
    Do not fetch if URL is invalid or rate limit exceeded.
    """
    if not _validate_url(url):
        return {"error": "URL_INVALID", "url": url}
    if not _rate_limit_check():
        return {"error": "RATE_LIMIT", "url": url}

    try:
        headers = {
            "User-Agent": "ZeroCutlossResearcher/1.0 (academic research)",
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = requests.get(url, timeout=timeout, headers=headers,
                            allow_redirects=True, stream=False)
        resp.raise_for_status()

        # Strip raw HTML tags (do not parse full DOM to avoid XSS-style attack)
        raw = resp.text[:50000]
        clean_text = re.sub(r"<[^>]+>", " ", raw)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()[:8000]

        # ── C1 FILTER (Qwopus3.5:4b) — with Content Hash Dedup ──
        # Refine spam content into core metadata (3 Keywords, 1 Sentiment, 1 Elite Sign)
        # 🛡️ DEDUP: MD5 hash of raw content. If already analyzed -> bypass LLM
        _content_hash = hashlib.md5(clean_text[:4000].encode("utf-8", errors="ignore")).hexdigest()
        _dedup_key = f"zcl:system:a12:c1:{_content_hash}"
        c1_metadata = "{}"
        try:
            _cached_c1 = matrix.client.get(_dedup_key)
            if _cached_c1:
                _cached_str = _cached_c1.decode("utf-8") if isinstance(_cached_c1, bytes) else str(_cached_c1)
                log.info(f"[A12 🛡️ DEDUP] Article already processed (hash={_content_hash[:8]}...) - bypassing LLM, using cache")
                c1_metadata = _cached_str
            else:
                c1_prompt = f"""Refine the following article:
{clean_text[:4000]}

Return JSON in EXACTLY the following structure:
{{
  "keywords": ["key1", "key2", "key3"],
  "sentiment": "POSITIVE or NEGATIVE or NEUTRAL",
  "elite_sign": "Elite manipulation signs (if any, otherwise NONE)",
  "summary": "One-sentence summary"
}}"""
                c1_resp = router_api_call(c1_prompt, agent_id="A12_CRAWL", est_tokens=150)
                start = c1_resp.find("{")
                end = c1_resp.rfind("}") + 1
                if start != -1 and end != 0:
                    c1_metadata = c1_resp[start:end]
                    # 🛡️ Save to Redis with TTL 6h for dedup
                    matrix.client.setex(_dedup_key, 21600, c1_metadata)
        except Exception as e:
            log.warning(f"[A12] C1 Filter/Dedup error: {e}")

        return {
            "url":         url,
            "domain":      urlparse(url).netloc,
            "status_code": resp.status_code,
            "content":     clean_text,
            "metadata":    c1_metadata,
            "content_len": len(clean_text),
            "publish_date": _extract_date(resp.text),
        }
    except requests.Timeout:
        return {"error": "TIMEOUT", "url": url}
    except requests.HTTPError as e:
        return {"error": f"HTTP_{e.response.status_code}", "url": url}
    except Exception as e:
        return {"error": str(e)[:100], "url": url}


def _extract_date(html: str) -> Optional[str]:
    """Extract publish date from HTML meta tags."""
    patterns = [
        r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"',
        r'<meta[^>]+name="publish_date"[^>]+content="([^"]+)"',
        r'"datePublished"\s*:\s*"([^"]+)"',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            return m.group(1)[:25]
    return None



def _aiq_semantic_filter(texts: list, loud: bool = False) -> list:
    """ AI-Q Semantic Filter for A12: CRAWL_LOUD used for URGENT cases requiring Cloud LLM """
    if not texts: return []
    filtered = []
    agent_id = "A12_CRAWL_LOUD" if loud else "A12_CRAWL"
    for i in range(0, len(texts), 20):
        batch = [a09_sanitize_text(t, max_len=2000) for t in texts[i:i+20]]
        payload = "\\n".join(f"[{idx}] {t[:500]}" for idx, t in enumerate(batch))
        prompt = f"Filter segments containing AEO or shill/manipulation:\\n{payload}\\nReturn a JSON array of valid IDs, e.g., [0, 2]"
        try:
            resp = router_api_call(prompt, agent_id=agent_id, est_tokens=50)
            indices = json.loads(re.search(r'\\[.*?\\]', resp).group(0))
            filtered.extend([batch[idx] for idx in indices if 0 <= idx < len(batch)])
        except:
            filtered.extend(batch[:5]) # Fallback
    return filtered

# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — LAYER 1: CITATION GRAPH
# ══════════════════════════════════════════════════════════════════════════════

def analyze_citation_graph(content: str, url: str) -> dict:
    """
    Analyze citation structure.
    Does not evaluate content — evaluates CITATION NETWORK.
    """
    # Extract links
    links = re.findall(r'https?://[^\s\'"<>]+', content)
    domains = [urlparse(l).netloc.replace("www.", "") for l in links if _validate_url(l)]

    own_domain      = urlparse(url).netloc.replace("www.", "")
    external_domains = [d for d in domains if d != own_domain and d]
    unique_roots    = len(set(external_domains))
    total_links     = len(external_domains)

    # Self-reference ratio
    self_refs = sum(1 for d in domains if d == own_domain)
    self_ref_ratio = self_refs / max(1, len(domains))

    # Citation depth estimation (shallow = only links to aggregate sites)
    aggregate_indicators = ["wikipedia", "britannica", "about.com", "investopedia",
                            "medium.com", "substack.com", "quora.com"]
    shallow_count = sum(1 for d in external_domains
                        if any(a in d for a in aggregate_indicators))
    depth_score = 1.0 - (shallow_count / max(1, total_links))  # High = deeper

    # Funding flag detection (organization names in content)
    funding_flags = []
    flag_keywords = {
        "pharma_funded": ["pfizer", "moderna", "johnson & johnson", "novartis", "merck"],
        "tech_lobby":    ["google foundation", "facebook fund", "openai grant", "microsoft research"],
        "finance_lobby": ["blackrock institute", "vanguard research", "jp morgan analysis"],
        "defense_adj":   ["rand corporation", "atlantic council", "brookings"],
    }
    content_lower = content.lower()
    for flag_type, keywords in flag_keywords.items():
        if any(kw in content_lower for kw in keywords):
            funding_flags.append(flag_type)

    # Circular reference score: cross-links ratio in the same cluster
    circular_score = 0.0
    if unique_roots < 3 and total_links > 5:
        circular_score += 0.4
    if self_ref_ratio > 0.3:
        circular_score += 0.3
    if shallow_count / max(1, total_links) > 0.6:
        circular_score += 0.3
    circular_score = min(1.0, circular_score)

    # Layer score
    layer_score = (
        (circular_score * 0.5) +
        ((1.0 - min(unique_roots, 10) / 10) * 0.3) +
        (len(funding_flags) / 4 * 0.2)
    )

    strongest = ""
    if circular_score > 0.6:
        strongest = f"Closed citation loop (score {circular_score:.2f})"
    elif unique_roots < 3:
        strongest = f"Only {unique_roots} independent root sources with {total_links} links"
    elif funding_flags:
        strongest = f"Detected potential funding: {', '.join(funding_flags)}"

    return {
        "score":                  round(layer_score, 3),
        "circular_reference":     circular_score > 0.5,
        "circular_score":         round(circular_score, 3),
        "unique_root_sources":    unique_roots,
        "total_external_links":   total_links,
        "self_reference_ratio":   round(self_ref_ratio, 3),
        "citation_depth_score":   round(depth_score, 3),
        "funding_flags":          funding_flags,
        "strongest_signal":       strongest,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART 4 — LAYER 2: SEMANTIC INTENT
# ══════════════════════════════════════════════════════════════════════════════

def analyze_semantic_intent(content: str, topic: str) -> dict:
    """
    Analyze ARGUMENTATIVE STRUCTURE, do not judge if conclusion is true/false.
    Use rule-based first — call LLM only when complex reasoning is needed.
    """
    # Conclusion-first score
    total_len = len(content)
    first_20pct = content[:int(total_len * 0.2)].lower()
    conclusion_markers = ["therefore", "thus", "in conclusion", "clearly", "obviously"]
    conclusion_in_intro = sum(1 for m in conclusion_markers if m in first_20pct)
    conclusion_position_score = min(1.0, conclusion_in_intro / 3)

    # Contradiction coverage
    opposition_markers = ["however", "on the other hand", "critics argue", "some say",
                          "but", "although", "despite", "despite this"]
    dismiss_markers = ["but these claims are", "but experts disagree", "despite this myth"]
    opposition_count = sum(1 for m in opposition_markers if m in content.lower())
    dismiss_count    = sum(1 for m in dismiss_markers if m in content.lower())
    # Low = few opposition views; high dismiss = dismisses opposing views too easily
    contradiction_coverage = min(1.0, opposition_count / 5) * (1.0 - min(1.0, dismiss_count / 3))

    # Authority without citation
    authority_phrases = ["experts say", "studies show", "research indicates",
                         "scientists agree", "data suggests"]
    auth_count   = sum(1 for p in authority_phrases if p in content.lower())
    link_count   = len(re.findall(r"https?://", content))
    authority_unlinked = max(0.0, min(1.0, (auth_count - link_count * 0.5) / max(1, auth_count)))

    # AI structure optimization score (v18.1: Enhanced Fingerprinting)
    ai_signals = []
    if re.search(r"^#{1,3}\s+(what is|how to|why does|when|where)\s", content, re.M | re.I):
        ai_signals.append("faq_headers")
    if re.search(r"(tldr|summary|key takeaways|in brief|bottom line)", content[:500], re.I):
        ai_signals.append("summary_box_front")
    word_count = len(content.split())
    headers = re.findall(r"#{1,4}\s+.+", content)
    if word_count > 100 and len(headers) / max(1, word_count / 100) > 0.5:
        ai_signals.append("header_density_high")
    if re.search(r"<(h[1-6]|strong|em)\b[^>]*>\s*\w{3,}", content, re.I) and len(headers) > 5:
        ai_signals.append("structured_for_extraction")
    # v18.1: Flesch Readability proxy — AEO content has short sentences, simple words
    sentences = re.split(r'[.!?]+', content)
    avg_sentence_len = sum(len(s.split()) for s in sentences) / max(1, len(sentences))
    if avg_sentence_len < 12 and word_count > 100:
        ai_signals.append("low_readability_mechanical")
    # v18.1: Bullet Density Ratio — >50% content is bullet/list = structured for AI
    bullet_lines = len(re.findall(r'^\s*[-\*\u2022\d]+[.)\s]', content, re.M))
    total_lines = max(1, len(content.splitlines()))
    bullet_density = bullet_lines / total_lines
    if bullet_density > 0.5:
        ai_signals.append(f"bullet_density_{bullet_density:.0%}")
    # v18.1: Definition/Dictionary-style article written for AI learning
    if re.search(r"(?:definition|meaning of|refers to|is defined as)", content[:1000], re.I):
        ai_signals.append("dictionary_style_entry")
    ai_structure_score = min(1.0, len(ai_signals) / 5)  # v18.1: denominator increased 4->5 due to new patterns

    # Layer score (v18.1: Increased ai_structure weight 0.15->0.25)
    layer_score = (
        conclusion_position_score * 0.20 +
        (1.0 - contradiction_coverage) * 0.35 +
        authority_unlinked * 0.20 +
        ai_structure_score * 0.25
    )

    strongest = ""
    if conclusion_position_score > 0.6:
        strongest = "Conclusion appears too early — structure is designed to declare, not to convince"
    elif contradiction_coverage < 0.1:
        strongest = f"No actual opposing views found on topic '{topic}'"
    elif authority_unlinked > 0.6:
        strongest = f"{auth_count} instances of 'experts say' but only {link_count} link(s) — authority stacking"
    elif ai_structure_score > 0.6:
        strongest = f"Structure highly optimized for AI extraction: {', '.join(ai_signals)}"

    return {
        "score":                      round(layer_score, 3),
        "conclusion_position_score":  round(conclusion_position_score, 3),
        "contradiction_coverage":     round(contradiction_coverage, 3),
        "authority_unlinked_density": round(authority_unlinked, 3),
        "ai_structure_score":         round(ai_structure_score, 3),
        "ai_structure_signals":       ai_signals,
        "strongest_signal":           strongest,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART 5 — LAYER 3: VELOCITY & COORDINATION
# ══════════════════════════════════════════════════════════════════════════════

def analyze_velocity_coordination(topic: str, timeframe_hours: int = 72) -> dict:
    """
    Analyze velocity and coordination patterns of the narrative.
    Does not fetch every article — uses RSS feeds and search trends.
    """
    # Find narrative volume through free RSS
    rss_feeds = {
        "reuters":    f"https://feeds.reuters.com/reuters/businessNews",
        "coindesk":   f"https://www.coindesk.com/arc/outboundfeeds/rss/",
        "cointelegraph": "https://cointelegraph.com/rss",
        "decrypt":    "https://decrypt.co/feed",
    }

    topic_kw   = topic.lower().replace("/usdt", "").replace("/", " ")
    total_hits = 0
    platform_hits: dict = {}
    publish_times: list = []
    author_domains: set = set()

    for source, feed_url in rss_feeds.items():
        try:
            feed = feedparser.parse(feed_url)
            count = 0
            for entry in feed.entries[:30]:
                title   = entry.get("title", "").lower()
                summary = entry.get("summary", "").lower()
                if any(kw in (title + summary) for kw in topic_kw.split()):
                    count += 1
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        import calendar
                        ts = calendar.timegm(entry.published_parsed)
                        publish_times.append(ts)
                    link = entry.get("link", "")
                    if link:
                        author_domains.add(urlparse(link).netloc.replace("www.", ""))
            log.info(f"[A12] RSS {source}: {count} hits")
            total_hits += count
            platform_hits[source] = count
        except Exception:
            pass

    # Velocity analysis
    cutoff = time.time() - (timeframe_hours * 3600)
    recent_times = [t for t in publish_times if t > cutoff]
    baseline_per_day = 3.0   # Baseline for standard crypto topic
    actual_per_day   = len(recent_times) / (timeframe_hours / 24) if recent_times else 0
    velocity_ratio   = actual_per_day / baseline_per_day if baseline_per_day > 0 else 0

    # Cross-platform synchronization
    active_platforms = sum(1 for v in platform_hits.values() if v > 0)
    cross_platform_sync = min(1.0, active_platforms / len(rss_feeds))

    # Search leads publish detection (proxy: if hits concentrate within last 24h)
    very_recent = [t for t in recent_times if t > time.time() - 86400]
    search_leads_publish = (len(very_recent) / max(1, len(recent_times))) > 0.8 if recent_times else False

    # Author diversity (fewer unique domains = higher concentration)
    author_diversity = min(1.0, len(author_domains) / max(1, total_hits))

    # Layer score
    layer_score = (
        min(1.0, (velocity_ratio - 1) / 9) * 0.40 +   # Velocity > 10x = 1.0
        cross_platform_sync * 0.30 +
        (1.0 if search_leads_publish else 0.0) * 0.20 +
        (1.0 - author_diversity) * 0.10
    )
    layer_score = max(0.0, min(1.0, layer_score))

    strongest = ""
    if velocity_ratio > 5:
        strongest = f"Velocity {velocity_ratio:.1f}x baseline without corresponding news event"
    elif search_leads_publish:
        strongest = "Publish concentrated within 24h — possible priming before event"
    elif cross_platform_sync > 0.75:
        strongest = f"Same narrative on {active_platforms}/{len(rss_feeds)} platforms simultaneously"

    return {
        "score":                   round(float(layer_score), 3),
        "total_hits_72h":          int(total_hits),
        "velocity_ratio":          round(float(velocity_ratio), 2),
        "cross_platform_sync":     round(float(cross_platform_sync), 3),
        "search_leads_publish":    bool(search_leads_publish),
        "active_platforms":        int(active_platforms),
        "author_diversity":        round(float(author_diversity), 3),
        "platform_breakdown":      platform_hits,
        "strongest_signal":        strongest,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART 6 — LAYER 4: EMF CROSS-VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def cross_validate_emf(topic: str) -> dict:
    """
    Cross-validate AEO narrative with signals from A10/A11 and A03.
    Distinguishes regular AEO from financial manipulation AEO.
    """
    a10_signal_match = False
    a11_scenario_match = False
    a03_mm_match = False
    details = []
    missing_data = []

    try:
        # A11 intent report
        msgs = matrix.xrevrange("EMF", "intent:report", count=1)
        if msgs:
            _, fields = msgs[0]
            emf_raw = fields.get("payload")
            if emf_raw:
                emf = json.loads(emf_raw)
                scenario = emf.get("scenario", {}).get("type", "WATCH") if isinstance(emf.get("scenario"), dict) else emf.get("scenario", "WATCH")
                confidence = emf.get("scenario", {}).get("confidence", 0) if isinstance(emf.get("scenario"), dict) else emf.get("confidence", 0)
                if scenario in ("CRISIS_INCOMING", "BOOM_INCOMING", "EXIT_POINT") and confidence > 0.5:
                    a11_scenario_match = True
                    details.append(f"A11: {scenario} (conf={confidence:.2f})")
            else:
                missing_data.append("A11_EMPTY")
        else:
            missing_data.append("A11_EMPTY")
    except Exception as e:
        missing_data.append(f"A11_ERROR: {e}")

    try:
        # A10 scored signals
        msgs = matrix.xrevrange("EMF", "signals:scored", count=1)
        if msgs:
            _, fields = msgs[0]
            emf_scored = fields.get("payload")
            if emf_scored:
                scored = json.loads(emf_scored)
                alert_level = scored.get("alert_level", "LOW")
                if alert_level in ("HIGH", "CRITICAL"):
                    a10_signal_match = True
                    details.append(f"A10: alert_level={alert_level}")
            else:
                missing_data.append("A10_EMPTY")
        else:
            missing_data.append("A10_EMPTY")
    except Exception as e:
        missing_data.append(f"A10_ERROR: {e}")

    try:
        raw_a03 = matrix.get("SENTIMENT", "latest") or {}
        if not raw_a03:
            missing_data.append("A03_EMPTY")
        else:
            if isinstance(raw_a03, str):
                try: raw_a03 = json.loads(raw_a03)
                except: raw_a03 = {}
                
            a03_core = raw_a03.get("algo_core", {})
            if a03_core:
                mm_score = a03_core.get("mm_score", 0)
            else:
                trinity = raw_a03.get("trinity", raw_a03)
                mm_score = trinity.get("metadata", {}).get("mm_score", trinity.get("mm_fingerprint", {}).get("score", 0))
            
            if mm_score >= 70:
                a03_mm_match = True
                details.append(f"A03: mm_score={mm_score}")
            else:
                details.append(f"A03: mm_score={mm_score} (no match)")
    except Exception as e:
        missing_data.append(f"A03_ERROR: {e}")

    financial_aeo_confirmed = a10_signal_match and a11_scenario_match and a03_mm_match

    return {
        "financial_aeo_confirmed": financial_aeo_confirmed,
        "details": details,
        "missing_data": missing_data,
        "confirmation_sources": sum([a10_signal_match, a11_scenario_match, a03_mm_match])
    }


def _goi_llm_brain_a_narrative(content_sanitized: str, topic: str,
                              layer_scores: dict, neo_questions: dict, is_main_cycle: bool = True) -> dict:
    """
    Brain A: Fast Narrative Pattern Recognition.
    """
    # [HingeEBM FIX] Brain A only returns 3 small JSON fields (audience, payload_fingerprint, confidence_a)
    # No need to send 900K chars content — 50K is enough to detect the pattern
    _brain_a_content = content_sanitized[:50000]
    prompt = f"""{NEO_TAM_LY_ANCHOR}
Topic: {topic}
Layer Scores: {json.dumps(layer_scores, ensure_ascii=False)}
Content: <target>\n{_brain_a_content}\n</target>

BRAIN A MISSION:
1. Identify the actual audience (AI vs Human).
2. Detect raw cognitive payloads.

Reply here (raw JSON):
{{"audience": "...", "payload_fingerprint": "...", "confidence_a": 0.0}}"""

    aid_target = "A12A" if is_main_cycle else "A12A_LITE"
    text = brain.think_as(aid_target, prompt, brain_mode="A12_NARRATIVE", est_tokens=5000)
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        raise ValueError("No JSON object could be extracted")
    except Exception as e:
        return {"audience": "UNCLEAR", "payload_fingerprint": "N/A", "confidence_a": 0.0}


def _goi_llm_brain_b_motive(content_sanitized: str, topic: str,
                             layer_scores: dict, brain_a_results: dict, l4_emf: dict, chu_ky: str = "NGAN", is_main_cycle: bool = True) -> dict:
    """
    Brain B: Deep Motive Analysis & Verdict.
    Uses A12_MOTIVE mode (Cerebras/Groq Qwen-32b / Gemini Pro) to draw the verdict.
    v18.1: Inject AEO Case Studies (ratio per topic + 1 sample) + breaking news context.
    """
    # ── Temporal Trajectory data retrieval 1M/6M/12M ──
    try:
        t1m = matrix.client.get("emf:trajectory:1M")
        t6m = matrix.client.get("emf:trajectory:6M")
        t12m = matrix.client.get("emf:trajectory:12M")
        traj_1m = t1m.decode('utf-8') if t1m else "No 1M data"
        traj_6m = t6m.decode('utf-8') if t6m else "No 6M data"
        traj_12m = t12m.decode('utf-8') if t12m else "No 12M data"
    except:
        traj_1m = traj_6m = traj_12m = "Redis Trajectory fetch error"
        
    trajectory_text = f"--- 1 Month Ago ---\n{traj_1m}\n--- 6 Months Ago ---\n{traj_6m}\n--- 12 Months Ago ---\n{traj_12m}"

    # ── 16D Sensors T0 direct retrieval ──
    try:
        raw_sensors = matrix.get("NARRATIVE", "sensors")
        sensors_text = json.dumps(raw_sensors, ensure_ascii=False) if raw_sensors else "{}"
    except:
        sensors_text = "{}"

    # FIX 4: Empty sensor guard — replace useless {} with informative text
    if not sensors_text or sensors_text in ('{}', '"{}"', ''):
        sensors_text = '[NO_SENSOR_DATA — Cognitive sensors unavailable this cycle]'

    try:
        raw_megafeed = matrix.client.get("zcl:A12:megafeed_hunt")
        megafeed_text = raw_megafeed.decode('utf-8') if raw_megafeed else "{}"
    except:
        megafeed_text = "{}"

    # FIX 4: Empty megafeed guard
    if not megafeed_text or megafeed_text in ('{}', '"{}"', ''):
        megafeed_text = '[NO_MEGAFEED_DATA — MegaFeed velocity data unavailable this cycle]'

    # v18.1: Load condensed Case Studies (ratio per topic calculated)
    case_studies_text = ""
    try:
        case_studies_text = _get_aeo_case_studies(max_topics=5, days=7)
    except Exception as e:
        log.warning(f"[A12B] Case studies load error (non-critical): {e}")

    # ── GROUND TRUTH: Read recent verdicts from Snapshot Harvester ──
    try:
        from tools.agent_session_logger import get_recent_verdicts
        _verdicts = get_recent_verdicts("A12", n=6)
        verdicts_str = json.dumps(_verdicts, ensure_ascii=False)[:8000]
    except Exception:
        verdicts_str = "No recent verdicts."

    # ── Read Condensed Chronicle (Condensed Flow) ──
    try:
        with open(BASE_DIR / "agentic" / "knowledge" / "a12_chronicle_compressed.md", "r", encoding="utf-8") as f:
            a12_compressed_flow = f.read()
    except Exception:
        a12_compressed_flow = "a12_chronicle_compressed.md not found"

    # ── A08 Swarm Oracle integration (6 Tiers / 16 Personas) ──
    try:
        a08_pred = matrix.client.get("zcl:a08:swarm_prediction")
        a08_text = a08_pred.decode('utf-8') if a08_pred else "No A08 data"
    except:
        a08_text = "A08 fetch error"

    # Dien Hong Council Minutes
    def _get_council_minutes():
        try:
            from dien_hong_council import load_council_history
            return load_council_history("A12")
        except Exception:
            return ""

    prompt = f"""{NEO_TAM_LY_ANCHOR}
Topic: {topic}
Layer Scores: {json.dumps(layer_scores, ensure_ascii=False)}
Brain A Findings: {json.dumps(brain_a_results, ensure_ascii=False)}
EMF Context (A11): {json.dumps(l4_emf, ensure_ascii=False)}
4. CASE STUDIES COMPARISON: Compare the current pattern with confirmed AEO cases. What is the AEO% ratio for this topic? Which topic is being pushed the most?
6. Provide complete Reasoning. AND YOU MUST provide an additional JSON field dedicated to Commander A05:
   - `expert_commentary`: Extremely concise, sharp commentary to conclude the verdict.

SYNTHETIC REASONING — DO NOT RETURN UNKNOWN:
- Compare with the past to detect the curvature of media compared to price variations.
- If data is weak, analyze the "silence" or "Stealth Fingerprints".
- Specify `confidence_score` (0.0 to 1.0) and `data_quality_verdict`.

[FLOW] (Flow history):
=== LONG-TERM DRIFT CONTEXT ===
{_get_drift_context("A12", tier="FULL")}
=== BASED ON LONG-TERM CONTEXT FLOW {chu_ky} (TRAJECTORY 1M/6M/12M) ===
{trajectory_text}
=== MEDIA FLOW COMPRESSED CHRONICLE (A12 CHRONICLE COMPRESSED) ===
{a12_compressed_flow}
=== HISTORICAL CASE STUDIES ===
{case_studies_text}
=== YOUR LATEST VERDICT DECISION (GROUND TRUTH — 6 SESSIONS AGO) ===
{verdicts_str}
=== PREVIOUS DIEN HONG COUNCIL MINUTES ===
{_get_council_minutes()}

[CURRENT] (Latest reality):
=== LATEST TELEMETRY DATA ===
RAW MEGAFEED SPIKES (Velocity / NVD): {megafeed_text}
RAW COGNITIVE SENSORS (ECS, CAD, NPA, DAR, IFT, OFND): {sensors_text}
=== A08 SWARM ORACLE SIMULATION RESULTS (16 PERSONAS) ===
{a08_text}

[FORECAST 1-48H] (Short term forecast):
=== SHORT TERM FORECAST REQUIREMENTS (1-48H) ===
- Task: Forecast public opinion steering acceleration (NPA), retail acceptance direction via A08 simulation, and potential AEO priming campaigns in the next 1-48h.

THINKING MANDATE (Probabilistic & Counter-factual Prompting):
Before making a decision, you MUST open a <think> tag. Inside this tag, perform:
1. Construct 2 scenarios that could occur (True news vs Manipulated fake news) based on the clear separation between FLOW and CURRENT.
2. Force yourself to doubt the evidence you have. Specialize in analyzing the 4 Sensor Layers (ECS, CAD, NPA, DAR) relative to EMF Context (Dark Pool A10 & Intent A11). Assess the divergence between them.
3. Assign probability (%) to each scenario. Answer the question: "What market data, if it appears, will immediately prove the media assessment at this time is wrong?" (Invalidation Point).
After completing <think>, output the JSON block.

Strictly adhere to JSON rules, do not omit any fields:
{{
  "dien_hong_analysis": "<Analyze the minutes of the Dien Hong meeting and cross-reference>",
  "beneficiary": "...", 
  "payload_hypothesis": "...", 
  "historical_shift_detected": bool, 
  "reasoning": "...", 
  "confidence_score": 0.0, 
  "data_quality_verdict": "GOOD | WEAK | INSUFFICIENT_PROCESSED_AS_STEALTH", 
  "verdict_aeo": "MANUFACTURED | HIGH_AEO | SUSPICIOUS | ORGANIC",
  "expert_commentary": "...",
  "forecast_48h": "<Detailed forecast of how the market will be in the next 1-48h>"
}}"""

    # FIX 3: Truncation guard — cap total prompt at ~100K tokens
    _max_prompt_chars = 400000  # ~100K tokens
    if len(prompt) > _max_prompt_chars:
        log.warning(f"[A12] Brain B prompt too large ({len(prompt)} chars), truncating to {_max_prompt_chars}")
        prompt = prompt[:_max_prompt_chars]

    aid_target = "A12B" if is_main_cycle else "A12B_LITE"
    text = brain.think_as(aid_target, prompt, brain_mode="A12_MOTIVE", est_tokens=15000)
    try:
        from tools.agent_session_logger import log_agent_snapshot
        
        metadata_log = {
            "narrative_sensors": raw_sensors if 'raw_sensors' in locals() and raw_sensors else {},
            "megafeed_spike": json.loads(megafeed_text) if 'megafeed_text' in locals() and megafeed_text != "{}" else {},
            "chu_ky": chu_ky,
            "topic": topic
        }
        log_agent_snapshot("A12", prompt, text, metadata=metadata_log)
    except Exception as e:
        log.warning(f"[A12B] Snapshot log metadata error: {e}")
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(text[start:end])
            
            # ── COMPILED INSIGHT: LEGACY REMOVED — Replaced by Snapshot Harvester ──
                
            return parsed
        raise ValueError("No JSON object could be extracted")
    except:
        # FIX 2: Proper structured fallback — derive verdict from L1/L2/L3 algo scores
        _ls = layer_scores if 'layer_scores' in dir() else {}
        _num_layers = len(_ls)
        _algo_scores = [v.get('score', 0) for v in _ls.values()] if _ls else []
        _avg_algo = sum(_algo_scores) / max(len(_algo_scores), 1)
        _verdict_fl = (
            "MANUFACTURED" if _avg_algo >= 0.80 else
            "HIGH_AEO" if _avg_algo >= 0.60 else
            "SUSPICIOUS" if _avg_algo >= 0.40 else
            "LOW_AEO" if _avg_algo >= 0.20 else "ORGANIC"
        )
        return {
            "dien_hong_analysis": "[A12_API_UNAVAILABLE] Unable to analyze narrative due to API timeout.",
            "beneficiary": "UNKNOWN",
            "payload_hypothesis": "INSUFFICIENT_DATA",
            "historical_shift_detected": False,
            "reasoning": "API timeout — using pure algo_core scores",
            "confidence_score": 0.15,
            "data_quality_verdict": "INSUFFICIENT_PROCESSED_AS_STEALTH",
            "verdict_aeo": _verdict_fl,
            "expert_commentary": f"[A12_FALLBACK] Analysis based on {_num_layers} layers algo. Verdict: {_verdict_fl}. Low confidence due to lack of LLM reasoning.",
            "forecast_48h": "Insufficient LLM data to forecast — refer to algo_core scores."
        }
# ══════════════════════════════════════════════════════════════════════════════
# PART 8 — COMPOSITE SCORE & VERDICT
# ══════════════════════════════════════════════════════════════════════════════

def calculate_composite_verdict(l1: dict, l2: dict, l3: dict, l4: dict,
                                 llm_analysis: dict) -> dict:
    """
    Combine 4 layers + LLM analysis into a final verdict.
    Financial AEO is prioritized — overlap with Elite positioning is the most critical threat.
    """
    # Base composite weights
    WEIGHTS = {
        "citation":  0.20,
        "semantic":  0.35,   # Most important — argumentative structure
        "velocity":  0.25,
        "financial": 0.20,   # Cross-validation with EMF
    }

    financial_score = 0.8 if l4.get("financial_aeo_confirmed") else (
        0.5 if l4.get("confirmation_sources", 0) >= 1 else 0.0
    )

    composite = (
        l1.get("score", 0) * WEIGHTS["citation"] +
        l2.get("score", 0) * WEIGHTS["semantic"] +
        l3.get("score", 0) * WEIGHTS["velocity"] +
        financial_score     * WEIGHTS["financial"]
    )

    # LLM confidence boost (max +0.1)
    boost = min(0.1, float(llm_analysis.get("confidence_score", 0)) / 10.0 if float(llm_analysis.get("confidence_score", 0)) > 1.0 else min(0.1, float(llm_analysis.get("confidence_score", 0))))
    composite = min(1.0, composite + boost)

    # Confidence: high when layers agree
    scores = [l1.get("score", 0), l2.get("score", 0), l3.get("score", 0)]
    score_std = (max(scores) - min(scores)) / max(0.01, sum(scores) / 3)
    confidence = 1.0 - min(0.5, score_std)  # Lower variance = higher confidence

    # Verdict
    if l4.get("financial_aeo_confirmed") and composite >= 0.50:
        verdict = "MANUFACTURED"
        confidence = max(confidence, 0.85)
    elif composite >= 0.80:
        verdict = "MANUFACTURED"
    elif composite >= 0.60:
        verdict = "HIGH_AEO"
    elif composite >= 0.40:
        verdict = "SUSPICIOUS"
    elif composite >= 0.20:
        verdict = "LOW_AEO"
    else:
        verdict = "ORGANIC"

    # Primary signal (strongest layer)
    signal_map = {
        "citation":  l1.get("strongest_signal", ""),
        "semantic":  l2.get("strongest_signal", ""),
        "velocity":  l3.get("strongest_signal", ""),
        "financial": f"Financial AEO confirmed: {l4.get('details', [])}" if l4.get("financial_aeo_confirmed") else "",
    }
    primary_signal = max(signal_map.items(), key=lambda x: len(x[1]))[1] or "No prominent signal"

    return {
        "label":                   verdict,
        "aeo_score":               round(composite, 3),
        "confidence":              round(confidence, 3),
        "financial_aeo_confirmed": l4.get("financial_aeo_confirmed", False),
        "primary_signal":          primary_signal,
        "payload_hypothesis":      llm_analysis.get("payload_hypothesis", ""),
        "beneficiary":             llm_analysis.get("beneficiary", ""),
        "summary":                 llm_analysis.get("reasoning", ""),
        "layer_weights_used":      WEIGHTS,
    }




# ══════════════════════════════════════════════════════════════════════════════
# PART 10 — MAIN FUNCTION: SCAN URL
# ══════════════════════════════════════════════════════════════════════════════

def _detect_optimization_4prong(content: str, topic: str, semantic_l2: dict) -> dict:
    """
    Detect the 4 dimensions of Cognitive Optimization:
    1. MEDIA:  Trending bait, emotional hijack, clickbait patterns
    2. SEO:    Keyword stuffing, structured data, schema markup for search engines
    3. AEO:    AI Answer Engine Optimization (targeting chatbot/assistant responses)
    4. GEO:    Geotargeted narrative (targeting specific regions/markets)
    """
    import re
    lower = content.lower()
    results = {}

    # === 1. MEDIA Optimization (Trending Bait) ===
    media_keywords = [
        "breaking:", "urgent:", "just in:", "exclusive:", "🚨", "🔥",
        "you won't believe", "what nobody tells", "insider reveals",
        "sources say", "confirmed:", "leaked:", "developing:",
    ]
    media_hits = [kw for kw in media_keywords if kw in lower]
    results["MEDIA"] = {
        "detected": len(media_hits) >= 2,
        "score": min(len(media_hits) / 5.0, 1.0),
        "evidence": media_hits[:5],
    }

    # === 2. SEO Optimization (Keyword Stuffing / Schema) ===
    seo_signals = []
    if topic:
        topic_lower = topic.lower()
        topic_count = lower.count(topic_lower)
        density = topic_count / max(len(lower.split()), 1)
        if density > 0.05:  # >5% keyword density = suspicious
            seo_signals.append(f"keyword_density={density:.2%}")
    # Schema/structured data markers
    schema_markers = ["schema.org", "itemtype=", "json-ld", "@context", "faq", "howto"]
    for m in schema_markers:
        if m in lower:
            seo_signals.append(f"schema:{m}")
    results["SEO"] = {
        "detected": len(seo_signals) >= 2,
        "score": min(len(seo_signals) / 4.0, 1.0),
        "evidence": seo_signals[:5],
    }

    # === 3. AEO Optimization (AI Answer Engine Targeting) — v18.1 Enhanced ===
    aeo_patterns = [
        r"(?:what is|how to|why does|when will|who is)\b",  # Q&A format
        r"step \d+[:\.]",                                     # Step-by-step
        r"(?:in conclusion|key takeaway|tldr|summary|bottom line)",  # Summary anchors
        r"(?:according to|experts say|data shows)",           # Authority anchors
        r"(?:key points|main takeaways|at a glance)",        # v18.1: RAG extraction anchors
        r"(?:definition|meaning of|refers to|is defined as)", # v18.1: Dictionary-style
        r"(?:FAQ|frequently asked)",                          # v18.1: FAQ schema explicit
        r"(?:bullet|list|step)\s*\d",                         # v18.1: Bullet-heavy format
    ]
    aeo_hits = sum(1 for p in aeo_patterns if re.search(p, lower))
    # v18.1: Flesch proxy + bullet density from L2 signals
    l2_authority = semantic_l2.get("score", 0) > 0.5
    l2_ai_signals = semantic_l2.get("ai_structure_signals", [])
    has_bullet_density = any("bullet_density" in s for s in l2_ai_signals)
    has_low_readability = "low_readability_mechanical" in l2_ai_signals
    # v18.1: Lower threshold: 2 hits enough if authority is high, or 1 hit if authority + bullet_density exist
    aeo_detected = (
        aeo_hits >= 3
        or (aeo_hits >= 2 and l2_authority)
        or (aeo_hits >= 1 and l2_authority and (has_bullet_density or has_low_readability))
    )
    results["AEO"] = {
        "detected": aeo_detected,
        "score": min(aeo_hits / 5.0, 1.0),  # v18.1: denominator 5
    }

    # === 4. GEO Optimization (Geotargeted Narrative) ===
    geo_markers = [
        "asia", "europe", "us market", "china", "japan", "korea",
        "emerging market", "global south", "latin america", "mena",
        "wall street", "silicon valley", "hong kong", "singapore",
    ]
    geo_hits = [m for m in geo_markers if m in lower]
    # GEO: concentration on 1 area + emotional
    results["GEO"] = {
        "detected": len(geo_hits) >= 3,
        "score": min(len(geo_hits) / 5.0, 1.0),
        "evidence": geo_hits[:5],
    }

    return results


def scan_url(url: str, topic: str = "", force_llm: bool = False, chu_ky: str = "NGAN") -> str:
    """
    Main function: scan 1 URL through 4 layers + LLM.
    Integrates the complete security architecture.

    Args:
        url:       URL to analyze
        topic:     Associated topic/coin (e.g., "BTC", "Fed rate", "AI regulation")
        force_llm: Force LLM call even if rule-based score is sufficient

    Returns:
        JSON string containing the complete report
    """
    timestamp_unix = int(time.time())
    report_id      = str(uuid.uuid4())

    log.info(f"[A12] Scanning: {url[:60]} | topic={topic}")

    # ── DoS Guardian check ─────────────────────────────────────────────────
    if _HAS_GUARDS:
        instructions = get_agent_instructions("12")
        if not instructions.get("allow_external_fetch", True):
            return json.dumps({
                "agent_id":  "12_MANIPULATION_DETECTIVE",
                "report_id": report_id,
                "error":     "BLOCKED_BY_DOS_GUARDIAN",
                "mode":      instructions.get("mode", "UNKNOWN"),
            })

    # ── Fetch content ──────────────────────────────────────────────────────
    fetched = _fetch_content(url)
    if "error" in fetched:
        return json.dumps({"agent_id": "12_MANIPULATION_DETECTIVE",
                           "report_id": report_id, "error": fetched["error"], "url": url})

    raw_content = fetched.get("content", "")

    # ── Security: sanitize content before processing ────────────────────────
    clean_content, was_poisoned = _sanitize_content(raw_content, source=url)
    if was_poisoned:
        log.warning(f"[A12] Injection attempt in content: {url[:60]}")

    # ── 5 psychological anchor questions (rule-based first) ───────────────────
    neo_questions = {
        "audience":           "AI" if was_poisoned or "ai training" in clean_content.lower() else "UNCLEAR",
        "payload_hypothesis": "Pending LLM analysis",
        "beneficiary":        "Pending LLM analysis",
        "timing":             fetched.get("publish_date", "Unknown"),
    }

    # ── 4 layers analysis ────────────────────────────────────────────────
    l1 = analyze_citation_graph(clean_content, url)
    l2 = analyze_semantic_intent(clean_content, topic)
    
    # Adjust timeframe window for historical analysis
    tf_hours = 720 if chu_ky == "DAI" else 72
    l3 = analyze_velocity_coordination(topic or fetched.get("domain", ""), timeframe_hours=tf_hours)
    l4 = cross_validate_emf(topic)

    layer_scores = {"citation": l1, "semantic": l2, "velocity": l3}

    # ── LLM deep analysis: called when complex reasoning is needed ─────────
    composite_prelim = (l1["score"] * 0.25 + l2["score"] * 0.40 + l3["score"] * 0.35)
    # ── REGISTER JOURNAL (Always run Brain A as commanded) ──
    global last_algo_time, _FORCE_NEXT_ANALYSIS
    is_main_cycle = (time.time() - last_algo_time >= ALGO_CYCLE_INTERVAL_SEC)
    is_algo_cycle = is_main_cycle or _FORCE_NEXT_ANALYSIS
    
    should_call_llm_a  = (is_algo_cycle or force_llm)
    should_call_llm_b  = (should_call_llm_a and (composite_prelim > 0.35 or force_llm or l4["financial_aeo_confirmed"]))

    llm_analysis = {}
    if should_call_llm_a:
        _FORCE_NEXT_ANALYSIS = False  # Reset flag after passing gate
        if is_algo_cycle:
            last_algo_time = time.time() # Reset timer for normal & forced cycle (Saga Pulse)
        # Brain A: Fast Narrative Pattern (Flash/Lite) - Always run to leave trace
        brain_a = _goi_llm_brain_a_narrative(clean_content, topic, layer_scores, neo_questions, is_main_cycle)
        neo_questions.update(brain_a)
        
        if should_call_llm_b:
            # Brain B: Deep Motive & Verdict (Qwen-32b/Pro) - Always run when there is a topic (Pulse A11)
            llm_analysis = _goi_llm_brain_b_motive(clean_content, topic, layer_scores, brain_a, l4, chu_ky, is_main_cycle)
            neo_questions.update(llm_analysis)
    else:
        log.info(f"[{ALGO_CYCLE_INTERVAL_SEC}s THROTTLE] Skipping A12 Brain A/B. Using Rule-based Score.")

    # ── Composite verdict ─────────────────────────────────────────────────
    verdict = calculate_composite_verdict(l1, l2, l3, l4, llm_analysis)

    # ── Action decisions ─────────────────────────────────────────────────
    flag_rag  = verdict["label"] in ("MANUFACTURED", "HIGH_AEO")

    needs_review = verdict["confidence"] < 0.5 or verdict["label"] == "SUSPICIOUS"
    alert_level = (
        "CRITICAL" if verdict["label"] == "MANUFACTURED" and l4["financial_aeo_confirmed"] else
        "WARN"     if verdict["label"] in ("MANUFACTURED", "HIGH_AEO") else
        "INFO"
    )

    # ── Build full report ──────────────────────────────────────────────
    report = {
        "agent_id":           "12_MANIPULATION_DETECTIVE",
        "report_id":          report_id,
        "timestamp_unix":     timestamp_unix,
        "timestamp_readable": datetime.utcfromtimestamp(timestamp_unix).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "state":              "CAMPAIGN_DETECTED" if verdict["label"] in ("MANUFACTURED", "HIGH_AEO") else "SCANNING",

        "target": {
            "url":             url,
            "domain":          fetched.get("domain", ""),
            "topic":           topic,
            "publish_date":    fetched.get("publish_date"),
            "content_snippet": clean_content[:200],
            "was_poisoned":    was_poisoned,
        },

        "neo_tam_ly": neo_questions,

        "layer_scores": {
            "citation_graph":      l1,
            "semantic_intent":     l2,
            "velocity_coordination": l3,
            "emf_cross_validation":  l4,
        },

        "llm_analysis": llm_analysis,

        "verdict": verdict,

        "actions": {
            "flag_for_rag_exclusion": flag_rag,

            "needs_human_review":     needs_review,
            "alert_level":            alert_level,
            "notify_a03":             l4["financial_aeo_confirmed"],
            "notify_a11":             l4["financial_aeo_confirmed"],
        },
    }

    # ── 4-Pronged Optimization Detection (Media/SEO/AEO/GEO) ──────────────
    optimization_fingerprints = _detect_optimization_4prong(clean_content, topic, l2)
    report["optimization_detection"] = optimization_fingerprints

    if any(v["detected"] for v in optimization_fingerprints.values()):
        # Publish keyword alert for A07 to include in report
        keyword_data = {
            "type": "A12_KEYWORD_ALERT",
            "topic": topic,
            "url": url[:200],
            "verdict": verdict["label"],
            "optimizations": {k: v for k, v in optimization_fingerprints.items() if v["detected"]},
            "ts": timestamp_unix,
        }
        # DNA 17.0: XADD alert to stream instead of static key
        matrix.xadd("A12", "keyword_alerts", keyword_data, maxlen=50)
        log.info(f"[A12] 🎯 Keyword Alert streamed: {[k for k,v in optimization_fingerprints.items() if v['detected']]}")

    # ── PHASE 6 GRAND SURGERY: HingeEBM Packet (A12_NARRATIVE_PACKET) ────────────
    is_fallback_a12 = (verdict.get("label") == "ORGANIC" and not llm_analysis)
    
    # Contract-compliant HingeEBM packet (A12_AEO_VERDICT_PACKET)
    _VERDICT_PRIORITY = {"ORGANIC": 0, "LOW_AEO": 1, "SUSPICIOUS": 2, "HIGH_AEO": 3, "MANUFACTURED": 4}
    _current_verdict = str(verdict.get("label", "ORGANIC"))

    # Build emf_cross_signals from latest cross-agent data
    try:
        _a10_raw = matrix.get("A10", "latest_macro_narrative") or matrix.get("MACRO", "latest")
        _a10_alert = 0
        if _a10_raw:
            _a10_d = json.loads(_a10_raw) if isinstance(_a10_raw, str) else _a10_raw
            _a10_alert = _a10_d.get("algo_core", {}).get("alert_level", 0)
        _a11_raw = matrix.get("A11", "intent")
        _a11_scenario = "WATCH"
        if _a11_raw:
            _a11_d = json.loads(_a11_raw) if isinstance(_a11_raw, str) else _a11_raw
            _a11_scenario = _a11_d.get("algo_core", {}).get("scenario_id", _a11_d.get("algo_core", {}).get("scenario_type", "WATCH"))
        _a03_raw = matrix.get("SENTIMENT", "latest")
        _a03_mm = 50.0
        if _a03_raw:
            _a03_d = json.loads(_a03_raw) if isinstance(_a03_raw, str) else _a03_raw
            _a03_mm = _a03_d.get("algo_core", {}).get("mm_score", 50.0)
    except Exception:
        _a10_alert, _a11_scenario, _a03_mm = 0, "WATCH", 50.0

    algo_core_a12 = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "symbol": topic if topic else "UNKNOWN",
        "topic": topic if topic else "UNKNOWN",           # Contract: required key
        "aeo_score": float(verdict.get("aeo_score", 0.0)),
        "score": float(verdict.get("aeo_score", 0.0)),     # Contract: required key
        "verdict": _current_verdict,
        "verdict_priority": _VERDICT_PRIORITY.get(_current_verdict, 2),  # Contract: required key
        "confidence": float(verdict.get("confidence", 0.0)),
        "emf_cross_signals": {                              # Contract: required key
            "a10_alert_level": _a10_alert,
            "a11_scenario_id": _a11_scenario,
            "a03_mm_score": _a03_mm,
        },
        "financial_aeo_confirmed": bool(l4.get("financial_aeo_confirmed", False)),
        "flagged_urls": [url] if flag_rag else [],
        "expert_metrics": {
            "is_fallback": is_fallback_a12,
            "url": url,
            "report_id": report_id,
            "optimization_fingerprints": optimization_fingerprints if any(v["detected"] for v in optimization_fingerprints.values()) else {},
        }
    }
    
    narrative_lens_a12 = {
        "summary": str(verdict.get("summary", "Analyzing news and AEO"))[:200],
        "payload_hypothesis": str(verdict.get("payload_hypothesis", "N/A"))[:300],
        "beneficiary": str(verdict.get("beneficiary", "Unknown"))[:100],
        "a12_story": str(llm_analysis.get("expert_commentary", f"Alert: {alert_level}"))[:1500]
    }
    
    hinge_packet_a12 = {
        "algo_core": algo_core_a12,
        "narrative_lens": narrative_lens_a12
    }
    
    # DNA v17.0: XADD HingeEBM Packet into reports_stream
    matrix.xadd("A12", "reports_stream", {
        "payload": json.dumps(report, ensure_ascii=False),
        "envelope": json.dumps(hinge_packet_a12, ensure_ascii=False),
    }, maxlen=20)
    
    # Save Packet to KV (A11 reads directly)
    matrix.set("AEO", "last_report", json.dumps(hinge_packet_a12, ensure_ascii=False), ttl=3600)

    # --- xadd SYSTEM telegram:queue Stream ---
    is_algo_plus = False
    try:
        is_algo_plus = (matrix.client.get("zcl:system:last_algo_mode:A12B") == b"algo_plus" or 
                        matrix.client.get("zcl:system:last_algo_mode:A12B") == "algo_plus")
    except Exception as e_chk:
        log.warning(f"[A12] Cannot check last_algo_mode: {e_chk}")
        
    if is_algo_plus:
        try:
            report_text = (
                f"🔍 *Topic*: {algo_core_a12['topic']}\n"
                f"⚡ *AEO Score*: {algo_core_a12['aeo_score']:.2f} | *Verdict*: {algo_core_a12['verdict']}\n"
                f"💰 *Beneficiary*: {narrative_lens_a12['beneficiary']}\n\n"
                f"🧠 *Detective Assessment*:\n|_{narrative_lens_a12['a12_story']}_|"
            )
            matrix.xadd("SYSTEM", "telegram:queue", {
                "payload": json.dumps({"type": "A12_TO_A06_REPORT", "chu_ky": int(time.time()), "report_text": report_text}, ensure_ascii=False)
            }, maxlen=1000)
        except Exception as e_tele:
            log.error(f"[A12] Error pushing to Telegram queue: {e_tele}")
    else:
        log.info("[A12] Bypass sending Telegram as it is not running in ALGO_PLUS mode")

    # ── SESSION LOG: Record condensed session for long-term drift analysis ──
    try:
        verdict = report.get("verdict", {})
        target = report.get("target", {})
        summary = f"Verdict:{verdict.get('label')} | Score:{verdict.get('aeo_score')} | Topic:{target.get('topic')} | Benefic:{verdict.get('beneficiary')}"
        
        # Get Narrative & Megafeed metrics if available
        try:
            n_state = matrix.get("NARRATIVE", "sensors") or {}
            ecs = float(n_state.get("ECS", {}).get("ecs", 0.0))
            cad = float(n_state.get("CAD", {}).get("cad", 0.0))
        except:
            ecs, cad = 0.0, 0.0
            
        try:
            raw_mf = matrix.client.get("zcl:A12:megafeed_hunt")
            if raw_mf:
                mf_data = json.loads(raw_mf.decode('utf-8'))
                nvd = float(mf_data.get("tensor_16d", {}).get("NVD", 0.0))
                cbm = float(mf_data.get("tensor_16d", {}).get("CBM", 0.0))
            else:
                nvd, cbm = 0.0, 0.0
        except:
            nvd, cbm = 0.0, 0.0

        # 16D AEO Metrics: PRP, BNX, URL, TFT + ECS, CAD, NVD, CBM
        tensor_16d = {
            "PRP": l3.get("score"),
            "BNX": 1.0 if verdict.get("beneficiary") and verdict.get("beneficiary") != "Unknown" else 0.0,
            "URL": 1.0 if flag_rag else 0.0,
            "TFT": verdict.get("aeo_score"),
            "ECS": ecs,
            "CAD": cad,
            "NVD": nvd,
            "CBM": cbm
        }
        _log_agent_session(
            agent_id="A12", redis_key="zcl:aeo:reports",
            summary=summary, signals_count=1,
            confidence=verdict.get("confidence", 0.0),
            expert_metrics=tensor_16d,
            extra={"verdict": verdict.get("label"), "beneficiary": verdict.get("beneficiary")}
        )
    except Exception:
        pass

    if flag_rag:
        # Cache URL in flagged list for exclusion in RAG pipeline
        try:
            flagged = {}
            if FLAGGED_CACHE.exists():
                with open(FLAGGED_CACHE, encoding="utf-8") as f:
                    flagged = json.load(f)
            flagged[url] = {
                "verdict": verdict["label"],
                "score": verdict["aeo_score"],
                "timestamp": timestamp_unix,
            }
            with open(FLAGGED_CACHE, "w", encoding="utf-8") as f:
                json.dump(flagged, f, ensure_ascii=False, indent=2)
            matrix.hset("AEO", "flagged_urls", url, verdict["label"])
        except Exception as e:
            log.warning(f"[A12] Writing flagged_urls error: {e}")



    if alert_level in ("WARN", "CRITICAL"):
        matrix.publish("aeo:alerts", report)
        if l4["financial_aeo_confirmed"]:
            # Alert A11 when financial AEO is detected
            matrix.publish("emf:aeo:cross_alert", {
                "type":        "FINANCIAL_AEO",
                "url":         url,
                "topic":       topic,
                "aeo_score":   verdict["aeo_score"],
                "timestamp":   timestamp_unix,
            })

    # Organic Heartbeat v15.7
    matrix.set("A12", "heartbeat", {"timestamp": datetime.now(timezone.utc).isoformat(), "status": "ALIVE", "last_verdict": verdict["label"]}, ttl=300)

    log.info(f"[A12] Done: {verdict['label']} score={verdict['aeo_score']:.2f} "
             f"| financial={l4['financial_aeo_confirmed']} | {url[:50]}")
    
    # ── Trigger Divergence Engine (A12 is the final trigger in 4-agent loop) ──────
    try:
        from divergence_engine import compute_and_publish as _div_compute
        current_state = matrix.get("GUARDIAN", "system_mode") or "HUNTING"
        _div_compute(state=current_state)
        log.info(f"[A12] Divergence matrix updated after AEO scan | state={current_state}")
    except Exception as e:
        log.warning(f"[A12] Divergence Engine update error (non-critical): {e}")
    
    # Organic Heartbeat logging
    try:
        score = verdict.get("aeo_score", 0.0)
        nlm_changelog.log_aeo_detection(
            case_id=url[:50], 
            score=score, 
            status="CONFIRMED" if score > 0.7 else "DETECTED",
            narrative_snippet=verdict.get("summary", "")[:500]
        )
    except Exception as e:
        log.warning(f"NLM Logging failed for A12 case: {e}")

    return json.dumps(report, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════════
# PART 11 — QUEUE PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

def process_scan_queue():
    """
    Consume URLs from `aeo:scan:queue` (Redis list).
    A10/A11 push into here when velocity spike is detected.
    """
    while True:
        try:
            item = matrix.blpop("AEO", "scan:queue", timeout=5)
            if not item:
                continue
            
            # matrix.blpop auto decodes json
            if isinstance(item, dict):
                data = item
                raw_str = ""
            elif isinstance(item, (tuple, list)) and len(item) == 2:
                _, raw = item
                try:
                    data = raw if isinstance(raw, dict) else json.loads(raw)
                    raw_str = raw
                except:
                    data = {}
                    raw_str = raw
            elif isinstance(item, str):
                try:
                    data = json.loads(item)
                    raw_str = item
                except:
                    data = {}
                    raw_str = item
            else:
                continue

            try:
                url   = data.get("url", "")
                topic = data.get("topic", "")
                force = data.get("force_llm", False)
                if url:
                    scan_url(url, topic, force_llm=force)
                    time.sleep(2)   # Rate limiting between scans
                elif raw_str.startswith("http"):
                    scan_url(raw_str.strip())
            except Exception as e:
                log.error(f"[A12] Scan URL error: {e}")
        except Exception as e:
            log.error(f"[A12] Queue processor error: {e}")
            time.sleep(10)
        except KeyboardInterrupt:
            break


# ── Orchestration & Brain Separation ──────────────────────────────────────────
def _listen_for_realtime_requests():
    """Listen for A12_REALTIME_REQUEST to trigger Brain A or Brain B."""
    log.info("[A12] Starting to listen for A12_REALTIME_REQUEST...")
    while True:
        try:
            _listen_inner()
        except Exception as e:
            log.error(f"[A12] Realtime Listener Error (Redis Disconnect?): {e}. Retrying in 5s...")
            time.sleep(5)
def _listen_inner():
    global _FORCE_NEXT_ANALYSIS
    pubsub = matrix.subscribe(["COMMANDER:events", "SWARM_REALTIME_REQUEST"])
    for message in pubsub.listen():
        if message['type'] != 'message':
            continue
        try:
            data = json.loads(message['data'])
            action_event = data.get("action") or data.get("event")
            if action_event in ["A12_REALTIME_REQUEST", "A12A_REALTIME_REQUEST", "SWARM_REALTIME_REQUEST"]:
                topic = data.get("topic", "BTC/USDT")
                mode  = data.get("mode", "BRAIN_A" if action_event == "A12A_REALTIME_REQUEST" else "BRAIN_B")
                requester = data.get("requester", "UNKNOWN")
                log.info(f"[A12] 🔔 Received Realtime Pulse command for {topic} (Mode: {mode}) from {requester}. A12B will bypass Throttle!")
                _FORCE_NEXT_ANALYSIS = True
                
                if requester == "A09_GUARDIAN":
                     matrix.publish("A06:telegram_outbound", json.dumps({
                          "message": f"🚨 [A12 GUARD] A09 just raised an emergency alert: Signs of news manipulation, biasing AI (Prompt Injection)!\n\nSuspect: {topic[:200]}\n\nRouting to CRAWL_LOUD core to analyze motive..."
                     }))
                
                if mode == "BRAIN_A":
                    # Brain A: Quick context fetch from Matrix/RSS to return to A11
                    l3_velocity = analyze_velocity_coordination(topic)
                    vel_score = l3_velocity.get("score", 0)
                    vel_signal = l3_velocity.get("strongest_signal", "N/A")
                    brain_a_payload = {
                        "topic": topic,
                        "velocity_score": vel_score,
                        "strongest_signal": vel_signal,
                        "velocity_ratio": l3_velocity.get("velocity_ratio", 0),
                        "active_platforms": l3_velocity.get("active_platforms", 0),
                        "cross_platform_sync": l3_velocity.get("cross_platform_sync", 0),
                        "ts": int(time.time()),
                        "mode": "BRAIN_A_CONTEXT"
                    }
                    matrix.set("A12", "brain_a", brain_a_payload, ttl=600)
                    log.info(f"[A12] Brain A (Narrative Context) ready for {topic} | vel={vel_score:.3f}")

                    # ── SESSION LOG: Brain A Pulse ──
                    tensor_16d = {"PRP": vel_score, "TFT": vel_score}
                    _log_agent_session(
                        agent_id="A12",
                        redis_key="zcl:A12:brain_a",
                        summary=f"PULSE_A | {topic} | vel:{vel_score:.3f} | ratio:{l3_velocity.get('velocity_ratio', 0):.1f}x | platforms:{l3_velocity.get('active_platforms', 0)} | {vel_signal[:80]}",
                        signals_count=l3_velocity.get("total_hits_72h", 0),
                        confidence=min(1.0, vel_score),
                        expert_metrics=tensor_16d,
                        extra={
                            "mode": "BRAIN_A",
                            "requester": requester,
                            "velocity": l3_velocity,
                        }
                    )
                
                else:
                    # ── Brain B: Deep Diagnostic ──
                    l4_emf = cross_validate_emf(topic)
                    financial_confirmed = l4_emf.get("financial_aeo_confirmed", False)
                    confirmation_sources = l4_emf.get("confirmation_sources", 0)

                    brain_b_payload = {
                        "topic": topic,
                        "financial_aeo_confirmed": financial_confirmed,
                        "confirmation_sources": confirmation_sources,
                        "emf_details": l4_emf.get("details", []),
                        "missing_data": l4_emf.get("missing_data", []),
                        "ts": int(time.time()),
                        "mode": "BRAIN_B_DIAGNOSTIC"
                    }
                    
                    # ── Generate Diagnostic Triptych via LLM ──
                    diag_prompt = f"""You are A12 Media Detective (Diagnostic Mode).
Preliminary analysis of submerged data: Topic '{topic}', AEO Confirmed: {financial_confirmed}, Confirmation Sources: {confirmation_sources}/3.
Strictly follow JSON rules, output only JSON containing 1 field:
{{
  "expert_comment": "<A12 preliminary assessment>"
}}"""
                    try:
                        llm_out = brain.think_as("A12_DIAGNOSTIC", diag_prompt, brain_mode="A12_MOTIVE", est_tokens=400)
                        start = llm_out.find("{")
                        end = llm_out.rfind("}") + 1
                        if start != -1 and end != 0:
                            diag_json = json.loads(llm_out[start:end])
                            brain_b_payload.update(diag_json)
                    except Exception as e:
                        log.error(f"[A12] LLM Diagnostic error: {e}")
                    
                    matrix.set("A12", "brain_b", brain_b_payload, ttl=3600)
                    
                    # ── Push A11 to activate if stale ──
                    a11_report = matrix.get("A11", "intent") or {}
                    a11_report = a11_report.get("trinity", a11_report)
                    is_stale = True
                    a11_age_min = -1
                    if a11_report:
                        ts_a11 = 0
                        ts_val = a11_report.get("algo_core", {}).get("ts", 0)
                        if isinstance(ts_val, str):
                            try:
                                if "+" in ts_val:
                                    ts_val = ts_val.split("+")[0]
                                dt = datetime.fromisoformat(ts_val)
                                ts_a11 = dt.timestamp()
                            except:
                                ts_a11 = 0
                        else:
                            try:
                                ts_a11 = float(ts_val)
                            except:
                                ts_a11 = 0
                        
                        if not ts_a11:
                            ts_a11 = a11_report.get("timestamp_unix", 0)
                            
                        if ts_a11:
                            a11_age_min = int((time.time() - ts_a11) / 60)
                            if a11_age_min < 30:
                                is_stale = False
                    
                    if is_stale:
                        log.info(f"[A12] 📢 A11 is passive (age={a11_age_min}m). 'Pushing' A11 to activate...")
                        matrix.publish("COMMANDER:events", {
                            "event": "A11_REALTIME_REQUEST", 
                            "topic": topic, 
                            "requester": "A12_DIAGNOSTIC_SIGNAL"
                        })

                    # ── Execute Divergence Engine after Brain B ──
                    div_result = "N/A"
                    div_score = 0
                    try:
                        log.info(f"[A12] 🔄 Activating Divergence Engine (Synthesis Hub)...")
                        curr_state = matrix.get("SYSTEM", "state") or "HUNTING"
                        from divergence_engine import compute_and_publish as _div_compute
                        div_matrix = _div_compute(state=curr_state)
                        div_score = div_matrix.get("divergence_score", 0)
                        div_result = div_matrix.get("conflict_type", "N/A")
                        log.info(f"[A12] ✅ Divergence synthesis completed: score={div_score} type={div_result}")
                    except Exception as div_err:
                        log.error(f"[A12] Error activating Divergence Engine: {div_err}")
                        div_result = f"ERROR:{str(div_err)[:40]}"

                    # ── SESSION LOG: Brain B Diagnostic ──
                    tensor_16d = {
                        "PRP": confirmation_sources / 3.0,
                        "BNX": 1.0 if financial_confirmed else 0.0,
                        "TFT": 0.8 if financial_confirmed else 0.4
                    }
                    _log_agent_session(
                        agent_id="A12",
                        redis_key="zcl:A12:brain_b",
                        summary=(
                            f"PULSE_B | {topic} | fin_aeo:{'YES' if financial_confirmed else 'NO'} "
                            f"| confirm:{confirmation_sources}/3 | A11:{'STALE' if is_stale else 'FRESH'}({a11_age_min}m) "
                            f"| div:{div_score:.0f}({div_result})"
                        ),
                        signals_count=confirmation_sources,
                        confidence=0.8 if financial_confirmed else 0.4,
                        expert_metrics=tensor_16d,
                        extra={
                            "mode": "BRAIN_B",
                            "requester": requester,
                            "financial_aeo": financial_confirmed,
                            "a11_stale": is_stale,
                            "a11_age_min": a11_age_min,
                            "divergence_score": div_score,
                            "divergence_type": div_result,
                            "emf_details": l4_emf.get("details", []),
                        }
                    )
                    
        except Exception as e:
            log.error(f"[A12] Realtime Request processing error: {e}")

def _megafeed_hunter_daemon():
    """Daemon: scan keywords every 10 minutes. On spike -> scan + alert."""
    log.info("[A12] 🔍 MegaFeed Hunter daemon started (cycle: 600s)")
    while True:
        try:
            results = hunt_keywords()
            spikes = detect_velocity_spike(results)
            
            for spike in spikes:
                if spike["is_breaking"]:
                    log.warning(f"[A12] 🚨 BREAKING: {spike['topic']} | "
                                f"velocity={spike['ratio']:.1f}x | sources={spike['sources']}")
                    
                    # 1. Push top article into scan_queue for deep analysis
                    if spike.get("top_url"):
                        matrix.rpush("AEO", "scan:queue", json.dumps({
                            "url": spike["top_url"],
                            "topic": spike["topic"],
                            "force_llm": True,
                        }))
                    
                    # 2. Alert A11 for cross-checking
                    matrix.publish("COMMANDER:events", {
                        "event": "A12_BREAKING_GEOPOLITICAL",
                        "topic": spike["topic"],
                        "category": spike["category"],
                        "velocity_ratio": spike["ratio"],
                        "sources": spike["sources"],
                        "requester": "A12_MEGAFEED",
                        "ts": int(time.time()),
                    })
                    
                    # 3. Alert A06 if category is geopolitical
                    if spike["category"] in ("geopolitical", "energy", "policy"):
                        alert_msg = (
                            f"Topic: {spike['topic']}\n"
                            f"Category: {spike['category']}\n"
                            f"Velocity: {spike['ratio']:.1f}x baseline\n"
                            f"Sources count: {spike['sources']}"
                        )
                        try:
                            msg_id = matrix.xadd("SYSTEM", "telegram:queue", {"payload": json.dumps({
                                "type": "ELITE_ALERT",
                                "report_text": alert_msg,
                                "chu_ky": int(time.time()),
                            })}, maxlen=1000)
                            if not msg_id:
                                raise Exception("Matrix xadd returned None")
                        except Exception as e:
                            log.error(f"[A12] Telegram Stream push error: {e}. Logging locally.")
                            with open("logs/a12_telegram_fallback.log", "a", encoding="utf-8") as f:
                                f.write(f"[{time.time()}] {alert_msg}\n")
            
            # 4. Log session with 16D tensor
            nvd = get_nvd_score(results)
            cbm = get_cbm_score()
            total_hits = sum(r.get("total_hits", 0) for r in results.values())
            breaking_count = len([s for s in spikes if s["is_breaking"]])
            
            _log_agent_session(
                agent_id="A12",
                redis_key="zcl:A12:megafeed_hunt",
                summary=f"HUNT | feeds:{len(results)} | hits:{total_hits} | breaking:{breaking_count}",
                signals_count=total_hits,
                confidence=min(1.0, nvd / 10.0),
                expert_metrics={"NVD": nvd, "CBM": cbm, "PRP": 0.0},
            )
            
        except Exception as e:
            log.error(f"[A12] MegaFeed Hunter error: {e}")
        
        time.sleep(600)  # 10 minutes

if __name__ == "__main__":
    import argparse
    import threading
    parser = argparse.ArgumentParser(description="A12 AEO Detective")
    parser.add_argument("--url",    type=str, default="", help="URL to scan")
    parser.add_argument("--topic",  type=str, default="", help="Topic/keyword")
    parser.add_argument("--queue",  action="store_true", help="Run queue processor continuously")
    parser.add_argument("--force-llm", action="store_true", help="Force LLM call")
    parser.add_argument("--run",    action="store_true", help="Run full service (Queue + Pulse Listener)")
    args = parser.parse_args()

    if args.run:
        print("Starting AEO Detective Swarm Service (Queue + Pulse Listener + MegaFeed)...")
        
        def run_autonomous_heartbeat_a12():
            while True:
                try:
                    q_len = matrix.llen("AEO", "scan:queue")
                    nlm_changelog.log_heartbeat("A12", {"status": "LISTENING_SPINNING", "queue_len": q_len})
                    matrix.set("A12", "heartbeat", {"timestamp": datetime.now(timezone.utc).isoformat(), "status": "LISTENING_SPINNING", "queue_len": q_len}, ttl=300)
                except Exception as e:
                    log.error(f"[A12 DAEMON] ERROR in heartbeat: {e}")
                time.sleep(60)

        t_hb = threading.Thread(target=run_autonomous_heartbeat_a12, daemon=True)
        t_queue = threading.Thread(target=process_scan_queue, daemon=True)
        t_pulse = threading.Thread(target=_listen_for_realtime_requests, daemon=True)
        t_hunt = threading.Thread(target=_megafeed_hunter_daemon, daemon=True)
        
        # Dien Hong Council daemon
        try:
            from dien_hong_council import start_council_daemon
            start_council_daemon("A12")
        except Exception as e_dh:
            log.warning(f"[A12] Dien Hong daemon failed to start: {e_dh}")
        
        t_hb.start()
        t_queue.start()
        t_pulse.start()
        t_hunt.start()
        
        t_queue.join()
    elif args.queue:
        process_scan_queue()
    elif args.url:
        result = scan_url(args.url, args.topic, force_llm=args.force_llm)
        print(json.dumps(json.loads(result), indent=2, ensure_ascii=False))
    else:
        parser.print_help()
