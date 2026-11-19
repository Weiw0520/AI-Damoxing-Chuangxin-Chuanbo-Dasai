"""Retrieve exact source-body windows as candidates, never as proof of support."""

import math
import re

from .evidence import is_ticket_gap_notice

METHOD = "source-body-overlap-v1"
QUOTE_LIMIT = 900
SOURCE_LIMIT = 3


def _tokens(text):
    tokens = set()
    for chunk in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", text):
        if re.fullmatch(r"[\u4e00-\u9fff]+", chunk):
            tokens.update(chunk[i:i + 2] for i in range(len(chunk) - 1))
        else:
            tokens.add(chunk.lower())
    return tokens


def retrieve_quotes(text, sources):
    """Bounded lexical retrieval from submitted bodies only; no URLs or titles.

    Keep a short source intact, including qualifiers and negation. For a long
    body, select its best contiguous 900-character window. The independent review
    still receives the full source, and must judge every fact in the new text.
    At most three distinct sources are retrieved; recall is not guaranteed.
    """
    query = _tokens(text)
    if len(query) < 2 or is_ticket_gap_notice(text):
        return []
    ranked = []
    for source_index, source in enumerate(sources):
        body = source["text"]
        starts = range(0, max(1, len(body) - QUOTE_LIMIT + 1), QUOTE_LIMIT // 2)
        # Always include the final window so a short tail cannot be missed.
        starts = sorted(set(starts) | {max(0, len(body) - QUOTE_LIMIT)})
        best = None
        for start in starts:
            quote = body[start:start + QUOTE_LIMIT]
            tokens = _tokens(quote)
            common = query & tokens
            if len(common) < 2:
                continue
            score = len(common) / math.sqrt(len(query) * len(tokens))
            item = (score, len(common), -start, quote)
            if best is None or item[:3] > best[:3]:
                best = item
        if best:
            ranked.append((best[0], best[1], -source_index,
                           {"source_id": source["id"], "quote": best[3]}))
    ranked.sort(key=lambda item: item[:3], reverse=True)
    return [item[3] for item in ranked[:SOURCE_LIMIT]]


def fill_missing_evidence(candidates, sources):
    """Offer fresh candidates for empty citations; keep all explicit citations.

    The result is sent to the same structural and semantic verifier. Never copy
    a previous verdict, replace a bad citation, or mark retrieved text supported.
    """
    result, audit = [], []
    for index, segment in enumerate(candidates):
        item = dict(segment)
        if not item["evidence"]:
            references = retrieve_quotes(item["text"], sources)
            if references:
                item["evidence"] = references
                audit.append({"candidate_index": index, "method": METHOD,
                              "source_ids": [ref["source_id"] for ref in references],
                              "quote_count": len(references)})
        result.append(item)
    return result, audit
