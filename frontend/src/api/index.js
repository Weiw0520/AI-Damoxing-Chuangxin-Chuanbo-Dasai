/**
 * 前端唯一的接口出口。
 *
 * 默认走真实后端。只有两种情况会切到「示例数据模式」：
 *   1. 构建时设了 VITE_USE_MOCK=true；
 *   2. 用户在页面上手动点「切换」（后端没起来、现场断网时用）。
 *
 * 示例数据模式下走的是 backend/data/cases.json 的同一份数据，
 * 也就是说演示内容和后端返回完全一致，不会出现「两套结果」。
 */

import { ApiFailure, request } from './client'
import { MOCK_CASES } from './fixtures'
import { buildFile } from '../utils/localExport'
import { nowTime } from '../utils/text'

let useMock = import.meta.env.VITE_USE_MOCK === 'true'
let mockSeq = 0
const mockDrafts = new Map()

export function isMock() {
  return useMock
}

export function setMock(value) {
  useMock = !!value
}

export function modeLabel() {
  return useMock ? '示例数据模式' : '真实后端模式'
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function stamp() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(
    d.getMinutes()
  )}`
}

/* ------------------------------------------------------------------ 案例 */
export async function listCases() {
  if (!useMock) return request('/cases')
  await sleep(60)
  return MOCK_CASES.map(({ result, ...rest }) => rest)
}

/* ------------------------------------------------------------------ 生成 */
const KEYWORDS = {
  typical: ['项目编号 Ⅶ-5', '恒顺', '同顺堂', '寒亭区文化馆', '项目序号 304'],
  conflict: ['寒亭区志', '起于元代', '六百余年', '公众号', '说法'],
  minimal: ['聂家庄', '泥塑', 'Ⅶ-47', '聂希蔚'],
}

function findMockCase(payload) {
  const byId = MOCK_CASES.find((c) => c.id === payload.case_id || c.no === payload.case_id)
  if (byId) return byId
  const material = payload.material || ''
  let best = null
  let bestScore = 0
  MOCK_CASES.forEach((c) => {
    const score = (KEYWORDS[c.id] || []).reduce(
      (n, k) => n + (material.split(k).length - 1),
      0
    )
    if (score > bestScore) {
      best = c
      bestScore = score
    }
  })
  return best
}

export async function generate(payload) {
  if (!useMock) return request('/generate', { method: 'POST', body: payload })

  await sleep(1100)
  const hit = findMockCase(payload)
  if (!hit) {
    throw new ApiFailure(
      '示例数据模式只内置了 3 个案例。请点上方案例卡载入资料，或切换到真实后端模式。',
      'MOCK_NO_MATCH',
      0
    )
  }
  const draft = JSON.parse(JSON.stringify(hit.result))
  mockSeq += 1
  const d = new Date()
  const day = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(
    d.getDate()
  ).padStart(2, '0')}`
  draft.draft_id = `D-${day}-${String(mockSeq).padStart(2, '0')}`
  draft.version = 1
  draft.created_at = stamp()
  mockDrafts.set(draft.draft_id, JSON.parse(JSON.stringify(draft)))
  return draft
}

/* ------------------------------------------------------------------ 保存 */
export async function saveDraft(draftId, payload) {
  if (!useMock) return request(`/drafts/${draftId}`, { method: 'PUT', body: payload })

  await sleep(420)
  const stored = mockDrafts.get(draftId)
  if (!stored) throw new ApiFailure('草稿不存在，可能已被清理，请重新生成。', 'DRAFT_NOT_FOUND', 404)

  const incoming = new Map(payload.segments.map((s) => [s.id, s.text]))
  const changed = []
  stored.segments.forEach((seg) => {
    const next = incoming.get(seg.id)
    if (next !== undefined && next !== seg.text) {
      seg.text = next
      changed.push(seg.id)
    }
  })
  stored.version = (stored.version || 1) + 1
  if (payload.history) stored.history = payload.history
  mockDrafts.set(draftId, stored)

  return {
    draft_id: draftId,
    version: stored.version,
    saved_at: nowTime(),
    changed_segments: changed,
  }
}

