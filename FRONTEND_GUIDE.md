# 鲁遗校真前端与 C 后端联调

前端为 Vue 3 + Vite。沿用 A 的三栏工作台、来源抽屉、逐段编辑和修改历史，接入仓库现有 FastAPI + SQLite 后端。所有生成、保存和导出均请求 C；不再提供前端模拟结果或失败时本地导出兜底。C 默认返回 `mode=mock`，页面明确展示“模拟联调，尚未完成真实 AI 核验”。

## Windows PowerShell 启动

需要 Python 3.10+、Node.js 22+（含 npm）。以下命令均从仓库根目录开始，不需要激活虚拟环境或配置密钥。

终端一：

```powershell
Set-Location -LiteralPath 'D:\项目\AI大模型创新传播大赛'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

终端二：

```powershell
Set-Location -LiteralPath 'D:\项目\AI大模型创新传播大赛\frontend'
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

浏览器打开 <http://127.0.0.1:5173>。后端接口文档为 <http://127.0.0.1:8000/docs>。后端默认数据库在 `data/drafts.sqlite3`；验收可在启动前指定 `$env:DRAFT_DB_PATH = Join-Path $PWD 'data\ac-integration.sqlite3'`，避免写入已有草稿库。两个终端分别用 Ctrl+C 停止。

开发默认请求相对路径 `/api`，由 Vite 代理到 `http://127.0.0.1:8000`，因此浏览器不用跨域请求。更改后端端口时，在终端二启动前设置：

```powershell
$env:VITE_PROXY_TARGET = 'http://127.0.0.1:8001'
npm run dev
```

若直接跨域访问，可用 `$env:VITE_API_BASE = 'http://127.0.0.1:8000/api'`，并在后端设置包含实际前端 origin 的 `CORS_ORIGINS`。`VITE_API_BASE` 必须包含 `/api`；更改这些环境变量后重启 Vite。旧 `VITE_USE_MOCK` 已不再使用。

## 页面操作与实际接口

1. 填写逐份资料的标题、原文和可选链接，可添加/移除资料；示例卡只载入输入，不提供预制结果。杨家埠卡含两份独立资料。
2. 填传播需求、选平台，点击生成：`POST /api/drafts`，请求仅包含 `sources`、`brief`、`platform`。资料不会合并后丢失出处，链接仅保存，不自动抓取。
3. 页面展示服务端 `blocks` 的正文、依据与状态。点击“查看原文依据”打开引文、标题及链接；来源清单可查看每份完整提交原文。
4. 在右栏逐段修改并保存：`PATCH /api/drafts/{draftId}`，只发送变化段落的 `blockId`、`text`。服务端完整响应替换页面数据；变化段落显示“人工修改后待复核”、当前依据清空，旧依据仍保存在服务端历史。未变化段落保持原状态和依据。失败时保留未保存文字并提示。
5. 导出只支持 `GET /api/drafts/{draftId}/export` 的 UTF-8 TXT。未保存时需先保存；页面接收真实文件字节并沿用响应文件名，不增加 BOM、不改正文。导出失败明确提示且不下载替代文件。复制全文仅为复制当前页面文字，不等同服务端导出。
6. 创建/读取后，URL 保留 `?draftId=...`，本机仅记住最后一个草稿编号。刷新通过 `GET /api/drafts/{draftId}` 读取数据库最新版；也可在左栏输入编号读取。左栏快捷入口仅覆盖本页打开过的草稿，不是服务端草稿列表。
7. 左栏“＋ 新建”会切到空白资料表单并聚焦第一份标题；有未保存正文时先确认，取消保留原稿和修改。窄屏的“草稿 / 正文 / 文件”导航位于三栏之外，在任一栏都可切换。
8. 打开或生成草稿后，中栏底部显示“新草稿生成要求”。提交按钮为“按新要求生成新草稿”：沿用原资料和平台，把原需求与新增要求合并后 POST /api/drafts，得到新编号，原稿保留。这不是多轮对话；模拟生成器只演示创建流程，不执行真实改写或核验。失败时保留原稿和输入，成功后切到新稿；请求中防止重复提交。若正文有未保存修改，请先保存。

状态值严格沿用 [API_CONTRACT.md](docs/API_CONTRACT.md)：`supported`（有资料依据）、`needs_review`（待核验）、`edited_needs_review`（人工修改后待复核）。当前“核验报告”为段落级展示，不捏造逐句 AI 核验。C 不提供版本号或并发锁，页面不向后端提交伪造版本。

## 当前不支持

多轮追问、服务端文件解析、服务端草稿列表、人工确认状态回写、Markdown/独立报告下载均暂不支持，相关操作已隐藏或标注，不会调用 `/generate`、`/cases`、`/extract`、`/refine` 等不存在的接口。平台选择会保存到草稿；模拟器尚不生成真实平台风格。

## 测试和构建

```powershell
# 在 frontend 目录
npm test
npm run build

# 在仓库根目录
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

`npm test` 使用 Node 自带测试工具，检查 C 请求字段、方法、资料保留、文件字节和导出错误，不调用模型。构建产物位于 `frontend/dist/`，不提交。生产部署需要另外提供 `/api` 转发、后端持久化和访问控制；C 不会自动托管 dist。本轮只验收本地开发联调，不部署。

“新建”和底部输入框的浏览器回归脚本为 `frontend/qa/new-draft-and-chat.cjs`。启动前后端后，从根目录使用独立浏览器会话（本机 Edge）运行：

```powershell
npx --yes --package @playwright/cli playwright-cli -s=new-chat-qa open http://127.0.0.1:5173 --browser msedge --headed
npx --yes --package @playwright/cli playwright-cli -s=new-chat-qa run-code --filename frontend/qa/new-draft-and-chat.cjs
```

脚本使用测试资料创建草稿，并模拟一次失败响应检查输入保留；应对独立验收数据库运行。它覆盖桌面/窄屏新建焦点、取消/确认未保存修改、新要求创建与防重、长文滚动、依据/保存/TXT 下载。检查记录见 [新建与输入框修复验收](docs/NEW_DRAFT_CHAT_REVIEW.md)。

`frontend/node_modules/`、`frontend/.npm-cache/`、`frontend/dist/`、`data/`、`output/playwright/` 和 `.playwright-cli/` 均为本机依赖或验收产物，不提交。网页验收记录见 [A–C 集成验收](docs/AC_INTEGRATION_REVIEW.md)。
