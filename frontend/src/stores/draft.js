/**
 * 全局状态与动作。
 *
 * 三人协作时这一层是「唯一真相」：组件只读 state、只调 action，
 * 不在组件里写业务判断。这样 B 改核验规则、C 改接口，都只需要动这里。
 *
 * 没有引入 Pinia —— 这个规模用 reactive + 模块单例足够，
 * 少一层概念，交接时不用额外解释。
 */

import { computed, reactive } from 'vue'
import * as api from '../api'
import { toast } from '../utils/toast'
import { copyText, download } from '../utils/io'
import { buildFile } from '../utils/localExport'
import {
  STATUS_CLASS,
  STATUS_TEXT,
  nowTime,
  splitByAnchor,
} from '../utils/text'

export const GEN_STEPS = [
  '解析资料与来源结构',
  '按平台风格生成分段文案',
  '逐句比对资料，标注来源编号',
  '标记待核验与无依据表述',
]

export const state = reactive({
  // 对话（左侧列表）
  conversations: [],
  convLoading: false,
  convError: '',

  // 输入
  cases: [],
  caseId: null,
  material: '',
  requirement: '',
  platform: 'xiaohongshu',
  formError: '',

  // 流程
  phase: 'empty', // empty | generating | error | result
  genStep: 0,
  errorTitle: '',
  errorMsg: '',

  // 结果
  result: null,
  edits: {},
  editMode: false,
  activeTab: 'copy',
  filter: null,

  // 草稿
  draftId: null,
  savedVersion: 0,
  savedAt: null,
  saving: false,
  saveError: '',
  history: [],

  // 追问
  refining: false,
  refineError: '',

  // 右栏（文件）
  panel: {
    collapsed: false,
    width: 308,
    tabs: [],        // 已打开的文件 id，按打开顺序
    active: null,    // 当前文件 id
  },

  // 核验待办：需要人工一条条判断的队列
  verify: {
    ids: [],         // 生成本稿时快照下来的待核验项
    skipped: [],     // 本轮跳过的，可以「再看一遍」捞回来
    hidden: false,   // 用户收起后不挡正文
  },

  // 上传
  uploading: false,

  // 浮层
  drawer: { open: false, mode: 'claim', claimId: null, sourceId: null },
  exportOpen: false,
  confirm: { open: false, title: '', desc: '' },

  mode: api.modeLabel(),
})

let confirmResolver = null

/* ------------------------------------------------------------ 派生数据 */
export const claimsList = computed(() => {
  if (!state.result) return []
  const out = []
  state.result.segments.forEach((seg) => {
    ;(seg.claims || []).forEach((claim) => out.push({ seg, claim }))
  })
  return out
})

export const stats = computed(() => {
  const r = { verified: 0, needs_check: 0, unsupported: 0, total: claimsList.value.length, pending: 0 }
  claimsList.value.forEach(({ claim }) => {
    r[claim.status] = (r[claim.status] || 0) + 1
  })
  r.pending = r.needs_check + r.unsupported
  return r
})

export const hasEdits = computed(() => {
  if (!state.result) return false
  return state.result.segments.some(
    (s) => state.edits[s.id] != null && state.edits[s.id] !== s.text
  )
})

export const activeClaimId = computed(() =>
  state.drawer.open && state.drawer.mode === 'claim' ? state.drawer.claimId : null
)

/**
 * 中间那列的消息流。
 *
 * 不做成独立数组，而是从「输入 + history」推导出来 —— 这样刷新页面、切到别的
 * 草稿再切回来，对话都还在。history 里 type=qa 的就是一轮追问（有 instruction
 * 和 desc），type=ai/human/save 的属于「修改记录」标签页，不进聊天流。
 *
 * 文案卡片固定排在最后：每轮改写都会换掉 segments，卡片如果留在开头，用户
 * 追问完看到的还是老位置的那张纸，得往上翻才知道改成了什么样。
 */
