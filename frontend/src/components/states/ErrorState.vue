<script setup>
import { backToInput, generate, state } from '../../stores/draft'
</script>

<template>
  <div class="error-state">
    <div class="err-icon">!</div>
    <h3>{{ state.errorTitle || '生成失败' }}</h3>
    <p>{{ state.errorMsg }}</p>

    <div class="err-actions">
      <button class="btn btn-primary" @click="generate">重试一次</button>
      <button class="btn btn-ghost" @click="backToInput">回到输入区</button>
    </div>

    <p class="err-tip">提示：如果是资料过长导致超时，可先粘贴其中一段来源再试。</p>
  </div>
</template>
