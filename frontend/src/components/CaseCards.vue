<script setup>
import { loadCase, state } from '../stores/draft'
</script>

<template>
  <div class="case-loader">
    <label class="field-label">
      载入示例案例 <span class="tag-muted">评委 5 秒跑通</span>
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
        案例列表没加载出来。检查后端是否启动，或点左下角「切换」改用示例数据模式。
      </div>
    </div>
  </div>
</template>