export const chatItems = computed(() => {
  if (!state.result) return []

  const items = [
    {
      id: 'm-material',
      role: 'user',
      kind: 'material',
      text: state.material,
      requirement: state.requirement,
      platform: state.platform,
    },
  ]

  state.history
    .filter((h) => h.type === 'qa')
    .forEach((h) => {
      items.push({
        id: h.id + '-q',
        role: 'user',
        kind: 'instruction',
        text: h.instruction || '',
      })
      items.push({
        id: h.id,
        role: 'ai',
        kind: 'reply',
        text: h.desc || '',
        applied: h.applied,
        changed: h.changed,
        diff: h.diff,
        at: h.time,
      })
    })

  items.push({ id: 'm-draft', role: 'ai', kind: 'draft' })
  return items
})

/** 最后一条追问的 AI 回话 —— 改完之后滚到这里，正好接上下面那张卡片。 */
export const lastReplyId = computed(() => {
  const items = chatItems.value
  for (let i = items.length - 1; i >= 0; i -= 1) {
    if (items[i].kind === 'reply') return items[i].id
  }
  return null
})

export const currentConv = computed(
  () => state.conversations.find((c) => c.draft_id === state.draftId) || null
)

/**
 * 「修改记录」标签页看到的内容。
 * 只问不改的追问轮次（「这些依据是什么」）不进这里 —— 正文没变，记它没意义。
 * 判断依据是 changed 而不是 diff：删掉整个话题标签段时没有 diff，但正文确实变了。
 */
export const visibleHistory = computed(() =>
  state.history.filter((h) => h.type !== 'qa' || h.changed || !!h.diff)
)

/* ------------------------------------------------------------ 右栏文件 */
/**
 * 右栏能打开的文件。
 *
 * 「文案正文」是唯一可编辑的一个 —— 它对应草稿本身。另外三个是导出产物，
 * 由正文和核验结论推出来，改它们没有意义（改了也会被下次导出覆盖），
 * 所以只在文案上给编辑按钮。
 */
export const FILE_TABS = [
  {
    id: 'draft',
    kind: 'draft',
    ext: '.txt',
    name: '文案正文',
    desc: '逐段改写；依据随改随核',
    editable: true,
  },
  {
    id: 'md',
    kind: 'export',
    fmt: 'md',
    ext: '.md',
    name: '文案 + 核验说明',
    desc: '正文、逐条核验、来源、修改记录',
  },
  {
    id: 'txt',
    kind: 'export',
    fmt: 'txt',
    ext: '.txt',
    name: '纯文案',
    desc: '只有正文，可直接贴到平台',
  },
  {
    id: 'report',
    kind: 'export',
    fmt: 'report',
    ext: '.md',
    name: '仅核验报告',
    desc: '给主编看的依据清单',
  },
]

export const fileTabs = computed(() => (state.result ? FILE_TABS : []))

export const activeFile = computed(
  () => FILE_TABS.find((f) => f.id === state.panel.active) || null
)

/**
 * 打开的文件内容。
 *
 * 用本地 buildFile 生成，和导出走同一个排版函数 —— 预览看到什么，下载下来就是什么。
 * 不为此专门调后端：预览要即时，而且未保存的改动也应该先看得见。
 * 下载仍然只认库里那一版（点下载会先保存），这条规则没有松动。
 */
export const activeFileContent = computed(() => {
  if (!state.result || !activeFile.value) return ''
  const f = activeFile.value
  return buildFile(draftSnapshot(), f.kind === 'draft' ? 'txt' : f.fmt).content
})

export function openFile(id) {
  if (!state.result) return
  if (!state.panel.tabs.includes(id)) state.panel.tabs.push(id)
  state.panel.active = id
  state.panel.collapsed = false
}

