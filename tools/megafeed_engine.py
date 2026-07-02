"""
🧬 DNA: v16.6 (Sovereign Purity)
🏢 UNIT: AGENTIC
🛠️ ROLE: SPEED_SENTINEL
📖 DESC: Multi-threaded RSS scanning engine for A12
"""
import time
import json
import logging
import feedparser
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import sys
import os
import urllib.parse

# Append the project root into sys.path to allow imports like `tools.imperial_state`
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.imperial_state import matrix

log = logging.getLogger("MegaFeedEngine")
# If not configured, configure a baseline logger for manual testing
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ═════════════════════════════════════════════════════════════════════════════
# PART 1: CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

MEGAFEED_RSS = {
    "geopolitical": {
        "ap_news":       {"url": "https://rsshub.app/apnews/topics/world-news", "weight": 0.95},
        "bbc_world":     {"url": "http://feeds.bbci.co.uk/news/world/rss.xml", "weight": 0.90},
        "aljazeera":     {"url": "https://www.aljazeera.com/xml/rss/all.xml", "weight": 0.85},
        "reuters_world": {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362", "weight": 0.95}, # cnbc world as fallback
        "guardian":      {"url": "https://www.theguardian.com/world/rss", "weight": 0.80},
        "google_news":   {"url": f"https://news.google.com/rss/search?q={urllib.parse.quote('geopolitics OR world war OR global conflict')}&hl=en-US&gl=US&ceid=US:en", "weight": 0.95},
    },
    "finance": {
        "cnbc":          {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "weight": 0.85},
        "marketwatch":   {"url": "http://feeds.marketwatch.com/marketwatch/topstories/", "weight": 0.80},
        "seekingalpha":  {"url": "https://seekingalpha.com/market_currents.xml", "weight": 0.75},
        "google_news":   {"url": f"https://news.google.com/rss/search?q={urllib.parse.quote('stock market crash OR global economy OR recession')}&hl=en-US&gl=US&ceid=US:en", "weight": 0.90},
    },
    "energy": {
        "oilprice":      {"url": "https://oilprice.com/rss/main", "weight": 0.90},
        "kitco_gold":    {"url": "https://www.kitco.com/rss/kitco.rss", "weight": 0.80},
        "google_news":   {"url": f"https://news.google.com/rss/search?q={urllib.parse.quote('crude oil OR energy crisis OR opec')}&hl=en-US&gl=US&ceid=US:en", "weight": 0.85},
    },
    "tech": {
        "techcrunch":    {"url": "https://techcrunch.com/feed/", "weight": 0.85},
        "theverge":      {"url": "https://www.theverge.com/rss/index.xml", "weight": 0.75},
        "arstechnica":   {"url": "https://feeds.arstechnica.com/arstechnica/index", "weight": 0.80},
        "wired":         {"url": "https://www.wired.com/feed/rss", "weight": 0.75},
        "google_news":   {"url": f"https://news.google.com/rss/search?q={urllib.parse.quote('artificial intelligence OR semiconductor OR big tech')}&hl=en-US&gl=US&ceid=US:en", "weight": 0.90},
    },
    "crypto": {
        "coindesk":      {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "weight": 0.80},
        "cointelegraph": {"url": "https://cointelegraph.com/rss", "weight": 0.75},
        "google_news":   {"url": f"https://news.google.com/rss/search?q={urllib.parse.quote('bitcoin etf OR cryptocurrency regulation OR sec crypto')}&hl=en-US&gl=US&ceid=US:en", "weight": 0.85},
    },
    "central_bank": {
        "fed_speeches":  {"url": "https://www.federalreserve.gov/feeds/speeches.xml", "weight": 0.95},
        "ecb_press":     {"url": "https://www.ecb.europa.eu/rss/press.html", "weight": 0.90},
        "google_news":   {"url": f"https://news.google.com/rss/search?q={urllib.parse.quote('federal reserve OR central bank rate cut OR ecb')}&hl=en-US&gl=US&ceid=US:en", "weight": 0.95},
    },
}

ELITE_KEYWORDS = {
    "geopolitical": ["war", "ceasefire", "peace deal", "sanctions", "embargo",
                     "hormuz", "iran", "israel", "russia", "ukraine", "china",
                     "taiwan", "missile", "nuclear", "invasion", "navy", "troops"],
    "policy":       ["trump", "netanyahu", "putin", "xi jinping", "fed rate",
                     "rate cut", "rate hike", "tariff", "trade war",
                     "executive order", "summit", "g7", "g20", "opec meeting"],
    "energy":       ["opec", "oil production", "crude oil", "natural gas",
                     "oil price", "pipeline", "brent", "wti", "energy crisis",
                     "refinery", "petroleum reserve"],
    "finance":      ["recession", "inflation", "default", "credit crisis",
                     "bank run", "quantitative easing", "bond yield",
                     "debt ceiling", "bankruptcy", "margin call", "short squeeze"],
    "tech":         ["nvidia", "openai", "google ai", "apple", "microsoft",
                     "semiconductor", "chip ban", "ai regulation",
                     "tsmc", "asml", "gpu shortage"],
    "crypto":       ["bitcoin etf", "ethereum etf", "sec crypto",
                     "stablecoin regulation", "cbdc", "crypto ban"],
}


VELOCITY_BASELINE = {
    "geopolitical": 5.0, 
    "finance": 8.0, 
    "energy": 3.0,
    "tech": 6.0, 
    "crypto": 4.0, 
    "central_bank": 1.0, 
    "policy": 3.0,
}

BREAKING_THRESHOLD = 3.0

# ═════════════════════════════════════════════════════════════════════════════
# PART 2: DATA HARVESTING AND ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════

def fetch_feed(category: str, source_name: str, feed_info: dict) -> list:
    """Fetch a specific RSS feed."""
    url = feed_info["url"]
    entries = []
    try:
        parsed = feedparser.parse(url)
        # 12h threshold
        now = datetime.now(timezone.utc)
        for entry in parsed.entries[:20]: # top 20
            # parse date
            dt = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            else:
                dt = now # fallback
                
            if (now - dt) < timedelta(hours=12):
                entries.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": dt,
                    "source": source_name,
                    "category": category,
                    "weight": feed_info["weight"]
                })
    except Exception as e:
        log.debug(f"[MegaFeed] Fetch error for {source_name}: {e}")
    return entries

