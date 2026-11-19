# B 追问模块示例

`01_shorten.request.json` 使用两份杨家埠资料和当前两段文案，要求精简第二段；`02_missing_price.request.json` 使用相同资料，要求写入资料没有提供的30元门票。

输入可用于 `python -m backend.real_refiner --request ...` 的真实调用。默认读取本机模型环境变量；不自动回放。

`fixtures/` 与 `*.output.fixture.json` 全部是显式离线测试材料，`meta.mode=fixture`，不代表真实模型验收。缺票价预设故意让错误候选和错误核验同时出现，以确认安全门仍拦截30元事实，返回段落待核验和全局票价缺口。

集成接口、启动和验收说明见 `docs/B_REFINE_INTEGRATION.md`。

## 真实网页同输入示例

`03_citation_completion.request.json` 是从真实网页请求及其服务端草稿还原的B核心输入（资料、当前正文、追问和可信上下文），规范化输入摘要与真实响应的 `ai_meta.input_sha256` 完全一致。可直接用 `python -m backend.real_refiner --request examples/b_refine/03_citation_completion.request.json` 独立调用；需要本机模型配置，真实输出会随模型运行变化。

`03_citation_completion.output.a-api.real.json` 是同次调用实际收到的A适配接口响应，保持原样，字段格式是A结构。独立CLI输出B核心结构，不能把该A响应冒充独立CLI原始输出。当前网页结果使用S1类别和S2工序引文，门票仍为资料不足待核验。

01/02的output.fixture已按当前0.1.3重新生成并明确标记fixture；它们仍是离线示例，不是新增的真实调用记录。
