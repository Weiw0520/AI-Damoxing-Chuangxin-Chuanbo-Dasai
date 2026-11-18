import re

from backend.a_compat.store import merge_history

LABELS = {"verified": "有据可查（既有人工/示例状态）", "needs_check": "待核验", "unsupported": "无依据"}


def export(draft, fmt, history):
    """Formatting only; content always comes from the persisted draft."""
    notice = draft.get('notice') or {}
    prefix = f"草稿 {draft['draft_id']} · v{draft['version']}\n{notice.get('text', '本次未运行 AI 生成或核验。')}\n"
    body = []
    for seg in draft["segments"]:
        statuses = {c["status"] for c in seg.get("claims", [])}
        if seg.get("review_status") == "edited_needs_review":
            marker = "【人工修改后待复核】\n"
        elif "unsupported" in statuses:
            marker = "【含无依据表述，需人工复核】\n"
        elif "needs_check" in statuses:
            marker = "【待核验】\n"
        else:
            marker = ""
        body.append(marker + seg["text"])
    content = prefix + "\n" + "\n\n".join(body)
    if fmt != "txt":
        report = ["## 资料依据与待核验项", "本报告只整理已存数据，不表示已运行 AI 核验。"]
        for seg in draft["segments"]:
            for claim in seg.get("claims", []):
                report.append(f"- {claim['anchor']}：{LABELS[claim['status']]}。{claim['reason']}")
                for quote in claim.get("quotes", []):
                    report.append(f"  - {quote['source_id']} 原文：{quote['quote']}")
        report.append("\n## 来源清单")
        report.extend(f"- {s['id']} {s['title']}｜{s.get('url') or '未提供链接'}\n  {s.get('snippet', '')}" for s in draft["sources"])
        report.append("\n## 人工修改记录")
        for h in merge_history(draft["history"], history):
            report.append(f"- {h.get('time', '')} {h.get('title', '')} {h.get('desc', '')}")
            if h.get("diff"):
                report.append(f"  - 原：{h['diff']['before']}\n  - 改：{h['diff']['after']}")
        content = (content + "\n\n" if fmt == "md" else prefix + "\n") + "\n".join(report)
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", draft["draft_id"])
    return {"draft_id": draft["draft_id"], "version": draft["version"], "format": fmt,
            "filename": f"{safe_id}_v{draft['version']}.{'txt' if fmt == 'txt' else 'md'}", "content": content}
