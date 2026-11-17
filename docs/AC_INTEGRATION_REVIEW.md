# A–C 本地集成验收

日期：2026-11-17（北京时间）。分支：`fix/a-c-integration`，基于本轮 `git fetch origin` 得到的 `origin/feature/a-frontend` 提交 `39ad8d2bfef17d232d92ecbf7187b9f645ed299b`。开始时工作区干净，因此直接创建本地分支；没有覆盖其他工作区改动。本轮未提交、未推送。

## 实现边界

保留 A 的 Vue 三栏工作台、来源抽屉、分段编辑、报告与历史样式。前端只调用 C 的四个已约定接口，`backend/` 和 `docs/API_CONTRACT.md` 没有改动。

- 创建传 `sources[]`（每份独立 title/text/url）、brief、platform；保存只传变化段落的 edits。
- POST/GET/PATCH 返回的完整草稿保存为状态层的 serverDraft，再适配到 A 的展示模型；不在前端重新判定核验状态。保存返回后替换正文、依据、状态和历史。
- `mode=mock` 明确显示“模拟联调”，supported 仅显示有资料依据，不表示真实 AI 核验通过。
- TXT 直接下载服务端响应 Blob，不拼接 BOM、不生成替代文件。未保存修改先保存；失败保留用户文字并明确提示。
- 左栏仅是当前页面的已打开草稿快捷入口，可手动按 draftId GET；刷新用 URL 或本机记住的最后一个编号重新 GET。没有调用服务端草稿列表接口。
- 多轮追问、服务端文件解析、人工判定回写、Markdown/报告下载暂不支持，操作入口隐藏或标注。

## 实际网页验收证据

启动仓库内未修改的 C 后端（127.0.0.1:8000），使用独立数据库 `data/ac-integration-20261117.sqlite3`；启动 Vite（127.0.0.1:5173，/api 转发到 C）。使用 Playwright 驱动本机 Edge，所有关键步骤通过网页按钮、文本框和下载事件完成，未用直接调用状态层代替用户操作。

两份资料采用本机 `Yangjiabu_Integration_Materials.zip` 的输入示例：

1. 杨家埠木版年画｜国家级非遗项目介绍；原文“山东省潍坊市杨家埠的一种民间版画”；链接 `https://www.ihchina.cn/project_details/13904.html`。
2. 年画之乡景色新｜工艺介绍；原文“杨家埠木版年画分钩描、刻版、印刷3道工序”；链接 `https://www.ihchina.cn/project_details/9691`。

| 步骤 | 结果 |
| --- | --- |
| 手动填写两份标题/原文/链接与传播需求，选择小红书并生成 | POST /api/drafts 为 201；请求保留两份资料，响应含两个独立 sourceId，mode=mock。草稿编号 `draft_287f190ea1af47bf8269c793431d6bd1`。 |
| 点击第一段“查看原文依据” | 抽屉显示第一份资料的原文引用、标题、来源编号和原链接，截图留存。第二份资料也保留在来源清单中；默认模拟器当前仅引用第一份，这是 C 的既有行为。 |
| 在右栏修改第二段并保存 | PATCH 200，服务端 history 增加一条；第二段显示“人工修改后待复核”、当前依据为空。未改第一段的正文、状态、依据与创建响应逐字段相同，仍可从网页点开。 |
| 点击导出，实际下载 TXT | 文件名 `draft_287f190ea1af47bf8269c793431d6bd1.txt`。浏览器下载文件与再次 GET C 导出的字节完全一致。 |
| 刷新网页及按编号读取 | 均请求 GET；完整草稿与最后 PATCH 响应相同，修改状态、历史和未改段落依据仍在。没有重新 POST 生成。 |
| 桌面视觉检查 | 1440×1000 三栏完整，来源抽屉、编辑、历史、新状态可读；1024×768 无横向溢出。修复旧样式在 981–1080px 将外壳撑高的问题后，窄窗口外壳高度为 768px，内容在栏内滚动。 |

下载包含新句：

> 走进杨家埠，感受木版年画的匠心；体验安排请提前向官方核实。

不包含被替换的旧句：

> 出发前，请向当地官方渠道确认开放时间、票价和体验预约方式。

TXT SHA-256：`4e63901f9eff3594c0562d2afa602b1e5965893ecf5335a98300d87b4620142a`。内容为 UTF-8，无新增 BOM，含“人工修改后待复核”标记。

## 错误分支与自动化检查

- 空输入：网页阻止提交并显示字段提示，没有发送创建请求。
- 添加/移除资料以及平台切换：网页交互正常。
- 保存故障：浏览器对单次 PATCH 模拟 503，页面提示保存失败并保留编辑文字；随后重试真实 PATCH 成功。503 是验收注入，不是修改后端行为。
- 导出故障：单次 GET export 模拟 503，页面明确显示失败，下载事件数量未增加；下一次真实下载成功。没有用本地文本冒充服务端导出。
- 不存在草稿：真实 GET 返回 404，页面提示“草稿不存在”；原草稿仍可重新读取。
- 网页网络记录只出现约定的 drafts 路径与方法，没有 /generate、/cases、/extract、/refine 请求；没有 Vue/JavaScript 未捕获异常。故障注入和 404 会产生预期的网络错误控制台记录。
- `npm test`：2 项通过，覆盖方法/路径、独立资料、PATCH 字段、TXT 文件字节、错误拒绝及 422 字段提示。
- `python -m pytest backend/tests -q`：5 项通过，1 条既有 TestClient/HTTPX 弃用警告。
- 最终 `npm run build`：通过（Vite 6.4.6）；`git diff --check`：通过。

## 文件变更

- API/状态：`frontend/src/api/client.js`、`index.js`，新增 `cases.js`、`draftView.js`；`frontend/src/stores/draft.js`。
- 界面：`frontend/src/components/` 下的 AppTopbar、CaseCards、ChatMessage、ChatStream、CiteChip、ConversationList、DraftCard、EditHistory、ExportModal、FilePanel、InputPanel、SegmentBlock、SourceDrawer、VerifyReport。
- 展示与下载：`frontend/src/styles/app.css`、`frontend/src/utils/io.js`、`text.js`；`frontend/index.html`（内联图标，避免 favicon 404）。
- 检查：`frontend/package.json` 新增 npm test 命令，新增 `frontend/tests/api.test.js`。
- 文档与忽略规则：`.gitignore`、`README.md`、`FRONTEND_GUIDE.md`、本记录。运行时截图、下载和 npm 缓存均排除。

## 本机产物与未验证项

网页验收脚本、截图及下载保存在忽略目录 `output/playwright/`；其中 `14-final.png` 为最终正文状态，`07-reloaded-evidence.png` 为刷新后的依据抽屉，`11-final-history.png` 为服务端修改记录，`13-narrow-final.png` 为窄窗口，`yangjiabu-latest.txt` 为实际浏览器下载文件。

本轮没有接入或验证真实 AI，没有抓取或独立核实上述外部网页；没有进行手机端完整验收、多用户并发、生产部署或真实外部模型超时测试。服务进程重启持久化已有 C 复核记录，本轮验证的是浏览器刷新后 GET 重载，没有重做后端进程重启。

本地前后端及专用验收浏览器有意保留运行，便于检查；没有部署或推送。启动/停止方法见根目录 FRONTEND_GUIDE.md。原有数据库和临时验收目录未清理、未覆盖。
