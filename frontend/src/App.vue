<script setup>
/**
 * 三栏骨架：左边对话列表，中间当前对话，右边文件。
 *
 * pane 只在窄屏（≤980px）用得上 —— 三栏挤不下时，中间那栏顶部会出现
 * 一个切换器，一屏只看一栏。宽屏上它被 CSS 隐藏，不影响布局。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppTopbar from './components/AppTopbar.vue'
import ConversationList from './components/ConversationList.vue'
import ChatStream from './components/ChatStream.vue'
import FilePanel from './components/FilePanel.vue'
import SourceDrawer from './components/SourceDrawer.vue'
import ExportModal from './components/ExportModal.vue'
import ConfirmModal from './components/ConfirmModal.vue'
import ToastHost from './components/ToastHost.vue'
import { closeDrawer, closeExport, generate, init, state } from './stores/draft'

const pane = computed({ get: () => state.activePane, set: (value) => { state.activePane = value } })
const viewport = ref(0)

/**
 * 右栏宽度由用户拖动决定，收起时收成一条图标轨。
 * 用 CSS 变量喂给 .shell 的 grid-template-columns，组件本身不用知道栅格怎么排。
 *
 * 还要盖一层「别把中栏挤没了」的限制：用户可以把右栏拖到 560，
 * 但窗口只有 900 宽的时候，560 加左栏就只剩 90 给正文 ——
 * 正文是主角，宁可让右栏自己收窄。所以实际宽度取「用户拖的」
 * 与「窗口宽度减掉左栏、再留够正文最低宽度」二者的小值。
 */
const MIN_MID = 420 // 正文再窄就没法读了
const MIN_RIGHT = 200 // 再窄连文件名都放不下
const LEFT_W = 264

const rightWidth = computed(() => {
  if (state.panel.collapsed) return '56px'
  // 首帧还没有视口宽度，先按用户拖的来，避免闪一下
  if (!viewport.value) return state.panel.width + 'px'
  const room = viewport.value - LEFT_W - MIN_MID
  return Math.max(MIN_RIGHT, Math.min(state.panel.width, room)) + 'px'
})

function onResize() {
  viewport.value = window.innerWidth
}

function onKeydown(e) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    e.preventDefault()
    if (state.phase === 'empty') generate()
  }
  if (e.key === 'Escape') {
    closeDrawer()
    closeExport()
  }
}

onMounted(() => {
  init()
  onResize()
  window.addEventListener('resize', onResize)
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="app">
    <AppTopbar />

    <nav class="pane-switch workspace-nav" aria-label="工作区栏位">
      <button :class="{ 'is-on': pane === 'list' }" :aria-pressed="pane === 'list'" @click="pane = 'list'">草稿</button>
      <button :class="{ 'is-on': pane === 'chat' }" :aria-pressed="pane === 'chat'" @click="pane = 'chat'">正文</button>
      <button :class="{ 'is-on': pane === 'files' }" :aria-pressed="pane === 'files'" @click="pane = 'files'">文件</button>
    </nav>

    <div class="shell" :class="'pane-' + pane" :style="{ '--right-w': rightWidth }">
      <ConversationList />
      <ChatStream />
      <FilePanel />
    </div>
  </div>

  <SourceDrawer />
  <ExportModal />
  <ConfirmModal />
  <ToastHost />
</template>
