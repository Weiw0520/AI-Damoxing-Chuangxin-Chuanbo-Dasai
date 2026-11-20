import assert from 'node:assert/strict'
import { after, afterEach, beforeEach, test } from 'node:test'
import { createServer } from 'vite'

// Exercise the real store and HTTP client, with controllable HTTP completion order.
process.env.VITE_USE_MOCK = 'false'
const vite = await createServer({ configFile: false, optimizeDeps: { noDiscovery: true, include: [] },
  server: { middlewareMode: true, hmr: false }, appType: 'custom' })
const store = await vite.ssrLoadModule('/src/stores/draft.js')
const { toastState } = await vite.ssrLoadModule('/src/utils/toast.js')
const clone = (x) => JSON.parse(JSON.stringify(x))
const json = (data, status = 200) => new Response(JSON.stringify(data), { status })
let drafts, pending
function draft(id = 'A', version = 1) {
  return { draft_id: id, version, created_at: '2026-11-20', updated_at: '2026-11-20',
    model: 'fixture-NOT-LIVE', sources: [], input: {}, history: [], segments: [
      { id: 'P1', label: '正文1', text: id + '第一段', claims: [] },
      { id: 'P2', label: '正文2', text: id + '第二段', claims: [] },
    ] }
}
function reply(id = 'A') {
  return { ...draft(id, 2), saved_at: '2026-11-20T01:00', changed: ['P1'], removed_segments: [],
    changed_segments: ['P1'], segments: draft(id).segments.map(s => ({ ...s, text: s.text + 'AI改写' })) }
}
beforeEach(async () => {
  drafts = { A: draft('A'), B: draft('B') }; pending = []
  globalThis.fetch = async (url, options = {}) => {
    const method = options.method || 'GET'
    if (method === 'GET') {
      return json(url === '/api/drafts' ? [] : clone(drafts[url.split('/').at(-1)]))
    }
    return new Promise(resolve => pending.push({ url, body: JSON.parse(options.body),
      ok: data => resolve(json(data)), fail: () => resolve(json({ detail: { message: '故障模拟', code: 'TEST_FAILURE' } }, 502)) }))
  }
  store.resetResult(); store.state.saving = false; store.state.refining = false
  await store.openConversation('A')
})
after(async () => { await vite.close() })
afterEach(async () => {
  for (const request of pending) request.fail()
  await new Promise(resolve => setImmediate(resolve))
})
async function open(id) {
  const p = store.openConversation(id)
  if (store.state.confirm.open) store.resolveConfirm(true)
  await p
}

test('refine preserves edits made after submission, including reverting to old text', async () => {
  store.setEdit('P1', '提交给AI的文字')
  const work = store.refine('精简')
  assert.equal(pending[0].body.segments[0].text, '提交给AI的文字')
  store.setEdit('P1', 'A第一段')
  pending[0].ok(reply()); await work
  assert.equal(store.currentText(store.state.result.segments[0]), 'A第一段')
  assert.equal(store.state.result.segments[0].text, 'A第一段AI改写')
  assert.equal(store.hasEdits.value, true)
  assert.equal(store.state.editMode, true)
})

test('refine structure conflict retains removed paragraph text visibly and dirty', async () => {
  const work = store.refine('删除第二段')
  store.setEdit('P2', 'AI等待期间输入的完整人工段落，不能被删除。')
  const result = reply(); result.segments = result.segments.slice(0, 1); result.removed_segments = ['P2']
  pending[0].ok(result); await work
  const visible = store.state.result.segments.map(store.currentText).join('\n')
  assert.ok(visible.includes('AI等待期间输入的完整人工段落，不能被删除。'))
  assert.ok(visible.includes('结构冲突'))
  assert.equal(store.hasEdits.value, true)
  assert.match(toastState.message, /段落结构/)
})

test('refine preserves a later edit even when typing returns to submitted text', async () => {
  const work = store.refine('精简')
  store.setEdit('P1', '临时输入')
  store.setEdit('P1', 'A第一段')
  pending[0].ok(reply()); await work
  assert.equal(store.currentText(store.state.result.segments[0]), 'A第一段')
  assert.equal(store.hasEdits.value, true)
})

test('save acknowledges submitted text only; later edits remain dirty', async () => {
  store.setEdit('P1', '本次提交')
  const work = store.save()
  store.setEdit('P1', '提交后继续输入')
  pending[0].ok(reply()); await work
  assert.equal(store.state.result.segments[0].text, '本次提交')
  assert.equal(store.currentText(store.state.result.segments[0]), '提交后继续输入')
  assert.equal(store.hasEdits.value, true)
})

test('old save response cannot acknowledge edits in another draft', async () => {
  store.setEdit('P1', 'A提交')
  const work = store.save()
  await open('B'); store.setEdit('P1', 'B尚未提交的新句')
  pending[0].ok(reply()); await work
  assert.equal(store.state.savedVersion, 1)
  assert.equal(store.state.result.segments[0].text, 'B第一段')
  assert.equal(store.currentText(store.state.result.segments[0]), 'B尚未提交的新句')
  assert.equal(store.hasEdits.value, true)
  assert.ok(!store.state.history.some(h => h.diff?.after === 'A提交'))
})

for (const kind of ['save', 'refine']) {
  test(`${kind}: mismatched receipt draft ID is rejected without losing edits`, async () => {
    store.setEdit('P1', '必须保留的人工字句')
    const work = kind === 'save' ? store.save() : store.refine('修改')
    pending[0].ok(reply('B')); await work
    assert.equal(store.currentText(store.state.result.segments[0]), '必须保留的人工字句')
    assert.equal(store.hasEdits.value, true)
    assert.equal(store.state.savedVersion, 1)
  })
  for (const outcome of ['ok', 'fail']) {
    test(`${kind}: old ${outcome}/finally cannot change a newer request`, async () => {
      store.setEdit('P1', 'A提交')
      const old = kind === 'save' ? store.save() : store.refine('A要求')
      await open('B'); store.setEdit('P1', 'B提交')
      const next = kind === 'save' ? store.save() : store.refine('B要求')
      assert.equal(pending.length, 2, 'switching must allow work on another draft')
      const busy = kind === 'save' ? 'saving' : 'refining'
      const error = kind === 'save' ? 'saveError' : 'refineError'
      pending[0][outcome](reply()); await old
      assert.equal(store.state[busy], true)
      assert.equal(store.state[error], '')
      pending[1].ok(reply('B')); await next
      assert.equal(store.state[busy], false)
      assert.equal(store.state.draftId, 'B')
    })
  }
  test(`${kind}: switching away and back invalidates the old view receipt`, async () => {
    const old = kind === 'save' ? store.save() : store.refine('A要求')
    await open('B'); drafts.A = draft('A', 2); await open('A')
    store.setEdit('P1', '重新打开之后的新编辑')
    pending[0].ok(reply()); await old
    assert.equal(store.currentText(store.state.result.segments[0]), '重新打开之后的新编辑')
    assert.equal(store.state.result.segments[0].text, 'A第一段')
    assert.equal(store.hasEdits.value, true)
  })
  test(`${kind}: failure preserves submitted and subsequent manual text`, async () => {
    store.setEdit('P1', '已提交')
    const work = kind === 'save' ? store.save() : store.refine('测试失败')
    store.setEdit('P1', '失败前继续输入')
    pending[0].fail(); await work
    assert.equal(store.currentText(store.state.result.segments[0]), '失败前继续输入')
    assert.equal(store.hasEdits.value, true)
    assert.equal(store.state.savedVersion, 1)
  })
}
