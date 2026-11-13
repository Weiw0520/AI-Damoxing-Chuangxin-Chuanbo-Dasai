"""Keep A's copyable JSON examples and TXT schema aligned with real endpoints."""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import Draft, create_app


ROOT = Path(__file__).resolve().parents[2]


def test_documented_examples(tmp_path):
    contract = (ROOT / "docs/API_CONTRACT.md").read_text(encoding="utf-8")
    examples = [json.loads(s) for s in re.findall(r"```json\n(.*?)\n```", contract, re.S)]
    payload, edits, changed_block, missing_draft, missing_block, duplicate, empty, invalid = examples
    sample = json.loads((ROOT / "docs/example-draft.json").read_text(encoding="utf-8"))
    Draft.model_validate(sample)
    client = TestClient(create_app(tmp_path / "contract.sqlite3"))
    response = client.post("/api/drafts", json=payload)
    assert response.status_code == 201
    draft = response.json()
    dynamic = {"draftId", "createdAt", "updatedAt"}
    assert {k: v for k, v in draft.items() if k not in dynamic} == {k: v for k, v in sample.items() if k not in dynamic}
    url = f"/api/drafts/{draft['draftId']}"
    saved = client.patch(url, json=edits)
    assert saved.status_code == 200
    assert saved.json()["blocks"][0] == changed_block
    for method, suffix, kwargs in [("get", "", {}), ("get", "/export", {}), ("patch", "", {"json": edits})]:
        response = getattr(client, method)("/api/drafts/missing" + suffix, **kwargs)
        assert response.status_code == 404
        assert response.json() == missing_draft
    response = client.patch(url, json={"edits": [{"blockId": "missing", "text": "文案"}]})
    assert response.status_code == 404 and response.json() == missing_block
    response = client.patch(url, json={"edits": edits["edits"] * 2})
    assert response.status_code == 422 and response.json() == duplicate
    response = client.post("/api/drafts", json=dict(payload, sources=[]))
    assert response.status_code == 422 and response.json() == empty

    def bad_generator(sources, brief, platform):
        return {"mode": "mock", "blocks": [dict(changed_block, status="supported", evidence=[
            {"sourceId": sources[0].sourceId, "quote": "资料里没有的引文"}
        ])]}

    bad_client = TestClient(create_app(tmp_path / "bad.sqlite3", generator=bad_generator))
    response = bad_client.post("/api/drafts", json=payload)
    assert response.status_code == 502 and response.json() == invalid
    response = client.get(url + "/export", headers={"Origin": "http://localhost:5173"})
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["content-disposition"] == f'attachment; filename="{draft["draftId"]}.txt"'
    assert response.headers["access-control-expose-headers"] == "Content-Disposition"
    assert not response.content.startswith(b"\xef\xbb\xbf")
    schema = client.get("/openapi.json").json()
    export_schema = schema["paths"]["/api/drafts/{draft_id}/export"]["get"]["responses"]["200"]["content"]
    assert set(export_schema) == {"text/plain"}
