# 真实文案生成与依据核验

## 调用协议

```python
from backend.generator import Generation, Source
from backend.real_generator import generate

result: Generation = generate(sources, brief, platform)
```

输入 `sources` 为已分配稳定 sourceId 的 `list[Source]`，每项含 title、text 和可选 url；brief 为宣传需求，platform 为目标平台。

返回 Generation，包含 mode 和非空 blocks。每段含 blockId、text、status、evidence 和 reviewReason；evidence 含 sourceId、quote。Source 和 Generation 类型定义沿用 `backend/generator.py`，后端路径及数据结构见 `API_CONTRACT.md`。

| 状态 | 含义 |
| --- | --- |
| supported | 引文、语义及现有保守检查通过 |
| needs_review | 资料不足或表达未获得充分支持 |
| edited_needs_review | 后端保存人工修改时设置，旧依据移入历史 |

资料编号保持输入值不变。引用必须逐字连续出现在对应资料正文中。标题、链接和宣传需求不能替代正文事实依据。

## 流程

1. 生成：根据正文、宣传需求和平台输出分段文案及引文。
2. 结构检查：确认来源编号存在，引文是对应正文中的连续片段。
3. 独立语义核验：单独请求模型，审查整段的全部事实，包括否定、范围、条件、生产方式及身份称呼。
4. 保守检查：比较数字、年份，检查费用、全程手工、排除工业生产和非遗身份等表述是否缺乏必要词证。
5. 结果整理：不足的段落返回待核验安全占位；缺失票价统一返回一条提示，不编造价格、免费或优惠结论。

单次生成包含两次串行模型调用。生成或核验失败时返回错误，不自动切换为模拟成功。

## 模型配置

| 环境变量 | 含义 / 默认值 |
| --- | --- |
| AI_BASE_URL | 兼容 Chat Completions 的服务地址；不含 `/chat/completions` 后缀 |
| AI_API_KEY | 运行环境提供的调用凭证 |
| AI_MODEL | 生成模型 ID，必须显式设置 |
| AI_VERIFY_MODEL | 可选独立核验模型；省略时使用生成模型 |
| AI_TIMEOUT | 单次网络超时秒数，默认60，允许1–120 |
| AI_MAX_TOKENS | 单次输出上限，默认4096 |

当前统一案例记录的配置为 `AI_MODEL=qwen4-max`、`AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`。服务需支持 JSON Object、temperature 和 max_tokens 参数。配置其他服务时需确认其兼容性。

模型地址使用 HTTPS，本机 localhost/127.0.0.1 服务可使用 HTTP。密钥不写入返回结果。

## 独立运行

在项目根目录、模型环境变量已设置的终端执行：

```powershell
.\.venv\Scripts\python.exe -m backend.real_generator --request examples/b_generator/02_request_normal.json --output outputs/normal.real.json
.\.venv\Scripts\python.exe -m backend.real_generator --request examples/b_generator/03_request_missing_price.json --output outputs/price.real.json
.\.venv\Scripts\python.exe -m scripts.check_b_examples --normal outputs/normal.real.json --price outputs/price.real.json
```

CLI 接受未编号的案例 JSON，按后端相同规则分配 sourceId。Python 调用则直接传入后端已有的 Source。

离线回放需显式传 `--replay examples/b_generator/fixtures/normal.json` 或对应的 missing_price.json。回放输出 mode=mock，并标明未调用真实模型；回放绑定输入摘要，不能套用到其他请求。结果检查脚本默认要求 real，离线演示需显式加 `--allow-mock`。

## 服务接入

使用 `create_app(db_path=..., generator=generate)` 注入真实生成器，或启动已有 `backend.real_app:app`。默认 `backend.main:app` 保持模拟模式。生成只在创建草稿时运行；读取、修改、导出从数据库获取，不重新生成。

保存后以前端收到的完整 Draft 更新页面状态。下载为 GET export 的 text/plain 响应，需要按文本或 Blob 处理。

## 错误与边界

| HTTP | code | 情况 |
| --- | --- | --- |
| 503 | ai_not_configured | 模型配置缺失或无效 |
| 502 | ai_generation_failed | 模型服务、JSON或核验结构失败 |
| 422 | ai_input_invalid | 输入超出生成器边界或来源编号冲突 |

最多30条来源、每条正文20000字符、正文合计60000字符、需求4000字符、平台80字符；超限报错，不静默截断。

检查范围为“输入资料能否支持表达”，不会自动访问来源链接，也不会证明原资料绝对真实。正则保护只是保守的缺证检查，不能证明语义充分支持；模型仍可能误判，发布前需要人工复核。数字保护可能拦截编辑性计数或复杂单位转换，应保留原始候选定位原因。
