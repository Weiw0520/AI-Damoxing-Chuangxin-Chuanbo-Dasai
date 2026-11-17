"""Explicit offline replay only. Never used as a default or fallback."""

import copy
import hashlib
import json
from pathlib import Path

from .errors import GenerationError
from .validation import parse_request


class FixtureModel:
    mode = "fixture"
    label = "offline-fixture-not-a-real-model"
    verify_label = label

    def __init__(self, path):
        self.data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.calls = []

    def complete(self, *, stage, system, payload):
        if stage == "generate":
            request = parse_request(payload)
            canonical = json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")
            if hashlib.sha256(canonical).hexdigest() != self.data.get("input_sha256"):
                raise GenerationError("离线样例与当前请求不匹配，不可将样例伪装成新输入的模型输出")
        self.calls.append(stage)
        if self.calls not in (["generate"], ["generate", "review"]):
            raise GenerationError("离线样例只支持一次 generate 和一次 review")
        return copy.deepcopy(self.data[stage])
