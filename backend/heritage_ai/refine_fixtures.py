"""Explicit, input-bound offline examples for the refiner; never a fallback."""

import copy
import hashlib
import json
from pathlib import Path

from .errors import GenerationError
from .refiner import parse_refine_request


class RefineFixtureModel:
    mode = "fixture"
    label = verify_label = "offline-refine-fixture-not-a-real-model"

    def __init__(self, path):
        self.data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.calls = []

    def complete(self, *, stage, system, payload):
        if stage == "refine":
            request = parse_refine_request(payload)
            digest = hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            if digest != self.data.get("input_sha256"):
                raise GenerationError("追问离线样例与当前输入不匹配")
        self.calls.append(stage)
        if self.calls not in (["refine"], ["refine", "review"]):
            raise GenerationError("追问回放仅支持一次 refine 和至多一次 review")
        try:
            return copy.deepcopy(self.data[stage])
        except KeyError:
            raise GenerationError("追问离线样例缺少阶段输出") from None
