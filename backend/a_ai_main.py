"""Opt-in A+B+C entry. Defaults to B live configuration, never a replay fallback."""
import math
import os

from backend.a_compat.ai import generate_draft
from backend.a_main import create_a_app


def create_ai_app(db_path=None, *, model_factory=None, timeout_seconds=None):
    timeout = float(os.getenv("A_AI_TIMEOUT_SECONDS", "45")) if timeout_seconds is None else timeout_seconds
    if not math.isfinite(timeout) or not 0 < timeout <= 50:
        raise ValueError("A_AI_TIMEOUT_SECONDS 须大于 0 且不超过 50 秒，以先于 A 原版的 60 秒超时返回错误。")
    app = create_a_app(db_path, draft_generator=lambda payload, deadline: generate_draft(
        payload, deadline, model_factory=model_factory), generation_timeout=timeout)
    app.title = "A+B+C 生成接入后端（追问暂未接入）"
    return app


app = create_ai_app()
