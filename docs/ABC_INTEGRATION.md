# A+B+C 可选接入入口与验收边界

2026-11-20 追问升级：可选 AI 入口已实现追问改写、独立依据核验及原子保存，见 [B_REFINE_INTEGRATION](B_REFINE_INTEGRATION.md)。本文件中的88项测试与真实调用为0描述的是下述2026-11-18离线基线；首次生成真实验收另见 `ABC_REAL_ACCEPTANCE_B.md`，新追问已完成qwen4-max与Windows Edge真实主流程验收，见 `B_REFINE_REAL_ACCEPTANCE.md`。

接入基线历史分支：`feat/abc-ai-integration`；本次追问交付分支：`feature/b-ai-refine`，基于 `ec50729155c150a0bb2ba74aa6913a45af843e16` 的源码。依赖 PR #4 的 A 原版前端恢复及非 AI 后端；PR #4 已合入 main（merge commit `4064d42beaff0c5b452686ebe024cc9d3c95353e`），本分支以该 main 为基线，不重复携带 PR #4 的前端变更。交付整理日期为 2026-11-19；88 项测试、构建和浏览器回放/故障验收记录日期为 2026-11-18，真实模型调用为 0，见 `ABC_ACCEPTANCE.md`。

前端以 A 的 `39ad8d2bfef17d232d92ecbf7187b9f645ed299b` 为基线；追问升级仅在 `stores/draft.js` 补充回执元数据同步与切换草稿保护，请求、样式和页面布局不变。原 `backend.a_main:app` 继续是非 AI 入口，生成和追问均501。`backend.a_ai_main:app` 将 A 的生成请求适配到 B 的v5核心，追问适配到新的refine-v2/review-v5核验流程（实现refine-core/0.1.3），复用 C 的 SQLite 保存、列表、修改、历史和导出。原 C 的 `backend.main:app` 及 B 独立生成入口保持不变。

## Windows PowerShell

在仓库根目录：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:DRAFT_DB_PATH = Join-Path $PWD 'data\abc-acceptance.sqlite3'
# 模型配置须在此终端安全提供；不要打印或提交 AI_API_KEY。
# AI_MODEL、AI_BASE_URL 应对应实际可用服务；配置说明见 AI_GENERATOR.md。
.\.venv\Scripts\python.exe -m uvicorn backend.a_ai_main:app --host 127.0.0.1 --port 8000
```

另一个终端从根目录启动原版前端：

```powershell
Set-Location frontend
npm ci
$env:VITE_USE_MOCK = 'false'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

打开 http://127.0.0.1:5173。缺配置时 `POST /api/generate` 返回 503 `AI_NOT_CONFIGURED`，不创建草稿，不自动回放。此页面“真实后端模式”只是网络模式，真实生成是否成功须查看 HTTP 响应、mode、ai_meta 和保存记录。普通服务入口没有通过环境变量启用回放的选项；离线验收只能显式注入 `create_ai_app(model_factory=...)`，响应始终标注 mock 和“模拟联调”。

## 资料与结果映射

A 只有一份资料文本框。以行首“资料一”“资料二”或“资料1”“资料2”显式分段时，后端分别保留正文；每段的“来源：”“链接：”行提取为元数据，不作为事实正文提交给模型。没有显式分段时整份文本视为一份资料。原始 material 完整保存在 input，不抓取链接。

```text
资料一
山东省潍坊市杨家埠的一种民间版画
来源：杨家埠项目资料
链接：https://www.ihchina.cn/project_details/13904.html

资料二
杨家埠木版年画分钩描、刻版、印刷3道工序
来源：杨家埠工艺资料
链接：https://www.ihchina.cn/project_details/9691
```

B 的稳定 src_ 编号保存在 sources.origin_id，A 展示别名为 S1、S2；所有 claims 的 cite_ids 和 quotes.source_id 同步映射。supported 映射为 verified；不足项映射为 needs_check，已被 B 替换的候选引文只留诊断历史，不冒充当前正文依据。B 核心的模型名、提示词版本、生成时间和输入摘要保留在 ai_meta；界面显示 model、prompt_version 和明确 notice。原有 A 字段保持不变，增加 mode、ai_meta 等审计字段。

成功后创建新 A 草稿 version=1，不覆盖原稿。人工修改和导出继续使用既有接口，不再次调用模型。A 原版在生成成功后仍要求手动点保存才允许页面导出；保存回执不刷新 claims，需重新打开查看服务端更新后的待复核信息。这些前端行为本轮仅记录。