def hunt_keywords() -> dict:
    """Scan all RSS feeds and match keywords."""
    all_entries = []
    futures = []
    
    # Execute full force multi-threading
    with ThreadPoolExecutor(max_workers=10) as executor:
        for cat, sources in MEGAFEED_RSS.items():
            for src_name, feed_info in sources.items():
                futures.append(executor.submit(fetch_feed, cat, src_name, feed_info))
                
        for future in as_completed(futures):
            res = future.result()
            all_entries.extend(res)
            
    log.info(f"Parsed {len(all_entries)} articles from RSS sources.")
    
    results = {cat: {"total_hits": 0, "articles": [], "keywords_detected": {}} for cat in ELITE_KEYWORDS.keys()}
    results["central_bank"] = {"total_hits": 0, "articles": [], "keywords_detected": {}}
    
    # Process keywords
    for entry in all_entries:
        text = entry["title"].lower()
        matched = False
        
        for k_cat, keywords in ELITE_KEYWORDS.items():
            import re
            hit_words = [kw for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE)]
            if hit_words:
                matched = True
                results[k_cat]["total_hits"] += 1
                for w in hit_words:
                    results[k_cat]["keywords_detected"][w] = results[k_cat]["keywords_detected"].get(w, 0) + 1
                results[k_cat]["articles"].append({
                    "title": entry["title"],
                    "link": entry["link"],
                    "source": entry["source"],
                    "words": hit_words
                })
        
        if entry["category"] == "central_bank":
             results["central_bank"]["total_hits"] += 1
             results["central_bank"]["keywords_detected"]["central_bank_general"] = results["central_bank"]["keywords_detected"].get("central_bank_general", 0) + 1
             results["central_bank"]["articles"].append({
                 "title": entry["title"],
                 "link": entry["link"],
                 "source": entry["source"],
                 "words": ["central_bank_general"]
             })
                
    return results

