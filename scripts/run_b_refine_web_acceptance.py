"""Real local-browser acceptance; never reads a model key or replaces UI writes with API calls."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

try:
    from run_b_refine_acceptance import Client, git_info
except ImportError:
    from scripts.run_b_refine_acceptance import Client, git_info

INSTRUCTION = (
    "请执行改写并重新核验，保留当前正文和‘门票价格：资料不足，待核验。’提示，不新增事实。"
    "请补齐第二段的引文：‘民间版画’引用资料一中的‘山东省潍坊市杨家埠的一种民间版画’；"
    "制作工序引用资料二中的‘杨家埠木版年画分钩描、刻版、印刷3道工序’。"
    "本轮必须返回完整正文并重新核验，不是仅解释现有依据。"
)
ARCHIVE = "B_REFINE_WEB_ACCEPTANCE_LATEST.zip"
TOOL_VERSION = "web-acceptance/0.1.1"


def now():
    return datetime.now(timezone.utc).isoformat()


class CheckFailed(Exception):
    pass


def require(ok, message):
    if not ok:
        raise CheckFailed(message)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_live(draft):
    require(draft.get("mode") == "real" and draft.get("data_origin") == "ai"
            and draft.get("ai_meta", {}).get("mode") == "live", "响应不是real/live，不能作为真实网页验收。")
    source_map = {s["id"]: s["snippet"] for s in draft["sources"]}
    for segment in draft["segments"]:
        for claim in segment.get("claims", []):
            if claim.get("status") == "verified":
                quotes = claim.get("quotes", [])
                require(bool(quotes), "verified缺少引文。")
                require(set(claim.get("cite_ids", [])) == {q["source_id"] for q in quotes}, "来源编号和引文列表不一致。")
                require(all(q["source_id"] in source_map and q["quote"] and q["quote"] in source_map[q["source_id"]]
                            for q in quotes), "引文不在对应的提交资料正文内。")
    body = "\n".join(s["text"] for s in draft["segments"])
    require(not re.search(r"30\s*元|三十\s*元|３０\s*元|免费入园|免费入场|免票", body), "出现无依据票价或免费断言。")
    notices = [s for s in draft["segments"] if s["text"] == "门票价格：资料不足，待核验。"]
    require(bool(notices) and all(s.get("claims") and all(c["status"] == "needs_check" and not c.get("quotes") and not c.get("cite_ids")
                                for c in s["claims"]) for s in notices), "门票待核验提示缺失或状态错误。")


def validate_p2(draft):
    validate_live(draft)
    segment = next((s for s in draft["segments"] if s["id"] == "P2"), None)
    require(segment is not None, "第二段P2已被删除，需要人工核对。")
    claims = segment.get("claims", [])
    require(bool(claims) and all(c["status"] == "verified" for c in claims), "第二段尚未完成有据核验。")
    quotes = [q for c in claims for q in c.get("quotes", [])]
    require(all(term in segment["text"] for term in ["钩描", "刻版", "印刷"])
            and re.search(r"(?:3|三)道工序", segment["text"]), "第二段丢失制作工序。")
    require(any(all(t in q["quote"] for t in ["钩描", "刻版", "印刷", "3道工序"]) for q in quotes), "第二段工序引文不完整。")
    if "民间版画" in segment["text"]:
        require(any("民间版画" in q["quote"] for q in quotes), "第二段仍写民间版画，但没有补齐类别引文。")
    first = next((s for s in draft["segments"] if s["id"] == "P1"), {})
    require(all(t in first.get("text", "") for t in ["山东", "潍坊", "杨家埠", "民间版画"]), "第一段丢失地点或类别介绍。")
    return segment


def check_download(path, exported):
    raw = path.read_bytes()
    # A's browser downloader intentionally prefixes UTF-8 BOM; retain original bytes.
    require(raw.decode("utf-8-sig") == exported["content"], "浏览器实际TXT与服务端export.content不一致，不能算下载通过。")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "utf8_bom": raw.startswith(b"\xef\xbb\xbf"),
            "matches_export_content": True}


class WebRunner:
    def __init__(self, root, directory, client, url, manifest=None):
        self.root, self.directory, self.client, self.url = root, directory, client, url
        directory.mkdir(parents=True, exist_ok=True)
        self.stage = "initializing"
        self.manifest = manifest or {"started_at": now(), "execution_mode": "live-required-browser",
            "tool_version": TOOL_VERSION,
            "frontend_url": url, "backend_base": client.base, "code": git_info(root),
            "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "steps": [], "checks": [], "snapshots": {}, "downloads": {}, "status": "running",
            "semantic_review": "待审阅全部JSON与截图；确定性检查不替代整段语义复核。",
            "restart_read": "pending", "provider_logs": "未采集，不以mode单独证明提供方调用。",
            "scope": "仅操作原验收记录中的普通、新票价两份草稿；只发一次网页AI追问，人工保存也通过页面。"}

    def record(self, name, method, path, status, elapsed, data, payload=None):
        suffix, index = name, 2
        while (self.directory / (suffix + ".response.json")).exists():
            suffix, index = name + "." + str(index), index + 1
        save(self.directory / (suffix + ".response.json"), data)
        step = {"name": suffix, "method": method, "path": path, "http_status": status,
                "elapsed_seconds": elapsed, "time": now(), "response_file": suffix + ".response.json"}
        if payload is not None:
            save(self.directory / (suffix + ".request.json"), payload)
            step["request_file"] = suffix + ".request.json"
        self.manifest["steps"].append(step)
        save(self.directory / "manifest.json", self.manifest)
        require(status == 200 and isinstance(data, dict), name + "没有得到200 JSON，已保存现有结果。")
        return data, step["response_file"]

    def api_get(self, name, draft_id):
        path = "/api/drafts/" + draft_id
        result = self.client.request("GET", path)
        return self.record(name, "GET", path, result["status"], result["elapsed_seconds"], result["body"])

    def response(self, name, response):
        request = response.request
        try:
            # json() waits for the complete response body. In Playwright 1.62,
            # finished() can leave an unobserved target-close task per response;
            # do not create that extra lifecycle listener just to read JSON.
            body = response.json()
        except Exception:
            body = {"local_error": "页面请求没有返回JSON。"}
        end = request.timing.get("responseEnd", -1)
        elapsed = round(end / 1000, 4) if end >= 0 else None
        payload = request.post_data_json if request.post_data else None
        return self.record(name, request.method, urlsplit(response.url).path, response.status, elapsed, body, payload)

    def match(self, draft_id, method="GET", suffix=""):
        expected = "/api/drafts/" + draft_id + suffix
        origin = urlsplit(self.url).netloc
        return lambda r: r.request.method == method and urlsplit(r.url).netloc == origin and urlsplit(r.url).path == expected

    def open_draft(self, page, draft_id, name):
        self.stage = name
        with page.expect_response(lambda r: r.request.method == "GET" and urlsplit(r.url).path == "/api/drafts", timeout=20000) as listed:
            page.goto(self.url, wait_until="domcontentloaded")
        response = listed.value
        require(response.status == 200, "网页草稿列表未成功加载。")
        drafts = response.json()
        # Read list order to choose the actual UI button. Do not save unrelated draft data.
        index = next((i for i, d in enumerate(drafts) if d["draft_id"] == draft_id), None)
        require(index is not None, "网页列表找不到本次验收草稿，请确认同一后端和数据库。")
        require("真实后端模式" in page.locator(".mode-pill").inner_text(), "网页处于示例模式，已停止真实验收。")
        with page.expect_response(self.match(draft_id), timeout=20000) as opened:
            page.locator("button.conv-item:not(.is-new)").nth(index).click()
        data, filename = self.response(name, opened.value)
        page.locator(".draft-card").wait_for(state="visible")
        require(draft_id in page.locator(".draft-chip").inner_text(), "网页打开的草稿编号不符。")
        return data, filename

    def screenshot(self, locator, name):
        filename = name + ".png"
        locator.screenshot(path=str(self.directory / filename), animations="disabled")
        self.manifest.setdefault("screenshots", []).append(filename)

    def show_report(self, page):
        page.locator(".draft-card .tabs").get_by_role("button", name=re.compile(r"^核验报告")).click()

    def download(self, page, name, draft):
        self.stage = name + ".browser-download"
        page.locator(".col-right .file-item").filter(has_text="文案正文").click()
        with page.expect_download(timeout=20000) as pending_download:
            with page.expect_response(self.match(draft["draft_id"], "POST", "/export"), timeout=20000) as pending_export:
                page.locator(".col-right .fview-bar").get_by_role("button", name="下载", exact=True).click()
            exported, _ = self.response(name + ".export", pending_export.value)
        download = pending_download.value
        filename = download.suggested_filename
        require(Path(filename).name == filename and filename == exported["filename"] and filename.endswith(".txt"), "浏览器文件名与服务端导出文件名不一致。")
        require(exported["draft_id"] == draft["draft_id"] and exported["version"] == draft["version"], "导出不是当前保存版本。")
        target = self.directory / "downloads" / filename
        target.parent.mkdir(exist_ok=True)
        download.save_as(target)
        proof = check_download(target, exported)
        self.manifest["downloads"][name] = {"file": "downloads/" + filename, "draft_id": draft["draft_id"],
                                             "version": draft["version"], **proof}
        self.screenshot(page.locator(".col-right"), name + ".download-view")

    def browser(self, page, price_id, normal_id, expected_price, expected_normal):
        before, _ = self.open_draft(page, price_id, "price.open")
        require(before == expected_price, "票价草稿已被其他操作修改，未自动重复模型追问。请提交结果包复核。")
        self.stage = "price.refine"
        page.locator("textarea.composer-input").fill(INSTRUCTION)
        with page.expect_response(self.match(price_id, "POST", "/refine"), timeout=65000) as pending:
            page.locator(".composer .send-btn").click()
        revised, _ = self.response("price.refine", pending.value)
        require(revised["version"] == before["version"] + 1 and revised["draft_id"] == price_id, "追问版本或草稿编号不符。")
        page.locator(".draft-card .dc-ver").filter(has_text=re.compile(r"^v" + str(revised["version"]) + r"$")).wait_for(state="visible")
        require(revised["ai_meta"].get("review_executed") is True, "本轮没有重新执行核验。")
        p2 = validate_p2(revised)
        self.manifest["refine_ai_meta"] = revised["ai_meta"]
        self.manifest["ai_text_changes"] = [{"id": s["id"], "after": s["text"],
            "before": next((x["text"] for x in before["segments"] if x["id"] == s["id"]), None)}
            for s in revised["segments"] if not any(x["id"] == s["id"] and x["text"] == s["text"] for x in before["segments"])]
        page.locator(".composer .send-btn").wait_for(state="visible")
        self.show_report(page)
        self.stage = "price.claim-drawer"
        page.locator(".check-item").filter(has_text="段落：" + p2["label"]).click()
        drawer = page.locator(".drawer")
        drawer.wait_for(state="visible")
        text = re.sub(r"\s+", "", drawer.inner_text())
        require("有据可查" in text and "民间版画" in text and "钩描" in text and "印刷" in text, "网页第二段依据未完整显示。")
        required_ids = {q["source_id"] for c in p2["claims"] for q in c["quotes"]}
        require(all(sid in text for sid in required_ids), "网页抽屉漏显示引用来源编号。")
        self.screenshot(drawer, "price.p2-evidence")
        for i in range(drawer.locator(".quote-box").count()):
            self.screenshot(drawer.locator(".quote-box").nth(i), "price.p2-quote-" + str(i + 1))
        drawer.get_by_role("button", name="关闭", exact=True).click()
        page.locator(".check-item").filter(has_text="门票价格：资料不足，待核验。").click()
        drawer.wait_for(state="visible")
        require("待核验" in drawer.inner_text() and "无（模型未给出处）" in drawer.inner_text(), "网页票价未显示待核验和无来源。")
        self.screenshot(drawer, "price.ticket-review")
        drawer.get_by_role("button", name="关闭", exact=True).click()
        self.stage = "price.manual-edit"
        first_index = next(i for i, s in enumerate(revised["segments"]) if s["id"] == "P1")
        first = revised["segments"][first_index]
        sentence = next((x for x in ["出发前，我会再次核实门票信息。", "计划出发前，我会再次确认门票信息。"] if x not in first["text"]), None)
        require(sentence is not None, "测试句已存在，未重复追加。")
        manual_text = first["text"] + sentence
        page.locator(".draft-card").get_by_role("button", name="在右栏编辑", exact=True).click()
        editor = page.locator(".col-right textarea.fe-input").nth(first_index)
        require(editor.input_value() == first["text"], "右栏编辑段落与当前正文不一致。")
        editor.fill(manual_text)
        with page.expect_response(self.match(price_id, "PUT"), timeout=20000) as pending_save:
            page.locator(".col-right .fview-foot").get_by_role("button", name="保存草稿", exact=True).click()
        receipt, _ = self.response("price.save", pending_save.value)
        require(receipt["version"] == revised["version"] + 1 and receipt["changed_segments"] == ["P1"], "人工保存版本或修改段落错误。")
        saved, snapshot = self.open_draft(page, price_id, "price.after-ui-save")
        validate_live(saved)
        validate_p2(saved)
        changed = next(s for s in saved["segments"] if s["id"] == "P1")
        require(changed["text"] == manual_text and changed.get("review_status") == "edited_needs_review"
                and all(c["status"] == "needs_check" and not c["quotes"] for c in changed["claims"]), "人工修改的新句或待复核状态未保存。")
        self.manifest["manual_edit"] = {"segment_id": "P1", "sentence": sentence, "version": saved["version"]}
        self.manifest["snapshots"]["price"] = {"draft_id": price_id, "file": snapshot, "version": saved["version"]}
        self.show_report(page)
        page.locator(".check-item").filter(has_text="段落：" + changed["label"]).click()
        self.screenshot(page.locator(".drawer"), "price.manual-needs-review")
        page.locator(".drawer").get_by_role("button", name="关闭", exact=True).click()
        self.download(page, "price", saved)
        normal, snapshot = self.open_draft(page, normal_id, "normal.open")
        require(normal == expected_normal, "普通案例已被其他操作修改，本次未覆盖。")
        require(normal.get("mode") == "real" and normal.get("data_origin") == "ai" and normal.get("ai_meta", {}).get("mode") == "live",
                "普通案例不是real/live，未把模拟数据算作真实验收。")
        self.manifest["snapshots"]["normal"] = {"draft_id": normal_id, "file": snapshot, "version": normal["version"]}
        self.download(page, "normal", normal)
        self.open_draft(page, price_id, "price.final-open")
        self.screenshot(page.locator(".draft-card"), "price.final-body")
        self.manifest["status"] = "browser-checks-completed"
        self.manifest["checks"].append({"name": "web-followup-evidence-manual-save-and-real-download", "result": "pass"})

    def verify_restart(self):
        self.stage = "restart-read"
        self.manifest["restart_read"] = "pending"
        try:
            require(self.manifest["status"] == "browser-checks-completed" and set(self.manifest["snapshots"]) == {"price", "normal"},
                    "网页流程或两份最终快照尚不完整，不能执行最终重启比较。")
            for name, snapshot in self.manifest["snapshots"].items():
                expected = json.loads((self.directory / snapshot["file"]).read_text(encoding="utf-8-sig"))
                actual, _ = self.api_get(name + ".after-restart", snapshot["draft_id"])
                require(actual == expected, name + "重启后与最新网页保存快照不一致。")
        except Exception:
            self.manifest["restart_read"] = "failed"
            raise
        self.manifest["restart_read"] = "passed"
        if self.manifest.get("error"):
            self.manifest.setdefault("previous_errors", []).append(self.manifest.pop("error"))
        self.manifest["restart_operator_note"] = "重启由操作者在原后端终端执行；脚本验证最新快照一致，不能独立证明重启动作。"

    def finish(self):
        self.manifest["finished_at"] = now()
        save(self.directory / "manifest.json", self.manifest)
        report = ["# B真实网页验收自动记录", "", "状态：" + self.manifest["status"],
            "重启读取：" + self.manifest["restart_read"], "", "实际浏览器操作与API直读在steps中分别记录。",
            "浏览器下载TXT原始字节保留，去除UTF-8 BOM后与服务端content逐字比较；不接受本地导出兜底冒充服务端导出。",
            "未收取模型密钥、认证头、环境变量或其他草稿内容。语义仍需审阅完整响应、文本变化与截图。", "",
            "| 步骤 | HTTP | 秒 |", "| --- | --- | --- |"]
        report += [f"| {s['name']} | {s['http_status']} | {s['elapsed_seconds'] if s['elapsed_seconds'] is not None else '未取得完整耗时'} |" for s in self.manifest["steps"]]
        if self.manifest.get("error"):
            report += ["", "未完成：" + self.manifest["error"]["message"]]
        (self.directory / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        archive = self.directory.parent / ARCHIVE
        with ZipFile(archive, "w", ZIP_DEFLATED) as z:
            for p in sorted(self.directory.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(self.directory))
        print("请上传结果包：" + str(archive.resolve()), flush=True)


def main():
    parser = argparse.ArgumentParser(description="B真实网页追问/保存/下载验收，Key只由已启动后端使用")
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--verify-restart", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    home = root / "data/b-refine-web-acceptance"
    home.mkdir(parents=True, exist_ok=True)
    pointer = home / "latest-run.json"
    runner = None
    try:
        Client(args.url)  # Reject external/non-loopback addresses and embedded credentials.
        client = Client(args.backend)
        if args.verify_restart:
            directory = Path(json.loads(pointer.read_text(encoding="utf-8"))["directory"])
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            require(client.base == manifest["backend_base"], "请使用相同后端地址和数据库。")
            runner = WebRunner(root, directory, client, args.url, manifest)
            runner.verify_restart()
            return 0
        directory = home / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        save(pointer, {"directory": str(directory.resolve())})
        runner = WebRunner(root, directory, client, args.url)
        runner.stage = "load-existing-acceptance"
        prior = json.loads((root / "data/b-refine-acceptance/latest-run.json").read_text(encoding="utf-8"))
        prior_dir = Path(prior["directory"])
        prior_manifest = json.loads((prior_dir / "manifest.json").read_text(encoding="utf-8"))
        price_case = prior_manifest["cases"][prior_manifest["current_price_case"]]
        normal_case = prior_manifest["cases"]["normal"]
        expected_price = json.loads((prior_dir / price_case["expected_snapshot"]).read_text(encoding="utf-8-sig"))
        expected_normal = json.loads((prior_dir / normal_case["expected_snapshot"]).read_text(encoding="utf-8-sig"))
        price_id, normal_id = price_case["draft_id"], normal_case["draft_id"]
        require(re.fullmatch(r"A-[0-9a-f]{32}", price_id) and re.fullmatch(r"A-[0-9a-f]{32}", normal_id), "验收草稿编号格式错误。")
        before, _ = runner.api_get("price.preflight", price_id)
        validate_live(before)
        require(before == expected_price, "草稿已变化，未自动重跑追问；请提交本次结果包供复核。")
        runner.stage = "launch-browser"
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise CheckFailed("缺少网页验收依赖，请使用run_b_refine_web_acceptance.cmd启动。") from None
        with sync_playwright() as p:
            browser = None
            for channel in ["msedge", "chrome"]:
                try:
                    browser = p.chromium.launch(channel=channel, headless=False)
                    runner.manifest["browser_channel"] = channel
                    break
                except Exception:
                    continue
            require(browser is not None, "无法启动本机Edge或Chrome；未自动安装浏览器或继续调用模型。")
            runner.manifest.update(browser_version=browser.version, playwright_version=importlib.metadata.version("playwright"))
            context = browser.new_context(viewport={"width": 1600, "height": 1100}, accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(20000)
            try:
                runner.browser(page, price_id, normal_id, expected_price, expected_normal)
                runner.finish()  # Persist UI evidence before waiting for an operator restart.
                print("网页操作完成。请在原后端终端Ctrl+C，再用相同数据库和模型环境启动后端。", flush=True)
                print("完成后回到这里按回车核对最新版本；输入s并回车可先保留未重启结果。", flush=True)
                if input().strip().lower() != "s":
                    runner.verify_restart()
            except Exception:
                try:
                    visible = page.locator(".drawer") if page.locator(".drawer").count() else page.locator(".draft-card")
                    if visible.count():
                        runner.screenshot(visible, "incomplete-current-view")
                except Exception:
                    pass
                raise
            finally:
                context.close()
                browser.close()
        return 0 if runner.manifest["restart_read"] == "passed" else 2
    except KeyboardInterrupt:
        if runner:
            runner.manifest["error"] = {"stage": runner.stage, "message": "操作者中断，已完成证据保留。"}
        return 130
    except Exception as error:
        message = str(error) if isinstance(error, CheckFailed) else "控件、依赖、记录文件或网页步骤未完成；请提交结果包定位。"
        if runner:
            runner.manifest.update(status="incomplete", error={"stage": runner.stage, "type": type(error).__name__, "message": message})
        print(message, file=sys.stderr)
        return 2
    finally:
        if runner:
            runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