export function closeFile(id) {
  const i = state.panel.tabs.indexOf(id)
  if (i < 0) return
  state.panel.tabs.splice(i, 1)
  if (state.panel.active === id) {
    state.panel.active = state.panel.tabs[i] || state.panel.tabs[i - 1] || null
  }
}

/**
 * 回到文件清单。
 *
 * 打开文件后内容会把清单顶掉，标签页关完才能回去 —— 那不叫浏览器，那叫迷宫。
 * 留一个「全部文件」的入口，标签还开着，随时能切回来。
 */
export function showFileList() {
  state.panel.active = null
}

export function togglePanel() {
  state.panel.collapsed = !state.panel.collapsed
}

export function setPanelWidth(w) {
  state.panel.width = Math.max(240, Math.min(560, Math.round(w)))
}

/* ------------------------------------------------------------ 核验待办 */
/**
 * 需要人工一条条判断的待核验项。
 *
 * 队列不自己维护游标：判断完的项 status 变了，自然从队列里掉出去；
 * 跳过的项进 skipped 集合，也掉出去但可以「再看一遍」捞回来。
 * 用一个游标去追列表的话，删改一次就得手工修正下标，很容易错位。
 */
export const verifyQueue = computed(() => {
  if (!state.result) return []
  const skip = new Set(state.verify.skipped)
  return state.verify.ids
    .map((id) => findClaim(id))
    .filter((f) => f && f.claim.status === 'needs_check' && !skip.has(f.claim.id))
})

export const verifyCurrent = computed(() => verifyQueue.value[0] || null)
export const verifyTotal = computed(() => state.verify.ids.length)
export const verifySkipped = computed(() => state.verify.skipped.length)
export const verifyVisible = computed(() => !state.verify.hidden && verifyQueue.value.length > 0)

export function resetVerify() {
  state.verify.ids = claimsList.value
    .filter(({ claim }) => claim.status === 'needs_check')
    .map(({ claim }) => claim.id)
  state.verify.skipped = []
  state.verify.hidden = false
}

/**
 * 通过 / 不通过。
 *
 * 不通过不是「删掉」—— 只是把这条判定改成「无依据」，正文里加删除线。
 * 删句子是另一件事，得用户自己下指令。工具不替他做这个决定。
 */
export function verifyDecide(pass) {
  const cur = verifyCurrent.value
  if (!cur) return
  const { claim } = cur
  claim.status = pass ? 'verified' : 'unsupported'
  claim.reason =
    (claim.reason || '') +
    (pass
      ? '\n（人工复核：已确认该表述可用，责任人签署）'
      : '\n（人工复核：该表述不予采信，已标为无依据，建议在正文中删除）')
  pushHistory({
    type: 'human',
    title: pass ? '人工核验通过' : '人工核验不通过',
    who: '人工',
    whoClass: 'human',
    desc: `核验项 #${claim.id}「${claim.anchor}」由人工判定为「${STATUS_TEXT[claim.status]}」。`,
  })
  toast(pass ? '已通过，记入修改记录' : '已标为无依据，正文加删除线')
}

export function verifySkip() {
  const cur = verifyCurrent.value
  if (!cur) return
  if (!state.verify.skipped.includes(cur.claim.id)) state.verify.skipped.push(cur.claim.id)
}

export function verifyRestart() {
  state.verify.skipped = []
  state.verify.hidden = false
}

export function hideVerify() {
  state.verify.hidden = true
}

export function showVerify() {
  state.verify.hidden = false
}

/* ------------------------------------------------------------ 工具函数 */
export function currentText(seg) {
  return state.edits[seg.id] != null ? state.edits[seg.id] : seg.text
}

export function staleClaims(seg) {
  const text = currentText(seg)
  return (seg.claims || []).filter((c) => text.indexOf(c.anchor) < 0)
}

function findClaim(id) {
  if (!state.result) return null
  for (const seg of state.result.segments) {
    for (const claim of seg.claims || []) {
      if (claim.id === id) return { seg, claim }
    }
  }
  return null
}

