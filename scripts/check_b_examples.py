"""Check the common-case acceptance invariants, rejecting mock output by default.

This is an acceptance aid for the supplied two snippets, not a general semantic prover.
Run from the project root using `python -m scripts.check_b_examples --help`.
"""

import argparse
import json
from pathlib import Path
import sys

from backend.generator import Generation
from backend.heritage_ai.evidence import MONEY_ASSERTION, guard_segment
from backend.real_generator import sources_from_request


def check(path, body, *, price, allow_mock):
    result = Generation.model_validate_json(path.read_text(encoding="utf-8"))
    if result.mode != "real" and not allow_mock:
        raise ValueError("结果为 mock，不属于真实模型验收；离线演示需显式传 --allow-mock")
    sources = {s.sourceId: s for s in sources_from_request(body)}
    if len({b.blockId for b in result.blocks}) != len(result.blocks):
        raise ValueError("段落编号重复")
    for block in result.blocks:
        if block.status == "supported" and not block.evidence:
            raise ValueError("有依据段落缺少引文")
        for ref in block.evidence:
            if ref.sourceId not in sources or ref.quote not in sources[ref.sourceId].text:
                raise ValueError("资料编号或连续原文引文无效")
        if block.status == "supported":
            issues = guard_segment(block.text, [e.quote for e in block.evidence])
            if issues:
                raise ValueError("有依据段落含缺少原文支持的断言：" + "；".join(reason for _, reason in issues))
    supported = [b for b in result.blocks if b.status == "supported"]
    if not any("潍坊" in b.text and "杨家埠" in b.text and any(
        "山东省潍坊市杨家埠" in e.quote for e in b.evidence) for b in supported):
        raise ValueError("缺少有所在地依据的文案")
    if not any(all(term in b.text for term in ["钩描", "刻版", "印刷"]) and any(
        "钩描、刻版、印刷3道工序" in e.quote for e in b.evidence) for b in supported):
        raise ValueError("缺少有三道制作工序依据的文案")
    if any(MONEY_ASSERTION.search(b.text) for b in result.blocks):
        raise ValueError("本案例未给出费用资料，正文不应出现费用、免费或优惠结论")
    if price and not any(
        b.status == "needs_review" and "门票" in b.text + b.reviewReason and
        "资料不足" in b.text + b.reviewReason and "待核验" in b.text + b.reviewReason
        for b in result.blocks
    ):
        raise ValueError("缺少门票资料不足、待核验提示")
    return result.mode


def main():
    parser = argparse.ArgumentParser(description="检查杨家埠两份生成结果；默认要求 mode=real")
    parser.add_argument("--normal", required=True, type=Path)
    parser.add_argument("--price", required=True, type=Path)
    parser.add_argument("--allow-mock", action="store_true")
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1] / "examples/b_generator"
    try:
        modes = []
        for output, name, is_price in [(args.normal, "02_request_normal.json", False),
                                       (args.price, "03_request_missing_price.json", True)]:
            body = json.loads((folder / name).read_text(encoding="utf-8"))
            modes.append(check(output, body, price=is_price, allow_mock=args.allow_mock))
        print(f"两份结果通过固定案例检查（mode={','.join(modes)}）。请再人工核对整句语义与引文。")
        return 0
    except (ValueError, OSError) as exc:
        print(f"验收未通过：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
