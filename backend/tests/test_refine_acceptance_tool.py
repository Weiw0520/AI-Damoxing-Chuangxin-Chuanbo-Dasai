"""The evidence collector must reject successful HTTP responses with lost body text."""

import copy
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.a_ai_main import create_ai_app
from backend.tests.test_refiner import Scripted
from scripts.run_b_refine_acceptance import EXPLAIN, PRICE, Runner


class MissingCitationModel(Scripted):
    degrade = False

    def complete(self, **kwargs):
        if kwargs["stage"] == "refine" and kwargs["payload"]["instruction"] == EXPLAIN:
            return {"action": "explain"}
        result = super().complete(**kwargs)
        if kwargs["stage"] == "refine" and kwargs["payload"]["instruction"] == PRICE:
            for segment in result["segments"]:
                segment.pop("evidence")
        if self.degrade and kwargs["stage"] == "review" and "本轮改写要求" in kwargs["payload"]["brief"]:
            for review in result["reviews"]:
                review.update(verdict="insufficient", used_evidence=[], reason="离线故障注入：本轮正文故意全部降级。")
        return result


class Bridge:
    base = "http://127.0.0.1:8000"

    def __init__(self, client):
        self.client = client

    def request(self, method, path, payload=None):
        response = self.client.request(method, path, json=payload)
        return {"status": response.status_code, "elapsed_seconds": 0.001, "body": response.json()}


@pytest.mark.parametrize("degrade", [False, True])
def test_price_only_recheck_preserves_old_evidence_and_rejects_all_placeholder_200(tmp_path, degrade):
    model = MissingCitationModel()
    client = TestClient(create_ai_app(tmp_path / "tool.sqlite3", model_factory=lambda: model))
    runner = Runner(Bridge(client), Path(__file__).resolve().parents[2], tmp_path / "evidence", live_required=False)
    runner.run_case("normal")
    before = copy.deepcopy(runner.manifest["cases"]["normal"])
    old_files = {p.name: p.read_bytes() for p in runner.directory.iterdir() if p.name not in {"manifest.json", "REPORT.md"}}
    model.degrade = degrade
    runner.recheck_price()
    case = runner.manifest["cases"]["missing_price_recheck_1"]
    assert case["status"] == ("failed" if degrade else "automatic-checks-completed")
    assert runner.manifest["cases"]["normal"] == before
    assert all((runner.directory / name).read_bytes() == content for name, content in old_files.items())
    steps = [s for s in runner.manifest["steps"] if s["name"].startswith("missing_price_recheck_1")]
    assert next(s for s in steps if s["name"].endswith("force-price"))["http_status"] == 200
    assert any(s["method"] == "PUT" for s in steps) is (not degrade)
    check = next(c for c in runner.manifest["checks"] if c["name"] == "missing_price_recheck_1.retained-backed-facts")
    assert check["result"] == ("fail" if degrade else "pass")
