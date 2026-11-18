<script setup>
import { visibleHistory } from '../stores/draft'
</script>

<template>
  <div class="history">
    <div v-if="!visibleHistory.length" class="empty-mini">还没有记录。</div>

    <template v-else>
      <div class="timeline">
        <div v-for="h in visibleHistory" :key="h.id" class="tl-item" :class="h.type">
          <div class="tl-head">
            <span class="tl-title">{{ h.title }}</span>
            <span class="tl-who" :class="h.whoClass">{{ h.who }}</span>
            <span class="tl-time">{{ h.time }}</span>
          </div>
          <div class="tl-desc">{{ h.desc }}</div>

          <div v-if="h.instruction" class="tl-instruction">「{{ h.instruction }}」</div>

          <div v-if="h.diff" class="diff">
            <div class="diff-row del">
              <span class="diff-sign">−</span><span>{{ h.diff.before }}</span>
            </div>
            <div class="diff-row ins">
              <span class="diff-sign">+</span><span>{{ h.diff.after }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="empty-mini" style="margin-top: 8px; text-align: left; line-height: 1.8">
        这份记录会随草稿一起保存，用于说明「哪些内容是 AI 写的、哪些是人改的」。
        导出时会附在文末，对应赛道三「人机协作留痕」的评审要求。
      </div>
    </template>
  </div>
</template>
