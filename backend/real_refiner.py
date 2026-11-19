"""Standalone CLI for B's callable rewrite/verification module."""

import argparse
import json
from pathlib import Path
import sys

from backend.heritage_ai import ConfigurationError, GenerationError, InputError, refine


def main():
    parser = argparse.ArgumentParser(description="B 追问改写与依据核验；默认调用真实模型")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--replay", type=Path, help="显式离线回放，meta.mode=fixture，不是真实验收")
    args = parser.parse_args()
    try:
        payload = json.loads(args.request.read_text(encoding="utf-8-sig"))
        model = None
        if args.replay:
            from backend.heritage_ai.refine_fixtures import RefineFixtureModel
            model = RefineFixtureModel(args.replay)
        result = refine(payload, model=model)
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0
    except (ConfigurationError, GenerationError, InputError, OSError, ValueError):
        # Do not print provider responses, payloads or configuration secrets.
        print("追问失败：请检查输入文件和本机模型配置；未写入任何草稿。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
