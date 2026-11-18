import io
import sqlite3
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from backend.a_main import create_a_app
from backend.a_seed import manual_test_draft


@pytest.fixture
def setup(tmp_path):
    db = tmp_path / "shared.sqlite3"
    app = create_a_app(db)
    draft = manual_test_draft("A-MANUAL-TEST")
    app.state.store.insert_manual(draft)
    return TestClient(app), app.state.store, draft, db


def edit_payload(draft, text="人工修改后的中文资料，请发布前复核。"):
    segments = [{"id": s["id"], "text": s["text"]} for s in draft["segments"]]
    segments[-1]["text"] = text
    return {"base_version": draft["version"], "segments": segments, "history": draft["history"],
            "edit_log": [{"segment_id": "s3", "before": "不可信客户端旧文本", "after": "不可信客户端新文本"}]}


def test_a_read_edit_export_and_restart(setup):
    client, store, original, db = setup
    url = "/api/drafts/" + original["draft_id"]
    cases = client.get("/api/cases")
    assert cases.status_code == 200 and len(cases.json()) == 3
    assert all("result" not in c and c["material"] and c["requirement"] for c in cases.json())
    listing = client.get("/api/drafts").json()
    assert listing[0]["draft_id"] == original["draft_id"] and listing[0]["version"] == 1
    assert listing[0]["stats"]["needs_check"] == 2
    assert client.get(url).json() == original
    response = client.put(url, json=edit_payload(original))
    assert response.status_code == 200
    assert response.json()["version"] == 2 and response.json()["changed_segments"] == ["s3"]
    saved = client.get(url).json()
    assert saved["segments"][1] == original["segments"][1]
    assert saved["segments"][-1]["claims"][0]["quotes"] == []
    assert saved["segments"][-1]["claims"][0]["status"] == "needs_check"
    assert saved["history"][-1]["before"] == original["segments"][-1]
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM a_revisions").fetchone()[0] == 1
    for fmt in ("txt", "md", "report"):
        exported = client.post(url + "/export", json={"format": fmt, "history": saved["history"]})
        assert exported.status_code == 200
        body = exported.json()
        assert body["draft_id"] == original["draft_id"] and body["version"] == 2
        assert "人工" in body["content"] and "AI" in body["content"]
        if fmt == "txt":
            assert saved["segments"][-1]["text"] in body["content"]
            assert original["segments"][-1]["text"] not in body["content"]
            assert "人工修改后待复核" in body["content"]
            assert "【待核验】" in body["content"]
    assert client.get(url).json() == saved  # Export does not write client history into DB.
    assert TestClient(create_a_app(db)).get(url).json() == saved


def test_atomic_validation_versions_and_append_only_history(setup):
    client, store, original, db = setup
    url = "/api/drafts/" + original["draft_id"]
    bad = edit_payload(original)
    bad["segments"].append({"id": "missing", "text": "不存在"})
    assert client.put(url, json=bad).status_code == 404
    assert client.get(url).json() == original
    bad["segments"][-1]["id"] = "s3"
    assert client.put(url, json=bad).status_code == 422
    missing = edit_payload(original)
    missing["segments"].pop()
    assert client.put(url, json=missing).status_code == 422
    payload = edit_payload(original)
    payload["history"] = []
    assert client.put(url, json=payload).status_code == 200
    saved = client.get(url).json()
    assert saved["history"][0] == original["history"][0]
    assert client.put(url, json=payload).status_code == 409
    assert client.get(url).json() == saved
    assert client.put(url, json={}).json()["detail"]["code"] == "INVALID_INPUT"
    assert client.get("/api/drafts/missing").status_code == 404
    assert client.post(url + "/export", json={"format": "pdf"}).status_code == 422
    with pytest.raises(Exception) as error:
        store.insert_manual(original)
    assert error.value.status_code == 409


def test_ai_501_never_saves_or_overwrites(setup):
    client, store, draft, db = setup
    before = store.get(draft["draft_id"])
    generated = client.post("/api/generate", json={"material": "中文资料", "requirement": "写文案", "platform": "xiaohongshu", "case_id": None})
    refined = client.post(f"/api/drafts/{draft['draft_id']}/refine", json={
        "instruction": "删掉一段", "base_version": 1,
        "segments": [{"id": s["id"], "text": s["text"]} for s in draft["segments"]], "history": draft["history"],
    })
    for response in (generated, refined):
        assert response.status_code == 501
        assert response.json()["detail"]["code"] == "AI_NOT_IMPLEMENTED"
        assert "AI 功能暂未接入" in response.json()["detail"]["message"]
    assert len(client.get("/api/drafts").json()) == 1
    assert store.get(draft["draft_id"]) == before
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM a_revisions").fetchone()[0] == 0


@pytest.mark.parametrize("filename,raw,expected", [
    ("资料.txt", "中文资料".encode(), "中文资料"),
    ("资料.md", "中文资料".encode("gb18030"), "中文资料"),
    ("资料.csv", "中文资料".encode("utf-16"), "中文资料"),
    ("资料.html", '<p>中文资料</p><script>坏内容</script>'.encode(), "中文资料"),
])
def test_extract_text_formats(setup, filename, raw, expected):
    client = setup[0]
    response = client.post("/api/extract", params={"filename": filename}, content=raw)
    assert response.status_code == 200
    assert response.json()["text"] == expected and not response.json()["truncated"]


def test_extract_limits_docx_and_invalid_files(setup):
    client = setup[0]
    for filename, data, status in [("a.txt", b"", 422), ("a.pdf", b"pdf", 415),
                                    ("a.docx", b"bad zip", 422), ("a.txt", b"x" * (5 * 1024 * 1024 + 1), 413)]:
        response = client.post("/api/extract", params={"filename": filename}, content=data)
        assert response.status_code == status and response.json()["detail"]["message"]
    response = client.post("/api/extract?filename=a.txt", content=("字" * 20001).encode())
    assert response.json()["truncated"] and response.json()["chars"] == 20000
    buf = io.BytesIO()
    with ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>中文文档</w:t></w:r></w:p></w:body></w:document>')
    assert client.post("/api/extract?filename=test.docx", content=buf.getvalue()).json()["text"] == "中文文档"


def test_existing_c_drafts_remain_readable_and_unchanged(tmp_path):
    from backend.main import create_app
    db = tmp_path / "both.sqlite3"
    c = TestClient(create_app(db))
    original = c.post("/api/drafts", json={"sources": [{"title": "原 C 资料", "text": "原 C 中文原文"}], "brief": "宣传", "platform": "小红书"}).json()
    url = f"/api/drafts/{original['draftId']}"
    a = TestClient(create_a_app(db))
    a.app.state.store.insert_manual(manual_test_draft())
    assert a.post("/api/generate", json={"material": "x", "requirement": "y", "platform": "z"}).status_code == 501
    assert c.get(url).json() == original
    assert c.get(url + "/export").status_code == 200
    assert a.get("/api/drafts").json()[0]["draft_id"].startswith("A-MANUAL-")
