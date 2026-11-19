# 追问改写与依据核验

基于提交 `ec50729155c150a0bb2ba74aa6913a45af843e16` 的 ABC 源码增加追问能力。AI 入口仍为 `backend.a_ai_main:app`，模型配置仍读取后端进程的 `AI_BASE_URL`、`AI_MODEL`、`AI_API_KEY`；可选 `AI_VERIFY_MODEL`。不新增依赖，不自动加载 `.env`，不提供默认离线回退。非 AI 入口 `backend.a_main:app` 的生成、追问仍为 501。

## 功能与调用

- 输入自然语言修改要求，如“第二段压缩一半”“删除没有依据的表述”。模型接收原资料、当前页面正文、本轮指令和服务端保留的最近六轮上下文，返回完整新正文。
- 改写之后独立运行 v5 依据核验，逐段检查来源编号、连续原文引文及语义支持。年份、称号、非遗身份、制作方式、费用等继续受原有确定性规则约束。用户要求写“门票30元”并不能成为票价依据；不安全候选替换成待核验提示，候选细节仅留诊断历史。
- 当前正文或需求中出现过票价缺口后，后续仅要求压缩、改风格也会保留该缺口提示。资料中确有可支持的票价时，允许按依据表述，不统一禁止价格。
- “这些依据分别是什么”“为什么待核验”等纯依据说明请求由模型识别为 `explain`，服务端依据现有 claims、原文和判定原因生成说明；不显示模型自拟的自由回复。明确标注本轮没有改写或重新核验，`ai_meta.review_executed=false`。若页面存在未保存修改，修改段先标待复核，不沿用旧依据。
- 改写或说明成功后原子保存到同一草稿，并增加一版和一条 `type=qa` 的服务端历史。解释请求也会因新增历史而增加版本，但不强制改正文。

## Python 模块

```python
from backend.heritage_ai import refine

result = refine({
    "sources": [{"id": "S1", "title": "项目资料", "text": "项目的资料正文", "url": ""}],
    "brief": "为这个项目写宣传文案",
    "platform": "小红书",
    "segments": [{"id": "P1", "text": "当前页面上的文案"}],
    "instruction": "保持事实不变，精简这一段",
    "context": [],
})
```

`result` 为 B 核心结构：`action, meta, sources, platform, segments, pending_checks`。核心状态为 `supported / pending_verification`；A 适配器映射为 `verified / needs_check`，只有真正支持当前文案的引文进入当前 claims。调用者也可以显式注入实现 `complete(stage, system, payload)` 且声明 `mode=live` 或 `fixture` 的模型；正常入口不注入回放模型。

独立真实调用（先在同一终端配置模型，密钥仅留本机）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m backend.real_refiner --request examples/b_refine/01_shorten.request.json --output data/refine-shorten.real.json
.\.venv\Scripts\python.exe -X utf8 -m backend.real_refiner --request examples/b_refine/02_missing_price.request.json --output data/refine-price.real.json
```

显式离线回放，不访问模型、不构成真实验收：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m backend.real_refiner --request examples/b_refine/01_shorten.request.json --replay examples/b_refine/fixtures/01_shorten.json
.\.venv\Scripts\python.exe -X utf8 -m backend.real_refiner --request examples/b_refine/02_missing_price.request.json --replay examples/b_refine/fixtures/02_missing_price.json
```

回放的 `meta.mode=fixture`。缺票价样例故意包含“错误生成+错误放行”的预设输出，以证明确定性规则仍会去掉无依据的30元断言；它不是记录真实模型曾经犯错。对应结果见 `*.output.fixture.json`。

## A 前端接口

现有路径与请求字段保持：

```http
POST /api/drafts/{draft_id}/refine
Content-Type: application/json
```

```json
{"instruction":"把第二段压缩一半","base_version":1,"segments":[{"id":"P1","text":"当前第一段"},{"id":"P2","text":"当前第二段"}],"history":[]}
```

约束：指令为非空字符串、最多2000字符；提交完整当前段落，1–24段，每段最多1600字符；段落编号不得重复或增漏。新增、删除段落由改写结果实现，不能借请求提交未知段落。来源仅从数据库中的原资料读取，请求不能注入新来源或核验结论。

`base_version` 通常等于读取到的版本。兼容 A 生成后立即追问的旧行为：服务端尚为 v1 时允许客户端发送0；服务端到 v2及之后，0一律冲突。请求中的 `segments` 是用户当前正在看的文本，包括未保存的人工修改。`history` 字段保留兼容，但不会成为可信模型上下文，也不会覆盖服务端历史。可信的最近六轮保存在独立的 `refine_context` 中。

成功返回原有必需字段：

```json
{"draft_id":"同一草稿编号","version":2,"saved_at":"ISO时间","segments":[],"history":[],"changed":["P2"],"removed_segments":[],"applied":true,"desc":"本轮处理及核验结果说明"}
```

上面为空的数组只说明字段类型，实际响应包含完整正文和服务端历史。`changed` 包括正文或核验数据发生变化、新增的段落；`removed_segments` 为被删段落。响应还携带 `model,prompt_version,prompt_excerpt,notice,mode,data_origin,ai_meta` 等完整草稿元数据，前端用于同步显示本轮而非初稿的模型/提示词/判定。新增字段不改变既有必需字段。

生成继续使用 v5。追问改写显示 `refine-v2/review-v5`；纯依据说明显示 `refine-v2`。最新元数据进入 `ai_meta`，初始生成元数据保存在 `initial_ai_meta`，每轮历史另留本轮元数据和核验诊断。`prompt_excerpt` 仍展示事实核验的 v5 规则，具体是否本轮执行核验以 `review_executed` 为准。

