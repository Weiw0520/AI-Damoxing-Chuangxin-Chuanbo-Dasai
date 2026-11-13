from fastapi.testclient import TestClient

from backend.main import create_app


PAYLOAD = {
    "sources": [{"title": "山东非遗资料", "text": "潍坊风筝历史悠久，具有鲜明的地方特色。", "url": "https://example.com/source"}],
    "brief": "介绍山东非遗体验，吸引游客", "platform": "小红书",
}


def test_chinese_edit_export_restart(tmp_path):
    db = tmp_path / "drafts.sqlite3"
    client = TestClient(create_app(db))
    response = client.post("/api/drafts", json=PAYLOAD)
    assert response.status_code == 201
    draft = response.json()
    assert draft["mode"] == "mock"
    block, other = draft["blocks"]
    assert block["evidence"][0]["quote"] in PAYLOAD["sources"][0]["text"]
    assert other["status"] == "needs_review"
    # Change the unsupported paragraph: the unchanged supported paragraph must keep evidence.
    replacement = "来山东，感受非遗匠心；具体体验安排请提前核实。"
    url = f"/api/drafts/{draft['draftId']}"
    saved = client.patch(url, json={"edits": [{"blockId": other["blockId"], "text": replacement}]}).json()
    assert saved["blocks"][0] == block
    assert saved["blocks"][1]["status"] == "edited_needs_review"
    assert saved["blocks"][1]["evidence"] == []
    assert saved["history"][0]["before"] == other
    assert saved["history"][0]["after"]["text"] == replacement
    assert saved["history"][0]["editedAt"]
    exported = client.get(url + "/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    text = exported.content.decode("utf-8")
    assert replacement in text and other["text"] not in text
    assert "人工修改后待复核" in text
    assert text.index(block["text"]) < text.index(replacement)
    restarted = TestClient(create_app(db))
    assert restarted.get(url).json() == saved
    assert restarted.get(url + "/export").content == exported.content


def test_atomic_changes_history_and_noop(tmp_path):
    client = TestClient(create_app(tmp_path / "test.sqlite3"))
    draft = client.post("/api/drafts", json=PAYLOAD).json()
    url = f"/api/drafts/{draft['draftId']}"
    block = draft["blocks"][0]
    assert client.patch(url, json={"edits": [{"blockId": block["blockId"], "text": block["text"]}]}).json() == draft
    edits = [{"blockId": block["blockId"], "text": "修改后的中文内容"}]
    assert client.patch(url, json={"edits": edits + [{"blockId": "missing", "text": "不存在"}]}).status_code == 404
    assert client.get(url).json() == draft
    assert client.patch(url, json={"edits": edits * 2}).status_code == 422
    saved = client.patch(url, json={"edits": edits}).json()
    assert saved["blocks"][0]["evidence"] == []
    assert saved["history"][0]["before"]["evidence"] == block["evidence"]
    assert saved["blocks"][1] == draft["blocks"][1]
    again = client.post("/api/drafts", json=PAYLOAD).json()
    assert again["sources"] == draft["sources"]


def test_errors(tmp_path):
    client = TestClient(create_app(tmp_path / "test.sqlite3"))
    for body in [{}, dict(PAYLOAD, sources=[]), dict(PAYLOAD, brief="  "),
                 dict(PAYLOAD, platform=""), dict(PAYLOAD, sources=[{"title": "标题", "text": " "}])]:
        assert client.post("/api/drafts", json=body).status_code == 422
    for suffix in ["", "/export"]:
        response = client.get("/api/drafts/missing" + suffix)
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "draft_not_found"
    assert client.patch("/api/drafts/missing", json={"edits": [{"blockId": "b", "text": "中文"}]}).status_code == 404


def test_cors_and_generator_injection(tmp_path):
    from backend.generator import Block, Evidence, Generation
    calls = []

    def replacement(sources, brief, platform):
        calls.append((sources, brief, platform))
        return Generation(mode="mock", blocks=[
            Block(blockId="b_custom", text="替换生成器验收：一线牵起齐鲁非遗之旅。",
                  status="supported",
                  evidence=[Evidence(sourceId=sources[0].sourceId, quote="潍坊风筝历史悠久")],
                  reviewReason="仅用于注入验收的原文引文，未进行真实 AI 核验。"),
            Block(blockId="b_uncertain", text="替换生成器验收：体验活动需进一步确认。",
                  status="needs_review", evidence=[], reviewReason="缺少活动资料。"),
        ])

    client = TestClient(create_app(tmp_path / "test.sqlite3", generator=replacement))
    response = client.post("/api/drafts", json=PAYLOAD)
    assert response.status_code == 201
    draft = response.json()
    assert draft["blocks"][0]["text"] == "替换生成器验收：一线牵起齐鲁非遗之旅。"
    assert draft["blocks"][0]["evidence"][0]["quote"] in PAYLOAD["sources"][0]["text"]
    url = f"/api/drafts/{draft['draftId']}"
    assert client.get(url).json() == draft
    new_text = "人工改写验收：循着风筝，发现山东非遗之美。"
    response = client.patch(url, json={"edits": [{"blockId": "b_custom", "text": new_text}]})
    assert response.status_code == 200
    saved = response.json()
    assert saved.keys() == draft.keys()
    assert saved["blocks"][0].keys() == draft["blocks"][0].keys()
    assert saved["blocks"][0]["status"] == "edited_needs_review"
    assert saved["blocks"][0]["evidence"] == []
    assert saved["history"][0]["before"] == draft["blocks"][0]
    assert saved["blocks"][1] == draft["blocks"][1]
    exported = client.get(url + "/export")
    assert exported.status_code == 200
    assert new_text in exported.text and draft["blocks"][0]["text"] not in exported.text
    assert "人工修改后待复核" in exported.text
    assert client.get(url).json() == saved
    assert len(calls) == 1  # Reading, editing, and exporting must never regenerate.
    assert calls[0][0][0].sourceId.startswith("src_")
    assert calls[0][1:] == (PAYLOAD["brief"], PAYLOAD["platform"])
    response = client.options("/api/drafts", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PATCH"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
