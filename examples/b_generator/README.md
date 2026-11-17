# 杨家埠木版年画统一案例

两份请求使用完全相同的来源。正常请求介绍所在地和制作工序；第二份仅增加门票问题。

| 资料 | 输入原文 | 来源 |
| --- | --- | --- |
| 所在地与类别 | 山东省潍坊市杨家埠的一种民间版画 | https://www.ihchina.cn/project_details/13904.html |
| 工序 | 杨家埠木版年画分钩描、刻版、印刷3道工序 | https://www.ihchina.cn/project_details/9691 |

以输入短摘为本次事实依据。链接用于追溯，不表示程序已经抓取整页。两条短摘没有提供门票价格。

- `02_request_normal.json`：普通宣传需求。
- `03_request_missing_price.json`：补充询问票价。
- `normal.output.real.json`、`missing_price.output.real.json`：本次通过内容核对的真实模式返回记录。
- `normal.output.mock.json`、`missing_price.output.mock.json`：显式离线演示输出。
- `fixtures/*.json`：绑定相应输入摘要的手工回放数据，不是真实生成证明。

真实输入输出使用 Generation 协议，后端随后包装为完整 Draft。sourceId 根据 title、text、url 规范化后的内容稳定计算。模式、状态及引文说明见 `docs/AI_GENERATOR.md`。
