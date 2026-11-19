import copy
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException


def now():
    return datetime.now(timezone.utc).isoformat()


def failure(status, code, message):
    return HTTPException(status, detail={"code": code, "message": message})


def merge_history(stored, incoming):
    """Client notes may append history; they cannot replace server audit records."""
    result = copy.deepcopy(stored)
    seen = {h.get("id") or json.dumps(h, sort_keys=True, ensure_ascii=False) for h in result}
    for item in incoming:
        key = item.get("id") or json.dumps(item, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            result.append(copy.deepcopy(item))
            seen.add(key)
    return result


class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("DRAFT_DB_PATH") or Path(__file__).resolve().parents[2] / "data/drafts.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS a_drafts (id TEXT PRIMARY KEY, document TEXT NOT NULL)")
            conn.execute("""CREATE TABLE IF NOT EXISTS a_revisions (
                draft_id TEXT NOT NULL, version INTEGER NOT NULL, segment_id TEXT NOT NULL,
                before_document TEXT NOT NULL, after_document TEXT NOT NULL, edited_at TEXT NOT NULL,
                PRIMARY KEY (draft_id, version, segment_id))""")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def read(self, conn, draft_id):
        row = conn.execute("SELECT document FROM a_drafts WHERE id=?", (draft_id,)).fetchone()
        if not row:
            raise failure(404, "DRAFT_NOT_FOUND", "A 格式草稿不存在；C 草稿请通过 C 入口读取。")
        return json.loads(row[0])

    def get(self, draft_id):
        with self.connect() as conn:
            return self.read(conn, draft_id)

    def insert_manual(self, draft):
        """Explicit manual import only; never called by generate/refine routes."""
        self._insert(draft)

    def insert_generated(self, draft):
        """Called only after the complete generation pipeline succeeds before timeout."""
        self._insert(draft)

    def _insert(self, draft):
        with self.connect() as conn:
            if conn.execute("SELECT 1 FROM a_drafts WHERE id=?", (draft["draft_id"],)).fetchone():
                raise failure(409, "DRAFT_EXISTS", "草稿编号已存在，未覆盖原稿。")
            conn.execute("INSERT INTO a_drafts VALUES (?, ?)", (draft["draft_id"], json.dumps(draft, ensure_ascii=False)))

    def list(self):
        with self.connect() as conn:
            docs = [json.loads(row[0]) for row in conn.execute("SELECT document FROM a_drafts")]
        result = []
        for draft in docs:
            stats = {"verified": 0, "needs_check": 0, "unsupported": 0, "total": 0}
            for seg in draft["segments"]:
                for claim in seg.get("claims", []):
                    stats[claim["status"]] += 1
                    stats["total"] += 1
            title = next((s["text"] for s in draft["segments"] if s.get("type") == "title"), "未命名文案")
            body = next((s["text"] for s in draft["segments"] if s.get("type") != "title"), "")
            result.append({"draft_id": draft["draft_id"], "title": title[:40], "preview": body[:80],
                           "version": draft["version"], "created_at": draft["created_at"],
                           "updated_at": draft["updated_at"], "platform": draft["input"]["platform"], "stats": stats})
        return sorted(result, key=lambda d: (d["updated_at"], d["draft_id"]), reverse=True)

    def save(self, draft_id, payload):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            draft = self.read(conn, draft_id)
            if payload.base_version != draft["version"]:
                raise failure(409, "VERSION_CONFLICT", "草稿版本已更新，请重新打开草稿后再保存；本次未覆盖。")
            incoming = {s.id: s.text for s in payload.segments}
            if len(incoming) != len(payload.segments):
                raise failure(422, "DUPLICATE_SEGMENT", "修改中含重复段落编号，全部未保存。")
            ids = {s["id"] for s in draft["segments"]}
            if set(incoming) - ids:
                raise failure(404, "SEGMENT_NOT_FOUND", "修改包含不存在的段落，全部未保存。")
            if ids - set(incoming):
                raise failure(422, "MISSING_SEGMENTS", "请提交完整段落列表，全部未保存。")
            history = merge_history(draft["history"], payload.history)
            changed = [s["id"] for s in draft["segments"] if incoming[s["id"]] != s["text"]]
            if changed or history != draft["history"]:
                timestamp = now()
                version = draft["version"] + 1
                for seg in draft["segments"]:
                    if seg["id"] not in changed:
                        continue
                    before = copy.deepcopy(seg)
                    seg["text"] = incoming[seg["id"]]
                    seg["review_status"] = "edited_needs_review"
                    seg["claims"] = [{"id": f"manual_{seg['id']}_v{version}", "anchor": seg["text"],
                                      "status": "needs_check", "cite_ids": [], "quotes": [], "suggest": None,
                                      "reason": "人工修改后待复核；旧依据仅保存在历史中，本次修改未重新运行 AI 核验。"}] if seg["text"].strip() else []
                    conn.execute("INSERT INTO a_revisions VALUES (?, ?, ?, ?, ?, ?)",
                                 (draft_id, version, seg["id"], json.dumps(before, ensure_ascii=False),
                                  json.dumps(seg, ensure_ascii=False), timestamp))
                    history.append({"id": f"server-{version}-{seg['id']}", "type": "human", "who": "人工",
                                    "whoClass": "human", "title": "人工修改正文（服务端留痕）", "time": timestamp,
                                    "desc": "人工修改已保存；当前依据需重新复核，未调用 AI。",
                                    "diff": {"before": before["text"], "after": seg["text"]},
                                    "before": before, "after": copy.deepcopy(seg)})
                draft.update(history=history, version=version, updated_at=timestamp)
                conn.execute("UPDATE a_drafts SET document=? WHERE id=?", (json.dumps(draft, ensure_ascii=False), draft_id))
            return {"draft_id": draft_id, "version": draft["version"], "saved_at": draft["updated_at"], "changed_segments": changed}

    def refine_snapshot(self, draft_id, payload):
        draft = self.get(draft_id)
        # Original A sends 0 immediately after generation although the server saved v1.
        valid = payload.base_version == draft["version"] or (payload.base_version == 0 and draft["version"] == 1)
        if not valid:
            raise failure(409, "VERSION_CONFLICT", "草稿版本已更新，请重新打开草稿后再追问；本次未覆盖。")
        if not payload.instruction.strip():
            raise failure(422, "AI_INPUT_INVALID", "追问要求不能为空。")
        incoming = {s.id: s.text for s in payload.segments}
        if len(incoming) != len(payload.segments):
            raise failure(422, "DUPLICATE_SEGMENT", "追问中含重复段落编号，原草稿未修改。")
        ids = {s["id"] for s in draft["segments"]}
        if set(incoming) - ids:
            raise failure(404, "SEGMENT_NOT_FOUND", "追问包含不存在的段落，原草稿未修改。")
        if ids - set(incoming):
            raise failure(422, "MISSING_SEGMENTS", "追问须提交当前完整段落，原草稿未修改。")
        if any(len(s.text) > 1600 for s in payload.segments):
            raise failure(422, "AI_INPUT_INVALID", "当前每段正文不能超过 1600 字符。")
        return draft

    def commit_refine(self, draft_id, expected_version, payload, candidate, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise failure(504, "AI_TIMEOUT", "追问已超时，原草稿未修改。")
        # Hold the lock only for final validation and persistence, never for an AI call.
        conn = sqlite3.connect(self.path, timeout=min(remaining, 30))
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                current = self.read(conn, draft_id)
                if current["version"] != expected_version:
                    raise failure(409, "VERSION_CONFLICT", "追问期间草稿已被更新，请重新打开后再操作；本次未覆盖。")
                if time.monotonic() >= deadline:
                    raise failure(504, "AI_TIMEOUT", "追问已超时，原草稿未修改。")
                timestamp, version = now(), current["version"] + 1
                before = {s["id"]: s for s in current["segments"]}
                after = {s["id"]: s for s in candidate["segments"]}
                if not after or len(after) != len(candidate["segments"]):
                    raise failure(502, "AI_REFINEMENT_FAILED", "改写段落为空或编号重复，原草稿未修改。")
                changed = [sid for sid, seg in after.items() if seg != before.get(sid)]
                removed = [sid for sid in before if sid not in after]
                for sid in dict.fromkeys(changed + removed):
                    conn.execute("INSERT INTO a_revisions VALUES (?, ?, ?, ?, ?, ?)",
                                 (draft_id, version, sid, json.dumps(before.get(sid), ensure_ascii=False),
                                  json.dumps(after.get(sid), ensure_ascii=False), timestamp))
                draft = copy.deepcopy(current)
                if "initial_ai_meta" not in draft and current.get("ai_meta"):
                    draft["initial_ai_meta"] = copy.deepcopy(current["ai_meta"])
                for key in ("segments", "model", "prompt_version", "prompt_excerpt", "notice", "mode", "data_origin", "ai_meta"):
                    draft[key] = candidate[key]
                # Client-supplied history never becomes trusted AI conversation context.
                history = copy.deepcopy(current["history"])
                entry = {"id": "server-qa-" + uuid4().hex, "version": version, "type": "qa", "title": "追问改写与核验" if candidate["action"] == "rewrite" else "依据说明",
                         "who": "AI" if candidate["mode"] == "real" else "测试回放", "whoClass": "ai" if candidate["mode"] == "real" else "system",
                         "instruction": payload.instruction.strip(), "time": timestamp, "desc": candidate["desc"],
                         "changed": bool(changed or removed), "applied": bool(changed or removed),
                         "changed_segments": changed, "removed_segments": removed,
                         "ai_meta": copy.deepcopy(candidate["ai_meta"]),
                         "page_edits": candidate["page_edits"], "diagnostics": candidate["diagnostics"]}
                old_text = "\n\n".join(s["text"] for s in current["segments"])
                new_text = "\n\n".join(s["text"] for s in candidate["segments"])
                if old_text != new_text:
                    entry["diff"] = {"before": old_text, "after": new_text}
                history.append(entry)
                context = current.get("refine_context", []) + [{"instruction": payload.instruction.strip(), "summary": candidate["desc"][:2000]}]
                draft.update(version=version, updated_at=timestamp, history=history, refine_context=context[-6:])
                if time.monotonic() >= deadline:
                    raise failure(504, "AI_TIMEOUT", "追问已超时，原草稿未修改。")
                conn.execute("UPDATE a_drafts SET document=? WHERE id=?", (json.dumps(draft, ensure_ascii=False), draft_id))
            return {**draft, "saved_at": timestamp, "changed": changed, "removed_segments": removed,
                    "applied": bool(changed or removed), "desc": candidate["desc"]}
        except sqlite3.OperationalError:
            raise failure(504 if time.monotonic() >= deadline else 409, "AI_TIMEOUT" if time.monotonic() >= deadline else "DRAFT_BUSY",
                          "数据库暂时繁忙，追问未保存，请重新打开草稿后重试。") from None
        finally:
            conn.close()
