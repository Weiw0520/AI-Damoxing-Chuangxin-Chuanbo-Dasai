# A 原版前端 / 非 AI 后端验收记录

日期：2026-11-18。以下记录对应本地验收阶段；该阶段没有提交、推送、合并或部署。后续分支交付以 Git 提交和 PR 记录为准。

## 代码基线

- 工作分支：`feat/a-frontend-backend-compat`。初次 fetch 的 main 为 `49461c6`；收尾 fetch 发现 PR #3 新增 B 模块，检查均为不重叠的新文件后，将工作分支基线更新到 `5b20f4d518d7b33681c4b0b93b4f70a33bebb0a4`，保留所有工作区改动，没有创建提交，也没有修改本地 main 或 A 分支。
- 前端完整恢复自 `origin/feature/a-frontend`：`39ad8d2bfef17d232d92ecbf7187b9f645ed299b`。`git diff --exit-code origin/feature/a-frontend -- frontend/` 退出 0；`git ls-files --others --exclude-standard -- frontend/` 无输出。相对于 main 的前端改动均来自这次恢复，不是另写了一版前端。
- `backend/main.py`、`backend/generator.py`、`docs/API_CONTRACT.md` 及新增的上游 B 模块与最新 main 一致。Git 暂存区为空，`git diff --check` 通过（仅有本机 LF/CRLF 提示）。

## 测试环境

Python 3.13.9、Node.js 24.13.0，Windows Edge / Playwright CLI，桌面视口 1600×1000。A 兼容后端实际启动在 127.0.0.1:8000，A 原版 Vite 前端在 127.0.0.1:5173，通过默认 `/api` 代理连接；没有修改前端配置文件。

网页测试库仅用 `data/a-compat-acceptance-20261118.sqlite3`，通过 `python -m backend.a_seed --db ... --id A-MANUAL-ACCEPTANCE` 显式导入人工样例。它有两份用户提供的资料节选、两条待核验引文与非 AI 提示，不是生成接口的输出。自动测试使用 pytest 独立临时数据库；模块初始化路径也设为独立 `data/a-tests-import.sqlite3`。用户原 `data/drafts.sqlite3` 未写入（最后修改时间仍为 2026-11-12）。

## 网页实测证据

| 流程 | 实际结果 |
| --- | --- |
| 案例与列表 | GET cases、GET drafts 均 200，三个案例输入和人工测试稿出现在原版页面 |
| 打开草稿 | GET `/api/drafts/A-MANUAL-ACCEPTANCE` 200，显示 v1 与“人工录入测试稿（非 AI）” |
| 查看依据 | 点“待核·S1”，抽屉显示来源标题、链接和“山东省潍坊市杨家埠的一种民间版画”原文引文 |
| 手工编辑保存 | 在右栏把 s3 从“杨家埠木版年画分钩描、刻版、印刷3道工序”改为“杨家埠木版年画的工艺资料由人工整理，发布前请逐项复核。”，PUT 200，回执 version=2、changed_segments=[s3] |
| 状态和历史 | GET 证实 s3 为 edited_needs_review、claims 为 needs_check 且旧 quotes 清空；s2 完整对象与原稿一致。重新打开后网页显示待核，点开可见“人工修改后待复核”原因，S1 引文仍可查看 |
| TXT 下载 | 网页 POST export 200，下载文件名 `A-MANUAL-ACCEPTANCE_v2.txt`；剥除原版前端添加的 UTF-8 BOM 后，下载全文与服务端 JSON content 完全相同。新句存在、旧句不存在，保留待核验/修改后待复核标记，无导出兜底冒充成功 |
| 追问 | 输入并点发送，真实 POST refine 返回 501 / AI_NOT_IMPLEMENTED；页面显示“AI 功能暂未接入”，输入保留，完整数据库草稿前后相等 |
| 文件上传 | 网页上传中文 TXT，真实 POST extract 200，返回 35 字并追加到资料框，未改写资料 |
| 生成 | 载入杨家埠案例后提交，真实 POST generate 返回 501 / AI_NOT_IMPLEMENTED；页面显示“生成失败，没有产生草稿”，点“回到输入区”资料仍在。数据库仍只有原 v2 测试稿，未新增/覆盖 |
| 重启读取 | 停止本轮启动的 A 后端并重新启动，网页再次打开 v2，修改记录显示服务端留痕及旧句/新句；导出仍与下载内容一致 |

本机验收脚本、截图、下载位于忽略目录 `output/playwright/`，不属于交付源码。关键证据：`a-compat-edited-review.png`、`a-compat-ai-501.png`、`a-compat-generate-501.png`、`a-compat-history.png`、`a-compat-latest.txt`。

## 自动检查

```powershell
$env:DRAFT_DB_PATH = Join-Path $PWD 'data\a-tests-import.sqlite3'
python -m pytest backend/tests -q
# 79 passed, 1 warning（既有 TestClient/httpx 弃用提示）

Set-Location frontend
npm run build
# Vite 构建成功，40 modules transformed
```

79 项包括原 C 的 5 项、本轮 A 兼容的 9 项（含参数化）以及新拉取 B 模块的 65 项离线回归。A 测试覆盖读取、版本、原子保存、前后历史、三种导出、重建应用读取、AI 501 无写入、文本编码/HTML/DOCX/大小限制、与 C 同库不破坏 C。B 测试使用显式 fixture 或替换的 HTTP transport；本轮没有真实模型验收。

## 保留原版前端的边界

本轮不改 A 的界面或请求。原版保存只处理回执，需重新打开草稿才能刷新服务端 claims；原版人工确认 claims 未随 PUT 发送，后端不会据历史文字推断通过；原版导出失败仍有本地兜底。空引文的 needs_check 在原版抽屉中还会附“故意留白”等通用示例解释，人工修改场景应以服务端 reason“人工修改后待复核”和历史为准。这些属于后续需要 A 同意改前端才能完整调整的行为。

窄屏、所有浏览器、所有可上传文件的网页交互未逐一验收；DOCX、编码、截断和错误分支已做后端自动测试。真实生成、追问改写和自动核验未连接到 A，当前明确返回 501。B 上游真实入口未启动，接口适配仍是后续工作，见 `AI_TODO.md`。

## 本轮交付文件

新增 `backend/a_main.py`、`backend/a_seed.py`、`backend/a_compat/{__init__.py,store.py,extract.py,exporter.py,cases.json}`、`backend/tests/test_a_compat.py`；新增 `docs/A_BACKEND_COMPAT.md`、`docs/AI_TODO.md`、本记录；更新根目录 `README.md`、`FRONTEND_GUIDE.md`。另含完整恢复的 A `frontend/`。依赖清单沿用 `backend/requirements.txt` 和 A 原版 package/lock，无新增 Python 依赖。

交给队友应包含完整工作区源码（包括尚未跟踪的新文件）、文档、依赖清单及测试；不包含数据库、日志、缓存、虚拟环境、截图、node_modules 或 dist。启动与人工样例命令见根目录 `FRONTEND_GUIDE.md`。
