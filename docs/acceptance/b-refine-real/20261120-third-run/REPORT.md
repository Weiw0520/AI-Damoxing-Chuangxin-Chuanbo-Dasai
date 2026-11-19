# B追问接口验收自动记录

开始时间（UTC）：2026-11-19T17:28:45.354477+00:00
执行模式：live-required

本报告仅记录接口和确定性检查，不替代语义复核、页面展示与实际浏览器下载验收。

| 步骤 | HTTP | 请求耗时（秒） |
| --- | --- | --- |
| normal.generate | 200 | 14.807 |
| normal.shorten | 200 | 14.8373 |
| normal.followup | 200 | 13.7519 |
| normal.explain | 200 | 2.3752 |
| normal.save | 200 | 0.0099 |
| normal.saved-get | 200 | 0.0047 |
| normal.export | 200 | 0.0413 |
| missing_price.generate | 200 | 39.6992 |
| missing_price.force-price | 502 | 12.1429 |
| missing_price.before-retry | 200 | 0.0376 |
| missing_price.force-price.2 | 502 | 12.3579 |
| missing_price.before-retry.2 | 200 | 0.0706 |
| missing_price.force-price.3 | 200 | 14.5015 |
| missing_price.save | 200 | 0.0101 |
| missing_price.saved-get | 200 | 0.0041 |
| missing_price.export | 200 | 0.0054 |

| 自动检查 | 结果 |
| --- | --- |
| normal.shorten.version | pass |
| normal.shorten.history | pass |
| normal.shorter | pass |
| normal.followup.version | pass |
| normal.followup.history | pass |
| normal.conversation | pass |
| normal.explain.version | pass |
| normal.explain.history | pass |
| normal.explanation | pass |
| normal.saved-version | pass |
| normal.manual-review | pass |
| normal.export-content | pass |
| missing_price.failed-request-atomic | pass |
| missing_price.failed-request-atomic | pass |
| missing_price.force-price.version | pass |
| missing_price.force-price.history | pass |
| missing_price.retry-no-fabricated-price | pass |
| missing_price.retry-ticket-gap | pass |
| missing_price.saved-version | pass |
| missing_price.manual-review | pass |
| missing_price.export-content | pass |
| missing_price.export-ticket | pass |

同库重启读取：pending

## 待补人工证据

- 阅读改写前后文案，判断引文是否真正支持全部事实及修改要求是否满足。
- 网页展示新正文、新判定与真实/说明提示的截图。
- 在网页打开本次草稿并下载TXT，将实际文件与对应export响应content核对。
- 核对测试代码提交；有未提交改动时，保留源码哈希清单并在提交后说明对应关系。

## 案例执行情况

| 案例 | 状态 | 说明 |
| --- | --- | --- |
| normal | automatic-checks-completed | 自动检查完成，语义和网页检查仍待人工复核 |
| missing_price | automatic-checks-completed | 自动检查完成，语义和网页检查仍待人工复核 |
