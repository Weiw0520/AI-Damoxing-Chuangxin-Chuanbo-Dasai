const ENV = import.meta.env || {}
const BASE = (ENV.VITE_API_BASE || '/api').replace(/\/$/, '')
const TIMEOUT = Number(ENV.VITE_TIMEOUT_MS || 60000)

export class ApiFailure extends Error {
  constructor(message, code = 'UNKNOWN', status = 0) {
    super(message)
    this.name = 'ApiFailure'
    this.code = code
    this.status = status
  }
}

export function errorDetail(data, status) {
  const detail = data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => `${(item.loc || []).filter((v) => v !== 'body').join('.')}: ${item.msg}`).join('；')
  }
  return (typeof detail === 'string' ? detail : detail?.message) || `请求失败（HTTP ${status}）`
}

export async function request(path, { method = 'GET', body, responseType = 'json', timeout = TIMEOUT } = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeout)
  try {
    const res = await fetch(BASE + path, {
      method, signal: ctrl.signal,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => null)
      throw new ApiFailure(errorDetail(data, res.status), data?.detail?.code || `HTTP_${res.status}`, res.status)
    }
    if (responseType === 'download') {
      if (!res.headers.get('Content-Type')?.toLowerCase().startsWith('text/plain')) {
        throw new ApiFailure('导出接口未返回 TXT 文件，未触发下载。', 'INVALID_EXPORT', res.status)
      }
      const disposition = res.headers.get('Content-Disposition') || ''
      const filename = /filename="?([^";]+)"?/i.exec(disposition)?.[1] || 'draft.txt'
      return { filename, blob: await res.blob() }
    }
    return await res.json()
  } catch (error) {
    if (error instanceof ApiFailure) throw error
    if (error.name === 'AbortError') {
      throw new ApiFailure('请求超时。请重新读取草稿确认保存状态后再重试。', 'CLIENT_TIMEOUT')
    }
    throw new ApiFailure('无法连接 C 后端，请确认后端已启动及 /api 代理配置正确。', 'NETWORK_ERROR')
  } finally { clearTimeout(timer) }
}