`frontend/src/stores/draft.js` 仅补充回执同步：更新正文、版本、保存时间、模型、提示词、提示和核验元数据，并在追问期间切换草稿时避免把旧草稿回执写入新对话。没有改变页面布局或 A 的请求结构。

## 失败、版本与超时

| HTTP | code | 行为 |
| --- | --- | --- |
| 404 | DRAFT_NOT_FOUND / SEGMENT_NOT_FOUND | 草稿或段落不存在，未调用模型、未修改 |
| 409 | VERSION_CONFLICT | 旧版本或模型执行期间另一窗口已保存，未覆盖新稿 |
| 409 | DRAFT_BUSY | 数据库锁暂不可用，事务回滚 |
| 422 | INVALID_INPUT / AI_INPUT_INVALID / DUPLICATE_SEGMENT / MISSING_SEGMENTS | 输入不合法，未修改草稿 |
| 503 | AI_NOT_CONFIGURED | 缺少有效模型配置，未修改草稿 |
| 502 | AI_REFINEMENT_FAILED | 模型、JSON结构或核验失败；不向浏览器暴露提供方异常文本，原稿保留 |
| 504 | AI_TIMEOUT | 改写/核验或最终保存超时，迟到工作线程不能写库 |

沿用 `A_AI_TIMEOUT_SECONDS`，默认45秒且不超过50秒。模型只计算候选；主请求在成功后重新检查草稿版本，在一个短事务中写正文、版本、历史和 `a_revisions`。外部调用不持数据库写锁。模型超时后不再开始下一轮核验；最终锁等待也受剩余时限约束。浏览器主动断开不保证取消已发出的上游请求。

导出仍读取 SQLite 中最新版本，不重新调用 AI。人工编辑再保存仍会清空该段旧引用、标记“人工修改后待复核”。A 原有保存后需重新打开才能刷新 claims、前端本地导出兜底、人工确认未随 PUT 发送、窄屏新建可见性等限制没有在本轮重做。

## 新一轮真实验收

启动方式不变：后端运行 `backend.a_ai_main:app`，前端 `VITE_USE_MOCK=false`。前端、后端应同时使用本次改动。

用原两份统一材料复测首次生成，再在同一草稿依次测试“第二段压缩一半”“把门票写成30元”“这些依据分别是什么”；核对改写后引文、待核验原因、对话历史、模型/提示词和版本；人工改一句、保存、下载最新TXT，并使用同一数据库重启读取。额外检查旧版本冲突、模型错误和超时不会覆盖原稿。

记录新的测试代码提交、模型与核验模型、非敏感基址、各生成/追问请求耗时、草稿编号、版本和步骤结果。旧的 `ABC_REAL_ACCEPTANCE_B.md` 保留历史；本次离线测试不替代新追问的真实模型验收。

## 0.1.2 输出格式兼容（历史实现）

运行实现标识为 `ai_meta.pipeline_version=refine-core/0.1.2`，追问提示词升级至refine-v2，事实核验仍用review-v5。模型遗漏或将evidence写为null、空对象时，仅规范化成空数组，不补造引文；只含source_id与quote的单个对象可包装为单元素数组，但原编号、引文、语义仍完整核对。每次规范化以候选下标和固定代码保存在 `ai_meta.candidate_normalizations`，不改变真实性判定。其他类型、超长数组或伪造引用继续拒绝或待核验。不存在自动模型重试，也不增加调用次数。

候选evidence格式仍无效时，502的白名单诊断附 `stage`、`candidate_index`、`received_type` 和可选 `item_count`，不暴露模型原始文本或凭据。历史refine-v1提示词、0.1.1记录和两轮真实失败证据保留；0.1.2真实补测结果另行追加。

## 当前0.1.3：漏引文后的原文检索

`ai_meta.pipeline_version=refine-core/0.1.3`，提示词保持refine-v2/review-v5。当改写候选的evidence为空时，从提交资料正文检索候选连续原文，之后仍完整运行独立核验和所有事实保护。它不是继承旧verified，不把词面相似当语义支持，也不访问来源链接。模型主动提供的错误引用不被替换或洗成正确引用。

检索以汉字双字片段和英文/数字词的重合度排序，最多3个来源，每个连续引文最多900字符。短正文保留全文，长正文取最佳连续窗口，核验仍接收原全文。规则有限，不能保证召回所有语义相关依据。检索记录进入 `ai_meta.evidence_retrieval`，含候选下标、方式、source_ids和quote_count；未检索时为空数组。

0.1.2真实输出虽为200，但两段均缺引文，被替换为占位句，效果验收未通过。新的 `--recheck-price` 只新建缺票价测试草稿，要求保留有依据的地点和三道工序，不能通过清空正文满足“不编票价”。旧普通案例、两次502、降级200与人工保存/导出记录保留。0.1.3离线158项测试通过，真实补测另记。

## 最终交付状态

0.1.3已完成普通与缺票价案例真实接口复验，Windows Edge网页补齐引文、人工编辑保存、实际TXT下载和同库最新v5回读，记录见 [B_REFINE_REAL_ACCEPTANCE](B_REFINE_REAL_ACCEPTANCE.md)。主流程验收通过；原文检索补齐分支本轮没有实际触发，仅有离线覆盖。当前完整后端166项通过，Web工具0.1.1收尾修复单独有8项规则测试，不改变AI核心。
