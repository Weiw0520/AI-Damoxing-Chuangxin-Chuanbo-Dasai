<script setup>
import { computed } from 'vue'
import { STATUS_TEXT, citeText } from '../utils/text'

const props = defineProps({
  claim: { type: Object, required: true },
  active: { type: Boolean, default: false },
})

const cls = computed(() => ({
  'is-warn': props.claim.status !== 'supported',
  'is-active': props.active,
}))

const label = computed(() => citeText(props.claim))
const title = computed(() => `${STATUS_TEXT[props.claim.status]}｜点击查看依据`)
</script>

<template>
  <button class="cite" :class="cls" :title="title" @click="$emit('open')">{{ label }}</button>
</template>
