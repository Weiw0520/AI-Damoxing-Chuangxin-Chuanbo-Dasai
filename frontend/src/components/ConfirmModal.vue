<script setup>
import { resolveConfirm, state } from '../stores/draft'
</script>

<template>
  <div v-if="state.confirm.open" class="modal-mask" @click.self="resolveConfirm(false)">
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-head">
        <h3>{{ state.confirm.title }}</h3>
        <button class="icon-btn" aria-label="关闭" @click="resolveConfirm(false)">×</button>
      </div>

      <div class="modal-body">
        <p style="margin: 0 0 6px">{{ state.confirm.desc }}</p>
      </div>

      <div class="modal-foot">
        <button class="btn btn-ghost" @click="resolveConfirm(false)">取消</button>
        <button class="btn btn-primary" @click="resolveConfirm(true)">确认</button>
      </div>
    </div>
  </div>
</template>
