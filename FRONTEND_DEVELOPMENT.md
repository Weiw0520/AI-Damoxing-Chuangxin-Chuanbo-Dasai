# A 前端开发与运行说明

本文面向负责前端页面（A）的开发者，说明前端目录、开发联调、验收和构建部署方式。项目根目录的 `README.md` 是当前 C 后端的总览；本文专门补充前端工作流，不替代 `docs/API_CONTRACT.md`。

> 当前分支包含从原项目迁入的前端源码。前端现有 API 层尚未适配 `docs/API_CONTRACT.md` 中 C 后端的字段与接口，因此页面可单独开发运行，但不能据此认为已完成 C 后端端到端联调。API 适配应作为 A 的后续工作，并以接口合同为准。

## 1. 前端要完成的功能

页面包含非遗资料与需求输入、目标平台选择、生成结果、来源依据与待核验提示、段落编辑保存、导出，以及左侧草稿栏和右侧文件面板。A 的目标流程是：

1. 输入一份或多份非遗资料、宣传需求和目标平台。
2. 调用后端创建草稿并展示分段文案。
3. 展示每段核验状态、对应的资料原文引文和待核验原因。
4. 修改文案段落并保存；后端将改变的段落标为 `edited_needs_review`，清空该段旧的当前依据并将修改记录写入历史。
5. 通过后端导出接口下载最新已保存的 TXT。

目前后端使用 `mode=mock` 模拟生成。页面必须明确提示这是模拟联调，不代表已完成真实 AI 核验。当前 A 分支尚未完成与 C 后端的 API 字段适配。

## 2. 目录与接口职责

前端实现完成后，推荐结构如下；实际结构以合并后的代码为准：

```text
frontend/
├── src/                 Vue 页面、组件、状态与 API 封装
├── index.html           Vite 页面入口
├── package.json         npm 命令和依赖声明
├── package-lock.json    锁定依赖版本
└── vite.config.js       开发服务器与后端代理
```

接口字段、请求示例、错误结构和状态语义以 [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) 为准。当前主要接口：

| 操作 | 请求 |
|---|---|
| 创建草稿/生成文案 | `POST /api/drafts` |
| 重新读取草稿 | `GET /api/drafts/{draftId}` |
| 保存一个或多个段落 | `PATCH /api/drafts/{draftId}` |
| 下载最新保存版本 | `GET /api/drafts/{draftId}/export` |

核心字段采用驼峰命名：`draftId`、`sources`、`brief`、`platform`、`blocks`、`history`。每个 block 包含 `blockId`、`text`、`status`、`evidence`、`reviewReason`；依据通过 `evidence[].sourceId` 关联资料，原文在 `evidence[].quote`。当前生成器示例为每个 block 提供整段引文，并不拆成逐句 claim；界面将以整段作为依据锚点展示。

当前 C 后端未定义案例列表、草稿列表、资料文件解析和追问改写接口。前端案例卡使用随代码提供的本地演示材料；草稿只能在生成后持有 draftId 并直接 GET 读取；上传仅浏览器读取纯文本；追问暂不可用。不要在未同步并修改 API 合同的情况下自行猜测新接口。

保存时 PATCH 的 `edits` 项包含 `blockId` 与新 `text`。必须等待保存成功后再下载。不能把旧版本中的 `draft_id`、`segments`、`claims` 当成本合同字段使用。

状态展示至少区分：

- `supported`：有资料依据；模拟模式下仍需注明未做真实 AI 核验。
- `needs_review`：待核验。
- `edited_needs_review`：人工修改后待复核。

## 3. 开发环境

需要安装：

- Git
- Node.js 22（或满足项目 Vite 版本要求的受支持版本）及 npm
- Python 3.10 或更高版本

从仓库根目录打开 VS Code。在 PowerShell 终端创建并激活后端环境，安装依赖并启动服务：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

保持该终端运行。后端接口文档可在 <http://127.0.0.1:8000/docs> 查看。

再打开 VS Code 的另一个 PowerShell 终端，启动前端开发服务器：

```powershell
Set-Location ".\frontend"
npm ci
npm run dev
```