function pushHistory(entry) {
  state.history.push({
    id: 'h' + Date.now() + Math.random().toString(16).slice(2, 6),
    time: nowTime(),
    ...entry,
  })
}

/* ------------------------------------------------------------ 抽屉数据 */
export const drawerData = computed(() => {
  const d = state.drawer
  if (!d.open || !state.result) return null

  if (d.mode === 'source') {
    const source = state.result.sources.find((s) => s.id === d.sourceId)
    if (!source) return null
    return { mode: 'source', kicker: '来源原文 · ' + source.id, title: source.title, source }
  }

  const found = findClaim(d.claimId)
  if (!found) return null
  const { seg, claim } = found
  const idx = claimsList.value.findIndex((x) => x.claim.id === claim.id) + 1

  const quotes = (claim.quotes || []).map((q) => {
    const src = state.result.sources.find((s) => s.id === q.source_id)
    const parts = splitByAnchor(q.quote, claim.anchor)
    return {
      sourceId: q.source_id,
      sourceTitle: src ? src.title : '来源缺失',
      parts,
      matched: parts.some((p) => p.mark),
      hasSource: !!src,
      publisher: src ? src.publisher : '',
      url: src ? src.url : '',
    }
  })

  return {
    mode: 'claim',
    kicker: '依据核验 · ' + STATUS_TEXT[claim.status],
    title: claim.anchor,
    seg,
    claim,
    no: String(idx).padStart(2, '0'),
    quotes,
    // 「一条引文都没有」有两种，语义正相反，界面必须分开说：
    //   blankGap = true  → 资料本身没写到（cite_ids 也为空），正文是刻意留白的，
    //                      让人去删这句话是错的，该去补资料
    //   blankGap = false → 声称有出处却没给引文，属依据缺失，该删或补来源
    blankGap: quotes.length === 0 && (claim.cite_ids || []).length === 0,
    statusClass: STATUS_CLASS[claim.status],
    promptExcerpt: state.result.prompt_excerpt || '',
    promptVersion: state.result.prompt_version || '',
  }
})

/* ------------------------------------------------------------ 启动 */
export async function init() {
  try {
    state.cases = await api.listCases()
  } catch (e) {
    state.cases = []
    toast('案例列表加载失败：' + e.message, 4000)
  }

  await loadConversations()

  // 演示直达：?demo=typical 自动载入并生成，答辩时可直接打开结果页
  const demo = new URLSearchParams(location.search).get('demo')
  if (demo) {
    const hit = state.cases.find((c) => c.id === demo || c.no === demo)
    if (hit) {
      loadCase(hit.id)
      setTimeout(() => generate(), 260)
    }
  }
}

/* ------------------------------------------------------------ 对话列表 */
export async function loadConversations() {
  state.convLoading = true
  state.convError = ''
  try {
    state.conversations = await api.listDrafts()
  } catch (e) {
    state.conversations = []
    state.convError = e.message || '草稿列表加载失败'
  } finally {
    state.convLoading = false
  }
}

/** 生成 / 保存 / 改写之后调一次，让左侧列表的标题、版本、统计跟着变。 */
export function refreshConversations() {
  loadConversations()
}

/** 从服务端的一整份草稿还原成页面状态。 */
function hydrate(d) {
  const segments = d.segments || []
  state.result = {
    draft_id: d.draft_id,
    version: d.version,
    created_at: d.created_at,
    model: d.model,
    prompt_version: d.prompt_version,
    prompt_excerpt: d.prompt_excerpt || '',
    notice: d.notice || null,
    sources: d.sources || [],
    segments,
  }
  state.draftId = d.draft_id
  state.savedVersion = d.version
  state.savedAt = d.updated_at || d.created_at
  state.history = Array.isArray(d.history) && d.history.length ? d.history : [seedAiEntry(d)]

  const input = d.input || {}
  state.material = input.material || ''
  state.requirement = input.requirement || ''
  state.platform = input.platform || 'xiaohongshu'
  state.caseId = input.case_id || null

  state.edits = {}
  state.editMode = false
  state.activeTab = 'copy'
  state.filter = null
  state.formError = ''
  state.refineError = ''
  state.phase = 'result'

  // 换了一份草稿：右栏的文件标签全部作废，核验队列按这份草稿重新快照
  state.panel.tabs = []
  state.panel.active = null
  resetVerify()
  closeDrawer()
}

