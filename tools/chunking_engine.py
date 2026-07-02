"""
🧬 DNA: v1.0 (Chunking Engine)
🏢 UNIT: SHARED_TOOL
🛠️ ROLE: TEXT_CHUNKER
📖 DESC: Algorithm to split raw data (Trunking/Chunking) for scraping Agents.
         Avoid stuffing >30k tokens into a single prompt -> crash Cloud/Local.
🔗 CALLS: tools/llm_router.py
📟 I/O: Input = raw text/list, Output = merged LLM response
🛡️ INTEGRITY: Token-safe, overlap-aware.
"""
import re
import json
import logging
import time
from typing import List, Callable, Optional

log = logging.getLogger("CHUNKING_ENGINE")

# ── CONSTANTS ────────────────────────────────────────────────────────────────
# Rough token estimation: ~3.5 chars per token for mixed languages
CHARS_PER_TOKEN = 3.5
DEFAULT_CHUNK_SIZE_TOKENS = 6000       # Safe for 4B (32k ctx) and Cloud APIs
MAX_CHUNK_SIZE_TOKENS = 10000          # Upper bound even for 9B/Cloud
OVERLAP_TOKENS = 200                   # Context overlap between chunks
MIN_INPUT_TOKENS_TO_CHUNK = 8000       # Don't chunk if input is < this


def estimate_tokens(text: str) -> int:
    """Rough estimation of token count from text (mixed languages)."""
    if not text:
        return 0
    return int(len(text) / CHARS_PER_TOKEN)


def chunk_text(text: str,
               chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
               overlap_tokens: int = OVERLAP_TOKENS) -> List[str]:
    """
    Splits text into chunks of safe size for LLMs.
    
    Algorithm:
    1. If text < minimum threshold -> return original as a whole
    2. Split by paragraph/sentence boundaries (do not cut mid-sentence)
    3. Gather paragraphs/sentences into a chunk until chunk_size is reached
    4. Overlap: each chunk keeps the tail of the previous chunk to maintain context
    
    Returns: List[str] of text chunks
    """
    if not text:
        return []

    total_tokens = estimate_tokens(text)
    if total_tokens <= chunk_size_tokens:
        return [text]

    # Split by paragraph (double newline or single newline)
    paragraphs = re.split(r'\n{2,}', text)
    if len(paragraphs) <= 1:
        # If only 1 long paragraph, split by sentence
        paragraphs = re.split(r'(?<=[.!?])\s+', text)
    if len(paragraphs) <= 1:
        # Fallback: split by hard character count
        chunk_chars = int(chunk_size_tokens * CHARS_PER_TOKEN)
        overlap_chars = int(overlap_tokens * CHARS_PER_TOKEN)
        chunks = []
        pos = 0
        while pos < len(text):
            end = min(pos + chunk_chars, len(text))
            chunks.append(text[pos:end])
            pos = max(pos + 1, end - overlap_chars) if end < len(text) else end
        return chunks

    # Gather paragraphs into chunks
    chunks = []
    current_chunk_parts = []
    current_tokens = 0
    overlap_chars = int(overlap_tokens * CHARS_PER_TOKEN)

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        # If 1 paragraph is larger than chunk_size -> split further by sentence
        if para_tokens > chunk_size_tokens:
            # Flush current chunk first
            if current_chunk_parts:
                chunks.append("\n\n".join(current_chunk_parts))
                current_chunk_parts = []
                current_tokens = 0

            # Split long paragraph by sentence
            sentences = re.split(r'(?<=[.!?])\s+', para)
            sub_parts = []
            sub_tokens = 0
            for sent in sentences:
                st = estimate_tokens(sent)
                if st > chunk_size_tokens:
                    sent_chars = int(chunk_size_tokens * CHARS_PER_TOKEN)
                    for i in range(0, len(sent), sent_chars):
                        sub_sent = sent[i:i+sent_chars]
                        sst = estimate_tokens(sub_sent)
                        if sub_tokens + sst > chunk_size_tokens and sub_parts:
                            chunks.append(" ".join(sub_parts))
                            overlap_text = " ".join(sub_parts)[-overlap_chars:]
                            sub_parts = [overlap_text] if overlap_text else []
                            sub_tokens = estimate_tokens(overlap_text) if overlap_text else 0
                        sub_parts.append(sub_sent)
                        sub_tokens += sst
                    continue
                if sub_tokens + st > chunk_size_tokens and sub_parts:
                    chunks.append(" ".join(sub_parts))
                    # Retain overlap
                    overlap_text = " ".join(sub_parts)[-overlap_chars:]
                    sub_parts = [overlap_text] if overlap_text else []
                    sub_tokens = estimate_tokens(overlap_text) if overlap_text else 0
                sub_parts.append(sent)
                sub_tokens += st
            if sub_parts:
                chunks.append(" ".join(sub_parts))
            continue

        # If adding another paragraph exceeds threshold -> create new chunk
        if current_tokens + para_tokens > chunk_size_tokens and current_chunk_parts:
            chunks.append("\n\n".join(current_chunk_parts))
            # Overlap: retain the tail end of the old chunk
            overlap_text = current_chunk_parts[-1][-overlap_chars:] if current_chunk_parts else ""
            current_chunk_parts = [overlap_text] if overlap_text else []
            current_tokens = estimate_tokens(overlap_text) if overlap_text else 0

        current_chunk_parts.append(para)
        current_tokens += para_tokens

    # Flush final chunk
    if current_chunk_parts:
        chunks.append("\n\n".join(current_chunk_parts))

    return chunks


