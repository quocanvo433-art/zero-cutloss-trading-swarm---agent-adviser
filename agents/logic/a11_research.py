"""
🧬 DNA: v16.6 (Sovereign Purity & Deep Research)
🏢 UNIT: DEEP_RESEARCHER (A11)
🛠️ ROLE: INSTITUTIONAL_ANALYST
📖 DESC: Deep Research system on institutional behavior, using AI-Q to synthesize reports from thousands of reliable Smart Money sources.
🔗 CALLS: tools/llm_router.py, tools/imperial_state.py
📟 I/O: Redis: zcl:a11:research_stream, logs/research/, zcl:A11:heartbeat
🛡️ INTEGRITY: Research-Purity, Source-Evidence, Depth-First-Search.
"""

import os
import json
import time
import uuid
import logging
import feedparser
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pathlib import Path
import urllib.request
import urllib.error

from chunking_engine import smart_truncate
from llm_router import router_api_call
from a09_immunity import sanitize_text_for_llm as a09_sanitize_text
from imperial_brain import brain

from imperial_state import matrix

BASE_DIR = Path(__file__).parent.parent.parent
EMF_LAB_DIR = BASE_DIR / "emf_lab"
DEEP_RESEARCH_DIR = EMF_LAB_DIR / "deep_research_reports"
DEEP_RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
log = logging.getLogger("A11_DEEP_RESEARCH")

RSS_FEEDS = {
    "reuters_biz": "https://feeds.reuters.com/reuters/businessNews",
    "yahoo_btc": "https://finance.yahoo.com/rss/headline?s=BTC-USD",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "wall_street_journal": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
}

def _fetch_rss_news() -> list:
    """Scrape news from RSS feeds."""
    articles = []
    seen_titles = set()
    seen_links = set()
    for source, url in RSS_FEEDS.items():
        try:
            # Use urllib with timeout to prevent Blocking IO (Zero-Cutloss)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read()
                
            feed = feedparser.parse(content)
            if not feed or getattr(feed, "entries", None) is None:
                continue
                
            for entry in feed.entries: # Remove [:15] limit, fetch all new news
                if not entry: continue
                # Must pass through A09 filter to prevent Prompt Injection
                raw_title = entry.get("title") or ""
                raw_summary = entry.get("summary") or ""
                safe_title = a09_sanitize_text(raw_title, max_len=200) or ""
                safe_summary = a09_sanitize_text(raw_summary, max_len=500) or ""
                
                # Skip if A09 detects malicious code or empty data (Junk Data Filtering)
                # Matches Vietnamese "NỘI DUNG ĐÃ BỊ LỌC" via unicode escape, plus English equivalents
                filter_keywords = ["N\u00d4I DUNG \u0110\u00c3 B\u1eca L\u1eccC", "CONTENT_FILTERED", "CRITICAL INJECTION"]
                if not safe_title or any(kw in safe_title for kw in filter_keywords) or any(kw in safe_summary for kw in filter_keywords):
                    continue

                link = entry.get("link") or ""
                if link and not link.startswith("http"): # Security: Filter malicious links
                    continue

                # Deduplication: Prevent duplicates across sources
                if safe_title in seen_titles or (link and link in seen_links):
                    continue
                seen_titles.add(safe_title)
                if link: seen_links.add(link)

                # Normalization: Normalize time to ISO 8601
                published_str = entry.get("published") or ""
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        dt = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                        published_str = dt.isoformat()
                except:
                    pass

                articles.append({
                    "source": source,
                    "title": safe_title,
                    "summary": safe_summary,
                    "link": link,
                    "published": published_str
                })
        except Exception as e:
            log.warning(f"Error scraping RSS {source}: {e}")
    return articles

def _aiq_semantic_filter(articles: list, intent_context: dict) -> list:
    """
    [NVIDIA AI-Q Blueprint] Semantic Filter using Local Model.
    Cost $0, runs extremely fast, filters out noise and low-value news.
    Only keeps news related to Money Flow, Whales, and Financial Institutions.
    """
    if not articles:
        return []

    log.info(f"Running AI-Q Semantic Filter on {len(articles)} articles...")
    filtered = []
    seen_links = set()
    
    # Split into small batches for local model processing (10 articles per batch)
    batch_size = 10
    
    context_str = json.dumps(intent_context, ensure_ascii=False) if intent_context else "None"
    import re
    
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i+batch_size]
        
        prompt = f"""You are the AI-Q Semantic Filter for the Hedge Fund.
Task: Filter out articles related to 'Institutional Behavior', 'Whales', 'Macro Policy', 'Money Flow'.
SKIP articles about 'Technical Analysis (TA)', 'Daily Coin Price', 'Gibberish Price Predictions'.
Pay special attention to the current market context (Intent Context): {context_str}

Article List (ID: Title - Summary):
"""
        for idx, art in enumerate(batch):
            if not isinstance(art, dict): continue
            prompt += f"[{idx}] {art.get('title', 'No Title')} - {art.get('summary', '')[:100]}\n"
            
        prompt += "\nReturn ONLY a JSON array containing the matching article IDs. Example: [0, 3, 7]. Return [] if no articles match."
        
        try:
            # Call Local LLM via router v3 with CRAWL flag
            resp = router_api_call(
                prompt,
                agent_id="A11_RESEARCH",
                brain_mode="NORMAL",
                est_tokens=50
            )
            
            resp_str = str(resp) if resp else ""
            
            match = re.search(r'\[(.*?)\]', resp_str)
            if match:
                nums = re.findall(r'\d+', match.group(1))
                indices = [int(n) for n in nums]
                for idx in indices:
                    if 0 <= idx < len(batch):
                        link = batch[idx].get("link") or str(uuid.uuid4())
                        if link not in seen_links:
                            filtered.append(batch[idx])
                            seen_links.add(link)
            else:
                # Zero-Cutloss Fallback
                for art in batch:
                    link = art.get("link") or str(uuid.uuid4())
                    if link not in seen_links:
                        filtered.append(art)
                        seen_links.add(link)

        except Exception as e:
            log.warning(f"Error in Semantic Filter batch index {i}: {e}. Activating Zero-Cutloss fallback.")
            for art in batch:
                link = art.get("link") or str(uuid.uuid4())
                if link not in seen_links:
                    filtered.append(art)
                    seen_links.add(link)
            
    log.info(f"AI-Q Filter retained {len(filtered)}/{len(articles)} high-value articles.")
    return filtered
