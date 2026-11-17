/**
 * 复制与下载。
 *
 * 注意：现在页面跑在 http://127.0.0.1:5173 下，属于安全上下文，
 * navigator.clipboard 正常可用；但同一份代码将来若被双击打开（file://），
 * 剪贴板 API 会被浏览器拒绝，所以这里保留 execCommand 兜底。
 */

export async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch (e) {
    /* 落到下面的兜底 */
  }
  return fallbackCopy(text)
}

function fallbackCopy(text) {
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.cssText = 'position:fixed;top:-9999px;left:0;opacity:0'
    document.body.appendChild(ta)
    ta.select()
    ta.setSelectionRange(0, text.length)
    const ok = document.execCommand('copy')
    ta.remove()
    return ok
  } catch (e) {
    return false
  }
}

export function download(filename, blob) {
  if (!(blob instanceof Blob)) throw new Error('服务端下载内容无效')
  const a = document.createElement('a')
  a.download = filename
  let objectUrl = null
  if (typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
    objectUrl = URL.createObjectURL(blob)
    a.href = objectUrl
  } else throw new Error('浏览器不支持文件下载')
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    if (objectUrl) URL.revokeObjectURL(objectUrl)
    a.remove()
  }, 1000)
}
