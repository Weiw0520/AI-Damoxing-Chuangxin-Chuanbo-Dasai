# 新建草稿与底部输入框修复验收

日期：2026-11-17（北京时间）。工作分支 `fix/new-draft-and-chat`，基于 fetch 后最新 `origin/main`：`dcc8f33ab5647f2e5315381059b42e219a2de99d`（PR #1 合并提交）。开始时工作区干净，直接建立分支；未提交、未推送、未合并、未部署。

## 复现与原因

修复前的实际浏览器检查发现：

- 从已生成草稿点“新建”后，资料确实清空，但第一份标题框不聚焦。浏览器回归脚本首先报 `New draft did not focus the first source title`。
- 900px 下从“对话”（旧导航名称）进入草稿栏再点“新建”，表单不可见，正文导航也不可见。检查结果 `formVisible=false, navVisible=false`。
- Composer 没有挂载到中间栏，旧组件依赖的 refine 动作已经不存在。后端当前仍只有草稿创建、读取、PATCH 保存和 TXT 导出，没有可用多轮接口。

根因是草稿重置动作与 App 的局部栏位状态脱节，且导航本身位于会被隐藏的中间栏。修复将栏位状态与新建动作联动，导航放到三栏之外；新建确认后等待 DOM 更新，再聚焦并滚动到第一份资料标题。

## 当前底部输入框的真实能力

按钮名称为“按新要求生成新草稿”。请求仍为 `POST /api/drafts`：沿用当前草稿的独立 sources 和 platform，将原 brief 与用户新增要求合并后创建另一份草稿。当前草稿不 PATCH、不覆盖，创建成功后切到新编号，并显示原稿编号。左栏或按编号 GET 可重新打开原稿。

请求失败时保留当前草稿、用户输入和页面修改，显示错误；进行中禁用输入/提交和冲突操作，防止重复提交。若当前正文有未保存修改，先提示保存。已有 C 的核验状态、保存和导出契约不变。

这不是多轮 AI 对话。当前 mode=mock，生成器只演示创建流程，不实际理解新增要求来完成真实改写或核验，文案可能与原稿相似。界面明确标识模拟模式和这一限制。

## 浏览器实测

使用 Playwright 驱动本机 Edge，前端 127.0.0.1:5174，通过 Vite 代理访问后端 127.0.0.1:8010。数据库为独立的 `data/new-draft-chat-20261117.sqlite3`，没有覆盖原库。

| 检查 | 结果 |
| --- | --- |
| 桌面 1440×1000、窄屏 900×1000、手机 390×844：草稿→新建 | 显示空白资料表单，标题框获得真实焦点，URL 不再带旧 draftId。 |
| 未保存正文→新建→取消 | 三种宽度均保留原 draftId 和未保存文字；返回文件栏仍能看到编辑内容。 |
| 未保存正文→新建→确认 | 三种宽度均切到空白表单并聚焦；已保存原稿仍可按编号读回。 |
| 窄屏导航 | 草稿、正文、文件栏之间可以往返，导航始终可见。手机确认弹窗原先超宽，现已约束在可用宽度内；顶部保存状态不再挤成竖排。 |
| 底部输入框 | 打开或生成草稿后可见；长正文测试只增加消息区滚动，页面不被撑高，输入框与提交按钮留在视口内。 |
| 新要求失败及重试 | 浏览器单次模拟创建接口 503，原稿编号与输入均保留；重试真实 POST 成功。503 为验收注入，未改后端行为。 |
| 防重复提交 | 延迟单次创建响应，输入和按钮禁用；按 Enter 不增加重复 POST。 |
| 新稿与原稿 | 新编号不同，原资料 sourceId/title/text/url 完全相同，brief 包含原需求和新增要求；原稿 GET 响应与创建时相同，未被覆盖。 |
| 依据、修改、保存与下载回归 | 引文可打开；修改第二段后 PATCH 成功，状态为 edited_needs_review，第一段依据不变且仍可查看。实际 TXT 包含新句、不含旧句，含待复核标记，与服务端导出字节完全相等。 |

最后一次完整验收的原稿编号为 `draft_0ebd8614de7f4d938e96120b8551316e`，新稿编号为 `draft_578253adf2a24f83a2916f945ec9f109`。TXT SHA-256：`30d6890a3501d7152eb50be6eb829d5606227957e9e6758570b5961523c55364`。

最终手机布局测量：页面宽度 390、顶部操作右边界 376、输入框底部 790、Composer 底部 844，均在 390×844 视口内。浏览器无未捕获 JavaScript 异常，未调用 `/chat` 或 `/refine`。

## 测试与文件

修改文件：`frontend/src/App.vue`、`frontend/src/stores/draft.js`、`frontend/src/styles/app.css`；组件 `ChatStream.vue`、`Composer.vue`、`ConfirmModal.vue`、`ConversationList.vue`、`DraftCard.vue`、`ExportModal.vue`、`FilePanel.vue`；`FRONTEND_GUIDE.md`。新增本记录及浏览器回归脚本 `frontend/qa/new-draft-and-chat.cjs`。后端源码与 API_CONTRACT.md 保持不变。

- 已有前端 `npm test`：2 项通过。
- 已有后端 `python -m pytest backend/tests -q`：5 项通过，1 条既有 TestClient/HTTPX 弃用警告。
- 最终 `npm run build`：通过（Vite 6.4.6）。
- `git diff --check`：通过；`backend/` 和 `docs/API_CONTRACT.md` 未改。
- 新增可重跑的浏览器回归脚本 `frontend/qa/new-draft-and-chat.cjs`。运行方法见根目录 `FRONTEND_GUIDE.md`；对独立验收数据库执行，脚本会创建测试草稿。

改动文件：`frontend/src/App.vue`；组件 ChatStream、Composer、ConfirmModal、ConversationList、DraftCard、ExportModal、FilePanel；`frontend/src/stores/draft.js`；`frontend/src/styles/app.css`；上述 QA 脚本；`FRONTEND_GUIDE.md`；本记录。保存/导出组件的变动仅用于创建请求进行中禁用冲突操作。

本机截图、下载、临时探针都留在已忽略的 `output/playwright/`：`new-chat-new-1440.png`、`new-chat-new-900.png`、`new-chat-new-390.png`、`new-chat-phone-final.png`、`new-chat-long-copy.png`、`new-chat-final-desktop.png`、`new-chat-regression.txt`。这些运行产物不属于交付源码。

未验证真实 AI 对话/改写、跨浏览器兼容、生产部署和多用户并发。本轮只使用 C 的现有模拟生成器。专用验收前后端与最终浏览器保留运行，便于本机查看；不需要 API 密钥。