浏览器打开 Vite 输出的本地地址，默认是 <http://127.0.0.1:5173>。开发服务器应将 `/api` 请求代理到 `http://127.0.0.1:8000`；确认 `frontend/vite.config.js` 的代理目标与本机后端端口一致。

如需验证后端测试（在新的 PowerShell 终端里从仓库根目录执行）：

```powershell
Set-Location "F:\code\AI-Damoxing-Chuangxin-Chuanbo-Dasai"
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

## 4. 联调验收

按以下顺序手工走完，并检查浏览器网络请求或后端 `/docs`：

1. 输入至少一份资料、宣传需求和平台，提交后收到 `201`，保存本次返回的 `draftId`。
2. 展示返回的 blocks；逐段显示状态、原文引用和 reviewReason。依据原文必须来自关联 source 的实际文本。
3. 修改至少一个 block，调用 PATCH；成功后重新 GET 同一 `draftId`，确认正文已更新、状态为 `edited_needs_review`，且修改历史已保留。
4. 对同一 `draftId` 调用 export，打开下载的 TXT，确认内容是刚保存的新版本。
5. 检查模拟模式提示始终可见，不将 `supported` 描述为真实 AI 核验结论。

错误处理至少覆盖空输入或字段验证错误（422）、草稿不存在（404）、无效生成器依据（502）和网络不可用。详细错误响应见 API 合同。

## 5. 构建与本地预览

在前端目录执行生产构建：

```powershell
Set-Location ".\frontend"
npm ci
npm run build
```

构建结果在 `frontend/dist/`。可以用 Vite 预览构建结果：

```powershell
npm run preview -- --host 127.0.0.1
```

Vite 的 preview 仅用于本地检查，不是生产级 Web 服务器。部署时将 `frontend/dist/` 发布到静态站点托管服务，并确认静态站点能访问 API。部署域名或端口改变时，应在后端设置精确的 `CORS_ORIGINS`，例如：

```powershell
$env:CORS_ORIGINS = 'https://你的前端域名'
```

该变量必须在启动后端服务之前设置。开发环境默认允许 `http://localhost:5173` 和 `http://127.0.0.1:5173`。

## 6. 后端本地运行与数据

后端默认绑定 `127.0.0.1:8000`，SQLite 草稿数据库默认创建在 `data/drafts.sqlite3`。需要更换位置时，在启动前设置：

```powershell
$env:DRAFT_DB_PATH = Join-Path $PWD 'data\local.sqlite3'
```

数据库目录包含运行时草稿数据，不要提交到 Git。不要将当前无用户鉴权的后端直接暴露到公网；正式部署前需另行设计访问控制、HTTPS、数据库备份和生产进程管理。

## 7. Git 提交范围

A 的工作从 `main` 创建独立分支：

```powershell
git switch main
git pull origin main
git switch -c feature/a-frontend
```

如果 Windows 本机 Git 对带斜杠的分支名创建异常，可用本地分支 `a-frontend` 工作，并将推送映射到团队约定的远程分支：

```powershell
git switch -c a-frontend main
git push -u origin HEAD:feature/a-frontend
```

通常提交 `frontend/src/`、`frontend/index.html`、`frontend/package.json`、`frontend/package-lock.json`、`frontend/vite.config.js` 和本说明。前端接口适配及相应测试应在实际完成后再纳入提交。提交前检查：

```powershell
git status --short
git diff --check
```

不要提交 `frontend/node_modules/`、`frontend/dist/`、缓存、临时浏览器 profile、本地 `.env`、数据库或个人草稿。`.gitignore` 应持续忽略依赖目录、构建产物和本机数据。

完成后推送分支并创建到 `main` 的 Pull Request：

```powershell
git add frontend FRONTEND_DEVELOPMENT.md .gitignore
git commit -m "feat(frontend): add heritage content review interface"
git push -u origin feature/a-frontend
```

只有在文件确实属于本次前端工作时才添加它；不要为了照抄命令而提交无关修改。PR 描述应列出实际运行过的测试；如果尚未适配 C 后端，应明确标注端到端联调未完成。