## 错误、超时与追问

- 422 `AI_INPUT_INVALID`：资料格式、长度或来源链接无效。
- 503 `AI_NOT_CONFIGURED`：缺少有效模型配置，未调用模型、未创建草稿。
- 502 `AI_GENERATION_FAILED`：模型服务或核验失败，响应不包含提供方异常文本或凭据。
- 504 `AI_TIMEOUT`：生成与核验总时限超出；没有创建草稿，超时工作线程即使稍后结束也不能写库。
- 追问：AI入口现已接通，错误、版本及重新核验行为见 `B_REFINE_INTEGRATION.md`；保留的非AI入口仍返回501。

`A_AI_TIMEOUT_SECONDS` 默认 45，允许大于 0 且不超过 50 秒，早于 A 原版默认 60 秒客户端超时。B 的每次 HTTP 超时还受剩余总预算限制。服务端时限到达后，迟到结果不落库，且不再开始下一轮核验。浏览器主动断开本身不能保证立即取消已经发出的上游请求。B 自己报告的服务连接/读取错误仍统一为 502；总时限为 504。

A 原版的本地导出兜底、空引文通用说明、刷新不自动打开上次草稿及人工确认状态未随 PUT 发送等行为不改。浏览器下载必须用服务端 export 200 与实际文件内容一致作为成功证据。真实模型、显式回放和故障模拟应分别报告，不能用回放通过替代真实验收。

## 供 B 复验

在独立、干净的检出目录获取交付分支：

```powershell
git clone --branch feature/b-ai-refine https://github.com/Weiw0520/AI-Damoxing-Chuangxin-Chuanbo-Dasai.git
Set-Location AI-Damoxing-Chuangxin-Chuanbo-Dasai
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

先运行不调用外部模型的测试。以下数据库路径只用于模块初始化，测试本身仍使用临时库：

```powershell
$env:DRAFT_DB_PATH = Join-Path $PWD 'data\abc-b-test-import.sqlite3'
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

真实复验时，在同一个后端终端使用独立数据库，并隐藏输入密钥。下列命令不把密钥写入文件或命令历史，也不打印其值：

```powershell
$env:DRAFT_DB_PATH = Join-Path $PWD 'data\abc-b-real-review.sqlite3'
$env:AI_BASE_URL = Read-Host '兼容服务基址（不含 /chat/completions 后缀）'
$env:AI_MODEL = Read-Host '实际可用的模型 ID'
$bReviewKey = Read-Host 'AI_API_KEY（隐藏输入）' -AsSecureString
$env:AI_API_KEY = [System.Net.NetworkCredential]::new('', $bReviewKey).Password
Remove-Variable bReviewKey
$env:A_AI_TIMEOUT_SECONDS = '45'
.\.venv\Scripts\python.exe -m uvicorn backend.a_ai_main:app --host 127.0.0.1 --port 8000
```

另开前端终端，按前面的 `npm ci`、`VITE_USE_MOCK=false` 和 5173 启动命令操作。需配置独立核验模型时，在后端启动前设置 AI_VERIFY_MODEL；否则沿用 AI_MODEL。后端只读进程环境，不自动加载 .env。

B 应分别跑普通资料和缺票价需求，确认响应为 mode=real，并核对 ai_meta、引文和逐段状态；走完查看依据、人工修改保存、服务端下载、刷新及重启读取。重启时保留同一 DRAFT_DB_PATH，只重新执行后端启动命令，不要换库。新一轮验收应记录模型、非敏感配置、耗时和真实结果，不把 mode 字段本身当成独立调用证明。

非AI入口追问仍为501；AI入口已接通追问。430×932窄屏从对话列表点新建后看不到资料表单的问题仍保留，追问补丁没有修改该布局。真实复验结果应另行补充，不覆盖既有回放记录。

## 2026-11-20最终追问复验

当前166项后端测试通过；普通案例精简、连续追问、依据说明及缺票价防编造完成真实调用复验。Windows Edge网页补齐P2的S1类别和S2工序引文，人工改句保存，普通与缺票价两份实际TXT均与export 200内容一致，最新v5同库重启读取完整一致。原离线基线与失败记录保留，最终结论、源码绑定和边界见B_REFINE_REAL_ACCEPTANCE.md；不把源码尚未提交时的ec50729单独当作新增追问的测试提交。
