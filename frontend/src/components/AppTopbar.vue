<script setup>
import { computed } from 'vue'
import { focusDraft, hasEdits, openExport, setTab, state } from '../stores/draft'
import { toast } from '../utils/toast'

const draftText = computed(() => {
  if (!state.draftId) return '草稿 未创建'
  return `草稿 ${state.draftId}`
})

const saveState = computed(() => {
  if (state.phase !== 'result') return { text: '—', cls: '' }
  if (hasEdits.value) return { text: '● 未保存修改', cls: 'is-dirty' }
  if (state.savedVersion > 0) return { text: '✓ 已由服务端保存', cls: 'is-saved' }
  return { text: '草稿尚未保存', cls: '' }
})

function goHistory() {
  if (!state.result) {
    toast('先生成一篇文案')
    return
  }
  setTab('history')
  // 卡片在对话流最底下，不滚过去的话用户会以为按钮没反应
  focusDraft()
}
</script>

<template>
  <header class="topbar">
    <div class="brand">
      <span class="seal">校</span>
      <div class="brand-text">
        <h1>鲁遗校真</h1>
        <p>山东非遗文旅宣传内容核验与改写助手</p>
      </div>
    </div>

    <div class="topbar-meta">
      <span class="mode-pill is-live">{{ state.mode }}</span>
      <div class="draft-chip" :class="{ 'is-live': !!state.draftId }" title="同一草稿贯穿生成、编辑、导出">
        <span class="dot"></span>
        <span>{{ draftText }}</span>
      </div>

      <div class="save-state" :class="saveState.cls">{{ saveState.text }}</div>

      <div class="topbar-actions">
        <button class="btn btn-ghost" title="查看 AI 生成与人工修改记录" @click="goHistory">
          协作记录
        </button>
        <button class="btn btn-primary" @click="openExport">
          导出
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path
              d="M2 8v2h8V8M6 1v6M3.5 4.5L6 7l2.5-2.5"
              stroke="currentColor"
              stroke-width="1.3"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>
  </header>
</template>
