"""Explicitly import a manual test draft. Does not generate text or invoke AI."""
import argparse
from uuid import uuid4

from backend.a_compat.store import Store, now


def manual_test_draft(draft_id=None):
    timestamp = now()
    return {
        "draft_id": draft_id or "A-MANUAL-" + uuid4().hex[:12], "version": 1,
        "created_at": timestamp, "updated_at": timestamp, "data_origin": "manual_test",
        "model": "人工录入测试稿（非 AI）", "prompt_version": "未使用", "prompt_excerpt": "",
        "notice": {"level": "warn", "text": "人工录入的联调测试草稿：不是 AI 生成或核验结果，所有资料仍需人工核实。"},
        "input": {"material": "资料一：山东省潍坊市杨家埠的一种民间版画\n资料二：杨家埠木版年画分钩描、刻版、印刷3道工序",
                  "requirement": "人工整理杨家埠资料，验收读取、编辑和导出。", "platform": "xiaohongshu", "case_id": None},
        "sources": [
            {"id": "S1", "title": "杨家埠项目资料（用户提供节选）", "publisher": "用户提供的资料",
             "url": "https://www.ihchina.cn/project_details/13904.html", "snippet": "山东省潍坊市杨家埠的一种民间版画"},
            {"id": "S2", "title": "杨家埠工艺资料（用户提供节选）", "publisher": "用户提供的资料",
             "url": "https://www.ihchina.cn/project_details/9691", "snippet": "杨家埠木版年画分钩描、刻版、印刷3道工序"},
        ],
        "segments": [
            {"id": "s1", "type": "title", "label": "标题", "text": "杨家埠资料整理｜人工测试稿", "claims": []},
            {"id": "s2", "type": "body", "label": "项目介绍", "text": "山东省潍坊市杨家埠的一种民间版画",
             "claims": [{"id": "c1", "anchor": "山东省潍坊市杨家埠的一种民间版画", "status": "needs_check", "cite_ids": ["S1"],
                         "quotes": [{"source_id": "S1", "quote": "山东省潍坊市杨家埠的一种民间版画"}],
                         "reason": "人工提供的原文引用，未进行 AI 核验。", "suggest": None}]},
            {"id": "s3", "type": "body", "label": "工艺介绍", "text": "杨家埠木版年画分钩描、刻版、印刷3道工序",
             "claims": [{"id": "c2", "anchor": "杨家埠木版年画分钩描、刻版、印刷3道工序", "status": "needs_check", "cite_ids": ["S2"],
                         "quotes": [{"source_id": "S2", "quote": "杨家埠木版年画分钩描、刻版、印刷3道工序"}],
                         "reason": "人工提供的原文引用，未进行 AI 核验。", "suggest": None}]},
        ],
        "history": [{"id": "manual-import", "type": "human", "title": "人工导入测试稿", "who": "人工", "whoClass": "human",
                     "time": timestamp, "desc": "显式导入人工编写的联调测试资料；没有调用 AI，没有自动核验。"}],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="SQLite path; defaults to DRAFT_DB_PATH or data/drafts.sqlite3")
    parser.add_argument("--id", help="Explicit ID; an existing ID will never be overwritten")
    args = parser.parse_args()
    draft = manual_test_draft(args.id)
    Store(args.db).insert_manual(draft)
    print(f"Imported manual non-AI test draft: {draft['draft_id']}")


if __name__ == "__main__":
    main()
