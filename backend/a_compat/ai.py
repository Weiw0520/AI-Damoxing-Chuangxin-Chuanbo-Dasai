"""Adapt A's original material input to B's core; no generation rules duplicated."""
from dataclasses import replace
import copy
from pathlib import Path
import re
import time
from uuid import uuid4

from backend.a_compat.store import failure, now
from backend.heritage_ai.errors import ConfigurationError, GenerationError, InputError
from backend.heritage_ai.generator import generate as generate_core
from backend.heritage_ai.refiner import refine as refine_core, safe_diagnostic
from backend.heritage_ai.model import ChatModel, Settings
from backend.real_generator import _core_payload, sources_from_request


def parse_material(material):
    """Split explicit source headings only; preserve the full original in draft.input.

    A has one textarea. Source/title/link lines become metadata, not factual body.
    Without headings the entire submitted text is one source; no URL is fetched.
    """
    material = material.strip()
    markers = list(re.finditer(r"(?m)^资料(?:[一二三四五六七八九十百]+|\d+)(?=[\s：:]|$)[ \t]*[：:]?[ \t]*", material))
    chunks = []
    if markers:
        preface = material[:markers[0].start()].strip()
        if preface and not (preface.startswith("【示例资料") and preface.endswith("】")):
            chunks.append(preface)
        for i, marker in enumerate(markers):
            chunks.append(material[marker.end():markers[i + 1].start() if i + 1 < len(markers) else len(material)])
    else:
        chunks = [material]
    sources = []
    for chunk in chunks:
        title, url, lines = "", None, []
        for line in chunk.splitlines():
            metadata = re.fullmatch(r"[ \t]*(来源|链接)[ \t]*[：:][ \t]*(.*)", line)
            if metadata:
                kind, value = metadata.groups()
                if kind == "来源":
                    title = value.strip()
                else:
                    url = value.strip() or None
            else:
                lines.append(line)
        text = "\n".join(lines).strip()
        if not text:
            raise InputError("每份资料须包含正文，不能只有标题或链接。")
        sources.append({"title": title or f"用户资料{len(sources) + 1}", "text": text, "url": url})
    return sources


class DeadlineModel:
    def __init__(self, model, deadline):
        self.model, self.deadline = model, deadline
        self.mode, self.label, self.verify_label = model.mode, model.label, model.verify_label

    def complete(self, **kwargs):
        remaining = self.deadline - time.monotonic()
        if remaining < 1:
            raise TimeoutError
        if isinstance(self.model, ChatModel):
            self.model.settings = replace(self.model.settings, timeout=min(self.model.settings.timeout, remaining))
        result = self.model.complete(**kwargs)
        if time.monotonic() >= self.deadline:
            raise TimeoutError
        return result


def map_segments(result, aliases, previous=()):
    old = {s["id"]: s for s in previous}
    segments = []
    for segment in result["segments"]:
        verified = segment["status"] == "supported"
        quotes = [{"source_id": aliases[e["source_id"]], "quote": e["quote"]}
                  for e in segment["evidence"] if verified and e["supports_segment"]]
        prior = old.get(segment["id"], {})
        segments.append({"id": segment["id"], "type": prior.get("type", "body"),
                         "label": prior.get("label", f"正文{len(segments) + 1}"),
                         "text": segment["text"], "claims": [{"id": "claim_" + segment["id"],
                         "anchor": segment["text"], "status": "verified" if verified else "needs_check",
                         "cite_ids": list(dict.fromkeys(q["source_id"] for q in quotes)), "quotes": quotes,
                         "reason": segment["verification_reason"], "suggest": None}]})
    append_pending(segments, result["pending_checks"])
    return segments


def append_pending(segments, pending):
    for i, issue in enumerate(pending):
        if issue["segment_id"] is not None:
            continue
        text = f"{issue['topic']}：资料不足，待核验。"
        if any(s["text"] == text for s in segments):
            continue
        sid = f"pending_{i}"
        while any(s["id"] == sid for s in segments):
            sid += "_new"
        segments.append({"id": sid, "type": "body", "label": "待补资料", "text": text,
                         "claims": [{"id": "pending_claim_" + sid[len("pending_"):], "anchor": text, "status": "needs_check",
                                     "cite_ids": [], "quotes": [], "reason": issue["reason"], "suggest": None}]})


