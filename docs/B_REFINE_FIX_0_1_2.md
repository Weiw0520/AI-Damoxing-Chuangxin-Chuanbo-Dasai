# 追问输出格式兼容：0.1.2

## 已确认的问题

B的第二次真实补测返回502 `AI_REFINEMENT_FAILED`，诊断为 `CANDIDATE_EVIDENCE_INVALID`，耗时12.3579秒。它对应模型候选段落的evidence数组校验失败。错误响应未保留原字段形状，不能确定是遗漏、null、对象还是超过数量限制，不能声称已看到模型原始候选。

补测前GET为200，整个v1草稿与初稿快照一致，确认第一次失败没有修改原稿；第二次失败后的回读尚待补充。普通案例已完成的真实接口结果保留。

## 修改

- 保留refine-v1，新增refine-v2：每个段落必须返回evidence数组，无引文使用空数组；服务端负责票价缺口提示，模型保留其他有据正文，不把用户指定的30元当事实。
- 仅兼容无歧义容器：缺字段、null、空对象转为空数组；精确包含source_id与quote的单个对象包装成单元素数组。不补造引文、不修饰原文、不更改资料编号。
- 空数组仍是没有证据；必须通过已有独立核验和事实保护，不能由格式兼容变成verified。超长数组不截断；其他类型继续502，原稿保留。
- 成功响应的 `ai_meta.candidate_normalizations` 记录候选下标与固定规范化代码；流程标识为refine-core/0.1.2，改写提示词标识为refine-v2/review-v5。纯依据说明为refine-v2，review_executed=false。
- 失败白名单诊断增加阶段、候选下标、JSON类型和可选容器数量，不包含模型原始文本、提供方响应或密钥。
- 不增加自动模型重试和调用次数。验收工具继续仅恢复失败案例，并记录新提示词文件的源码摘要。

## 已执行验证与边界

完整后端146项测试通过，1个原有Starlette/httpx弃用警告；包括无证据不能被错误supported放行、单对象包装后伪造编号/引文及无依据价格仍被拦截、异常格式不改稿和诊断不泄露内容。工具离线恢复演练通过，旧502及普通案例保留。

本次未执行真实模型调用，仍需在B本机补测，不以离线结果替代真实验收。原始两轮结果及记录在 `B_REFINE_REAL_ACCEPTANCE.md` 与 `acceptance/b-refine-real/`。

## 补测

停止后端，合并本次backend/docs/scripts文件，运行后端测试。保留原模型环境与DRAFT_DB_PATH，重启同一 `backend.a_ai_main:app` 后，从项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/run_b_refine_acceptance.py --resume-failed
```

只恢复已有缺票价草稿，新的响应依次使用`.3`等后缀，原始两次502不覆盖。若其他操作修改了原稿，工具会停止覆盖。补测后提交最新B_REFINE_ACCEPTANCE_LATEST.zip供审阅。