/* ------------------------------------------------------------------ 导出 */
export async function exportDraft(draftId, format, history = []) {
  // 用 POST 而不是 GET：把前端最新的修改记录一并送过去，
  // 导出的「人工修改记录」才是最新的那一份（GET 版本留给 curl 和第三方）。
  if (!useMock) {
    return request(`/drafts/${draftId}/export`, {
      method: 'POST',
      body: { format, history },
    })
  }

  await sleep(120)
  const stored = mockDrafts.get(draftId)
  if (!stored) throw new ApiFailure('草稿不存在', 'DRAFT_NOT_FOUND', 404)
  const { filename, content } = buildFile(stored, format)
  return { draft_id: draftId, version: stored.version, format, filename, content }
}

/* ------------------------------------------------------------------ 草稿列表 */
export async function listDrafts() {
  if (!useMock) return request('/drafts')
  await sleep(80)
  return [...mockDrafts.values()]
    .map((d) => {
      const st = { verified: 0, needs_check: 0, unsupported: 0, total: 0 }
      d.segments.forEach((s) =>
        (s.claims || []).forEach((c) => {
          st[c.status] += 1
          st.total += 1
        })
      )
      const titleSeg = d.segments.find((s) => s.type === 'title')
      const bodySeg = d.segments.find((s) => s.type !== 'title')
      return {
        draft_id: d.draft_id,
        title: titleSeg ? titleSeg.text.slice(0, 40) : '未命名文案',
        version: d.version,
        created_at: d.created_at,
        updated_at: d.created_at,
        platform: 'xiaohongshu',
        preview: bodySeg ? bodySeg.text.slice(0, 46) : '',
        stats: st,
      }
    })
    .sort((a, b) => (a.draft_id < b.draft_id ? 1 : -1))
}

export async function getDraft(draftId) {
  if (!useMock) return request(`/drafts/${draftId}`)
  await sleep(60)
  const stored = mockDrafts.get(draftId)
  if (!stored) throw new ApiFailure('草稿不存在，可能已被清理。', 'DRAFT_NOT_FOUND', 404)
  return JSON.parse(JSON.stringify(stored))
}

/* ------------------------------------------------------------------ 多轮追问 */
export async function refineDraft(draftId, payload) {
  if (!useMock) return request(`/drafts/${draftId}/refine`, { method: 'POST', body: payload })

  // 追问要由服务端的改写引擎执行（要按分句边界删改、要重算 anchor 是否还在）。
  // 前端不复制一套同样的规则 —— 两份实现迟早会跑出两种结果。
  await sleep(200)
  throw new ApiFailure(
    '示例数据模式下不能追问：追问要由服务端的改写引擎执行。请点右上角「切换」回到真实后端。',
    'MOCK_NO_REFINE',
    0
  )
}

/* ------------------------------------------------------------------ 资料上传 */
const TEXT_LIKE = /\.(txt|md|markdown|csv|tsv|json)$/i

/**
 * 把上传的文件读成纯文本。
 *
 * 解析在服务端做（docx 要拆 zip，还要判大小、判编码）。只有**连不上后端**
 * 且文件本身是纯文本时，才退回浏览器本地读取 —— 断网演示还能用，别让用户白等。
 *
 * 注意只在 NETWORK_ERROR 上退回。服务端明确拒绝的（超过 5 MB、空文件、
 * 不支持 PDF）必须原样抛给用户：本地读一遍就把 5 MB 的限制绕过去了，
 * 用户会以为上传成功，之后 anchor 对不上却查不出原因。
 */
export async function extractFile(file) {
  try {
    return await request(`/extract?filename=${encodeURIComponent(file.name)}`, {
      method: 'POST',
      body: file,
      raw: true,
    })
  } catch (e) {
    const offline = e instanceof ApiFailure && e.code === 'NETWORK_ERROR'
    if (offline && TEXT_LIKE.test(file.name)) {
      const text = await file.text()
      return {
        filename: file.name,
        kind: 'text',
        text,
        chars: text.length,
        truncated: false,
        limit: 20000,
      }
    }
    throw e
  }
}
