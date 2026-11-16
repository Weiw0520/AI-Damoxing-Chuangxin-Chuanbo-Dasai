<script setup>
import SegmentBlock from './SegmentBlock.vue'
import { state } from '../stores/draft'
</script>

<template>
  <article class="paper">
    <SegmentBlock v-for="seg in state.result.segments" :key="seg.id" :seg="seg" />
  </article>
</template>