def chunk_list(items: list,
               max_items_per_chunk: int = 30,
               max_tokens_per_chunk: int = DEFAULT_CHUNK_SIZE_TOKENS,
               item_to_text: Callable = str) -> List[List]:
    """
    Splits a list of items into small batches.
    Useful for: RSS articles, Reddit posts, YouTube comments, tweets.
    
    Args:
        items: Original items list
        max_items_per_chunk: Item count limit per chunk
        max_tokens_per_chunk: Token limit per chunk
        item_to_text: Function to convert item -> text to estimate tokens
    
    Returns: List[List] — list of batches
    """
    if not items:
        return []

    batches = []
    current_batch = []
    current_tokens = 0

    for item in items:
        item_text = item_to_text(item)
        item_tokens = estimate_tokens(item_text)

        should_flush = (
            (len(current_batch) >= max_items_per_chunk) or
            (current_tokens + item_tokens > max_tokens_per_chunk and current_batch)
        )

        if should_flush:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(item)
        current_tokens += item_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def process_chunks_with_llm(
    chunks: List[str],
    prompt_template: str,
    llm_call: Callable[[str], str],
    merge_strategy: str = "concatenate",
    chunk_label: str = "data",
    agent_name: str = "UNKNOWN"
) -> str:
    """
    Processes each chunk through LLM and then merges results.
    
    Args:
        chunks: List of text chunks
        prompt_template: Template with placeholders {chunk_data} and {chunk_info}
        llm_call: LLM calling function (takes prompt str, returns response str)
        merge_strategy:
            - "concatenate": Concatenate all responses
            - "summarize": Gather responses and call LLM to summarize one last time
            - "json_merge": Merge JSON responses into a single object
        chunk_label: Log label
        agent_name: Agent name for logging
    
    Returns: Merged response
    """
    if not chunks:
        return ""

    # If only 1 chunk -> call directly, no merge needed
    if len(chunks) == 1:
        prompt = prompt_template.replace("{chunk_data}", chunks[0])
        prompt = prompt.replace("{chunk_info}", f"[Full data — 1/1]")
        return llm_call(prompt)

    log.info(f"[{agent_name}] Chunking: {len(chunks)} chunks for {chunk_label}")
    
    responses = []
    for i, chunk in enumerate(chunks):
        chunk_info = f"[Chunk {i+1}/{len(chunks)} — Analyze piece-by-piece then summarize]"
        prompt = prompt_template.replace("{chunk_data}", chunk)
        prompt = prompt.replace("{chunk_info}", chunk_info)

        try:
            resp = llm_call(prompt)
            if resp and "ERROR" not in str(resp)[:10]:
                responses.append(resp)
                log.info(f"[{agent_name}] Chunk {i+1}/{len(chunks)} OK ({estimate_tokens(resp)} tokens)")
            else:
                log.warning(f"[{agent_name}] Chunk {i+1}/{len(chunks)} FAILED: {str(resp)[:80]}")
        except Exception as e:
            log.warning(f"[{agent_name}] Chunk {i+1}/{len(chunks)} ERROR: {e}")
        
        # Brief pause between chunks to avoid rate limit
        if i < len(chunks) - 1:
            time.sleep(1)

    if not responses:
        return ""

    # ── MERGE STRATEGIES ──
    if merge_strategy == "concatenate":
        return "\n\n---\n\n".join(responses)

    elif merge_strategy == "json_merge":
        merged = {}
        for resp in responses:
            try:
                clean = resp
                if "```" in clean:
                    clean = re.sub(r'```json|```', '', clean).strip()
                match = re.search(r'\{.*\}', clean, re.DOTALL)
                if match:
                    obj = json.loads(match.group(0))
                    # Shallow merge: subsequent values overwrite previous ones
                    for k, v in obj.items():
                        if k in merged and isinstance(merged[k], list) and isinstance(v, list):
                            merged[k].extend(v)
                        else:
                            merged[k] = v
            except (json.JSONDecodeError, ValueError):
                continue
        return json.dumps(merged, ensure_ascii=False) if merged else responses[-1]

    elif merge_strategy == "summarize":
        # Gather all chunk responses and call LLM one last time to summarize
        combined = "\n\n".join(f"=== SECTION RESULT {i+1} ===\n{r}" for i, r in enumerate(responses))
        
        # If combined is still too large, truncate proportionally
        if estimate_tokens(combined) > MAX_CHUNK_SIZE_TOKENS:
            log.warning(f"[{agent_name}] Combined responses still large ({estimate_tokens(combined)} tokens), truncating proportionally")
            allowed_tokens = MAX_CHUNK_SIZE_TOKENS // max(1, len(responses))
            truncated_resps = [smart_truncate(r, allowed_tokens) for r in responses]
            combined = "\n\n".join(f"=== SECTION RESULT {i+1} ===\n{r}" for i, r in enumerate(truncated_resps))

        summary_prompt = f"""Summarize {len(responses)} separate analyses into a single unified conclusion.
Each section analyzed a slice of the data. Please merge, remove duplicates, and retain the most critical insights.

{combined}

Return the final synthesized conclusion (in the same format as each part):"""
        try:
            return llm_call(summary_prompt)
        except Exception as e:
            log.warning(f"[{agent_name}] Summary merge FAILED: {e}, using final response")
            return responses[-1]

    return "\n\n".join(responses)


def smart_truncate(text: str, max_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS) -> str:
    """
    Smartly truncates text (along sentence boundaries) to not exceed max_tokens.
    Used when complex chunking is unnecessary, but text must not be too long.
    """
    if not text:
        return ""
    
    if estimate_tokens(text) <= max_tokens:
        return text

    max_chars = int(max_tokens * CHARS_PER_TOKEN)
    truncated = text[:max_chars]
    
    # Truncate at the nearest sentence boundary
    last_period = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
    if last_period > max_chars * 0.5:  # Only truncate if the punctuation lies in the second half
        truncated = truncated[:last_period + 1]
    
    return truncated + f"\n\n[... Truncated — showing {estimate_tokens(truncated)}/{estimate_tokens(text)} tokens ...]"
