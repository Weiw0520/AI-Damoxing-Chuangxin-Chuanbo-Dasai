// C is the only persistence and export provider. No offline result fallback.
import { request } from './client.js'
const draftPath = (id) => `/drafts/${encodeURIComponent(id)}`
export const generate = (payload) => request('/drafts', { method: 'POST', body: payload })
export const getDraft = (id) => request(draftPath(id))
export const saveDraft = (id, edits) => request(draftPath(id), { method: 'PATCH', body: { edits } })
export const exportDraft = (id) => request(`${draftPath(id)}/export`, { responseType: 'download' })
