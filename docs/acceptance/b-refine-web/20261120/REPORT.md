# B真实网页验收自动记录

状态：browser-checks-completed
重启读取：passed

实际浏览器操作与API直读在steps中分别记录。
浏览器下载TXT原始字节保留，去除UTF-8 BOM后与服务端content逐字比较；不接受本地导出兜底冒充服务端导出。
未收取模型密钥、认证头、环境变量或其他草稿内容。语义仍需审阅完整响应、文本变化与截图。

| 步骤 | HTTP | 秒 |
| --- | --- | --- |
| price.preflight | 200 | 0.0088 |
| price.open | 200 | 0.0108 |
| price.refine | 200 | 16.9749 |
| price.save | 200 | 0.0164 |
| price.after-ui-save | 200 | 0.0109 |
| price.export | 200 | 0.0079 |
| normal.open | 200 | 0.0667 |
| normal.export | 200 | 0.012 |
| price.final-open | 200 | 0.0073 |
| price.after-restart | 200 | 0.0355 |
| normal.after-restart | 200 | 0.021 |
