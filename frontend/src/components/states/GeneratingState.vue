<script setup>
import { GEN_STEPS, state } from '../../stores/draft'
</script>

<template>
  <div class="generating">
    <div class="gen-head">
      <div class="spinner"></div>
      <div>
        <h3>正在生成与核对</h3>
        <p>已提交资料，等待模型返回…</p>
      </div>
    </div>

    <ol class="gen-steps">
      <li
        v-for="(label, i) in GEN_STEPS"
        :key="label"
        :class="{ 'is-done': i < state.genStep, 'is-active': i === state.genStep }"
      >
        <span class="mark">✓</span><span>{{ label }}</span>
      </li>
    </ol>

    <div class="skeleton">
      <span class="sk w70"></span><span class="sk w95"></span><span class="sk w90"></span
      ><span class="sk w45"></span>
    </div>
  </div>
</template>
