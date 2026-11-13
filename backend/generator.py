"""Replace generate() with B's implementation; keep this typed contract."""
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(StrictModel):
    sourceId: str
    title: str
    text: str
    url: str | None = None


class Evidence(StrictModel):
    sourceId: str
    quote: str = Field(min_length=1)


class Block(StrictModel):
    blockId: str
    text: str = Field(min_length=1)
    status: Literal["supported", "needs_review", "edited_needs_review"]
    evidence: list[Evidence]
    reviewReason: str


class Generation(StrictModel):
    mode: Literal["mock", "real"]
    blocks: list[Block] = Field(min_length=1)


class Generator(Protocol):
    def __call__(self, sources: list[Source], brief: str, platform: str) -> Generation: ...


def generate(sources: list[Source], brief: str, platform: str) -> Generation:
    quote = sources[0].text[:120]
    return Generation(mode="mock", blocks=[
        Block(blockId="block_1", text=f"走近山东非遗：{quote}", status="supported",
              evidence=[Evidence(sourceId=sources[0].sourceId, quote=quote)],
              reviewReason="仅展示原文引用匹配；模拟模式尚未完成真实 AI 核验。"),
        Block(blockId="block_2", text="出发前，请向当地官方渠道确认开放时间、票价和体验预约方式。",
              status="needs_review", evidence=[],
              reviewReason="资料不足：未确认开放时间、票价及预约信息，发布前需核实。模拟模式尚未完成真实 AI 核验。"),
    ])
