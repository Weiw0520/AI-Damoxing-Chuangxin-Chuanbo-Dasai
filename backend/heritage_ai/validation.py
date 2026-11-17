"""Strict boundaries for untrusted input and model-produced JSON."""

import re
from urllib.parse import urlsplit

from .errors import GenerationError, InputError

ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


def string(value, label, *, limit=2000, error=InputError, allow_empty=False):
    if not isinstance(value, str) or (not value.strip() and not allow_empty):
        raise error(f"{label} 必须是{'可空' if allow_empty else '非空'}字符串")
    if len(value) > limit:
        raise error(f"{label} 长度超过 {limit}")
    return value


def identifier(value, label, error=InputError):
    value = string(value, label, limit=128, error=error)
    if not ID_PATTERN.fullmatch(value):
        raise error(f"{label} 须为 1–128 位字母、数字或 _ . : -")
    return value


def parse_request(data):
    if not isinstance(data, dict):
        raise InputError("请求必须是 JSON 对象")
    brief = string(data.get("brief"), "brief", limit=4000)
    platform = string(data.get("platform"), "platform", limit=80)
    sources = data.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 30:
        raise InputError("sources 必须有 1–30 条资料")
    parsed, seen = [], set()
    # Reserve supplied IDs first so a generated S1 cannot collide with a later explicit S1.
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            raise InputError(f"sources[{i}] 必须是对象")
        if "id" in source:
            sid = identifier(source["id"], f"sources[{i}].id")
            if sid in seen:
                raise InputError("资料编号不能重复")
            seen.add(sid)
    for i, source in enumerate(sources):
        sid = source.get("id")
        if sid is None:
            n = 1
            while f"S{n}" in seen:
                n += 1
            sid = f"S{n}"
            seen.add(sid)
        title = string(source.get("title"), f"sources[{i}].title", limit=300)
        text = string(source.get("text"), f"sources[{i}].text", limit=20000)
        url = string(source.get("url", ""), f"sources[{i}].url", limit=2000, allow_empty=True)
        try:
            u = urlsplit(url)
            if url and (u.scheme not in {"http", "https"} or not u.hostname or u.username or u.password):
                raise ValueError
        except ValueError:
            raise InputError(f"sources[{i}].url 须为空或 HTTP(S) 来源链接") from None
        parsed.append({"id": sid, "title": title, "text": text, "url": url})
    if sum(len(s["text"]) for s in parsed) > 60000:
        raise InputError("资料正文总长度不得超过 60000 字符")
    return {"sources": parsed, "brief": brief, "platform": platform}


def parse_draft(data):
    if not isinstance(data, dict):
        raise GenerationError("生成结果须为对象")
    segments = data.get("segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= 12:
        raise GenerationError("生成结果须包含 1–12 个 segments")
    result, seen = [], set()
    for i, item in enumerate(segments):
        if not isinstance(item, dict):
            raise GenerationError("段落须为对象")
        sid = identifier(item.get("id"), f"segments[{i}].id", GenerationError)
        if sid in seen:
            raise GenerationError("生成的段落编号重复")
        seen.add(sid)
        text = string(item.get("text"), "段落 text", limit=1600, error=GenerationError)
        refs = item.get("evidence")
        if not isinstance(refs, list) or len(refs) > 12:
            raise GenerationError("每段 evidence 须为数组且不超过 12 条")
        evidence = []
        for ref in refs:
            if not isinstance(ref, dict):
                raise GenerationError("evidence 元素须为对象")
            evidence.append({
                "source_id": identifier(ref.get("source_id"), "source_id", GenerationError),
                "quote": string(ref.get("quote"), "quote", limit=3000, error=GenerationError),
            })
        result.append({"id": sid, "text": text, "evidence": evidence})
    return result


def parse_reviews(data, segments):
    if not isinstance(data, dict) or not isinstance(data.get("reviews"), list):
        raise GenerationError("核验结果缺少 reviews 数组")
    expected = {s["id"]: s for s in segments}
    result = {}
    for review in data["reviews"]:
        if not isinstance(review, dict):
            raise GenerationError("review 须为对象")
        sid = review.get("segment_id")
        if not isinstance(sid, str) or sid not in expected or sid in result:
            raise GenerationError("核验段落编号无效或重复")
        if review.get("text") != expected[sid]["text"]:
            raise GenerationError("核验文本与待核验段落不一致")
        if not isinstance(review.get("verdict"), str) or review["verdict"] not in {"supported", "insufficient"}:
            raise GenerationError("核验 verdict 只能为 supported 或 insufficient")
        string(review.get("reason"), "核验 reason", limit=600, error=GenerationError)
        used = review.get("used_evidence")
        if not isinstance(used, list) or any(
            type(i) is not int or i < 0 or i >= len(expected[sid]["evidence"]) for i in used
        ) or len(set(used)) != len(used):
            raise GenerationError("核验 used_evidence 必须是合法且不重复的引文下标")
        if review["verdict"] == "supported" and not used:
            raise GenerationError("supported 核验结果至少需要一条引文")
        result[sid] = review
    if set(result) != set(expected):
        raise GenerationError("核验结果遗漏了段落")
    return result
