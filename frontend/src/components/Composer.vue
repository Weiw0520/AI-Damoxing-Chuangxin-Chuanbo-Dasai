<script setup>
/**
 * 中栏底部的输入框 —— 生成之后，用户在这里继续提要求。
 *
 * 这里只负责「把一句话交出去」，判断能不能改、怎么改全在服务端。
 * 前端不做本地规则：同一句话在两处被解释成两个意思，是最难查的那种 bug。
 */
import { computed, nextTick, ref } from 'vue'
import { refine, state } from '../stores/draft'

const QUICK = [
  '删掉无依据的表述',
  '第二段太长，压缩一半',
  '把没出处的说法改保守',
  '这些依据分别是什么',
]

const text = ref('')
const ta = ref(null)
const busy = computed(() => state.refining)

function autogrow() {
  const el = ta.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

async function send(preset) {
  if (busy.value) return
  const t = (preset != null ? preset : text.value).trim()
  if (!t) return

  const res = await refine(t)
  // 成功才清空：失败（比如示例数据模式下不能追问）时把话留在框里，改完能直接重发
  if (res) {
    text.value = ''
    await nextTick()
    autogrow()
  }
  ta.value?.focus()
}

function onKeydown(e) {
  if (e.key !== 'Enter' || e.shiftKey) return
  if (e.isComposing) return // 中文输入法选词时的回车不能当发送
  e.preventDefault()
  send()
}
</script>

<template>
  <div class="composer">
    <div class="composer-inner">
      <div class="quick-row">
        <button
          v-for="q in QUICK"
          :key="q"
          class="quick-chip"
          :disabled="busy"
          @click="send(q)"
        >
          {{ q }}
        </button>
      </div>

      <div class="composer-box" :class="{ 'is-busy': busy }">
        <textarea
          ref="ta"
          v-model="text"
          rows="1"
          class="composer-input"
          placeholder="继续说要求，例如「删掉第三段那句没出处的」「整体再短一点」"
          :disabled="busy"
          @input="autogrow"
          @keydown="onKeydown"
        ></textarea>

        <button class="send-btn" :disabled="busy || !text.trim()" @click="send()">
          {{ busy ? '改写中…' : '发送' }}
        </button>
      </div>

      <div class="composer-hint">
        <span v-if="state.refineError" class="composer-error">{{ state.refineError }}</span>
        <span v-else class="composer-tip">
          能删、能压缩、能改保守；不会凭空补事实 —— 补写会让核验结论失效。
        </span>
        <span class="composer-kbd">Enter 发送 · Shift + Enter 换行</span>
      </div>
    </div>
  </div>
</template>