/** 初稿那条「AI 生成初稿」记录：生成时写进 history，老草稿没有就补一条。 */
function seedAiEntry(d) {
  const segments = d.segments || []
  const claimCount = segments.reduce((n, s) => n + (s.claims || []).length, 0)
  const created = d.created_at || ''
  return {
    id: 'h-ai-' + d.draft_id,
    type: 'ai',
    title: 'AI 生成初稿',
    who: 'AI',
    whoClass: 'ai',
    time: created.length >= 19 ? created.slice(11, 19) : nowTime(),
    desc: `模型 ${d.model} · 提示词 ${d.prompt_version} · 共 ${segments.length} 段、${claimCount} 处事实性表述已完成来源核对。承诺：未引入资料以外的知识。`,
  }
}

export async function openConversation(draftId) {
  if (!draftId || draftId === state.draftId) return
  if (hasEdits.value) {
    const ok = await askConfirm(
      '切换到别的草稿？',
      '当前草稿有未保存的修改，切换后会丢失。想保留的话先点「保存草稿」。'
    )
    if (!ok) return
  }
  try {
    const d = await api.getDraft(draftId)
    hydrate(d)
  } catch (e) {
    toast('打开草稿失败：' + e.message, 3600)
    refreshConversations()
  }
}

export async function newConversation() {
  if (hasEdits.value) {
    const ok = await askConfirm(
      '开始新对话？',
      '当前草稿有未保存的修改，开新对话后会丢失。'
    )
    if (!ok) return
  }
  resetResult()
  state.material = ''
  state.requirement = ''
  state.caseId = null
  state.refineError = ''
}

/* ------------------------------------------------------------ 输入 */
export function loadCase(id) {
  const c = state.cases.find((x) => x.id === id)
  if (!c) return
  state.caseId = id
  state.material = c.material
  state.requirement = c.requirement
  state.platform = c.platform || 'xiaohongshu'
  state.formError = ''
  resetResult()
  toast(`已载入「${c.caseType}」示例资料，点「生成文案并核对依据」`)
}

export function setMaterial(text) {
  state.material = text
  state.caseId = null
  state.formError = ''
}

export function setRequirement(text) {
  state.requirement = text
}

export function setPlatform(p) {
  state.platform = p
}

export function resetInput() {
  state.material = ''
  state.requirement = ''
  state.caseId = null
  state.formError = ''
  resetResult()
  toast('已清空')
}

export function resetResult() {
  state.result = null
  state.edits = {}
  state.editMode = false
  state.activeTab = 'copy'
  state.filter = null
  state.draftId = null
  state.savedVersion = 0
  state.savedAt = null
  state.saveError = ''
  state.history = []
  state.phase = 'empty'
  // 右栏宽度是用户拖出来的偏好，跨草稿保留；标签页与核验队列属于上一份稿子，清掉
  state.panel.tabs = []
  state.panel.active = null
  state.verify.ids = []
  state.verify.skipped = []
  state.verify.hidden = false
  closeDrawer()
}

