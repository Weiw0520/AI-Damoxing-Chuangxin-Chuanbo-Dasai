# AI 接入待办（A 原版前端）

当前新增可选 `backend.a_ai_main:app`，已实现 A 输入到 B 生成/核验核心的后端适配，并保留审计元数据；真实模型是否可用仍须配置后验收。本文件以下 501 说明仍适用于保留的非 AI 入口 `backend.a_main:app`。追问改写尚未实现，在两个入口均返回 501。最新启动与验收边界见 `ABC_INTEGRATION.md`。

本轮只实现非 AI 后端。`backend.a_main:app` 的生成、追问接口均返回 HTTP 501；不会创建草稿、修改正文、增加版本或写入历史，不调用外部模型，也不需要密钥。

补充 fetch 后，最新 main 已包含 PR #3 的 B 模块 `backend/real_generator.py`、`backend/heritage_ai/` 和 C 格式的独立入口 `backend.real_app:app`。这些上游文件原样保留，本轮未启动该入口、未读取模型密钥、未调用真实模型。它们输出的是 C 格式，不能直接替代 A 的 `/generate` 或 `/refine`；A 仍是上述 501 行为。后续可由 B 增加 A 结构适配和真实追问实现，具体 B 协议见 `AI_GENERATOR.md`，本轮不把上游离线回放测试算作真实 AI 联调。

## 生成与自动核验

`POST /api/generate` 接收 A 原有请求：

```json
{"material":"用户提供的原文资料", "requirement":"宣传需求", "platform":"xiaohongshu", "case_id":null}
```

当前响应：

```json
{"detail":{"code":"AI_NOT_IMPLEMENTED","message":"AI 功能暂未接入：文案生成与自动事实核验尚未实现，未创建或保存草稿。"}}
```

未来成功响应须为 A 格式完整草稿：`draft_id, version, created_at, updated_at, model, prompt_version, prompt_excerpt, notice, sources, segments, input, history`。`input` 保存原请求；`sources` 每条为 `{id,title,publisher,url,snippet}`；`segments` 每条为 `{id,type,label,text,claims}`；`claims` 每条为 `{id,anchor,status,cite_ids,quotes,reason,suggest}`，`quotes` 每条为 `{source_id,quote}`。核验状态为 `verified / needs_check / unsupported`。真实来源与引文必须可追溯；不得用示例结果当作模型结果。

后续实现位置：`backend/a_main.py` 的 `generate`，接入 B 的服务层，验证输出结构、来源 ID 和逐字引文后再用独立的真实生成持久化方法写入 `a_drafts`。`Store.insert_manual` 仅供显式人工测试导入，不能作为真实 AI 已接入的替身。成功创建新编号，不覆盖旧稿。

## 对话追问与重新核验

`POST /api/drafts/{draft_id}/refine`：

```json
{"instruction":"把结尾缩短", "base_version":1, "segments":[{"id":"s1","text":"当前正文"}], "history":[]}
```

当前 HTTP 501：

```json
{"detail":{"code":"AI_NOT_IMPLEMENTED","message":"AI 功能暂未接入：对话追问改写与自动事实核验尚未实现，原草稿未修改。"}}
```

未来成功响应应提供 `{segments,history,version,saved_at,changed,removed_segments,applied,desc}`；其中 `changed`、`removed_segments` 为段落 ID 数组，`segments` 为含 claims 的完整分段对象。与 A 的 `frontend/src/stores/draft.js` 中 `refine` 对照接入，服务端应检查基线版本、保留旧版本并重新核对改动后的 anchor、引文与来源。后续位置为 `backend/a_main.py` 的 `refine` 和 B 的改写/核验服务；本轮没有实现改写规则或模型。

自动事实核验没有独立的前端请求接口：它属于上述两项未来生成流程。当前读取和导出仅呈现已存资料，人工编辑将变更段落标为 `needs_check`，并附 `review_status=edited_needs_review`，不执行自动判断。A 的人工确认按钮只在浏览器修改 claim；原 PUT 请求不含 claims，后端不会根据历史文字推断核验结论。

## 三种模式必须区分

- A 原有“示例数据模式”：`VITE_USE_MOCK=true` 或页面“切换”，使用 `frontend/src/api/fixtures.js` 的预制结果和浏览器内存。前端保持原样，不是实际 AI，刷新会丢失内存草稿。
- A 的“真实后端模式”：表示走 HTTP；本轮有列表、读取、解析、保存、历史和导出，**不表示 AI 已上线**。人工测试稿明确带非 AI 提示，普通空库不会自动出现假草稿。`/api/cases` 只返回案例输入，不含示例生成结果。
- 原 C 入口 `backend.main:app`：仍遵循 `docs/API_CONTRACT.md`，默认 `mode=mock`。它与 A 的路由结构冲突，分别启动；不能把 C 模拟输出当作 A 的真实生成结果。

接入后保持 A 的接口路径、原请求/响应字段和 `detail.code / detail.message` 错误结构；更改后新增覆盖版本冲突、失败回滚、引用有效性及未覆盖原稿的测试。
