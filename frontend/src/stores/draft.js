import { computed, reactive } from 'vue'
import * as api from '../api'
import { CASES } from '../api/cases'
import { toDraftView, toHistoryView } from '../api/draftView'
import { toast } from '../utils/toast'
import { copyText, download } from '../utils/io'
import { STATUS_CLASS, STATUS_TEXT, splitByAnchor } from '../utils/text'

export const GEN_STEPS = ['提交独立资料与传播需求', '等待服务端分段文案', '接收来源与原文引用', '显示待核验提示（不代表真实 AI 核验）']
const emptySource = () => ({ title: '', text: '', url: '' })
const LAST_DRAFT = 'luyi:last-c-draft-id'
export const state = reactive({
  conversations: [], cases: CASES, caseId: null,
  inputSources: [emptySource()], material: '', requirement: '', platform: '小红书', formError: '',
  phase: 'empty', genStep: 0, errorTitle: '', errorMsg: '', result: null, serverDraft: null,
  edits: {}, editMode: false, activeTab: 'copy', filter: null,
  draftId: null, savedVersion: 0, savedAt: null, saving: false, saveError: '', history: [],
  exporting: false, exportError: '', loadingDraft: false,
  panel: { collapsed: false, width: 308, tabs: [], active: null },
  drawer: { open: false, mode: 'claim', claimId: null, sourceId: null },
  exportOpen: false, confirm: { open: false, title: '', desc: '' }, mode: 'C 后端联调',
})
let confirmResolver = null
const busy = () => state.saving || state.exporting || state.loadingDraft || state.phase === 'generating'
export const claimsList = computed(() => (state.result?.segments || []).flatMap((seg) => seg.claims.map((claim) => ({ seg, claim }))))
export const stats = computed(() => {
  const counts = { supported: 0, needs_review: 0, edited_needs_review: 0, total: claimsList.value.length }
  claimsList.value.forEach(({ claim }) => { counts[claim.status] += 1 })
  return { ...counts, pending: counts.needs_review + counts.edited_needs_review }
})
export const hasEdits = computed(() => (state.result?.segments || []).some((s) => currentText(s) !== s.text))
export const activeClaimId = computed(() => state.drawer.open ? state.drawer.claimId : null)
export const currentConv = computed(() => state.conversations.find((c) => c.draft_id === state.draftId))
export const visibleHistory = computed(() => state.history)
export const lastReplyId = computed(() => null)
export const chatItems = computed(() => state.result ? [
  { id: 'material', role: 'user', kind: 'material', text: state.material, requirement: state.requirement, platform: state.platform },
  { id: 'draft', role: 'ai', kind: 'draft' },
] : [])
export const FILE_TABS = [{ id: 'draft', kind: 'draft', ext: '.txt', name: '文案正文',
  desc: '逐段编辑；下载服务端保存的 TXT', editable: true }]
export const fileTabs = computed(() => state.result ? FILE_TABS : [])
export const activeFile = computed(() => FILE_TABS.find((f) => f.id === state.panel.active) || null)
export const activeFileContent = computed(() => (state.result?.segments || []).map((s) => currentText(s)).join('\n\n'))
export function openFile(id) {
  if (!state.result || !FILE_TABS.some((f) => f.id === id)) return
  if (!state.panel.tabs.includes(id)) state.panel.tabs.push(id)
  state.panel.active = id
  state.panel.collapsed = false
}
export function closeFile(id) {
  state.panel.tabs = state.panel.tabs.filter((tab) => tab !== id)
  if (state.panel.active === id) state.panel.active = state.panel.tabs[0] || null
}
export function showFileList() { state.panel.active = null }
export function togglePanel() { state.panel.collapsed = !state.panel.collapsed }
export function setPanelWidth(w) { state.panel.width = Math.max(240, Math.min(560, Math.round(w))) }
export function currentText(seg) { return state.edits[seg.id] ?? seg.text }
export function staleClaims(seg) { return currentText(seg) !== seg.text ? seg.claims : [] }

