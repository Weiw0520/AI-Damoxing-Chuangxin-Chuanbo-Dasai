"""Run this entry point on port 8000 for the original A frontend. No AI implementation."""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.a_compat import exporter
from backend.a_compat.extract import MAX_BYTES, extract
from backend.a_compat.store import Store, failure


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SegmentEdit(InputModel):
    id: str = Field(min_length=1)
    text: str


class SaveInput(InputModel):
    base_version: int = Field(ge=1)
    segments: list[SegmentEdit] = Field(min_length=1)
    edit_log: list[dict] = Field(default_factory=list)
    history: list[dict] = Field(default_factory=list)


class ExportInput(InputModel):
    format: Literal["txt", "md", "report"]
    history: list[dict] = Field(default_factory=list)


class GenerateInput(InputModel):
    material: str
    requirement: str
    platform: str
    case_id: str | None = None


class RefineInput(InputModel):
    instruction: str
    base_version: int = Field(ge=0)
    segments: list[SegmentEdit]
    history: list[dict] = Field(default_factory=list)


def create_a_app(db_path=None, *, draft_generator=None, generation_timeout=45):
    store = Store(db_path)
    app = FastAPI(title="A 原版前端非 AI 兼容后端", version="0.1.0")
    app.state.store = store
    app.add_middleware(CORSMiddleware,
                       allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")],
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        message = "；".join(f"{'.'.join(str(v) for v in e['loc'])}: {e['msg']}" for e in error.errors())
        return JSONResponse(status_code=422, content={"detail": {"code": "INVALID_INPUT", "message": message}})

    @app.get("/api/cases")
    def cases():
        return json.loads((Path(__file__).parent / "a_compat/cases.json").read_text(encoding="utf-8"))

    @app.get("/api/drafts")
    def drafts():
        return store.list()

    @app.get("/api/drafts/{draft_id}")
    def get(draft_id: str):
        return store.get(draft_id)

    @app.put("/api/drafts/{draft_id}")
    def save(draft_id: str, payload: SaveInput):
        return store.save(draft_id, payload)

    @app.post("/api/drafts/{draft_id}/export")
    def export(draft_id: str, payload: ExportInput):
        return exporter.export(store.get(draft_id), payload.format, payload.history)

    @app.post("/api/generate", status_code=501 if draft_generator is None else 200)
    async def generate(payload: GenerateInput):
        if draft_generator is None:
            raise failure(501, "AI_NOT_IMPLEMENTED", "AI 功能暂未接入：文案生成与自动事实核验尚未实现，未创建或保存草稿。")
        deadline = time.monotonic() + generation_timeout
        try:
            draft = await asyncio.wait_for(
                asyncio.to_thread(draft_generator, payload, deadline), generation_timeout)
        except TimeoutError:
            raise failure(504, "AI_TIMEOUT", "生成与核验超时，未创建或保存草稿；请稍后重试。") from None
        # The worker only computes a candidate. Never let a timed-out worker save later.
        store.insert_generated(draft)
        return draft

    @app.post("/api/drafts/{draft_id}/refine", status_code=501)
    def refine(draft_id: str, payload: RefineInput):
        raise failure(501, "AI_NOT_IMPLEMENTED", "AI 功能暂未接入：对话追问改写与自动事实核验尚未实现，原草稿未修改。")

    @app.post("/api/extract")
    async def extract_file(request: Request, filename: str):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise failure(413, "FILE_TOO_LARGE", "单个文件不能超过 5 MB。")
        return extract(filename, bytes(data))

    return app


app = create_a_app()
