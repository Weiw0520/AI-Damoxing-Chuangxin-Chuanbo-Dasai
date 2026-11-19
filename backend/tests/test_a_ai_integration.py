"""Offline integration proof only: fixtures/faults are never live AI acceptance."""
import json
from pathlib import Path
import time

from fastapi.testclient import TestClient
import pytest

from backend.a_ai_main import create_ai_app
from backend.a_compat.ai import parse_material
from backend.a_main import create_a_app
from backend.a_seed import manual_test_draft
from backend.heritage_ai.errors import GenerationError
from backend.heritage_ai.fixtures import FixtureModel

EXAMPLES = Path(__file__).resolve().parents[2] / "examples/b_generator"


def request(price=False):
    body = json.loads((EXAMPLES / ("03_request_missing_price.json" if price else "02_request_normal.json")).read_text(encoding="utf-8"))
    material = "\n\n".join(f"资料{i + 1}\n{s['text']}\n来源：{s['title']}\n链接：{s['url']}" for i, s in enumerate(body["sources"]))
    return {"material": material, "requirement": body["brief"], "platform": "xiaohongshu", "case_id": None}


@pytest.mark.parametrize("price", [False, True])
def test_replay_create_edit_export_and_restart(tmp_path, price):
    models = []
    def factory():
        model = FixtureModel(EXAMPLES / "fixtures" / ("missing_price.json" if price else "normal.json"))
        models.append(model)
        return model
    db = tmp_path / "ai.sqlite3"
    app = create_ai_app(db, model_factory=factory)
    client = TestClient(app)
    payload = request(price)
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["mode"] == "mock" and "模拟联调" in draft["notice"]["text"]
    assert draft["input"] == payload and draft["version"] == 1
    assert len(draft["sources"]) == 2 and draft["sources"][0]["origin_id"].startswith("src_")
    source_map = {s["id"]: s["snippet"] for s in draft["sources"]}
    for seg in draft["segments"][:2]:
        assert seg["claims"][0]["status"] == "verified"
        for quote in seg["claims"][0]["quotes"]:
            assert quote["quote"] in source_map[quote["source_id"]]
    if price:
        assert len(draft["segments"]) == 3
        pending = draft["segments"][-1]
        assert "门票" in pending["text"] and pending["claims"][0]["status"] == "needs_check"
        assert pending["claims"][0]["quotes"] == []
    url = "/api/drafts/" + draft["draft_id"]
    edits = [{"id": s["id"], "text": s["text"]} for s in draft["segments"]]
    edits[1]["text"] = "人工修改后的资料宣传文案，发布前请复核。"
    saved = client.put(url, json={"base_version": 1, "segments": edits, "history": draft["history"]})
    assert saved.status_code == 200 and saved.json()["changed_segments"] == [edits[1]["id"]]
    current = client.get(url).json()
    assert current["segments"][0] == draft["segments"][0]
    assert current["segments"][1]["claims"][0]["quotes"] == []
    assert current["history"][-1]["before"] == draft["segments"][1]
    exported = client.post(url + "/export", json={"format": "txt"}).json()
    assert edits[1]["text"] in exported["content"] and draft["segments"][1]["text"] not in exported["content"]
    assert "人工修改后待复核" in exported["content"]
    assert TestClient(create_ai_app(db, model_factory=factory)).get(url).json() == current
    assert len(models) == 1 and models[0].calls == ["generate", "review"]


def test_missing_configuration_never_saves(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    client = TestClient(create_ai_app(tmp_path / "no-config.sqlite3"))
    response = client.post("/api/generate", json=request())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "AI_NOT_CONFIGURED"
    assert client.get("/api/drafts").json() == []


@pytest.mark.parametrize("stage", ["generate", "review"])
def test_model_failure_is_safe_and_atomic(tmp_path, stage):
    class Failure(FixtureModel):
        def complete(self, **kwargs):
            if kwargs["stage"] == stage:
                raise GenerationError("provider-sensitive-test-marker")
            return super().complete(**kwargs)
    app = create_ai_app(tmp_path / "failure.sqlite3", model_factory=lambda: Failure(EXAMPLES / "fixtures/normal.json"))
    original = manual_test_draft("EXISTING")
    app.state.store.insert_manual(original)
    client = TestClient(app)
    response = client.post("/api/generate", json=request())
    assert response.status_code == 502 and "provider-sensitive-test-marker" not in response.text
    assert len(client.get("/api/drafts").json()) == 1
    assert client.get("/api/drafts/EXISTING").json() == original


def test_timeout_does_not_save_late_worker(tmp_path):
    def late_worker(payload, deadline):
        time.sleep(.12)
        return manual_test_draft("LATE-WORKER")
    app = create_a_app(tmp_path / "timeout.sqlite3", draft_generator=late_worker, generation_timeout=.025)
    client = TestClient(app)
    response = client.post("/api/generate", json=request())
    assert response.status_code == 504 and response.json()["detail"]["code"] == "AI_TIMEOUT"
    time.sleep(.15)
    assert client.get("/api/drafts").json() == []


def test_invalid_input_and_source_metadata(tmp_path):
    assert parse_material("资料一\n原文甲\n来源：标题甲\n链接：https://example.test/a\n\n资料二：原文乙")[0] == {
        "title": "标题甲", "text": "原文甲", "url": "https://example.test/a"}
    assert parse_material("没有显式分段的原始资料")[0]["text"] == "没有显式分段的原始资料"
    client = TestClient(create_ai_app(tmp_path / "invalid.sqlite3"))
    payload = request()
    for material in ("", "资料一\n来源：只有标题", "资料一\n正文\n链接：not-a-url"):
        payload["material"] = material
        assert client.post("/api/generate", json=payload).status_code == 422
    assert client.get("/api/drafts").json() == []


def test_original_entry_stays_501(tmp_path):
    client = TestClient(create_a_app(tmp_path / "original.sqlite3"))
    assert client.post("/api/generate", json=request()).status_code == 501
    assert "501" in client.get("/openapi.json").json()["paths"]["/api/generate"]["post"]["responses"]


def test_identical_sources_have_unique_aliases(tmp_path):
    class EchoReplay:
        mode = "fixture"
        label = verify_label = "test-only-not-live"
        def complete(self, *, stage, system, payload):
            if stage == "generate":
                source = payload["sources"][0]
                return {"segments": [{"id": "P1", "text": source["text"], "evidence": [
                    {"source_id": source["id"], "quote": source["text"]}]}]}
            segment = payload["segments"][0]
            return {"reviews": [{"segment_id": "P1", "text": segment["text"], "verdict": "supported",
                                 "reason": "逐字复述测试原文。", "used_evidence": [0]}]}
    payload = request()
    payload["material"] = "资料一\n山东省潍坊市杨家埠的一种民间版画\n来源：相同标题\n\n资料二\n山东省潍坊市杨家埠的一种民间版画\n来源：相同标题"
    client = TestClient(create_ai_app(tmp_path / "duplicates.sqlite3", model_factory=EchoReplay))
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    draft = response.json()
    assert len(draft["sources"]) == 1 and draft["sources"][0]["id"] == "S1"
    assert draft["segments"][0]["claims"][0]["cite_ids"] == ["S1"]
    assert draft["input"]["material"] == payload["material"]
