# A 原版前端的非 AI 后端契约

入口 `backend.a_main:app`，工厂 `create_a_app(db_path=...)`。此文描述 A 的实际调用；原 C 契约 `API_CONTRACT.md` 保持不变。启动见根目录 `FRONTEND_GUIDE.md`。

## 持久化与入口

默认沿用 `data/drafts.sqlite3`，启动前可通过 `DRAFT_DB_PATH` 指定另一文件。A 只新增 `a_drafts`、`a_revisions` 表，不迁移、不改写 C 的 `drafts` 表。A 列表只列 A 格式记录；既有 C 草稿继续用 `backend.main:app` 和原 C API 读取，不自动转换。相同路径的响应结构冲突，因此 A、C 使用两个独立应用，分别启动到不同端口。原版前端默认 `/api` 代理到 8000，应在 8000 启动 A 入口。

## 路由

| 方法 / 路径 | 请求 | 成功响应 |
| --- | --- | --- |
| GET `/api/cases` | 无 | 案例输入数组：`id,no,label,hint,caseType,platform,material,requirement`，不含 `result` |
| GET `/api/drafts` | 无 | 草稿摘要数组：`draft_id,title,version,created_at,updated_at,platform,preview,stats`；stats 为 `verified,needs_check,unsupported,total` |
| GET `/api/drafts/{id}` | 无 | 最新完整 A 草稿，字段详见 `AI_TODO.md` 和 `backend/a_seed.py` 的人工样例 |
| PUT `/api/drafts/{id}` | `{base_version,segments:[{id,text}],edit_log:[],history:[]}` | `{draft_id,version,saved_at,changed_segments:[段落ID]}` |
| POST `/api/drafts/{id}/export` | `{format:"txt"或"md"或"report",history:[]}` | `{draft_id,version,format,filename,content}` JSON；A 用 content 下载 UTF-8 文件并加 BOM |
| POST `/api/extract?filename=文件名` | 原始文件字节，不是 multipart | `{filename,kind,text,chars,truncated,limit}` |
| POST `/api/generate` | `{material,requirement,platform,case_id}` | 暂无成功响应，HTTP 501，详见 `AI_TODO.md` |
| POST `/api/drafts/{id}/refine` | `{instruction,base_version,segments:[{id,text}],history:[]}` | 暂无成功响应，HTTP 501，详见 `AI_TODO.md` |

## 保存与历史

PUT 必须包含当前所有段落，不能新增、漏传或重复 ID。服务端在单个事务中校验版本和全部 ID，再比较真实文本变化；`edit_log` 不作为原文的权威来源。无变化且没有新增历史不升版本。修改前后完整段落和时间写入 `a_revisions`，同时追加服务端历史到完整草稿 `history`；客户端历史只能追加，不能覆盖既有审计记录。

变更段落的旧依据只留历史，当前 claims 改为 `needs_check`，引文清空，reason 明确“人工修改后待复核”，并添加 `review_status=edited_needs_review`。未改段落及其依据保持原样。A 原版只处理保存回执，不刷新 claims，因此保存后重新从草稿列表打开（必要时刷新页面）才呈现服务端更新后的核验信息。人工确认按钮的 claims 更改不在 A 的 PUT 请求里，后端只保留随请求提交的历史备注，不从备注推断核验通过。

例：

```json
{"draft_id":"A-MANUAL-TEST","version":2,"saved_at":"2026-11-18T05:00:00+00:00","changed_segments":["s3"]}
```

## 导出

每次按同一草稿 ID 从 SQLite 读取最新版，不生成新文案；请求的 `history` 仅与已存历史合并用于报告渲染，不写数据库，也不替换正文。TXT 包含当前标题、正文、待复核标记与非 AI 提示，不输出被替换的旧句；Markdown 和核验报告还包含来源、已有 claims 和历史，历史中可含旧句。此处报告只是已有数据汇总，不是新运行的 AI 核验。

A 原版保留了服务端导出失败时的本地导出兜底逻辑，本轮不能修改前端。验收以 POST export HTTP 200 且下载内容（去除前端添加的 BOM）与响应 content 完全一致为准；网络失败后的本地文件不能作为服务端成功的证据。

## 文件解析

支持 txt、md、markdown、csv、tsv、json、html、htm、docx；只提取文本，不抓取网页或 URL，不调用 AI。文本支持 UTF-8（含 BOM）、UTF-16 BOM、GB18030。HTML 去除 script/style；DOCX 读取正文 XML，限制 ZIP 解压尺寸并拒绝实体声明。单文件上限 5 MB，返回文本最多 20000 字符；超出字符数时 `truncated=true`，`chars` 为实际返回长度。PDF、旧 doc 和图片返回 415；空文件、损坏 DOCX 返回 422。

## 错误结构

下列业务错误与字段验证错误使用 A 客户端识别的 `detail.code` 和 `detail.message`；字段验证失败为 HTTP 422 `INVALID_INPUT`。

```json
{"detail":{"code":"VERSION_CONFLICT","message":"草稿版本已更新，请重新打开草稿后再保存；本次未覆盖。"}}
```

| HTTP | code | 场景 |
| --- | --- | --- |
| 404 | DRAFT_NOT_FOUND / SEGMENT_NOT_FOUND | 草稿或段落不存在，保存全部回滚 |
| 409 | VERSION_CONFLICT / DRAFT_EXISTS | 旧版本保存或人工导入重复编号 |
| 422 | INVALID_INPUT / DUPLICATE_SEGMENT / MISSING_SEGMENTS | 请求格式、重复或缺失段落 |
| 413 | FILE_TOO_LARGE | 上传超过 5 MB |
| 415 | UNSUPPORTED_FILE_TYPE | 不支持的文件类型 |
| 413 | DOCX_TOO_LARGE | DOCX 解压内容过大或正文加密 |
| 422 | EMPTY_FILE / INVALID_DOCX / INVALID_ENCODING | 空文件、损坏文件或无法解码 |
| 501 | AI_NOT_IMPLEMENTED | 生成、追问未接入，草稿不变 |

人工验收样例使用显式 CLI `python -m backend.a_seed --db data/a-compat-test.sqlite3 --id A-MANUAL-TEST` 导入，绝不在应用启动或 AI 端点自动生成。
