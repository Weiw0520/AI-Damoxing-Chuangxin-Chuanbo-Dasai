"""Guard the browser evidence criteria without pretending to run a real browser."""
import copy
from pathlib import Path

import pytest

from scripts.run_b_refine_web_acceptance import CheckFailed, WebRunner, check_download, save, validate_p2


def draft():
    s1 = "山东省潍坊市杨家埠的一种民间版画"
    s2 = "杨家埠木版年画分钩描、刻版、印刷3道工序"
    def segment(sid, text, quotes):
        return {"id": sid, "text": text, "claims": [{"status": "verified", "quotes": quotes,
            "cite_ids": [q["source_id"] for q in quotes]}]}
    q1, q2 = {"source_id": "S1", "quote": s1}, {"source_id": "S2", "quote": s2}
    return {"mode": "real", "data_origin": "ai", "ai_meta": {"mode": "live"},
        "sources": [{"id": "S1", "snippet": s1}, {"id": "S2", "snippet": s2}],
        "segments": [segment("P1", s1, [q1]), segment("P2", s2 + "，一起认识这门民间版画。", [q1, q2]),
            {"id": "pending_0", "text": "门票价格：资料不足，待核验。", "claims": [{"status": "needs_check", "quotes": []}]}]}


def test_category_needs_its_own_paragraph_quote_even_if_cited_earlier():
    value = draft()
    assert validate_p2(value)["id"] == "P2"
    claim = value["segments"][1]["claims"][0]
    claim["quotes"] = claim["quotes"][1:]
    claim["cite_ids"] = ["S2"]
    with pytest.raises(CheckFailed, match="类别引文"):
        validate_p2(value)


@pytest.mark.parametrize("kind", ["mock", "fake_quote", "invented_price"])
def test_unsafe_or_nonlive_results_are_not_browser_acceptance(kind):
    value = draft()
    if kind == "mock":
        value["mode"] = "mock"
    elif kind == "fake_quote":
        value["segments"][1]["claims"][0]["quotes"][0]["quote"] = "并不存在的引用"
    else:
        value["segments"][0]["text"] += "门票30元。"
    with pytest.raises(CheckFailed):
        validate_p2(value)


def test_actual_download_preserves_bom_and_rejects_fallback_content(tmp_path):
    target = tmp_path / "download.txt"
    target.write_bytes(b"\xef\xbb\xbf" + "最新版文案".encode())
    proof = check_download(target, {"content": "最新版文案"})
    assert proof["utf8_bom"] and proof["matches_export_content"]
    with pytest.raises(CheckFailed):
        check_download(target, {"content": "旧版或本地兜底内容"})


def test_restart_compares_latest_web_snapshots_and_clears_stale_pass(tmp_path):
    expected = {"version": 5, "segments": [{"text": "网页修改后的最新句子"}]}
    class Client:
        base = "http://127.0.0.1:8000"
        changed = False
        def request(self, method, path):
            assert method == "GET"
            return {"status": 200, "elapsed_seconds": .001, "body": {"version": 4} if self.changed else copy.deepcopy(expected)}
    client = Client()
    runner = WebRunner(Path(__file__).resolve().parents[2], tmp_path, client, "http://127.0.0.1:5173")
    runner.manifest["status"] = "browser-checks-completed"
    for name in ["price", "normal"]:
        save(tmp_path / (name + ".json"), expected)
        runner.manifest["snapshots"][name] = {"draft_id": name, "file": name + ".json"}
    runner.verify_restart()
    assert runner.manifest["restart_read"] == "passed"
    client.changed = True
    with pytest.raises(CheckFailed):
        runner.verify_restart()
    assert runner.manifest["restart_read"] == "failed"


@pytest.mark.parametrize("end,expected", [(123.4, .1234), (-1, None)])
def test_full_response_body_is_read_without_creating_finished_listener(tmp_path, end, expected):
    class Request:
        method = "POST"
        post_data = '{"instruction":"测试"}'
        post_data_json = {"instruction": "测试"}
        body_read = False
        @property
        def timing(self):
            assert self.body_read, "Read response body before consulting final network timing"
            return {"responseEnd": end}
    class Response:
        request = Request()
        status = 200
        url = "http://127.0.0.1:5173/api/drafts/A-test/refine"
        def finished(self):
            raise AssertionError("Do not invoke the method that leaves target-close tasks")
        def json(self):
            self.request.body_read = True
            return {"version": 4}
    class Client:
        base = "http://127.0.0.1:8000"
    runner = WebRunner(Path(__file__).resolve().parents[2], tmp_path, Client(), "http://127.0.0.1:5173")
    body, filename = runner.response("price.refine", Response())
    assert body == {"version": 4} and (tmp_path / filename).exists()
    assert runner.manifest["steps"][-1]["elapsed_seconds"] == expected