/* ------------------------------------------------------------ 生成 */
export async function generate() {
  const material = state.material.trim()
  if (!material) {
    state.formError = '请先粘贴资料原文，或点击上方示例案例一键载入。'
    return
  }
  if (material.length < 20) {
    state.formError = `资料只有 ${material.length} 字，生成结果会大面积为「待核验」。建议补充年代、地点、传承人、可体验项目等信息，或直接载入案例 3 查看这种边界情况的表现。`
  } else {
    state.formError = ''
  }

  resetResult()
  state.phase = 'generating'
  state.genStep = 0

  const started = Date.now()
  const timer = setInterval(() => {
    if (state.genStep < GEN_STEPS.length - 1) state.genStep += 1
  }, 420)

  try {
    const data = await api.generate({
      material,
      requirement: state.requirement.trim() || '为该项目写一篇面向年轻游客的小红书宣传文案。',
      platform: state.platform,
      case_id: state.caseId,
    })

    // 让四步进度条走完再切结果，避免接口太快导致画面一闪而过
    const rest = 900 - (Date.now() - started)
    if (rest > 0) await new Promise((r) => setTimeout(r, rest))

    state.result = data
    state.draftId = data.draft_id
    state.savedVersion = 0
    state.history = [seedAiEntry(data)]
    state.phase = 'result'
    state.panel.tabs = []
    state.panel.active = null
    resetVerify()
    refreshConversations()
    toast('生成完成，可点开上标查看依据')
  } catch (err) {
    state.phase = 'error'
    state.errorTitle = '生成失败，没有产生草稿'
    state.errorMsg = err.message || '未知错误'
  } finally {
    clearInterval(timer)
    state.genStep = GEN_STEPS.length
  }
}

export function backToInput() {
  state.phase = 'empty'
}

/* ------------------------------------------------------------ 多轮追问 */
/**
 * 把一句自然语言指令交给后端改写引擎。
 *
 * 送过去的是**当前页面上的正文**（含未保存的人工修改）—— 用户说「第二段太长」
 * 时指的是他眼睛看到的那段，不是库里那一版。
 *
 * 回执里带完整 segments，这里整段替换；history 也整份覆盖，于是聊天流
 * （由 history 推导）会自动多出「你的指令 + AI 回话」两条。
 */
export async function refine(instruction) {
  const text = (instruction || '').trim()
  if (!text || !state.draftId || state.refining) return null

  state.refining = true
  state.refineError = ''
  try {
    const res = await api.refineDraft(state.draftId, {
      instruction: text,
      base_version: state.savedVersion,
      segments: state.result.segments.map((s) => ({ id: s.id, text: currentText(s) })),
      history: state.history,
    })

    state.result.segments = res.segments
    state.edits = {}
    state.editMode = false
    state.history = res.history
    state.savedVersion = res.version
    // 改写会删掉/新增核验项，待办队列按新正文重新快照
    resetVerify()

    if (res.changed.length || res.removed_segments.length) {
      state.savedAt = res.saved_at
      toast(`已改到 v${res.version}`)
      refreshConversations()
    }
    return res
  } catch (err) {
    state.refineError = err.message || '改写失败'
    toast(state.refineError, 4200)
    return null
  } finally {
    state.refining = false
  }
}

/* ------------------------------------------------------------ 结果操作 */
export function setTab(tab) {
  state.activeTab = tab
  if (tab === 'report') state.filter = null
}

/** 顶栏按钮离卡片很远：切完标签页把卡片滚到眼前，否则用户以为没反应。 */
export function focusDraft() {
  if (!state.result) return false
  requestAnimationFrame(() => {
    const el = document.querySelector('.draft-card')
    if (el) el.scrollIntoView({ block: 'start', behavior: 'smooth' })
  })
  return true
}

export function jumpToReport(filter) {
  state.filter = filter
  state.activeTab = 'report'
}

export function setEditMode(on) {
  state.editMode = on
  if (on) {
    openFile('draft')
    toast('已进入编辑，改完记得保存草稿')
  }
}

export function setEdit(segId, text) {
  state.edits[segId] = text
}

