<script setup>
import { ref } from 'vue'
import { isBusy, newConversation, openConversation, state } from '../stores/draft'
const draftId = ref('')
</script>
<template>
  <aside class="col col-left">
    <div class="left-head"><h2>草稿</h2><button class="btn btn-new" :disabled="isBusy" @click="newConversation">＋ 新建</button></div>
    <div class="conv-scroll">
      <form class="draft-loader" @submit.prevent="openConversation(draftId)">
        <label class="field-label" for="loadDraft">按草稿编号读取</label>
        <input id="loadDraft" v-model="draftId" placeholder="draft_…" />
        <button class="btn btn-ghost" :disabled="!draftId.trim() || isBusy">{{ state.loadingDraft ? '读取中…' : '读取草稿' }}</button>
      </form>
      <p class="conv-hint">以下仅为本页打开过的草稿快捷入口。服务端草稿列表暂不支持；刷新会按 URL 或本机记录读取最后一份草稿。</p>
      <button v-for="c in state.conversations" :key="c.draft_id" class="conv-item" :class="{ 'is-active': c.draft_id === state.draftId }" @click="openConversation(c.draft_id)">
        <span class="conv-title">{{ c.title }}</span><span class="conv-preview">{{ c.preview }}</span><span class="conv-meta">{{ new Date(c.updated_at).toLocaleString('zh-CN') }}</span>
      </button>
    </div>
    <div class="left-foot"><span class="mode-pill is-live">{{ state.mode }}</span></div>
  </aside>
</template>
