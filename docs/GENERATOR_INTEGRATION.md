# B：生成器接入

接口定义在 `backend/generator.py`，入口为同步 callable：

```python
def generate(sources: list[Source], brief: str, platform: str) -> Generation:
    ...
```

sources 已经分配稳定 sourceId；每项含 title、text、可选 url。返回 Generation，含 mode（mock 或 real）及非空 blocks。每段包含唯一 blockId、text、status、evidence 和 reviewReason。依据包含 sourceId 与 quote，quote 必须是该资料正文的连续原文片段。supported 必须有依据；资料不足使用 needs_review 并解释原因。edited_needs_review 由服务端人工修改流程使用。真实模块应在完成真实核验后才标 supported，不得把无依据的推断标成有依据。

最小接入示例（未来创建 `backend/real_generator.py`）：

```python
from backend.generator import Block, Evidence, Generation, Source

def generate(sources: list[Source], brief: str, platform: str) -> Generation:
    # 在这里接 B 的真实生成与核验结果；此示例仍为 mock。
    source = sources[0]
    return Generation(mode="mock", blocks=[Block(
        blockId="block_1", text=source.text,
        status="supported",
        evidence=[Evidence(sourceId=source.sourceId, quote=source.text)],
        reviewReason="原文引用示例，未完成真实 AI 核验。",
    )])
```

接入时在 `backend/main.py` 最后一行改为：

```python
from backend.real_generator import generate as real_generate
app = create_app(generator=real_generate)
```

无需改 A 的路径或 JSON 结构。生成器只在 POST 时运行，读取、修改和导出均从 SQLite 读取。后端校验重复 blockId、依据来源和原文片段；无效依据返回 502。模型调用失败由 B 转换为适当的服务异常，不能假冒成功。默认实现不会读取密钥或发送网络请求。

本地隔离验收时可直接使用 `create_app(db_path="data/b-test.sqlite3", generator=your_generator)`，再通过 TestClient 或独立入口启动该应用。不要覆盖默认 `app`，也不要使用已有业务数据库。可参考 `backend/tests/test_drafts.py` 的 `test_cors_and_generator_injection`：测试专用生成器返回不同中文文案和有效引文，经同一个 POST 接口创建后继续读取、修改、导出，并断言字段不变且生成器只调用一次。测试生成器始终标为 mock，仅用于验收。
