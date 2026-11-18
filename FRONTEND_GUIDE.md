# A 原版前端与非 AI 后端联调

本分支 `frontend/` 完整恢复自 `origin/feature/a-frontend`，保留原有界面、请求、示例模式、新建、对话输入和导出交互。后端使用专门的 `backend.a_main:app`，不使用 C 的同名路由来冒充 A 的响应。

## Windows PowerShell 启动

需要 Python 3.10+、Node.js 22+（含 npm）。从仓库根目录执行，首次安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

终端一，从根目录启动 A 兼容后端。以下使用独立测试库，可安全验收，不写用户已有库；人工样例是显式导入，不是 AI 生成。重复导入同一编号会拒绝覆盖，已有样例时略过导入命令即可。

```powershell
$env:DRAFT_DB_PATH = Join-Path $PWD 'data\a-compat-test.sqlite3'
.\.venv\Scripts\python.exe -m backend.a_seed --db $env:DRAFT_DB_PATH --id A-MANUAL-TEST
.\.venv\Scripts\python.exe -m uvicorn backend.a_main:app --host 127.0.0.1 --port 8000
```

日常使用可去掉测试导入，并在启动前移除测试路径变量 `Remove-Item Env:DRAFT_DB_PATH -ErrorAction SilentlyContinue`，恢复默认 `data/drafts.sqlite3`。空库返回空列表，不会自动生成测试稿。A 和 C 分别使用 `a_drafts/a_revisions` 与原 `drafts` 表；C 旧草稿不会自动转换到 A 列表，也不会被覆盖。

终端二，从仓库根目录：

```powershell
Set-Location frontend
npm ci
$env:VITE_USE_MOCK = 'false'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

打开 <http://127.0.0.1:5173>；确认右上角是“真实后端模式”。API 文档为 <http://127.0.0.1:8000/docs>。Vite 原配置将 `/api` 代理到 `http://127.0.0.1:8000`，无需改前端文件。若改后端端口，启动 Vite 前设置 `$env:VITE_PROXY_TARGET = 'http://127.0.0.1:8001'`。若直接跨域，`VITE_API_BASE` 必须含 `/api`，后端 `CORS_ORIGINS` 配置精确前端 origin，默认支持 localhost/127.0.0.1 的 5173。环境变量修改后需重启对应服务。

## 本轮实际支持

- 案例卡读取：只加载 A 原有三份案例的输入，不返回预制生成结果。
- 资料上传：服务端提取文本和 DOCX 正文；5 MB/20000 字符，PDF 等返回明确错误。
- 草稿列表、详情、已有资料引文查看：从数据库读取 A 格式人工测试稿或将来 B 保存的 A 格式稿。
- 人工编辑保存：PUT 全段列表，版本冲突拒绝覆盖，事务保存正文与前后历史；变更段落需重新复核，未变段落依据保留。A 原版收到保存回执后不重载 claims，重新打开草稿后可见服务端更新的核验信息。
- TXT、Markdown、核验报告导出：POST 从数据库取最新正文，返回 JSON 内容供原版前端下载。报告只是已有数据汇总，未运行事实核验。

保留的原版行为：导出失败后 A 有本地兜底；判定服务端导出成功必须检查 POST export 200。人工确认按钮修改的 claims 不在 PUT 请求中，后端保留历史备注，不推断核验通过。原有“新建”和对话交互未做改动。

原版抽屉对 needs_check 空引文附有“故意留白”等通用说明；人工修改场景以服务端返回的“人工修改后待复核”原因和历史为准。已验证范围与这些边界见 [验收记录](docs/A_COMPAT_REVIEW.md)。

## AI 与示例边界

“生成文案”调用 `POST /api/generate`，对话提交调用 `POST /api/drafts/{id}/refine`；两者当前返回 501 和“AI 功能暂未接入”，数据库不变。A 的“真实后端模式”表示网络接口可用，不表示模型上线。人工样例明确显示“人工录入测试稿（非 AI）”。

原有 `VITE_USE_MOCK=true` 或页面“切换”仍可启用前端内存示例模式；示例数据不是模型输出，不写后端库。真实 AI 的输入、预期输出和后续位置见 [AI 待办](docs/AI_TODO.md)。实际非 AI 契约见 [A 后端兼容契约](docs/A_BACKEND_COMPAT.md)。

## 验证命令

仓库根目录：

```powershell
# 避免模块导入时初始化用户已有库；测试本身用 pytest 临时库
$env:DRAFT_DB_PATH = Join-Path $PWD 'data\a-tests-import.sqlite3'
.\.venv\Scripts\python.exe -m pytest backend/tests -q
git diff --exit-code origin/feature/a-frontend -- frontend/
git ls-files --others --exclude-standard -- frontend/
git diff --check
```

frontend 目录：

```powershell
npm run build
```

A 原版未提供 `npm test`，不添加虚构命令。`node_modules/`、`dist/`、测试库及浏览器产物不提交。C 原入口仍可单独启动 `python -m uvicorn backend.main:app --port 8001`，接口见 [原 C 契约](docs/API_CONTRACT.md)，它不能作为本页原版 A 前端的后端入口。
