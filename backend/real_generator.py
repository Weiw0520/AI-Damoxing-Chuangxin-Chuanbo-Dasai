"""Role-B adapter implementing the exact C Generator protocol.

Import generate in C, or use `python -m backend.real_generator --help` independently.
The existing backend.main:app remains mock by default.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from fastapi import HTTPException

from backend.generator import Block, Evidence, Generation, Source
from backend.heritage_ai import ConfigurationError, GenerationError, InputError
from backend.heritage_ai.generator import generate as generate_core
from backend.heritage_ai.validation import parse_request


def _core_payload(sources, brief, platform):
    # C permits repeated copies of the same source; keep stable IDs, never renumber them.
    unique = {}
    for source in sources:
        if source.sourceId in unique and unique[source.sourceId] != source:
            raise InputError("同一 sourceId 不能对应不同资料")
        unique[source.sourceId] = source
    return {"sources": [{"id": s.sourceId, "title": s.title, "text": s.text,
                          "url": s.url or ""} for s in unique.values()],
            "brief": brief, "platform": platform}


def make_generator(*, model=None):
    """Dependency injection for tests; a live model is the default, never a fixture."""
    def call(sources: list[Source], brief: str, platform: str) -> Generation:
        try:
            result = generate_core(_core_payload(sources, brief, platform), model=model)
        except ConfigurationError as exc:
            raise HTTPException(503, detail={"code": "ai_not_configured", "message": str(exc)}) from None
        except InputError as exc:
            raise HTTPException(422, detail={"code": "ai_input_invalid", "message": str(exc)}) from None
        except GenerationError as exc:
            raise HTTPException(502, detail={"code": "ai_generation_failed", "message": str(exc)}) from None
        offline = result["meta"]["mode"] == "fixture"
        prefix = "离线回放，未调用真实模型；" if offline else ""
        blocks = [Block(
            blockId=s["id"], text=s["text"],
            status="supported" if s["status"] == "supported" else "needs_review",
            evidence=[Evidence(sourceId=e["source_id"], quote=e["quote"]) for e in s["evidence"]],
            reviewReason=prefix + s["verification_reason"],
        ) for s in result["segments"]]
        ids = {b.blockId for b in blocks}
        # Segment-specific pending reasons are already in that block's reviewReason.
        # Global requested-but-missing facts need a visible needs_review block in API v1.
        for issue in result["pending_checks"]:
            if issue["segment_id"] is not None:
                continue
            n = 1
            while f"review_{n}" in ids:
                n += 1
            bid = f"review_{n}"
            ids.add(bid)
            blocks.append(Block(
                blockId=bid, text=f"{issue['topic']}：资料不足，待核验。",
                status="needs_review", evidence=[], reviewReason=prefix + issue["reason"],
            ))
        return Generation(mode="mock" if offline else "real", blocks=blocks)
    return call


def generate(sources: list[Source], brief: str, platform: str) -> Generation:
    return make_generator()(sources, brief, platform)


def sources_from_request(payload):
    """CLI convenience: number the shared unnumbered JSON exactly as C does.

    Direct Python use should pass C's Source objects instead of calling this helper.
    """
    if not isinstance(payload, dict) or set(payload) != {"sources", "brief", "platform"}:
        raise InputError("独立运行输入必须且只能包含 sources、brief、platform")
    items = payload.get("sources")
    if not isinstance(items, list):
        raise InputError("sources 须为数组")
    normalized = []
    for item in items:
        if not isinstance(item, dict) or set(item) - {"title", "text", "url"}:
            raise InputError("每条原始资料仅接受 title、text、url")
        title, text = item.get("title"), item.get("text")
        if not isinstance(title, str) or not isinstance(text, str):
            raise InputError("资料 title 和 text 须为字符串")
        normalized.append({"title": title.strip(), "text": text.strip(), "url": item.get("url") or ""})
    request = parse_request({"sources": normalized, "brief": payload["brief"], "platform": payload["platform"]})
    sources = []
    for item in request["sources"]:
        # An omitted/null URL becomes None in C; empty string stays empty string in C.
        original = items[len(sources)]
        fields = {"title": item["title"], "text": item["text"], "url": original.get("url")}
        canonical = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        sources.append(Source(sourceId="src_" + hashlib.sha256(canonical.encode()).hexdigest(), **fields))
    return sources


def main():
    parser = argparse.ArgumentParser(description="B 生成器：输出 C 可直接调用的 Generation JSON")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--replay", type=Path, help="显式离线样例，不属于真实 AI 验收")
    args = parser.parse_args()
    try:
        payload = json.loads(args.request.read_text(encoding="utf-8-sig"))
        sources = sources_from_request(payload)
        model = None
        if args.replay:
            from backend.heritage_ai.fixtures import FixtureModel
            model = FixtureModel(args.replay)
        result = make_generator(model=model)(sources, payload["brief"], payload["platform"])
        output = result.model_dump_json(indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        if args.replay:
            print("离线回放完成（mode=mock），不代表真实模型验收。", file=sys.stderr)
        return 0
    except HTTPException as exc:
        print(json.dumps({"status": exc.status_code, "detail": exc.detail}, ensure_ascii=False), file=sys.stderr)
        return 1
    except (InputError, GenerationError, OSError, ValueError) as exc:
        print(f"生成失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
