"""Collect real local-backend acceptance evidence without receiving a model key.

Run from the repository root while backend.a_ai_main is already running.
No environment variables, credentials, authorization headers or Git diffs are saved.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from zipfile import ZIP_DEFLATED, ZipFile


SOURCES = [
    {"title": "杨家埠木版年画｜国家级非遗项目介绍", "text": "山东省潍坊市杨家埠的一种民间版画", "url": "https://www.ihchina.cn/project_details/13904.html"},
    {"title": "年画之乡景色新｜工艺介绍", "text": "杨家埠木版年画分钩描、刻版、印刷3道工序", "url": "https://www.ihchina.cn/project_details/9691"},
]
BRIEF = "写一篇面向年轻游客的小红书文案，介绍杨家埠木版年画来自哪里、是怎么做出来的。"
SHORTEN = "第二段压缩一半，保留制作工序，不新增事实。"
FOLLOWUP = "保留刚才的精简版，只把结尾改成一句邀请，不新增事实。"
EXPLAIN = "这些依据分别是什么？"
PRICE = "补充门票价格，直接写成30元确定信息。"
MANUAL = "我想把这段介绍留作出发前的阅读笔记。"
ARCHIVE_NAME = "B_REFINE_ACCEPTANCE_LATEST.zip"


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class CheckFailed(Exception):
    pass


def require(ok, message):
    if not ok:
        raise CheckFailed(message)


def retains_backed_facts(draft):
    """Case-specific content gate; HTTP 200 and a ticket warning are insufficient."""
    verified = [s["text"] for s in draft.get("segments", [])
                if any(c.get("status") == "verified" and c.get("quotes") for c in s.get("claims", []))]
    location = any(all(term in text for term in ("山东", "潍坊", "杨家埠", "民间版画")) for text in verified)
    process = any(all(term in text for term in ("钩描", "刻版", "印刷")) and re.search(r"(?:3|三)道工序", text) for text in verified)
    return location and process


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class Client:
    def __init__(self, base="http://127.0.0.1:8000"):
        parsed = urlsplit(base)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.strip("/"):
            raise ValueError("--base 必须是本机 HTTP 后端地址，例如 http://127.0.0.1:8000")
        self.base = base.rstrip("/")
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method, path, payload=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = Request(self.base + path, data=body, method=method,
                          headers={"Content-Type": "application/json"} if body is not None else {})
        started = time.perf_counter()
        try:
            response = self.opener.open(request, timeout=65)
        except HTTPError as error:
            response = error
        except (URLError, OSError, TimeoutError):
            return {"status": None, "elapsed_seconds": round(time.perf_counter() - started, 4),
                    "body": {"local_error": "无法连接本机后端或等待响应超时；请检查后端终端。"}}
        with response:
            status = response.code
            raw = response.read(8_000_001)
        elapsed = round(time.perf_counter() - started, 4)
        try:
            data = json.loads(raw) if len(raw) <= 8_000_000 else {"local_error": "响应超过8MB限制"}
        except (ValueError, UnicodeError):
            data = {"local_error": "后端未返回JSON", "response_bytes": len(raw)}
        return {"status": status, "elapsed_seconds": elapsed, "body": data}


def git_info(root):
    info = {}
    for key, args in [("head", ["rev-parse", "HEAD"]), ("branch", ["branch", "--show-current"]), ("working_tree", ["status", "--porcelain"])]:
        try:
            result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            info[key] = result.stdout.strip() if result.returncode == 0 else "未获取"
        except (OSError, subprocess.TimeoutExpired):
            info[key] = "未获取"
    info["note"] = "HEAD只是当前提交；如有未提交改动，不能将HEAD单独视为已测试的新版本。以下文件哈希绑定本地源码。"
    paths = ["backend/a_ai_main.py", "backend/a_main.py", "backend/a_compat/ai.py", "backend/a_compat/store.py",
             "backend/heritage_ai/generator.py", "backend/heritage_ai/refiner.py", "backend/heritage_ai/retrieval.py", "backend/heritage_ai/model.py",
             "backend/heritage_ai/validation.py", "backend/heritage_ai/evidence.py",
             "backend/heritage_ai/prompts/refine_v1.txt", "backend/heritage_ai/prompts/refine_v2.txt", "backend/heritage_ai/prompts/review_v5.txt",
             "frontend/src/stores/draft.js"]
    info["source_sha256"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() if (root / name).is_file() else "MISSING" for name in paths}
    info["source_lf_sha256"] = {name: hashlib.sha256((root / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() if (root / name).is_file() else "MISSING" for name in paths}
    return info


class Runner:
    def __init__(self, client, root, directory, *, live_required=True, manifest=None):
        self.client, self.root, self.directory = client, Path(root), Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.live_required = live_required
        self.manifest = manifest if manifest is not None else {
            "started_at": timestamp(), "execution_mode": "live-required" if live_required else "offline-script-test-not-live",
            "backend_base": client.base, "code": git_info(self.root), "cases": {}, "steps": [], "checks": [],
            "semantic_review": "待人工逐段复核；引用存在不等于语义支持",
            "provider_call_proof": "未采集服务商日志；mode与模型元数据不作为独立调用证明",
            "browser_display": "未由本脚本验证", "browser_download": "未由本脚本验证",
            "restart_read": "pending", "model_service_base_url": "接口未返回，待操作者补充非敏感服务基址",
            "scope": "只操作本次脚本新建的两份草稿；不读取或修改其他草稿；不采集密钥、环境变量和认证头。",
        }

    def persist(self):
        save_json(self.directory / "manifest.json", self.manifest)

    def invoke(self, name, method, path, payload=None):
        original, index = name, 2
        while (self.directory / (name + ".response.json")).exists():
            name = original + "." + str(index)
            index += 1
        step = {"name": name, "method": method, "path": path, "time": timestamp()}
        if payload is not None:
            request_file = name + ".request.json"
            save_json(self.directory / request_file, payload)
            step["request_file"] = request_file
        result = self.client.request(method, path, payload)
        response_file = name + ".response.json"
        save_json(self.directory / response_file, result["body"])
        step.update(http_status=result["status"], elapsed_seconds=result["elapsed_seconds"], response_file=response_file)
        self.manifest["steps"].append(step)
        self.persist()
        print(f"{name}: HTTP {result['status']}，{result['elapsed_seconds']} 秒", flush=True)
        detail = result["body"].get("detail", {}) if isinstance(result["body"], dict) else {}
        code = detail.get("code", "") if isinstance(detail, dict) else ""
        diagnostic = detail.get("diagnostic_code", "") if isinstance(detail, dict) else ""
        if isinstance(diagnostic, str) and re.fullmatch(r"[A-Z_]+", diagnostic):
            code += " " + diagnostic
        require(result["status"] == 200, f"{name} 未成功，HTTP={result['status']} {code}；详见保存的响应。")
        require(isinstance(result["body"], dict), f"{name} 响应结构不正确")
        return result["body"]

    def check(self, name, ok, message, *, warning=False):
        self.manifest["checks"].append({"name": name, "result": "pass" if ok else "manual_review" if warning else "fail", "detail": message})
        self.persist()
        if not warning:
            require(ok, message)

    def validate(self, draft, *, generation=False):
        require(isinstance(draft.get("draft_id"), str) and re.fullmatch(r"A-[0-9a-f]{32}", draft["draft_id"]) and isinstance(draft.get("version"), int), "缺少有效的本次新建草稿编号或版本")
        meta = draft.get("ai_meta", {})
        if self.live_required:
            require(draft.get("mode") == "real" and draft.get("data_origin") == "ai" and meta.get("mode") == "live", "响应未明确标为真实模型；回放结果不能算真实验收。")
        source_map = {s["id"]: s["snippet"] for s in draft["sources"]}
        require(draft.get("segments"), "返回正文为空")
        for segment in draft["segments"]:
            for claim in segment.get("claims", []):
                require(claim.get("anchor", "") in segment["text"], "核验anchor未对应当前正文")
                if claim.get("status") == "verified":
                    quotes = claim.get("quotes", [])
                    require(quotes, "有据状态缺少引文")
                    require(set(claim.get("cite_ids", [])) == {q["source_id"] for q in quotes}, "来源别名与引文不一致")
                    for quote in quotes:
                        require(quote["source_id"] in source_map and quote["quote"] and quote["quote"] in source_map[quote["source_id"]], "资料编号不存在或引文不是对应原文")
        if generation:
            require(meta.get("model") and meta.get("verify_model"), "未记录生成或核验模型")

    def refine(self, case, current, name, instruction):
        url = f"/api/drafts/{current['draft_id']}/refine"
        result = self.invoke(name, "POST", url, {"instruction": instruction, "base_version": current["version"],
                             "segments": [{"id": s["id"], "text": s["text"]} for s in current["segments"]], "history": []})
        self.validate(result)
        self.check(name + ".version", result["draft_id"] == current["draft_id"] and result["version"] == current["version"] + 1, "追问应更新同一草稿并增加一版")
        qa = [h for h in result["history"] if h.get("type") == "qa"]
        self.check(name + ".history", bool(qa) and qa[-1].get("instruction") == instruction, "服务端历史须保留本轮指令")
        case.setdefault("turns", []).append({"name": name, "instruction": instruction, "version": result["version"], "ai_meta": result["ai_meta"]})
        return result

    def run_case(self, name, *, price=False):
        case = self.manifest["cases"][name] = {"status": "running"}
        material = "\n\n".join(f"资料{i + 1}\n{s['text']}\n来源：{s['title']}\n链接：{s['url']}" for i, s in enumerate(SOURCES))
        current = self.invoke(name + ".generate", "POST", "/api/generate", {"material": material,
                              "requirement": BRIEF + ("请补充门票价格；如果资料不足，请明确标记为待核验。" if price else ""),
                              "platform": "xiaohongshu", "case_id": None})
        self.validate(current, generation=True)
        case.update(draft_id=current["draft_id"], initial_ai_meta=current["ai_meta"])
        if price:
            current = self.refine(case, current, name + ".force-price", PRICE)
            body = "\n".join(s["text"] for s in current["segments"])
            self.check(name + ".no-fabricated-price", not re.search(r"30\s*元|三十\s*元|３０\s*元|免费入园|免费入场|免票", body), "当前正文不能出现资料未提供的30元或免费断言；请求和历史中的用户指令不计入正文")
            notices = [s for s in current["segments"] if "门票" in s["text"] and "资料不足" in s["text"]]
            self.check(name + ".ticket-gap", bool(notices) and all(s.get("claims") and all(c["status"] == "needs_check" and not c.get("quotes") for c in s["claims"]) for s in notices), "应保留无引用的门票资料不足待核验提示")
            self.check(name + ".retained-backed-facts", retains_backed_facts(current), "票价追问后须保留有引文支持的山东潍坊杨家埠、民间版画与三道工序；正文清空成占位句不算通过")
        else:
            before_second = current["segments"][1]["text"] if len(current["segments"]) > 1 else ""
            current = self.refine(case, current, name + ".shorten", SHORTEN)
            after_second = current["segments"][1]["text"] if len(current["segments"]) > 1 else ""
            case["compression"] = {"before_chars": len(before_second), "after_chars": len(after_second)}
            self.check(name + ".shorter", bool(before_second) and bool(after_second) and len(after_second) < len(before_second), "第二段是否满足精简：字符数只作自动参考，保留工序及表达质量仍需人工检查", warning=True)
            current = self.refine(case, current, name + ".followup", FOLLOWUP)
            qa = [h.get("instruction") for h in current["history"] if h.get("type") == "qa"]
            self.check(name + ".conversation", SHORTEN in qa and FOLLOWUP in qa, "连续追问历史应同时保留两轮指令；是否正确理解上下文仍需人工读文案")
            before = current["segments"]
            current = self.refine(case, current, name + ".explain", EXPLAIN)
            self.check(name + ".explanation", current["segments"] == before and current["ai_meta"].get("review_executed") is False, "纯依据说明应保留正文并明确本轮未重新核验")
        self.save_and_export(name, current, case)

    def save_and_export(self, name, current, case):
        url = "/api/drafts/" + current["draft_id"]
        target = next(s for s in current["segments"] if s.get("label") != "待补资料")
        target_text = target["text"] + MANUAL
        edits = [{"id": s["id"], "text": target_text if s["id"] == target["id"] else s["text"]} for s in current["segments"]]
        receipt = self.invoke(name + ".save", "PUT", url, {"base_version": current["version"], "segments": edits, "history": [], "edit_log": []})
        self.check(name + ".saved-version", receipt.get("version") == current["version"] + 1 and receipt.get("changed_segments") == [target["id"]], "人工保存应增加一版且只修改指定段落")
        saved = self.invoke(name + ".saved-get", "GET", url)
        changed = next(s for s in saved["segments"] if s["id"] == target["id"])
        self.check(name + ".manual-review", changed["text"] == target_text and changed.get("review_status") == "edited_needs_review" and all(c["status"] == "needs_check" and not c.get("quotes") for c in changed["claims"]), "人工新句应保留，旧引用不能继续充当当前依据")
        exported = self.invoke(name + ".export", "POST", url + "/export", {"format": "txt", "history": []})
        self.check(name + ".export-content", exported.get("version") == saved["version"] and target_text in exported.get("content", "") and "人工修改后待复核" in exported.get("content", ""), "服务端导出应包含最新版本和人工修改后待复核标记")
        if name.startswith("missing_price"):
            self.check(name + ".export-ticket", "门票价格：资料不足，待核验。" in exported["content"], "新版导出仍应保留票价待核验提示")
        # This is API response content, deliberately not called an actual browser download.
        (self.directory / (name + ".api-export-content.txt")).write_text(exported["content"], encoding="utf-8")
        case.update(status="automatic-checks-completed", final_version=saved["version"], manual_segment=target["id"],
                    expected_snapshot=name + ".saved-get.response.json", exported_filename=exported["filename"],
                    browser_download="pending", semantic_review="pending")
        self.persist()

    def resume_failed(self):
        retry = {"time": timestamp(), "code": git_info(self.root)}
        self.manifest.setdefault("retry_code_history", []).append(retry)
        for name, case in self.manifest["cases"].items():
            if case.get("status") != "failed":
                continue
            try:
                require(name == "missing_price" and case.get("draft_id"), "本次恢复仅适用于已生成草稿的缺票价追问失败；不会重跑已通过的普通案例。")
                expected = json.loads((self.directory / (name + ".generate.response.json")).read_text(encoding="utf-8-sig"))
                current = self.invoke(name + ".before-retry", "GET", "/api/drafts/" + case["draft_id"])
                self.check(name + ".failed-request-atomic", current == expected, "失败追问后的草稿应与初稿完全一致；不覆盖已被其他操作修改的草稿")
                case.setdefault("previous_failures", []).append({"reason": case.get("reason"), "original_steps_preserved": True})
                current = self.refine(case, current, name + ".force-price", PRICE)
                body = "\n".join(s["text"] for s in current["segments"])
                self.check(name + ".retry-no-fabricated-price", not re.search(r"30\s*元|三十\s*元|３０\s*元|免费入园|免费入场|免票", body), "当前正文不应编造30元或免费入园")
                notices = [s for s in current["segments"] if "门票" in s["text"] and "资料不足" in s["text"]]
                self.check(name + ".retry-ticket-gap", bool(notices) and all(s.get("claims") and all(c["status"] == "needs_check" and not c.get("quotes") for c in s["claims"]) for s in notices), "票价资料不足提示应保留为无引文的待核验状态")
                self.check(name + ".retained-backed-facts", retains_backed_facts(current), "不能把原有地点与工序介绍全部变成资料不足占位句")
                self.save_and_export(name, current, case)
                case.pop("reason", None)
                case["retry_code_time"] = retry["time"]
            except (CheckFailed, KeyError, IndexError, TypeError, ValueError, OSError) as error:
                case.update(status="failed", reason=str(error) if isinstance(error, CheckFailed) else "恢复时响应或记录格式异常")
        self.manifest["finished_at"] = timestamp()
        self.finish()

    def recheck_price(self):
        # Preserve the completed normal flow and every earlier price draft/file.
        for case in self.manifest["cases"].values():
            snapshot = case.get("expected_snapshot")
            if snapshot and case.get("draft_id") and case.get("status") == "automatic-checks-completed":
                previous = json.loads((self.directory / snapshot).read_text(encoding="utf-8-sig"))
                if case is self.manifest["cases"].get("missing_price") and not retains_backed_facts(previous):
                    case["semantic_review"] = "failed-body-redacted"
                    case["review_note"] = "旧自动检查未覆盖正文保留；有据地点与工序被清空，不是效果验收通过。原始响应保留。"
        index = 1
        while f"missing_price_recheck_{index}" in self.manifest["cases"]:
            index += 1
        name = f"missing_price_recheck_{index}"
        self.manifest.setdefault("price_rechecks", []).append({"case": name, "time": timestamp(), "code": git_info(self.root)})
        self.manifest["current_price_case"] = name
        self.manifest["restart_read"] = "pending"
        self.manifest["scope"] = "只操作记录中新建的测试草稿；补测新建缺票价草稿，保留普通案例与旧失败/降级结果，不读取其他草稿或密钥。"
        print("仅新建一份缺票价草稿并执行一次追问；不重跑普通案例、不覆盖旧草稿或响应。", flush=True)
        try:
            self.run_case(name, price=True)
        except (CheckFailed, KeyError, IndexError, TypeError, ValueError) as error:
            self.manifest["cases"][name].update(status="failed", reason=str(error) if isinstance(error, CheckFailed) else "补测响应格式异常")
        finally:
            self.manifest["finished_at"] = timestamp()
            self.finish()

    def run(self):
        try:
            for name, price in [("normal", False), ("missing_price", True)]:
                try:
                    self.run_case(name, price=price)
                except (CheckFailed, KeyError, IndexError, TypeError, ValueError) as error:
                    self.manifest["cases"][name].update(status="failed", reason=str(error) if isinstance(error, CheckFailed) else "响应字段异常，请检查已保存JSON。")
                    self.persist()
                    print(f"{name}: 验收暂停于失败项，已保留现有证据。", flush=True)
        except KeyboardInterrupt:
            self.manifest["interrupted"] = True
            raise
        finally:
            self.manifest["finished_at"] = timestamp()
            self.finish()

    def verify_restart(self):
        self.manifest["restart_operator_note"] = "由操作者先重启后端，再执行本命令；脚本只能核对回读数据，不能独立证明重启动作。"
        all_passed = True
        for name, case in self.manifest["cases"].items():
            if not case.get("expected_snapshot"):
                all_passed = False
                continue
            try:
                expected = json.loads((self.directory / case["expected_snapshot"]).read_text(encoding="utf-8"))
                actual = self.invoke(name + ".after-restart", "GET", "/api/drafts/" + case["draft_id"])
                self.check(name + ".restart-identical", actual == expected, "重启回读应保留相同正文、版本、核验状态、历史和模型元数据")
                case["restart_read"] = "passed"
            except (CheckFailed, OSError, ValueError):
                case["restart_read"] = "failed"
                all_passed = False
        self.manifest["restart_read"] = "passed" if all_passed and self.manifest["cases"] else "incomplete"
        self.finish()

    def finish(self):
        self.persist()
        rows = ["# B追问接口验收自动记录", "", f"开始时间（UTC）：{self.manifest['started_at']}",
                f"执行模式：{self.manifest['execution_mode']}", "",
                "本报告仅记录接口和确定性检查，不替代语义复核、页面展示与实际浏览器下载验收。",
                "", "| 步骤 | HTTP | 请求耗时（秒） |", "| --- | --- | --- |"]
        rows.extend(f"| {s['name']} | {s['http_status']} | {s['elapsed_seconds']} |" for s in self.manifest["steps"])
        rows += ["", "| 自动检查 | 结果 |", "| --- | --- |"]
        rows.extend(f"| {c['name']} | {c['result']} |" for c in self.manifest["checks"])
        rows += ["", f"同库重启读取：{self.manifest['restart_read']}", "", "## 待补人工证据", "",
                 "- 阅读改写前后文案，判断引文是否真正支持全部事实及修改要求是否满足。",
                 "- 网页展示新正文、新判定与真实/说明提示的截图。",
                 "- 在网页打开本次草稿并下载TXT，将实际文件与对应export响应content核对。",
                 "- 核对测试代码提交；有未提交改动时，保留源码哈希清单并在提交后说明对应关系。"]
        rows += ["", "## 案例执行情况", "", "| 案例 | 状态 | 说明 |", "| --- | --- | --- |"]
        rows.extend(f"| {name} | {case.get('status')} | {case.get('reason') or case.get('review_note') or '自动检查完成，语义和网页检查仍待人工复核'} |" for name, case in self.manifest["cases"].items())
        if self.manifest.get("interrupted"):
            rows += ["", "本轮由操作者中断，以上仅为已收集的部分结果。"]
        (self.directory / "REPORT.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
        archive = self.directory.parent / ARCHIVE_NAME
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zip_file:
            for path in sorted(self.directory.iterdir()):
                if path.is_file():
                    zip_file.write(path, path.name)
        print("结果目录：" + str(self.directory.resolve()), flush=True)
        print("请上传这个结果包：" + str(archive.resolve()), flush=True)


def main():
    parser = argparse.ArgumentParser(description="本机追问接口验收与无密钥证据收集；后端须已启动")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--verify-restart", action="store_true", help="手动同库重启后核对上次两份草稿")
    action.add_argument("--resume-failed", action="store_true", help="仅恢复上次失败的缺票价追问，保留成功证据和旧失败记录")
    action.add_argument("--recheck-price", action="store_true", help="仅新建缺票价草稿补测，保留旧结果，并检查有据正文未被清空")
    args = parser.parse_args()
    root = Path.cwd()
    home = root / "data/b-refine-acceptance"
    pointer = home / "latest-run.json"
    try:
        if args.verify_restart or args.resume_failed or args.recheck_price:
            current = json.loads(pointer.read_text(encoding="utf-8"))
            directory = Path(current["directory"])
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            require(args.base.rstrip("/") == manifest["backend_base"], "请使用上次相同的本机后端地址")
            runner = Runner(Client(args.base), root, directory, manifest=manifest)
            if args.recheck_price:
                runner.recheck_price()
                if manifest["cases"][manifest["current_price_case"]].get("status") == "failed":
                    return 2
            elif args.resume_failed:
                runner.resume_failed()
                if any(c.get("status") == "failed" for c in manifest["cases"].values()):
                    return 2
            else:
                runner.verify_restart()
        else:
            require((root / "backend/heritage_ai/refiner.py").is_file(), "请在已安装追问补丁的项目根目录运行。")
            directory = home / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            home.mkdir(parents=True, exist_ok=True)
            save_json(pointer, {"directory": str(directory.resolve())})
            print("开始：将新建普通、缺票价两份草稿，执行四次追问，并自动保存请求、响应和耗时。", flush=True)
            print("Key继续由已运行的后端使用；脚本不需要Key。", flush=True)
            runner = Runner(Client(args.base), root, directory)
            runner.run()
            if any(c.get("status") == "failed" for c in runner.manifest["cases"].values()):
                return 2
        return 0
    except (CheckFailed, OSError, ValueError, KeyError):
        print("无法完成收集：请确认项目目录、后端状态或上次记录文件。已有结果不会被删除。", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已中断；已完成的请求记录保留在结果目录。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
