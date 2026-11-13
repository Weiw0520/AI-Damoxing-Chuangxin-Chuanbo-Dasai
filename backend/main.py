import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import Field, field_validator

from backend.generator import Block, Generation, Generator, Source, StrictModel, generate


class SourceInput(StrictModel):
    title: str
    text: str
    url: str | None = None

    @field_validator("title", "text")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("资料标题和正文不能为空")
        return value.strip()


class CreateDraft(StrictModel):
    sources: list[SourceInput] = Field(min_length=1)
    brief: str
    platform: str

    @field_validator("brief", "platform")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("宣传需求和目标平台不能为空")
        return value.strip()


class Edit(StrictModel):
    blockId: str = Field(min_length=1)
    text: str

    @field_validator("text")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("修改后的文案不能为空")
        return value


class PatchDraft(StrictModel):
    edits: list[Edit] = Field(min_length=1)


class History(StrictModel):
    blockId: str
    before: Block
    after: Block
    editedAt: str


class Draft(StrictModel):
    draftId: str
    mode: str
    sources: list[Source]
    brief: str
    platform: str
    blocks: list[Block]
    history: list[History]
    createdAt: str
    updatedAt: str


def now():
    return datetime.now(timezone.utc).isoformat()


def create_app(db_path=None, generator: Generator = generate):
    db_path = Path(db_path or os.getenv("DRAFT_DB_PATH", str(Path(__file__).resolve().parents[1] / "data" / "drafts.sqlite3")))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect():
        conn = sqlite3.connect(db_path, timeout=30)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, document TEXT NOT NULL)")

    app = FastAPI(title="山东非遗文旅宣传内容核验与改写助手", version="1.0.0")
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins if o.strip()],
                       allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"],
                       expose_headers=["Content-Disposition"])

    def read(conn, draft_id):
        row = conn.execute("SELECT document FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise HTTPException(404, detail={"code": "draft_not_found", "message": "草稿不存在", "draftId": draft_id})
        return json.loads(row[0])

    def save(conn, draft):
        conn.execute("INSERT INTO drafts(id, document) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET document=excluded.document",
                     (draft["draftId"], json.dumps(draft, ensure_ascii=False)))

    @app.post("/api/drafts", response_model=Draft, status_code=201)
    def create(payload: CreateDraft):
        sources = []
        for item in payload.sources:
            canonical = json.dumps(item.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            sources.append(Source(sourceId="src_" + hashlib.sha256(canonical.encode()).hexdigest(), **item.model_dump()))
        result = Generation.model_validate(generator(sources, payload.brief, payload.platform))
        source_map = {s.sourceId: s.text for s in sources}
        if len({b.blockId for b in result.blocks}) != len(result.blocks):
            raise HTTPException(502, detail={"code": "invalid_generation", "message": "生成器返回重复段落 ID"})
        for block in result.blocks:
            if (block.status == "supported" and not block.evidence) or any(
                e.sourceId not in source_map or e.quote not in source_map[e.sourceId] for e in block.evidence
            ):
                raise HTTPException(502, detail={"code": "invalid_generation", "message": "生成器返回无效原文依据"})
        timestamp = now()
        draft = dict(draftId="draft_" + uuid4().hex, mode=result.mode,
                     sources=[s.model_dump() for s in sources], brief=payload.brief, platform=payload.platform,
                     blocks=[b.model_dump() for b in result.blocks], history=[], createdAt=timestamp, updatedAt=timestamp)
        with connect() as conn:
            save(conn, draft)
        return draft

    @app.get("/api/drafts/{draft_id}", response_model=Draft)
    def get(draft_id: str):
        with connect() as conn:
            return read(conn, draft_id)

    @app.patch("/api/drafts/{draft_id}", response_model=Draft)
    def patch(draft_id: str, payload: PatchDraft):
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            draft = read(conn, draft_id)
            blocks = {b["blockId"]: b for b in draft["blocks"]}
            ids = [e.blockId for e in payload.edits]
            if len(ids) != len(set(ids)):
                raise HTTPException(422, detail={"code": "duplicate_block_id", "message": "同次修改不能包含重复段落 ID"})
            missing = [i for i in ids if i not in blocks]
            if missing:
                raise HTTPException(404, detail={"code": "block_not_found", "message": "段落不存在，全部修改均未保存", "blockIds": missing})
            timestamp = now()
            changed = False
            for edit in payload.edits:
                before = blocks[edit.blockId]
                if before["text"] == edit.text:
                    continue
                after = dict(before, text=edit.text, status="edited_needs_review", evidence=[],
                             reviewReason="人工修改后待复核，旧依据已移至历史记录。")
                draft["history"].append(dict(blockId=edit.blockId, before=before.copy(), after=after.copy(), editedAt=timestamp))
                blocks[edit.blockId] = after
                changed = True
            if changed:
                draft["blocks"] = [blocks[b["blockId"]] for b in draft["blocks"]]
                draft["updatedAt"] = timestamp
                save(conn, draft)
            return draft

    @app.get("/api/drafts/{draft_id}/export", response_class=Response,
             responses={200: {"content": {"text/plain": {"schema": {"type": "string"}}},
                              "description": "下载 UTF-8 TXT 文件"}})
    def export(draft_id: str):
        with connect() as conn:
            draft = read(conn, draft_id)
        labels = {"supported": "有资料依据", "needs_review": "待核验", "edited_needs_review": "人工修改后待复核"}
        content = f"山东非遗文旅宣传文案\n模式：{draft['mode']}（模拟模式不代表完成真实 AI 核验）\n\n"
        content += "\n\n".join(f"【{labels[b['status']]}】\n{b['text']}" for b in draft["blocks"])
        return Response(content=content.encode("utf-8"), media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{draft_id}.txt"'})

    return app


app = create_app()
