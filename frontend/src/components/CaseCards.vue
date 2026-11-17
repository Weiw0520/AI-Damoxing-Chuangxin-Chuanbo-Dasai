<script setup>
import { loadCase, state } from '../stores/draft'
</script>

<template>
  <div class="case-loader">
    <label class="field-label">
      载入示例资料 <span class="tag-muted">结果由 C 后端生成</span>
    </label>

    <div class="case-list">
      <button
        v-for="c in state.cases"
        :key="c.id"
        class="case-card"
        :class="{ 'is-active': state.caseId === c.id }"
        @click="loadCase(c.id)"
      >
        <span class="case-no">{{ c.no }}</span>
        <span class="case-body">
          <span class="case-title">{{ c.label }}</span>
          <span class="case-hint">{{ c.hint }}</span>
        </span>
      </button>

      <div v-if="!state.cases.length" class="empty-mini" style="text-align: left">
        暂无预设资料，请填写每份资料的标题与原文。
      </div>
    </div>
  </div>
</template>
