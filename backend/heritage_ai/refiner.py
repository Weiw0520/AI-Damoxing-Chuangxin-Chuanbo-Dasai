"""Role B: revise the current text, then independently verify every returned block."""

import hashlib
import json
from datetime import datetime, timezone

from .errors import GenerationError, InputError
from .evidence import is_ticket_gap_notice, mandatory_questions
from .generator import _prompt, verify_candidates
from .model import ChatModel, Settings
from .retrieval import fill_missing_evidence
from .validation import identifier, parse_draft, parse_request, string

REFINE_PROMPT_VERSION = "refine-v2"
REVIEW_PROMPT_VERSION = "v5"
PIPELINE_VERSION = "refine-core/0.1.3"


class CandidateEvidenceError(GenerationError):
    """Keep only field shape for safe diagnostics, never candidate text or values."""

    def __init__(self, index, value):
        super().__init__("每段 evidence 须为数组且不超过 12 条")
        self.index = index
        self.shape = ("array" if isinstance(value, list) else "object" if isinstance(value, dict)
                      else "boolean" if isinstance(value, bool) else "string" if isinstance(value, str)
                      else "number" if isinstance(value, (int, float)) else "other")
        self.count = len(value) if isinstance(value, (list, dict)) else None


def normalize_candidate_evidence(segments):
    """Normalize unambiguous JSON containers; never manufacture a reference.

    Empty/absent evidence stays empty and must still pass the independent review.
    A singleton reference object only gains array brackets; its ID and quote remain
    subject to exactly the same structural and semantic checks as any other entry.
    All other shapes and oversized arrays fail without truncation or coercion.
    """
    if not isinstance(segments, list):
        return segments, []  # parse_draft reports the existing segment-array error.
    normalized, changes = [], []
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            normalized.append(segment)
            continue
        item = dict(segment)
        refs = item.get("evidence")
        code = None
        if "evidence" not in item:
            item["evidence"], code = [], "EVIDENCE_OMITTED_TO_EMPTY"
        elif refs is None:
            item["evidence"], code = [], "EVIDENCE_NULL_TO_EMPTY"
        elif isinstance(refs, dict) and not refs:
            item["evidence"], code = [], "EVIDENCE_EMPTY_OBJECT_TO_EMPTY"
        elif isinstance(refs, dict) and set(refs) == {"source_id", "quote"}:
            item["evidence"], code = [dict(refs)], "EVIDENCE_OBJECT_TO_ARRAY"
        elif not isinstance(refs, list) or len(refs) > 12:
            raise CandidateEvidenceError(index, refs)
        if code:
            changes.append({"candidate_index": index, "code": code})
        normalized.append(item)
    return normalized, changes


def safe_diagnostic(error):
    """Whitelist internal categories, never publish arbitrary provider error text."""
    if isinstance(error, CandidateEvidenceError):
        detail = {"diagnostic_code": "CANDIDATE_EVIDENCE_INVALID", "stage": "refine",
                  "candidate_index": error.index, "received_type": error.shape}
        if error.count is not None:
            detail["item_count"] = error.count
        return detail
    message = str(error)
    categories = {
        "pending_ 段落编号保留给服务端资料缺口提示": "RESERVED_SEGMENT_ID",
        "追问输出须声明 action=rewrite 或 explain": "REFINE_ACTION_INVALID",
        "生成结果须包含 1–12 个 segments": "DRAFT_SEGMENTS_INVALID",
        "核验文本与待核验段落不一致": "REVIEW_TEXT_MISMATCH",
        "核验结果缺少 reviews 数组": "REVIEW_FORMAT_INVALID",
        "核验结果遗漏了段落": "REVIEW_SEGMENTS_MISSING",
        "核验 used_evidence 必须是合法且不重复的引文下标": "REVIEW_EVIDENCE_INVALID",
        "supported 核验结果至少需要一条引文": "REVIEW_EVIDENCE_MISSING",
        "模型响应为空、JSON 无效或结构不完整": "MODEL_JSON_INVALID",
        "模型输出未完整结束；请检查 token 上限或服务状态": "MODEL_OUTPUT_TRUNCATED",
        "核验 reason 长度超过 600": "REVIEW_REASON_TOO_LONG",
        "每段 evidence 须为数组且不超过 12 条": "CANDIDATE_EVIDENCE_INVALID",
    }
    import re
    http = re.fullmatch(r"模型服务 HTTP (\d{3})（阶段：(refine|review)）", message)
    if http:
        return {"diagnostic_code": "MODEL_HTTP_ERROR", "upstream_status": int(http[1]), "stage": http[2]}
    connection = re.fullmatch(r"模型服务连接失败或超时（阶段：(refine|review)）", message)
    if connection:
        return {"diagnostic_code": "MODEL_CONNECTION_ERROR", "stage": connection[1]}
    return {"diagnostic_code": categories.get(message, "MODEL_OR_VALIDATION_FAILED")}


