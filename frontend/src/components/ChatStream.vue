<script setup>
/**
 * 中栏：当前对话。
 *
 * 三栏里只有它是「活的」——左边选一份草稿，这里就换成那一段对话；
 * 输入框在底部，追问之后消息流自己长出新的一轮。
 */
import { computed, nextTick, ref, watch } from 'vue'
import ChatMessage from './ChatMessage.vue'
import InputPanel from './InputPanel.vue'
import Composer from './Composer.vue'
import GeneratingState from './states/GeneratingState.vue'
import ErrorState from './states/ErrorState.vue'
import { chatItems, currentConv, lastReplyId, state } from '../stores/draft'

const scroller = ref(null)

const title = computed(() => {
  if (state.phase === 'empty') return '新对话'
  return currentConv.value?.title || '当前对话'
})

const subtitle = computed(() => {
  if (state.phase === 'empty') return '提交资料后开始'
  if (state.phase === 'generating') return '正在生成与核对'
  if (state.phase === 'error') return '生成失败'
  return `${state.draftId || '草稿未创建'} · ${state.savedAt ? '已保存' : '未保存'}`
})

/** 新生成的一份文案从资料读起；切到旧草稿也一样，先看到自己提交了什么。 */
watch(
  () => state.phase,
  async (p) => {
    if (p !== 'result') return
    await nextTick()
    if (scroller.value) scroller.value.scrollTop = 0
  }
)

/** 多出一轮追问时滚到那句回话：下面紧接着就是改写后的卡片。 */
watch(
  () => chatItems.value.length,
  async () => {
    const id = lastReplyId.value
    if (!id) return
    await nextTick()
    document.getElementById('msg-' + id)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }
)
</script>

<template>
  <section class="col col-mid">
    <div class="chat-head">
      <div class="ch-text">
        <h2>{{ title }}</h2>
        <span class="ch-sub">{{ subtitle }}</span>
      </div>

    </div>

    <!-- 待办顶在正文上方：生成完先看到「哪几条要你拍板」，不用翻核验报告 -->
    <div v-if="state.phase === 'result'" class="integration-note">{{ state.newDraftNotice || '底部输入框会按新要求生成另一份草稿并保留原稿，不是多轮 AI 对话。' }}</div>

    <div ref="scroller" class="chat-scroll">
      <div class="chat-inner">
        <InputPanel v-if="state.phase === 'empty'" />
        <GeneratingState v-else-if="state.phase === 'generating'" />
        <ErrorState v-else-if="state.phase === 'error'" />

        <template v-else>
          <ChatMessage v-for="it in chatItems" :key="it.id" :item="it" />
        </template>
      </div>
    </div>

    <Composer v-if="state.phase === 'result'" />
  </section>
</template>
