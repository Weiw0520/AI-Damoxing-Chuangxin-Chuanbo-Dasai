import { reactive } from 'vue'

/** 同一时刻只显示一条提示，与原型行为一致。 */
export const toastState = reactive({ message: '', visible: false })

let timer = null

export function toast(message, ms = 2400) {
  toastState.message = message
  toastState.visible = true
  clearTimeout(timer)
  timer = setTimeout(() => {
    toastState.visible = false
  }, ms)
}
