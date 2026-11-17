"""Small, dependency-free client for a JSON-mode Chat Completions endpoint."""

from dataclasses import dataclass
import json
import math
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .errors import ConfigurationError, GenerationError

MAX_RESPONSE_BYTES = 2_000_000


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model: str
    verify_model: str = ""
    timeout: float = 60
    max_tokens: int = 4096

    def __post_init__(self):
        u = urlsplit(self.base_url)
        if not u.hostname or u.username or u.password or u.query or u.fragment:
            raise ConfigurationError("AI_BASE_URL 必须是无认证信息、查询参数和 fragment 的服务地址")
        if u.scheme != "https" and not (
            u.scheme == "http" and u.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ConfigurationError("模型地址须用 HTTPS；本机服务可用 HTTP")
        if not self.api_key.strip() or not self.model.strip():
            raise ConfigurationError("请在本机设置 AI_API_KEY 和 AI_MODEL；不要把密钥写进代码")
        if not math.isfinite(self.timeout) or not 1 <= self.timeout <= 120:
            raise ConfigurationError("AI_TIMEOUT 应在 1–120 秒之间")
        if type(self.max_tokens) is not int or not 256 <= self.max_tokens <= 16384:
            raise ConfigurationError("AI_MAX_TOKENS 应在 256–16384 之间")

    @classmethod
    def from_env(cls):
        try:
            return cls(
                base_url=os.environ.get("AI_BASE_URL", "https://api.deepseek.com"),
                api_key=os.environ.get("AI_API_KEY", ""),
                model=os.environ.get("AI_MODEL", ""),
                verify_model=os.environ.get("AI_VERIFY_MODEL", ""),
                timeout=float(os.environ.get("AI_TIMEOUT", "60")),
                max_tokens=int(os.environ.get("AI_MAX_TOKENS", "4096")),
            )
        except ValueError as exc:
            raise ConfigurationError("AI_TIMEOUT 或 AI_MAX_TOKENS 配置无效") from exc


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class ChatModel:
    mode = "live"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.label = settings.model
        self.verify_label = settings.verify_model or settings.model
        self._opener = build_opener(_NoRedirect())

    def complete(self, *, stage: str, system: str, payload: dict) -> dict:
        model = self.verify_label if stage == "review" else self.label
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": self.settings.max_tokens,
            "stream": False,
        }
        request = Request(
            self.settings.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.settings.api_key,
                     "Content-Type": "application/json"},
            method="POST",
        )
        # No automatic retry: callers can retry explicitly under their timeout/billing policy.
        try:
            with self._opener.open(request, timeout=self.settings.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            # Do not log response bodies: providers may echo secrets or private input.
            raise GenerationError(f"模型服务 HTTP {exc.code}（阶段：{stage}）") from None
        except (URLError, TimeoutError, socket.timeout, OSError):
            raise GenerationError(f"模型服务连接失败或超时（阶段：{stage}）") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise GenerationError("模型响应超过大小限制")
        try:
            envelope = json.loads(raw)
            choice = envelope["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise GenerationError("模型输出未完整结束；请检查 token 上限或服务状态")
            message = choice["message"]
            if message.get("refusal") or message.get("tool_calls"):
                raise GenerationError("模型未返回所需 JSON 内容")
            result = json.loads(message["content"])
            if not isinstance(result, dict):
                raise GenerationError("模型内容须为 JSON 对象")
            return result
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, UnicodeError):
            raise GenerationError("模型响应为空、JSON 无效或结构不完整") from None
