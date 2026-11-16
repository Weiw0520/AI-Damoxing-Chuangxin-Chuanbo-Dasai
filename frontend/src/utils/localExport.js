/**
 * 本地导出（备用路径）。
 *
 * 正常流程：保存后调用后端 GET /api/drafts/{id}/export，由服务端生成文件，
 *          保证「导出的就是库里那一版」。
 * 这条本地实现只在两种情况下兜底：
 *   1. 示例数据模式（没有后端）；
 *   2. 后端导出接口异常，但草稿已经在本地保存过。
 * 两边的排版规则保持一致，改格式时请同步 backend/app/services/exporter.py。
 */

import { STATUS_TEXT } from './text'

function pad(n) {
  return String(n).padStart(2, '0')
}

function stamp(d = new Date()) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes()
  )}:${pad(d.getSeconds())}`
}

export function allClaims(draft) {
  const out = []
  draft.segments.forEach((seg) => {
    ;(seg.claims || []).forEach((claim) => out.push({ seg, claim }))
  })
  return out
}

export function buildBody(draft) {
  const lines = []
  draft.segments.forEach((seg) => {
    if (seg.type === 'title') lines.push('# ' + seg.text + '\n')
    else if (seg.type === 'tag') lines.push('\n' + seg.text + '\n')
    else lines.push(seg.text + '\n')
  })
  return lines.join('\n')
}

export function buildReport(draft, now = new Date()) {
  const lines = []
  lines.push('## 核验说明\n')
  lines.push('| 序号 | 表述 | 状态 | 来源 | 判定依据 |')
  lines.push('| --- | --- | --- | --- | --- |')
  allClaims(draft).forEach(({ claim }, i) => {
    const anchor = claim.anchor.replace(/\|/g, '｜')
    const reason = String(claim.reason || '')
      .replace(/\n/g, ' ')
      .replace(/\|/g, '｜')
    const cites = (claim.cite_ids || []).join('、') || '无'
    lines.push(
      `| ${pad(i + 1)} | ${anchor} | ${STATUS_TEXT[claim.status]} | ${cites} | ${reason} |`
    )
  })

  lines.push('\n## 来源清单\n')
  ;(draft.sources || []).forEach((s) => {
    lines.push(`- **${s.id}** ${s.title}｜${s.publisher}${s.url ? '｜' + s.url : ''}`)
    if (s.snippet) lines.push(`  > ${s.snippet}`)
  })

  lines.push('\n## 人工修改记录\n')
  const hist = (draft.history || []).filter((h) => h.type === 'human' || h.type === 'save')
  if (!hist.length) lines.push('- 无人工修改，AI 初稿直接使用。')
  hist.forEach((h) => {
    lines.push(`- [${h.time || ''}] ${h.title || ''}（${h.who || ''}）${h.desc || ''}`)
    if (h.diff) {
      lines.push(`  - 原：${h.diff.before}`)
      lines.push(`  - 改：${h.diff.after}`)
    }
  })

  lines.push('\n## 生成信息\n')
  lines.push(`- 草稿编号：${draft.draft_id}`)
  lines.push(`- 版本：v${draft.version}`)
  lines.push(`- 模型：${draft.model || ''}`)
  lines.push(`- 提示词版本：${draft.prompt_version || ''}`)
  lines.push(`- 导出时间：${stamp(now)}`)
  lines.push(
    '\n> 本文案由 AI 依据用户提交资料生成，每处事实性表述均标注来源或核验状态；人工修改记录见上。'
  )
  return lines.join('\n')
}

export function buildMarkdown(draft, now = new Date()) {
  return buildBody(draft) + '\n\n---\n\n' + buildReport(draft, now)
}

export function buildPlain(draft) {
  const parts = draft.segments.map((s) => s.text).join('\n\n')
  const pending = allClaims(draft).filter((x) => x.claim.status !== 'verified')
  if (!pending.length) return parts
  const tips = pending.map((x, i) => {
    const first = String(x.claim.reason || '').split('\n')[0]
    return `${i + 1}. 「${x.claim.anchor}」：${STATUS_TEXT[x.claim.status]}。${first}`
  })
  return parts + '\n\n——\n【待核验提示】\n' + tips.join('\n')
}

export function titleOf(draft) {
  const t = draft.segments.find((s) => s.type === 'title')
  return (t ? t.text : '未命名文案').replace(/[\\/:*?"<>|]/g, '').slice(0, 30)
}

export function buildFile(draft, format, now = new Date()) {
  const base = `${draft.draft_id}-v${draft.version}-${titleOf(draft)}`
  if (format === 'md') return { filename: base + '.md', content: buildMarkdown(draft, now) }
  if (format === 'txt') return { filename: base + '.txt', content: buildPlain(draft) }
  return {
    filename: `${draft.draft_id}-v${draft.version}-核验报告.md`,
    content: '# 核验报告\n\n' + buildReport(draft, now),
  }
}