/* ------------------------------------------------------------ 资料上传 */
/**
 * 把上传的文件读成资料。
 *
 * 资料框已有内容时**追加**而不是覆盖 —— 用户可能刚粘了一段，再补一份文件；
 * 直接替换会让他刚才的粘贴无声消失，这比多一个换行糟糕得多。
 */
export async function uploadMaterial(file) {
  if (!file || state.uploading) return null
  state.uploading = true
  try {
    const res = await api.extractFile(file)
    const had = state.material.trim().length > 0
    state.material = had ? state.material.replace(/\s+$/, '') + '\n\n' + res.text : res.text
    state.caseId = null
    state.formError = ''

    if (res.truncated) {
      toast(
        `「${res.filename}」已读入，但超过 ${res.limit} 字上限被截断，请检查资料是否完整`,
        5200
      )
    } else {
      toast(`已读入「${res.filename}」${res.chars} 字${had ? '，追加到资料末尾' : ''}`)
    }
    return res
  } catch (e) {
    state.formError = `读取文件失败：${e.message}`
    toast('读取文件失败：' + e.message, 4400)
    return null
  } finally {
    state.uploading = false
  }
}

export function openClaim(id) {
  state.drawer = { open: true, mode: 'claim', claimId: id, sourceId: null }
}

export function openSource(id) {
  state.drawer = { open: true, mode: 'source', claimId: null, sourceId: id }
}

export function closeDrawer() {
  state.drawer.open = false
  state.drawer.claimId = null
  state.drawer.sourceId = null
}

export function applySuggest() {
  const found = findClaim(state.drawer.claimId)
  if (!found) return
  const { seg, claim } = found
  if (!claim.suggest) return

  const oldText = currentText(seg)
  if (oldText.indexOf(claim.anchor) < 0) {
    toast('原表述已被改动，建议无法自动替换')
    return
  }

  state.edits[seg.id] = oldText.replace(claim.anchor, claim.suggest)
  claim.status = 'needs_check'
  claim.reason = claim.reason + '\n（已采纳 AI 建议表述，依据需重新核对）'
  pushHistory({
    type: 'human',
    title: '采纳 AI 改写建议',
    who: '人工',
    whoClass: 'human',
    desc: `核验项 #${claim.id}：把「${claim.anchor}」改为「${claim.suggest}」，该段其余依据保持不动。`,
    diff: { before: claim.anchor, after: claim.suggest },
  })
  closeDrawer()
  toast('已替换并记入修改记录，记得保存')
}

export function toggleManual() {
  const found = findClaim(state.drawer.claimId)
  if (!found) return
  const { claim } = found
  const wasVerified = claim.status === 'verified'
  claim.status = wasVerified ? 'needs_check' : 'verified'
  claim.reason =
    claim.reason +
    (wasVerified
      ? '\n（人工复核：该表述存疑，已退回待核验）'
      : '\n（人工复核：已确认该表述可用，责任人签署）')
  pushHistory({
    type: 'human',
    title: wasVerified ? '人工退回待核验' : '人工确认通过',
    who: '人工',
    whoClass: 'human',
    desc: `核验项 #${claim.id}「${claim.anchor}」由人工判定为「${STATUS_TEXT[claim.status]}」。此操作会写入草稿记录。`,
  })
  closeDrawer()
  toast('已记录人工裁决')
}

