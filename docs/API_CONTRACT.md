# A：API 合同 v1

本地地址 `http://127.0.0.1:8000`；启动与 CORS 配置见根目录 README。请求使用 `Content-Type: application/json`。所有字段区分大小写。可选 url 可省略或为 null；未知请求字段返回 422。交互文档 `/docs`，机器可读 schema `/openapi.json`。

## POST /api/drafts

请求：

```json
{"sources":[{"title":"山东非遗资料","text":"潍坊风筝历史悠久，具有鲜明的地方特色。","url":"https://example.com/source"}],"brief":"介绍山东非遗体验，吸引游客","platform":"小红书"}
```

成功 201，返回完整 Draft，见 [example-draft.json](example-draft.json)，可直接用于前端 fixture。示例资料为联调文本，链接为占位地址，不是经过核实的权威来源。sourceId 为规范化 title、text、url 的 SHA-256：title/text 去掉首尾空白后计算，url 省略等同 null；规范化后的内容变化会改变 ID，相同资料跨请求一致。保留输入资料顺序。示例中的 draftId 和时间仅为 fixture，调用后续接口须使用本次 POST 返回的 draftId。

## GET /api/drafts/{draftId}

无请求体。成功 200，返回同一完整 Draft，包含数据库最后保存的 blocks 和 history。响应结构与 POST 相同。

## PATCH /api/drafts/{draftId}

请求示例（blockId 取自已返回草稿）：

```json
{"edits":[{"blockId":"block_1","text":"来山东，感受非遗匠心；具体体验安排请提前核实。"}]}
```

成功 200，返回完整 Draft。实际改变的段落响应示例：

```json
{"blockId":"block_1","text":"来山东，感受非遗匠心；具体体验安排请提前核实。","status":"edited_needs_review","evidence":[],"reviewReason":"人工修改后待复核，旧依据已移至历史记录。"}
```

只有 text 完全不同时才记录修改。历史项包含 blockId、before（修改前完整段落含旧依据）、after（修改后完整段落）、editedAt。时间为 UTC ISO 8601。未修改段落不变，完全无变化时 updatedAt 不变。重复 blockId 返回 422；任意不存在的段落返回 404，整批不保存。并发请求按 SQLite 写事务顺序处理，同一段落以后提交的修改为准；本版没有乐观锁。

## GET /api/drafts/{draftId}/export

无请求体。成功 200，`Content-Type: text/plain; charset=utf-8`，`Content-Disposition: attachment; filename="draft_xxx.txt"`。返回 UTF-8 字节，无 BOM；按原段落顺序包含最新保存正文和中文状态标记，不包含历史旧正文。使用同一 draftId 从数据库读取，不触发生成器。前端应先等待 PATCH 成功再下载。

```javascript
const base = 'http://127.0.0.1:8000';
const response = await fetch(`${base}/api/drafts/${draftId}/export`);
if (!response.ok) throw new Error(await response.text());
const url = URL.createObjectURL(await response.blob());
const a = document.createElement('a');
a.href = url; a.download = `${draftId}.txt`; a.click();
URL.revokeObjectURL(url);
```

## 状态与字段

Draft 包含 draftId、mode、sources、brief、platform、blocks、history、createdAt、updatedAt。blocks 每项始终包含 blockId、text、status、evidence、reviewReason；evidence 每项包含 sourceId 和 quote。

| status | 展示建议 |
| --- | --- |
| supported | 有资料依据 |
| needs_review | 待核验 |
| edited_needs_review | 人工修改后待复核 |

`mode=mock` 必须在前端显著展示“模拟联调，尚未完成真实 AI 核验”，不能把 supported 直接宣传为真实核验通过。未来 B 接入可返回 mode=real，路径、字段不变。前端根据 evidence.sourceId 关联 sources，并展示 quote 与 reviewReason。

## 错误示例

三个按 ID 读取的接口（GET、PATCH、export）在草稿不存在时均为 404：

```json
{"detail":{"code":"draft_not_found","message":"草稿不存在","draftId":"missing"}}
```

PATCH 段落不存在 404：

```json
{"detail":{"code":"block_not_found","message":"段落不存在，全部修改均未保存","blockIds":["missing"]}}
```

PATCH 重复段落 422：

```json
{"detail":{"code":"duplicate_block_id","message":"同次修改不能包含重复段落 ID"}}
```

POST 空 sources、空白标题/正文/brief/platform，PATCH 空 edits、空白 text，均返回 FastAPI 标准 422 验证错误。例如 sources=[]：

```json
{"detail":[{"type":"too_short","loc":["body","sources"],"msg":"List should have at least 1 item after validation, not 0","input":[],"ctx":{"field_type":"List","min_length":1,"actual_length":0}}]}
```

验证错误的 msg/ctx 随依赖版本可能略变，前端以 HTTP 状态及 detail[].loc 定位字段。GET/export 无其他输入验证要求。

POST 在生成器引用无效时返回 502：

```json
{"detail":{"code":"invalid_generation","message":"生成器返回无效原文依据"}}
```

生成器返回重复段落 ID 也为 502，message 为“生成器返回重复段落 ID”。
