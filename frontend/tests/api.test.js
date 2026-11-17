import { test } from 'node:test'
import assert from 'node:assert/strict'
import { generate, getDraft, saveDraft, exportDraft } from '../src/api/index.js'

test('C requests preserve separate sources and use POST / GET / PATCH / GET export', async () => {
  const original = globalThis.fetch
  const calls = []
  const bytes = '【人工修改后待复核】\n保存后的中文文案'
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return url.endsWith('/export')
      ? new Response(bytes, { headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename="draft_1.txt"' } })
      : Response.json({ draftId: 'draft_1', mode: 'mock' })
  }
  try {
    const payload = { sources: [{ title: '甲', text: '甲原文', url: 'https://example.com/a' }, { title: '乙', text: '乙原文' }], brief: '宣传需求', platform: '小红书' }
    await generate(payload)
    await getDraft('draft_1')
    await saveDraft('draft_1', [{ blockId: 'block_2', text: '新句' }])
    const file = await exportDraft('draft_1')
    assert.deepEqual(calls.map(({ url, options }) => [url, options.method]), [
      ['/api/drafts', 'POST'], ['/api/drafts/draft_1', 'GET'], ['/api/drafts/draft_1', 'PATCH'], ['/api/drafts/draft_1/export', 'GET'],
    ])
    assert.deepEqual(JSON.parse(calls[0].options.body), payload)
    assert.deepEqual(JSON.parse(calls[2].options.body), { edits: [{ blockId: 'block_2', text: '新句' }] })
    assert.equal(calls[3].options.body, undefined)
    assert.equal(file.filename, 'draft_1.txt')
    assert.equal(await file.blob.text(), bytes)
  } finally { globalThis.fetch = original }
})

test('export failure rejects without returning substitute file; validation errors stay readable', async () => {
  const original = globalThis.fetch
  try {
    globalThis.fetch = async () => Response.json({ detail: { code: 'draft_not_found', message: '草稿不存在' } }, { status: 404 })
    await assert.rejects(exportDraft('missing'), (e) => e.code === 'draft_not_found' && e.message === '草稿不存在')
    globalThis.fetch = async () => Response.json({ detail: [{ loc: ['body', 'sources', 0, 'text'], msg: '资料不能为空' }] }, { status: 422 })
    await assert.rejects(generate({}), /sources.0.text: 资料不能为空/)
    globalThis.fetch = async () => new Response('<html>proxy page</html>', { headers: { 'Content-Type': 'text/html' } })
    await assert.rejects(exportDraft('draft_1'), /未返回 TXT/)
  } finally { globalThis.fetch = original }
})