/* ------------------------------------------------------------ 保存 */
export async function save() {
  if (!state.result) return null
  const segments = state.result.segments.map((s) => ({ id: s.id, text: currentText(s) }))

  const editLog = []
  state.result.segments.forEach((s) => {
    const next = state.edits[s.id]
    if (next != null && next !== s.text) {
      editLog.push({
        segment_id: s.id,
        before: s.text,
        after: next,
        editor: 'human',
        at: new Date().toISOString(),
      })
    }
  })

  state.saving = true
  state.saveError = ''
  try {
    const res = await api.saveDraft(state.draftId, {
      base_version: state.savedVersion || 1,
      segments,
      edit_log: editLog,
      history: state.history,
    })

    // 保存成功后，编辑结果成为新的「原文」，保证导出即最后保存的版本
    state.result.segments.forEach((s) => {
      if (state.edits[s.id] != null) s.text = state.edits[s.id]
    })
    state.edits = {}
    state.savedVersion = res.version
    state.savedAt = res.saved_at

    editLog.forEach((e) => {
      const seg = state.result.segments.find((x) => x.id === e.segment_id)
      pushHistory({
        type: 'human',
        title: '人工修改正文',
        who: '人工',
        whoClass: 'human',
        desc: `段落「${seg ? seg.label || '正文' : e.segment_id}」改写后保存。`,
        diff: { before: e.before, after: e.after },
      })
    })
    pushHistory({
      type: 'save',
      title: `保存为 v${res.version}`,
      who: '系统',
      time: res.saved_at || nowTime(),
      desc: `草稿 ${state.draftId} 已写入，共 ${res.changed_segments.length} 段变更。之后导出的就是这个版本。`,
    })

    toast(`已保存为 v${res.version}`)
    refreshConversations()
    return res
  } catch (err) {
    state.saveError = err.message || '未知错误'
    toast('保存失败：' + state.saveError, 3600)
    return null
  } finally {
    state.saving = false
  }
}

/* ------------------------------------------------------------ 导出 */
export function openExport() {
  if (!state.result) {
    toast('还没有可导出的文案')
    return
  }
  state.exportOpen = true
}

export function closeExport() {
  state.exportOpen = false
}

function draftSnapshot() {
  return {
    draft_id: state.draftId,
    version: state.savedVersion,
    model: state.result.model,
    prompt_version: state.result.prompt_version,
    sources: state.result.sources,
    segments: state.result.segments,
    history: state.history,
  }
}

export async function doExport(format) {
  const version = state.savedVersion
  if (!version) {
    toast('请先保存草稿，再导出')
    return
  }

  let file = null
  if (api.isMock()) {
    file = buildFile(draftSnapshot(), format)
  } else {
    try {
      file = await api.exportDraft(state.draftId, format, state.history)
    } catch (e) {
      // 后端导出异常时不让演示中断：本地按同一套规则生成
      file = buildFile(draftSnapshot(), format)
      toast('后端导出接口异常，已改用本地生成（排版规则一致）', 3200)
    }
  }

  download(file.filename, file.content)
  closeExport()
  toast(`已导出 v${version}，草稿编号 ${state.draftId}`)
}

export async function copyAll() {
  if (!state.result) return
  const plain = buildFile(draftSnapshot(), 'txt').content
  const ok = await copyText(plain)
  toast(
    ok ? '全文已复制' : '复制被浏览器阻止，请用「导出」保存文件',
    ok ? 2400 : 3600
  )
}

export async function saveThenExport() {
  const res = await save()
  if (res) state.exportOpen = true
}

/* ------------------------------------------------------------ 模式切换 */
export function askConfirm(title, desc) {
  return new Promise((resolve) => {
    confirmResolver = resolve
    state.confirm.title = title
    state.confirm.desc = desc
    state.confirm.open = true
  })
}

export function resolveConfirm(value) {
  state.confirm.open = false
  const resolve = confirmResolver
  confirmResolver = null
  if (resolve) resolve(value)
}

export async function toggleMode() {
  const next = !api.isMock()
  const ok = await askConfirm(
    next ? '切换到示例数据模式？' : '切换到真实后端？',
    next
      ? '页面将使用内置的 3 个示例案例，适合第一次跑通流程和答辩演示。'
      : '页面将请求后端 /api/generate。如果服务还没启动，会进入「生成失败」状态——这也是要演示的容错分支。'
  )
  if (!ok) return
  api.setMock(next)
  state.mode = api.modeLabel()
  toast(next ? '已切换为示例数据' : '已切换为真实后端，请确认服务已启动')
}