export const drawerData = computed(() => {
  const d = state.drawer
  if (!d.open || !state.result) return null
  if (d.mode === 'source') {
    const source = state.result.sources.find((s) => s.id === d.sourceId)
    return source ? { mode: 'source', kicker: source.label, title: source.title, source } : null
  }
  const index = claimsList.value.findIndex(({ claim }) => claim.id === d.claimId)
  if (index < 0) return null
  const { seg, claim } = claimsList.value[index]
  const quotes = claim.quotes.map((q) => {
    const src = state.result.sources.find((s) => s.id === q.source_id)
    return { sourceId: q.source_id, sourceLabel: src?.label, sourceTitle: src?.title || '来源缺失',
      parts: splitByAnchor(q.quote, q.quote), matched: true, hasSource: !!src, publisher: src?.publisher, url: src?.url }
  })
  return { mode: 'claim', kicker: STATUS_TEXT[claim.status], title: claim.anchor,
    seg, claim, no: index + 1, quotes, blankGap: quotes.length === 0, statusClass: STATUS_CLASS[claim.status] }
})
function rememberDraft(id) {
  try { localStorage.setItem(LAST_DRAFT, id) } catch { /* optional */ }
  const url = new URL(location.href)
  url.searchParams.set('draftId', id)
  window.history.replaceState(null, '', url)
}
function forgetDraft() {
  try { localStorage.removeItem(LAST_DRAFT) } catch { /* optional */ }
  const url = new URL(location.href)
  url.searchParams.delete('draftId')
  window.history.replaceState(null, '', url)
}
function hydrate(draft, keepView = false) {
  state.serverDraft = draft
  state.result = toDraftView(draft)
  state.draftId = draft.draftId
  // Legacy UI truthy saved flag only; C has no version/concurrency-token field.
  state.savedVersion = 1
  state.savedAt = draft.updatedAt
  state.history = toHistoryView(draft.history)
  state.inputSources = draft.sources.map(({ title, text, url }) => ({ title, text, url: url || '' }))
  state.material = draft.sources.map((s, i) => `【资料 ${i + 1}】${s.title}\n${s.text}\n${s.url || '未提供链接'}`).join('\n\n')
  state.requirement = draft.brief
  state.platform = draft.platform
  state.mode = draft.mode === 'mock' ? '模拟联调' : '服务端生成器'
  state.edits = {}
  state.formError = ''
  state.saveError = ''
  state.phase = 'result'
  if (!keepView) {
    state.editMode = false
    state.activeTab = 'copy'
    state.filter = null
    state.panel.tabs = []
    state.panel.active = null
  }
  closeDrawer()
  rememberDraft(draft.draftId)
  refreshConversations()
}
export async function init() {
  let id = new URLSearchParams(location.search).get('draftId')
  try { id ||= localStorage.getItem(LAST_DRAFT) } catch { /* optional */ }
  if (id) await openConversation(id)
}
// This page's shortcuts, not a server-side draft list. Never calls GET /api/drafts.
export function refreshConversations() {
  if (!state.serverDraft) return
  const d = state.serverDraft
  const entry = { draft_id: d.draftId, title: d.sources[0]?.title, preview: d.blocks[0]?.text,
    updated_at: d.updatedAt, stats: stats.value }
  state.conversations = [entry, ...state.conversations.filter((c) => c.draft_id !== d.draftId)]
}
export async function openConversation(id) {
  id = id?.trim()
  if (!id || busy()) return
  if (hasEdits.value && !await askConfirm('重新读取草稿？', '未保存的修改将丢失，请先保存或确认放弃。')) return
  state.loadingDraft = true
  try { hydrate(await api.getDraft(id)); toast('已读取服务端最后保存的草稿') }
  catch (error) { toast('读取草稿失败：' + error.message, 5000) }
  finally { state.loadingDraft = false }
}
export async function newConversation() {
  if (busy()) return
  if (hasEdits.value && !await askConfirm('开始新草稿？', '未保存的修改将丢失。')) return
  resetInput()
}
export function resetResult() {
  state.result = null; state.serverDraft = null; state.edits = {}; state.editMode = false
  state.activeTab = 'copy'; state.filter = null; state.draftId = null; state.savedVersion = 0
  state.savedAt = null; state.saveError = ''; state.exportError = ''; state.exportOpen = false
  state.history = []; state.phase = 'empty'; state.panel.tabs = []; state.panel.active = null
  state.mode = 'C 后端联调'
  closeDrawer()
}
export function resetInput() {
  if (busy()) return
  resetResult()
  state.inputSources = [emptySource()]; state.material = ''; state.requirement = ''
  state.caseId = null; state.formError = ''
  forgetDraft()
}
export function loadCase(id) {
  const c = CASES.find((item) => item.id === id)
  if (!c || busy()) return
  resetResult(); forgetDraft()
  state.caseId = id; state.inputSources = c.sources.map((s) => ({ ...s }))
  state.requirement = c.requirement; state.platform = c.platform
  toast('已载入独立资料；生成将由 C 后端处理')
}
export function addSource() { state.inputSources.push(emptySource()); state.caseId = null }
export function removeSource(index) { if (state.inputSources.length > 1) state.inputSources.splice(index, 1); state.caseId = null }
export function setRequirement(text) { state.requirement = text }
export function setPlatform(platform) { state.platform = platform }
export async function generate() {
  if (busy()) return
  const sources = state.inputSources.map((s) => ({ title: s.title.trim(), text: s.text.trim(), ...(s.url.trim() ? { url: s.url.trim() } : {}) }))
  if (!sources.length || sources.some((s) => !s.title || !s.text) || !state.requirement.trim()) {
    state.formError = '每份资料都需要标题和原文，并填写传播需求。'
    return
  }
  resetResult()
  state.phase = 'generating'; state.genStep = 0
  const timer = setInterval(() => { state.genStep = Math.min(state.genStep + 1, GEN_STEPS.length - 1) }, 400)
  try {
    hydrate(await api.generate({ sources, brief: state.requirement.trim(), platform: state.platform }))
    toast('草稿已由服务端创建并保存，可点开依据查看原文')
  } catch (error) {
    state.phase = 'error'; state.errorTitle = '生成请求未成功，请检查后重试'; state.errorMsg = error.message
  } finally { clearInterval(timer) }
}
export function backToInput() { state.phase = 'empty' }
export function setTab(tab) { state.activeTab = tab; if (tab === 'report') state.filter = null }
export function focusDraft() {
  requestAnimationFrame(() => document.querySelector('.draft-card')?.scrollIntoView({ block: 'start', behavior: 'smooth' }))
}
export function jumpToReport(filter) { state.filter = filter; state.activeTab = 'report' }
export function setEditMode(on) {
  state.editMode = on
  if (on) { openFile('draft'); toast('改完请保存；修改段落需重新复核') }
}
export function setEdit(id, text) { if (!state.saving && !state.exporting) state.edits[id] = text }
export function openClaim(id) { state.drawer = { open: true, mode: 'claim', claimId: id, sourceId: null } }
export function openSource(id) { state.drawer = { open: true, mode: 'source', claimId: null, sourceId: id } }
export function closeDrawer() { state.drawer.open = false }
export async function save() {
  if (!state.result || busy()) return null
  const edits = state.result.segments.filter((s) => currentText(s) !== s.text).map((s) => ({ blockId: s.id, text: currentText(s) }))
  if (!edits.length) { toast('没有需要保存的修改'); return state.serverDraft }
  state.saving = true; state.saveError = ''
  try {
    const draft = await api.saveDraft(state.draftId, edits)
    hydrate(draft, true)
    toast('已保存；修改段落标为人工修改后待复核')
    return draft
  } catch (error) {
    state.saveError = error.message
    toast('保存失败，修改仍保留：' + error.message, 5000)
    return null
  } finally { state.saving = false }
}
export function openExport() {
  if (!state.result) { toast('请先创建草稿'); return }
  state.exportError = ''; state.exportOpen = true
}
export function closeExport() { if (!state.exporting) state.exportOpen = false }
export async function doExport() {
  if (!state.draftId || state.saving || state.exporting) return
  if (hasEdits.value) { toast('请先保存修改，再下载服务端最新版'); return }
  state.exporting = true; state.exportError = ''
  try {
    const file = await api.exportDraft(state.draftId)
    download(file.filename, file.blob)
    state.exportOpen = false
    toast('已下载服务端最后保存的 TXT')
  } catch (error) {
    state.exportError = `导出失败：${error.message}。没有生成或下载本地替代文件。`
    state.exportOpen = true; toast(state.exportError, 6000)
  } finally { state.exporting = false }
}
export async function copyAll() {
  const ok = await copyText(activeFileContent.value)
  toast(ok ? '页面正文已复制（不等同服务端导出）' : '复制失败，请使用服务端 TXT 下载')
}
export async function saveThenExport() { if (await save()) state.exportOpen = true }
export function askConfirm(title, desc) {
  return new Promise((resolve) => { confirmResolver = resolve; state.confirm = { open: true, title, desc } })
}
export function resolveConfirm(value) {
  state.confirm.open = false; confirmResolver?.(value); confirmResolver = null
}
