<script setup>
import { toastState } from '../utils/toast'
</script>

<template>
  <div class="toast" :class="{ show: toastState.visible }">{{ toastState.message }}</div>
</template>