def refine_draft(draft, payload, deadline, *, model_factory=None):
    visible = copy.deepcopy(draft["segments"])
    incoming = {s.id: s.text for s in payload.segments}
    page_edits = []
    for seg in visible:
        text = incoming[seg["id"]]
        if text == seg["text"]:
            continue
        page_edits.append({"id": seg["id"], "before": seg["text"], "after": text})
        seg.update(text=text, review_status="edited_needs_review", claims=[{
            "id": f"manual_{seg['id']}_v{draft['version'] + 1}", "anchor": text,
            "status": "needs_check", "cite_ids": [], "quotes": [], "suggest": None,
            "reason": "人工修改后待复核；本轮仅解释现有依据，尚未重新核验该段。"}] if text.strip() else [])
    aliases = {s.get("origin_id") or s["id"]: s["id"] for s in draft["sources"]}
    request = {"sources": [{"id": s.get("origin_id") or s["id"], "title": s["title"],
                            "text": s["snippet"], "url": s.get("url") or ""} for s in draft["sources"]],
               "brief": draft["input"]["requirement"],
               "platform": "小红书" if draft["input"]["platform"] == "xiaohongshu" else draft["input"]["platform"],
               "segments": [{"id": s["id"], "text": s["text"]} for s in visible],
               "instruction": payload.instruction, "context": draft.get("refine_context", [])}
    try:
        model = model_factory() if model_factory else ChatModel(Settings.from_env())
        result = refine_core(request, model=DeadlineModel(model, deadline))
    except ConfigurationError:
        raise failure(503, "AI_NOT_CONFIGURED", "未配置可用模型，无法处理追问，原草稿未修改。") from None
    except InputError as error:
        raise failure(422, "AI_INPUT_INVALID", str(error)) from None
    except GenerationError as error:
        response = failure(502, "AI_REFINEMENT_FAILED", "模型改写或依据核验失败，原草稿未修改；请检查模型服务后重试。")
        response.detail.update(safe_diagnostic(error))
        raise response from None
    meta, action = result["meta"], result["action"]
    live = meta["mode"] == "live"
    if action == "rewrite":
        segments = map_segments(result, aliases, visible)
        supported = sum(c["status"] == "verified" for s in segments for c in s["claims"])
        pending = sum(c["status"] == "needs_check" for s in segments for c in s["claims"])
        desc = f"已处理追问并重新核验当前文案：{supported} 处有资料依据，{pending} 处待核验。请查看最新版正文和核验报告。"
        notice = "真实模型已执行本轮改写与依据核验；仅核对提交资料，发布前仍需人工复核。"
    else:
        segments = visible
        append_pending(segments, result["pending_checks"])
        lines = ["本轮说明现有核验记录，未执行改写或重新核验。"]
        for seg in segments:
            for claim in seg.get("claims", []):
                references = "；".join(f"{q['source_id']} 原文“{q['quote']}”" for q in claim.get("quotes", []))
                lines.append(f"{seg['label']}：{'有资料依据' if claim['status'] == 'verified' else '待核验'}。"
                             + (references + "。" if references else "当前没有可用引文。") + claim["reason"])
        desc = "\n".join(lines)
        notice = "本轮模型仅解析依据说明请求；正文依据来自现有记录，未重新运行事实核验。"
    if not live:
        desc = "模拟联调（未调用真实模型）：" + desc
        notice = "模拟联调：显式注入的离线模型，不是真实追问验收。"
    return {"action": action, "segments": segments, "model": meta["model"],
            "mode": "real" if live else "mock", "data_origin": "ai" if live else "offline_replay",
            "prompt_version": meta["prompt_version"],
            "prompt_excerpt": (Path(__file__).parents[1] / "heritage_ai/prompts/review_v5.txt").read_text(encoding="utf-8"),
            "notice": {"level": "warn", "text": notice}, "ai_meta": meta, "desc": desc,
            "diagnostics": result["segments"], "page_edits": page_edits}


def generate_draft(payload, deadline, *, model_factory=None):
    try:
        request = {"sources": parse_material(payload.material), "brief": payload.requirement,
                   "platform": "小红书" if payload.platform == "xiaohongshu" else payload.platform}
        numbered = sources_from_request(request)
        # B deduplicates identical stable IDs; A source aliases must be unique too.
        numbered = list({source.sourceId: source for source in numbered}.values())
        model = model_factory() if model_factory else ChatModel(Settings.from_env())
        result = generate_core(_core_payload(numbered, request["brief"], request["platform"]),
                               model=DeadlineModel(model, deadline))
    except ConfigurationError:
        raise failure(503, "AI_NOT_CONFIGURED", "未配置可用模型：请在启动后端的终端配置 AI_API_KEY、AI_MODEL 和对应 AI_BASE_URL；未创建草稿。") from None
    except InputError as error:
        raise failure(422, "AI_INPUT_INVALID", str(error)) from None
    except GenerationError:
        # Never return arbitrary model/provider exception text to the browser.
        raise failure(502, "AI_GENERATION_FAILED", "模型生成或依据核验失败，未创建或保存草稿；请检查模型服务后重试。") from None

    meta = result["meta"]
    live = meta["mode"] == "live"
    mode = "real" if live else "mock"
    timestamp, draft_id = now(), "A-" + uuid4().hex
    aliases = {s.sourceId: f"S{i + 1}" for i, s in enumerate(numbered)}
    sources = [{"id": aliases[s.sourceId], "origin_id": s.sourceId, "title": s.title,
                "publisher": "用户提交资料（未抓取网页）", "url": s.url or "", "snippet": s.text} for s in numbered]
    segments = map_segments(result, aliases)
    notice = ("真实模型已执行生成与依据核验；仅核对提交资料，不能证明资料本身真实。发布前仍需人工复核。" if live else
              "模拟联调：显式离线回放或故障模拟，不是真实模型验收结果。")
    return {"draft_id": draft_id, "mode": mode, "data_origin": "ai" if live else "offline_replay",
            "version": 1, "created_at": timestamp, "updated_at": timestamp,
            "model": meta["model"], "prompt_version": meta["prompt_version"],
            "prompt_excerpt": (Path(__file__).parents[1] / "heritage_ai/prompts/review_v5.txt").read_text(encoding="utf-8"),
            "notice": {"level": "warn", "text": notice}, "sources": sources, "segments": segments,
            "input": payload.model_dump(), "ai_meta": meta,
            "history": [{"id": "generated-" + draft_id, "type": "ai" if live else "system",
                         "title": "模型生成与核验" if live else "显式离线回放（非真实模型）",
                         "who": "AI" if live else "测试回放", "whoClass": "ai" if live else "system",
                         "time": timestamp, "desc": notice, "diagnostics": result["segments"]}]}
