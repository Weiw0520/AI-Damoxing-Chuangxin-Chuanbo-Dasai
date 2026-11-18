<script setup>
/**
 * 左栏：对话列表。
 *
 * 一行 = 一份草稿。标题取正文第一段，预览取第二段开头 —— 评委一眼能看出
 * 「这份稿子是关于哪个项目的」，不用点进去。
 */
import { computed } from 'vue'
import {
  loadConversations,
  newConversation,
  openConversation,
  state,
  toggleMode,
} from '../stores/draft'

const items = computed(() => state.conversations)

function pending(c) {
  const s = c.stats || {}
  return (s.needs_check || 0) + (s.unsupported || 0)
}

/** 今天只显示时分，其余显示月-日。列表里全是完整时间戳会挤成一片。 */
function fmtTime(raw) {
  if (!raw) return ''
  const s = String(raw).replace('T', ' ')
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate()
  ).padStart(2, '0')}`
  if (s.slice(0, 10) === today) return s.slice(11, 16) || '今天'
  return s.slice(5, 10)
}
</script>

<template>
  <aside class="col col-left">
    <div class="left-head">
      <h2>对话</h2>
      <button class="btn btn-new" @click="newConversation">＋ 新建</button>
    </div>

    <div class="conv-scroll">
      <div v-if="state.convLoading && !items.length" class="conv-hint">正在读取草稿…</div>

      <div v-else-if="state.convError" class="conv-hint is-error">
        <p>{{ state.convError }}</p>
        <button class="link-btn" @click="loadConversations">重试</button>
      </div>

      <div v-else-if="!items.length" class="conv-hint">
        <p>还没有草稿。</p>
        <p>点「新建」提交一份资料，生成的每一版都会出现在这里。</p>
      </div>

      <button
        v-if="state.phase === 'empty' && items.length"
        class="conv-item is-active is-new"
        @click="newConversation"
      >
        <span class="conv-title">新对话</span>
        <span class="conv-preview">等待提交资料…</span>
      </button>

      <button
        v-for="c in items"
        :key="c.draft_id"
        class="conv-item"
        :class="{ 'is-active': c.draft_id === state.draftId }"
        @click="openConversation(c.draft_id)"
      >
        <span class="conv-title">{{ c.title || '未命名文案' }}</span>
        <span v-if="c.preview" class="conv-preview">{{ c.preview }}</span>
        <span class="conv-meta">
          <span class="conv-ver">v{{ c.version }}</span>
          <span v-if="pending(c)" class="conv-badge">{{ pending(c) }} 待核</span>
          <span class="conv-time">{{ fmtTime(c.updated_at || c.created_at) }}</span>
        </span>
      </button>
    </div>

    <div class="left-foot">
      <span class="mode-pill" :class="{ 'is-live': state.mode === '真实后端模式' }">
        {{ state.mode }}
      </span>
      <button class="link-btn" title="后端未启动时可切到内置示例数据" @click="toggleMode">
        切换
      </button>
    </div>
  </aside>
</template>
