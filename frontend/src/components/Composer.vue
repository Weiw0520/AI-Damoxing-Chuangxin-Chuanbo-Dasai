<script setup>
import { nextTick, ref } from 'vue'
import { generateFromRequirements, isBusy, state } from '../stores/draft'

const ta = ref(null)
function autogrow() {
  if (!ta.value) return
  ta.value.style.height = 'auto'
  ta.value.style.height = Math.min(ta.value.scrollHeight, 120) + 'px'
}
async function send() {
  if (isBusy.value) return
  const result = await generateFromRequirements()
  if (result) { await nextTick(); autogrow() }
  ta.value?.focus()
}
function onKeydown(e) {
  if (e.key !== 'Enter' || e.shiftKey || e.isComposing) return
  e.preventDefault()
  send()
}
</script>

<template>
  <form class="composer" @submit.prevent="send">
    <div class="composer-inner">
      <label for="newDraftRequirement" class="composer-title">新草稿生成要求</label>
      <div class="composer-box" :class="{ 'is-busy': state.creatingFromBrief }">
        <textarea
          id="newDraftRequirement"
          ref="ta"
          v-model="state.composerText"
          rows="2"
          class="composer-input"
          placeholder="例如：更简短，侧重工艺介绍。将使用原资料创建另一份草稿。"
          :disabled="isBusy"
          @input="autogrow"
          @keydown="onKeydown"
        ></textarea>
        <button type="submit" class="send-btn" :disabled="isBusy || !state.composerText.trim()">
          {{ state.creatingFromBrief ? '正在生成新草稿…' : '按新要求生成新草稿' }}
        </button>
      </div>
      <p v-if="state.composerError" role="alert" class="composer-error">{{ state.composerError }}</p>
      <div class="composer-hint">
        <span>沿用原资料与平台，合并原需求和新增要求；保留原稿，不是多轮 AI 对话。{{ state.result?.mode === 'mock' ? '模拟生成器仅演示流程，不执行真实改写或核验。' : '' }}</span>
      </div>
    </div>
  </form>
</template>
