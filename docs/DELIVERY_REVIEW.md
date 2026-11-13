# C v0.1 交付复核记录

复核收尾日期：2026-11-13（北京时间）。结论：可交付用于 A、B 的本地模拟联调；真实 AI 尚未接入。

## 验收环境与来源

从当前工作区文件复制源码、文档、依赖和测试到项目内独立的 `.acceptance-<随机标识>/`，包含当前新增文件；没有使用 Git 历史，没有复制旧虚拟环境、数据库或缓存。交付复核开始时目录尚不是 Git 仓库，该轮复核未提交、推送或部署。

Windows PowerShell，新建 `.venv`，Python 3.13.9，未继承系统 site-packages。按 README 执行安装和启动命令：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

依赖实际安装版本：FastAPI 0.162.5、Uvicorn 0.54.0、Pydantic 2.14.3、Starlette 1.10.0、HTTPX 0.28.1、pytest 9.2.0。`pip check` 输出 `No broken requirements found.`。依赖清单使用兼容版本范围，以上为本次实测版本；其他 Python 版本未在本轮实测。

## 三项验收证据

| 验收 | 实测结果 |
| --- | --- |
| 干净安装、启动与持久化 | 全新虚拟环境安装成功。按 README 带 `--reload` 在 127.0.0.1:8000 启动，`/docs` 和 `/openapi.json` 均 200。真实 HTTP 中文创建为 201，读取、PATCH、TXT 下载均为 200。下载含新句、不含被替换的旧句，保持段落顺序，修改段落为 edited_needs_review，未修改段落及依据不变。停止该次进程树后重新启动，同一 draftId 返回的 JSON 与下载字节逐一相等。默认 SQLite 在验收副本的 data/ 内，无需密钥。 |
| A 的接口合同 | 新增自动化测试解析 API_CONTRACT.md 中的 JSON 示例并实际请求，核对示例草稿（除随机 ID 和时间）、PATCH 返回段落、404/422/502 错误示例、Content-Type、下载文件名、UTF-8 无 BOM、CORS 和暴露的下载响应头。修复 OpenAPI 的下载类型声明后通过，example-draft.json 无需修改。 |
| B 的生成器替换 | 在验收目录创建临时入口，以 create_app(db_path="data/injected.sqlite3", generator=...) 注入独立生成器。真实 HTTP POST 返回“注入验收：风筝牵起一段齐鲁匠心之旅。”及资料中真实的“潍坊风筝历史悠久”引文；继续 GET、PATCH、导出成功。顶层和段落字段与默认结果相同。永久测试同时断言生成器只调用一次、旧依据移入历史、修改状态正确。临时入口不交付，项目默认仍使用原模拟生成器。 |

在干净副本执行 README 测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

结果：`5 passed, 1 warning`。警告来自 Starlette 对 TestClient 使用 HTTPX 的弃用提示；未过滤警告，当前测试与真实 HTTP 验收均通过。

## 本轮变更及接入影响

- `backend/main.py`：仅修正 export 的 OpenAPI 成功响应类型为 text/plain，实际 TXT 格式不变。
- `backend/tests/test_drafts.py`：注入测试改为返回独立中文文案并验证读取、修改、导出、历史与调用次数。
- `backend/tests/test_contract.py`：新增文档示例与实际接口一致性测试。
- `docs/API_CONTRACT.md`：准确说明 sourceId 计算前的首尾空白处理，说明 fixture ID 不能直接用于真实服务。
- `docs/GENERATOR_INTEGRATION.md`：补充独立数据库注入和测试入口。
- `README.md`、本记录：补充交付文件范围与验收结果。
- `.gitignore`：排除临时 `.acceptance-*/` 验收目录，避免误纳入后续版本控制。

API 路径、请求/响应字段、状态值和默认模拟生成器均保持原约定，A、B 无需适配破坏性变化。

## 交付内容与后续

整包包含 `backend/__init__.py`、`backend/main.py`、`backend/generator.py`、`backend/requirements.txt`、`backend/tests/*.py`、`docs/*.md`、`docs/example-draft.json`、`README.md`、`pytest.ini`、`.gitignore`。A 先读 API_CONTRACT.md 并使用示例 JSON；B 先读 GENERATOR_INTEGRATION.md 并实现生成器协议。

所有记录的本轮测试服务进程（含重载子进程）已确认退出；原工作区虚拟环境、数据库及其他文件未清理。

清理未完成：自动审批审查拒绝删除已核实的单一验收目录，返回原因仅为 `blocked by policy`。未尝试绕过该限制。残留目录为项目根目录下 `.acceptance-d4b27d88cb5f429291088e4f167eb378/`，其中包含本轮新建虚拟环境、测试数据库、临时生成器、验收脚本与日志，不属于交付内容，打包时必须排除。此限制不影响已通过的安装、测试及 HTTP 验收。

后续工作：B 接入真实生成与核验；A 完成正式前端。在此之前 mode=mock 及原文引用只供联调，不能表示已完成真实 AI 核验。
