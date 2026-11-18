/**
 * 统一请求封装。
 *
 * 所有接口都走相对路径 /api —— 开发时由 Vite 代理到 127.0.0.1:8000，
 * 生产时由后端自己托管 dist，两种部署方式都不用改代码。
 */

const BASE = import.meta.env.VITE_API_BASE || '/api'
const TIMEOUT = Number(import.meta.env.VITE_TIMEOUT_MS || 60000)

export class ApiFailure extends Error {
  constructor(message, code = 'UNKNOWN', status = 0) {
    super(message)
    this.name = 'ApiFailure'
    this.code = code
    this.status = status
  }
}

export async function request(path, { method = 'GET', body, raw = false, timeout = TIMEOUT } = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeout)

  // raw=true 时 body 原样发出（File / Blob / ArrayBuffer），不套 JSON。
  // 上传资料走这条路：后端用 request.body() 读原始字节，省掉 multipart 依赖。
  const payload = body === undefined ? undefined : raw ? body : JSON.stringify(body)
  const headers = body === undefined || raw ? undefined : { 'Content-Type': 'application/json' }

  let res
  try {
    res = await fetch(BASE + path, {
      method,
      headers,
      body: payload,
      signal: ctrl.signal,
    })
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new ApiFailure(
        `请求超时（${Math.round(timeout / 1000)} 秒）。资料较长时模型可能来不及返回，可先缩短资料再试。`,
        'CLIENT_TIMEOUT',
        0
      )
    }
    throw new ApiFailure(
      '连不上后端服务。请确认 backend 已启动（默认 http://127.0.0.1:8000），或点左下角「切换」改用示例数据模式。',
      'NETWORK_ERROR',
      0
    )
  } finally {
    clearTimeout(timer)
  }

  const text = await res.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch (e) {
      data = null
    }
  }

  if (!res.ok) {
    const detail = data && data.detail
    const message =
      (detail && typeof detail === 'object' ? detail.message : detail) ||
      `请求失败（HTTP ${res.status}）`
    const code = (detail && typeof detail === 'object' && detail.code) || `HTTP_${res.status}`
    throw new ApiFailure(message, code, res.status)
  }

  return data
}
