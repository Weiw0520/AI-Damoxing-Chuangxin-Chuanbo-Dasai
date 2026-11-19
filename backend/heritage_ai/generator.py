"""Pure-call service entry point: generate(payload, model=...)."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .evidence import TICKET_TOPIC, guard_segment, is_ticket_gap_notice, locate, mandatory_questions
from .errors import GenerationError
from .model import ChatModel, Settings
from .validation import parse_draft, parse_request, parse_reviews

PROMPT_VERSION = "v5"
PROMPTS = Path(__file__).with_name("prompts")
PENDING_TEXT = "资料不足，待核验：本段事实依据尚不充分，确认后再补充。"


def _prompt(name):
    return (PROMPTS / name).read_text(encoding="utf-8")


def generate(payload: dict, *, model=None) -> dict:
    """Return a standalone core result; C must map it to the existing API contract.

    The injected model must implement complete(stage, system, payload) -> dict.
    Without injection a real configured endpoint is used. No mock fallback exists.
    """
    request = parse_request(payload)
    model = model if model is not None else ChatModel(Settings.from_env())
    missing_questions = mandatory_questions(request)
    candidates = parse_draft(model.complete(
        stage="generate", system=_prompt("generate_v5.txt"),
        payload={**request, "mandatory_missing_fields": missing_questions}))
    return verify_candidates(request, candidates, model, missing_questions)


def verify_candidates(request, candidates, model, missing_questions):
    """Shared exact/semantic checks for initial generation and later rewrites."""
    source_map = {s["id"]: s for s in request["sources"]}
    checked = {}
    for candidate in candidates:
        checked[candidate["id"]] = [locate(ref, source_map) for ref in candidate["evidence"]]
    # Independent call without the generation conversation or self-assigned confidence.
    # Review includes the whole paragraph: do not let a model omit an unsupported subclaim.
    reviews = parse_reviews(model.complete(
        stage="review", system=_prompt("review_v5.txt"), payload={
            "sources": request["sources"], "brief": request["brief"],
            "segments": candidates,
            "structural_checks": {
                sid: [{"index": i, "quote_found": entry[0] is not None,
                       "error": entry[1]} for i, entry in enumerate(items)]
                for sid, items in checked.items()
            },
        }), candidates)
    segments, pending = [], []
    for candidate in candidates:
        sid = candidate["id"]
        review = reviews[sid]
        checks = checked[sid]
        # Known missing ticket prices are rendered once by the deterministic global notice.
        # Preserve other uncertain blocks; never merge a paragraph carrying source evidence.
        if missing_questions and not candidate["evidence"] and (
            is_ticket_gap_notice(candidate["text"]) or (
                candidate["text"] == PENDING_TEXT and TICKET_TOPIC.search(review["reason"])
            )
        ):
            continue
        issues = [(code, reason) for _, code, reason in checks if code]
        if not candidate["evidence"]:
            issues.append(("no_evidence", "该段没有提供原文引文。"))
        used = review["used_evidence"]
        quotes = [checks[i][0]["quote"] for i in used if checks[i][0] is not None]
        issues.extend(guard_segment(candidate["text"], quotes))
        if review["verdict"] != "supported":
            issues.append(("semantic_insufficient", review["reason"]))
        supported = not issues
        # An unsafe candidate never enters publishable text, even with a warning suffix.
        text = candidate["text"] if supported else PENDING_TEXT
        evidence = []
        for i in used if supported else range(len(checks)):
            item = checks[i][0]
            if item is not None:
                evidence.append({**item, "supports_segment": supported})
        segments.append({
            "id": sid, "text": text,
            "status": "supported" if supported else "pending_verification",
            "evidence": evidence,
            "verification_reason": review["reason"] if supported else "；".join(dict.fromkeys(r for _, r in issues)),
        })
        for code, reason in dict.fromkeys(issues):
            pending.append({"segment_id": sid, "code": code, "topic": "段落事实", "reason": reason})
    for item in missing_questions:
        pending.append({"segment_id": None, **item})
    canonical = json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")
    mode = getattr(model, "mode", None)
    if mode not in {"live", "fixture"}:
        raise GenerationError("注入模型必须明确声明 mode=live 或 fixture")
    return {
        "schema_version": "b-core/0.1",
        "meta": {"mode": mode, "prompt_version": PROMPT_VERSION,
                 "model": getattr(model, "label", "unknown"),
                 "verify_model": getattr(model, "verify_label", "unknown"),
                 "generated_at": datetime.now(timezone.utc).isoformat(),
                 "input_sha256": hashlib.sha256(canonical).hexdigest()},
        "sources": request["sources"], "platform": request["platform"],
        "segments": segments, "pending_checks": pending,
    }