def parse_refine_request(payload):
    request = parse_request(payload)
    instruction = string(payload.get("instruction"), "instruction", limit=2000).strip()
    segments = payload.get("segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= 24:
        raise InputError("追问须包含当前完整的 1–24 个段落")
    current, seen = [], set()
    for segment in segments:
        if not isinstance(segment, dict):
            raise InputError("当前段落须为对象")
        sid = identifier(segment.get("id"), "当前段落 id")
        if sid in seen:
            raise InputError("当前段落编号重复")
        seen.add(sid)
        current.append({"id": sid, "text": string(segment.get("text"), "当前段落 text", limit=1600, allow_empty=True)})
    context = payload.get("context", [])
    if not isinstance(context, list) or len(context) > 6:
        raise InputError("追问上下文最多保留 6 轮")
    turns = []
    for turn in context:
        if not isinstance(turn, dict):
            raise InputError("追问上下文须为对象")
        turns.append({"instruction": string(turn.get("instruction"), "历史 instruction", limit=2000),
                      "summary": string(turn.get("summary", ""), "历史 summary", limit=2000, allow_empty=True)})
    return {**request, "instruction": instruction, "segments": current, "context": turns}


def refine(payload, *, model=None):
    request = parse_refine_request(payload)
    model = model if model is not None else ChatModel(Settings.from_env())
    if getattr(model, "mode", None) not in {"live", "fixture"}:
        raise GenerationError("注入模型必须明确声明 mode=live 或 fixture")
    # Current text and prior instructions keep a requested ticket gap visible in later turns.
    topics = "\n".join([request["brief"], request["instruction"],
                         *(s["text"] for s in request["segments"]),
                         *(t["instruction"] for t in request["context"])])
    missing = mandatory_questions({**request, "brief": topics})
    # Server-owned missing-field notices are not editable AI body paragraphs.
    # Keep them in the canonical request/hash, but send only ordinary text to rewrite.
    model_payload = {**request, "segments": [s for s in request["segments"] if not s["id"].startswith("pending_")],
                     "mandatory_missing_fields": missing}
    answer = model.complete(stage="refine", system=_prompt("refine_v2.txt"), payload=model_payload)
    if not isinstance(answer, dict) or answer.get("action") not in {"rewrite", "explain"}:
        raise GenerationError("追问输出须声明 action=rewrite 或 explain")
    normalizations, retrievals = [], []
    if answer["action"] == "explain":
        # An explanation is rendered from stored claims by C's adapter. Never publish
        # unverified free-form model replies or call an explanation a new verification.
        result = {"segments": [], "pending_checks": [{"segment_id": None, **item} for item in missing]}
    else:
        # A model can still echo a canonical warning. Let the server render that
        # warning once; never discard arbitrary factual text or bad references here.
        raw_segments, normalizations = normalize_candidate_evidence(answer.get("segments"))
        if missing and isinstance(raw_segments, list):
            raw_segments = [s for s in raw_segments if not (
                isinstance(s, dict) and isinstance(s.get("id"), str) and s["id"].startswith("pending_")
                and isinstance(s.get("text"), str) and is_ticket_gap_notice(s["text"])
                and s.get("evidence") in (None, []))]
        candidates = parse_draft({"segments": raw_segments})
        if any(s["id"].startswith("pending_") for s in candidates):
            raise GenerationError("pending_ 段落编号保留给服务端资料缺口提示")
        # Retrieval supplies candidate quotations from original bodies, never a
        # verdict. New text still undergoes every provenance and semantic check.
        candidates, retrievals = fill_missing_evidence(candidates, request["sources"])
        # The review sees the new instruction too, but neither it nor conversation
        # history becomes factual evidence. Only supplied source bodies can support text.
        review_request = {**request, "brief": request["brief"] + "\n本轮改写要求：" + request["instruction"]}
        result = verify_candidates(review_request, candidates, model, missing)
    canonical = json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")
    action = answer["action"]
    result.update({"schema_version": "b-refine/0.1", "action": action,
                   "sources": request["sources"], "platform": request["platform"],
                   "meta": {"mode": model.mode, "operation": action, "pipeline_version": PIPELINE_VERSION,
                            "prompt_version": REFINE_PROMPT_VERSION + "/review-v5" if action == "rewrite" else REFINE_PROMPT_VERSION,
                            "refine_prompt_version": REFINE_PROMPT_VERSION,
                            "review_prompt_version": REVIEW_PROMPT_VERSION,
                            "review_executed": action == "rewrite", "candidate_normalizations": normalizations,
                            "evidence_retrieval": retrievals,
                            "model": model.label,
                            "verify_model": model.verify_label,
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "input_sha256": hashlib.sha256(canonical).hexdigest()}})
    return result
