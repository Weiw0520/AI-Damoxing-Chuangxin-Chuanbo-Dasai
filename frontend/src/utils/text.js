/**
 * 文本与状态的小工具。
 * 这里集中放「依据定位」相关逻辑，B 同学改核验规则时不用翻组件。
 */

export const STATUS_TEXT = {
  supported: '有资料依据',
  needs_review: '待核验',
  edited_needs_review: '人工修改后待复核',
}

export const STATUS_CLASS = {
  supported: 'ok',
  needs_review: 'warn',
  edited_needs_review: 'warn',
}

/**
 * 最长公共子串，用于在来源原文里高亮出真正的「依据片段」。
 *
 * 阈值取 3 而非 4：官方条目与文案用词常有出入
 * （如「公布时间2006（第一批）」vs「列入第一批国家级非遗名录」），
 * 3 字足以捕捉「第一批」这类关键锚点，又不会把无意义的单字标出来。
 */
export function lcs(a, b) {
  if (!a || !b) return ''
  a = a.replace(/\s/g, '')
  b = b.replace(/\s/g, '')
  let best = ''
  let prev = new Array(b.length + 1).fill(0)
  for (let i = 1; i <= a.length; i++) {
    const cur = new Array(b.length + 1).fill(0)
    for (let j = 1; j <= b.length; j++) {
      if (a[i - 1] === b[j - 1]) {
        cur[j] = prev[j - 1] + 1
        if (cur[j] > best.length) best = a.slice(i - cur[j], i)
      }
    }
    prev = cur
  }
  return best.length >= 3 ? best : ''
}

/**
 * 把一段引文按 anchor 切成 [{text, mark}]，mark=true 的部分在抽屉里高亮。
 *
 * 注意这里不能直接在原文上 indexOf：lcs 是去空白后比对的，
 * 一旦命中的片段跨了空格（如「2008 年列入第二批…」），
 * 拿去掉空格的片段回原文里找必然找不到，高亮就会静默失效。
 * 所以先在去空白的副本里定位，再用下标映射表还原到原文位置。
 */
export function splitByAnchor(quote, anchor) {
  const seg = lcs(anchor, quote)
  if (!seg) return [{ text: quote, mark: false }]

  let stripped = ''
  const map = []
  for (let i = 0; i < quote.length; i++) {
    if (/\s/.test(quote[i])) continue
    stripped += quote[i]
    map.push(i)
  }

  const k = stripped.indexOf(seg)
  if (k < 0) return [{ text: quote, mark: false }]

  const start = map[k]
  const end = map[k + seg.length - 1] + 1

  const parts = []
  if (start > 0) parts.push({ text: quote.slice(0, start), mark: false })
  parts.push({ text: quote.slice(start, end), mark: true })
  if (end < quote.length) parts.push({ text: quote.slice(end), mark: false })
  return parts
}

/**
 * 把正文按 claim.anchor 切成文本片段与高亮片段。
 * anchor 找不到（用户改过这句）时该 claim 会被跳过，由调用方单独提示「依据失效」。
 */
export function splitByClaims(text, claims = []) {
  const items = []
  claims.forEach((c) => {
    const i = text.indexOf(c.anchor)
    if (i >= 0) items.push({ start: i, end: i + c.anchor.length, claim: c })
  })
  items.sort((a, b) => a.start - b.start)

  const parts = []
  let cursor = 0
  for (const it of items) {
    if (it.start < cursor) continue
    if (it.start > cursor) parts.push({ type: 'text', text: text.slice(cursor, it.start) })
    parts.push({ type: 'hl', text: text.slice(it.start, it.end), claim: it.claim })
    cursor = it.end
  }
  if (cursor < text.length) parts.push({ type: 'text', text: text.slice(cursor) })
  return parts
}

export function hlClass(status) {
  if (status !== 'supported') return 'hl-warn'
  return 'hl-ok'
}

/** 上标文字：有据显示来源号，待核验加前缀，无依据固定两字。 */
export function citeText(claim) {
  const ids = claim.cite_ids || []
  if (claim.status === 'supported') return '查看原文依据'
  if (claim.status === 'edited_needs_review') return '人工修改后待复核'
  return '待核验'
}

export function sanitizeFilename(name) {
  return String(name || '未命名文案')
    .replace(/[\\/:*?"<>|]/g, '')
    .slice(0, 30)
}

export function nowTime() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}
