// Present C's blocks in A's existing segment/claim widgets without inferring verdicts.
export function toDraftView(draft) {
  return {
    draft_id: draft.draftId, created_at: draft.createdAt, mode: draft.mode,
    model: draft.mode === 'mock' ? '模拟生成器' : '服务端生成器',
    notice: draft.mode === 'mock' ? { text: '模拟联调：原文引用仅供演示，尚未完成真实 AI 核验。' } : null,
    sources: draft.sources.map((s, index) => ({
      ...s, id: s.sourceId, label: `资料 ${index + 1}`, snippet: s.text, publisher: '用户提交资料',
    })),
    segments: draft.blocks.map((b, index) => ({
      ...b, id: b.blockId, label: `第 ${index + 1} 段`, type: 'body',
      claims: [{
        id: b.blockId, anchor: b.text, status: b.status, reason: b.reviewReason,
        cite_ids: [...new Set(b.evidence.map((e) => e.sourceId))],
        quotes: b.evidence.map((e) => ({ source_id: e.sourceId, quote: e.quote })),
      }],
    })),
  }
}

export function toHistoryView(history) {
  return history.map((entry, index) => ({
    id: `${entry.blockId}-${index}`, type: 'human', title: '人工修改正文',
    who: '人工', whoClass: 'human', time: new Date(entry.editedAt).toLocaleString('zh-CN'),
    desc: `段落 ${entry.blockId} 已保存，人工修改后待复核。旧依据保存在服务端历史中。`,
    diff: { before: entry.before.text, after: entry.after.text }, ...entry,
  }))
}
