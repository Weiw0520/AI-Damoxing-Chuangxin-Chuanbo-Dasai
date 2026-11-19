# 山东非遗文旅宣传内容核验与改写助手

可选 A+B+C 入口 `backend.a_ai_main:app` 已接入首次生成、追问改写与依据核验。追问实现、独立运行示例和新一轮验收见 [追问模块说明](docs/B_REFINE_INTEGRATION.md)。沿用已有模型环境变量，缺少配置返回503，不自动回放。生成接入说明见 [ABC_INTEGRATION](docs/ABC_INTEGRATION.md)。2026-11-20已完成qwen4-max真实模型、Windows Edge网页追问、补齐引文、人工保存、实际TXT下载与同库重启读取；记录见 [B追问真实验收](docs/B_REFINE_REAL_ACCEPTANCE.md)。当前完整后端测试166项通过。

首次生成的真实网页验收见 [B真实验收记录](docs/ABC_REAL_ACCEPTANCE_B.md)。此前 C 的离线基线记录保留在 [ABC_ACCEPTANCE](docs/ABC_ACCEPTANCE.md)。它们均不替代新增追问功能的真实验收。真实AI演示使用 `backend.a_ai_main:app`，模型环境配置与前端启动见 [ABC接入说明](docs/ABC_INTEGRATION.md)。

## 兼容入口的历史说明

以下命令与说明保留非AI联调入口；生成与追问501仅适用于 `backend.a_main:app`。

本分支恢复 A 原版前端，并增加匹配其请求的非 AI 后端入口 `backend.a_main:app`。列表、详情、文件解析、人工保存、历史和导出可用；生成与对话改写返回 501“AI 功能暂未接入”。无需 API 密钥，不调用模型。完整启动步骤见 [前端联调指南](FRONTEND_GUIDE.md)，实际契约见 [A 兼容后端](docs/A_BACKEND_COMPAT.md)，B 的后续工作见 [AI 待办](docs/AI_TODO.md)。

本轮网页实测、测试结果和保留原版前端的边界见 [兼容验收记录](docs/A_COMPAT_REVIEW.md)。最新 main 已包含 B 的独立生成模块，本轮原样保留，未接到 A，也未运行真实模型。

原 C 入口 `backend.main:app` 保留原接口和 SQLite 草稿，默认 `mode=mock`。即使段落为 supported，也只表示模拟器提供了原文引用，不代表完成真实 AI 核验。A、C 的同名路径结构不同，必须使用各自入口。A 默认代理的 8000 端口应启动 A 入口；以下单独列出的 C 命令供原契约使用。

## Windows PowerShell：A 原版前端

仓库根目录安装并启动（Python 3.10+、Node.js 22+）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.a_main:app --host 127.0.0.1 --port 8000
```

另一终端从仓库根目录运行：

```powershell
Set-Location frontend
npm ci
$env:VITE_USE_MOCK = 'false'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

打开 <http://127.0.0.1:5173>。空库没有自动生成的草稿；显式导入人工测试稿、使用独立测试库及示例模式说明见 [指南](FRONTEND_GUIDE.md)。A 只新增表，已有 C 草稿仍由 C 入口读取，不自动转换。

## Windows PowerShell：原 C 入口

在项目根目录运行（Python 3.10+）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

另开 PowerShell，在项目根目录运行测试：

```powershell
$env:DRAFT_DB_PATH = Join-Path $PWD 'data\a-tests-import.sqlite3'
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

原 C 交互接口文档：<http://127.0.0.1:8001/docs>。默认数据库为项目根目录 `data/drafts.sqlite3`，启动自动建表，重启保留草稿。数据目录、虚拟环境、密钥文件已加入 `.gitignore`。可配置数据库路径：

```powershell
$env:DRAFT_DB_PATH = Join-Path $PWD 'data\local.sqlite3'
$env:CORS_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
```

在启动命令之前设置环境变量。更换前端端口时同步配置 CORS_ORIGINS（逗号分隔的精确 origin）。本服务面向本地联调，无用户鉴权，不应直接暴露到公网。

- 原 C 接入：[API 合同与示例](docs/API_CONTRACT.md)。
- B 接入：[生成器替换说明](docs/GENERATOR_INTEGRATION.md)。
- A 原版的三栏工作台使用 [独立兼容后端](docs/A_BACKEND_COMPAT.md)，保留原有示例模式。页面“真实后端模式”仅表示 HTTP 连接，AI 仍未接入；人工样例带明确提示。
- 测试覆盖中文创建、引用、修改历史、原子保存、下载最新版、重建应用读回、空输入、404、稳定资料 ID 和生成器注入。

C v0.1 交付前已在独立目录的新虚拟环境中完成安装、5 项测试、真实 HTTP 联调和服务进程重启验收，详见 [交付复核记录](docs/DELIVERY_REVIEW.md)。交给队友时包含 `backend/` 的源码、依赖清单和测试，以及 `docs/`、`README.md`、`pytest.ini`、`.gitignore`；不要打包 `.venv/`、`data/`、`.acceptance-*/` 或缓存。示例 JSON 只用于前端开发，读取服务中的草稿必须使用本次创建返回的 draftId。