def detect_velocity_spike(hunt_result: dict) -> list:
    """Measure ratio against baseline to detect BREAKING NEWS."""
    spikes = []
    for cat, data in hunt_result.items():
        if cat not in VELOCITY_BASELINE:
             continue
             
        baseline = VELOCITY_BASELINE[cat]
        hits = data["total_hits"]
        ratio = hits / baseline if baseline > 0 else 0
        
        is_breaking = ratio > BREAKING_THRESHOLD
        
        if is_breaking or (hits > 0 and __name__ == "__main__"): # in test mode, return all with hits
            # Find main topic
            top_word = None
            if data["keywords_detected"]:
                top_word = max(data["keywords_detected"].items(), key=lambda x: x[1])[0]
            
            top_url = data["articles"][0]["link"] if data["articles"] else None
            sources = list(set([a["source"] for a in data["articles"]]))
            
            spikes.append({
                "category": cat,
                "topic": top_word.upper() if top_word else f"HOT_{cat.upper()}",
                "ratio": ratio,
                "sources": len(sources),
                "source_names": sources,
                "is_breaking": is_breaking,
                "top_url": top_url
            })
            
    return spikes


def get_nvd_score(hunt_result: dict) -> float:
    """News Velocity Divergence (NVD) tensor dimension. 0.0 - 10.0"""
    ratios = []
    for cat, data in hunt_result.items():
        if cat in VELOCITY_BASELINE:
            r = data["total_hits"] / VELOCITY_BASELINE[cat]
            ratios.append(r)
    
    if not ratios:
        return 0.0
    
    max_ratio = max(ratios)
    # Scale: ratio 1.0 -> score 2.0; ratio 3.0 -> score 6.0; ratio 5.0 -> score 10.0
    score = min(10.0, max_ratio * 2.0)
    return round(score, 2)

def get_cbm_score(hunt_result: dict = None) -> float:
    """Central Bank Momentum (CBM) tensor dimension. 0.0 - 10.0"""
    if hunt_result and "central_bank" in hunt_result:
        hits = hunt_result["central_bank"]["total_hits"]
        return min(10.0, 2.5 + hits * 1.5)
    return 2.5 # baseline default when normal

# ═════════════════════════════════════════════════════════════════════════════
# PART 3: CLI TEST MODE
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MegaFeed Engine - 30+ RSS Scanner")
    parser.add_argument("--test", action="store_true", help="Run unit test")
    args = parser.parse_args()
    
    if args.test:
        print("=== STARTING MEGAFEED ENGINE TEST (PHASE 1.1) ===")
        t1 = time.time()
        
        results = hunt_keywords()
        spikes = detect_velocity_spike(results)
        nvd = get_nvd_score(results)
        
        t2 = time.time()
        
        print(f"\n[+] Total scan time: {t2 - t1:.2f}s")
        print(f"[+] NVD (News Velocity Divergence) Score: {nvd}/10\n")
        
        print(f"{'CATEGORY':<15} | {'HITS':<5} | {'HIGHLIGHT':<20} | {'ALERT'}")
        print("-" * 65)
        for cat, data in results.items():
            hits = data.get('total_hits', 0)
            top_word = ""
            alert = ""
            if data.get('keywords_detected'):
                top_word = max(data['keywords_detected'].items(), key=lambda x: x[1])[0]
                
            # check breaking in spikes
            for s in spikes:
                if s["category"] == cat:
                    alert = f"{s['ratio']:.1f}x VELOCITY"
                    if s["is_breaking"]:
                        alert += " (BREAKING!)"
            print(f"{cat:<15} | {hits:<5} | {top_word:<20} | {alert}")
            
        print("\n=== END OF TEST ===")
