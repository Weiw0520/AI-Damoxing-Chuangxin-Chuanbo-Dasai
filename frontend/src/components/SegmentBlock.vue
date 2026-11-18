<script setup>
/**
 * 正文里的一段（只读）。
 *
 * 这里不再提供输入框：改写统一在右栏「文案正文」那份文件里做。
 * 同一段文字在屏幕上两个地方都能改，是「以哪个为准」这类问题的最好来源，
 * 所以中间这栏只负责看，改由右栏负责。
 */
import { computed } from 'vue'
import CiteChip from './CiteChip.vue'
import { currentText, jumpToReport, openClaim, staleClaims, state } from '../stores/draft'
import { hlClass, splitByClaims } from '../utils/text'

const props = defineProps({ seg: { type: Object, required: true } })

const text = computed(() => currentText(props.seg))
const edited = computed(
  () => state.edits[props.seg.id] != null && state.edits[props.seg.id] !== props.seg.text
)
const parts = computed(() => splitByClaims(text.value, props.seg.claims || []))
const stale = computed(() => staleClaims(props.seg))
const unsupported = computed(() =>
  (props.seg.claims || []).filter((c) => c.status === 'unsupported')
)
const needsCheck = computed(() => (props.seg.claims || []).filter((c) => c.status === 'needs_check'))
</script>

<template>
  <div class="seg" :class="'seg-' + (props.seg.type || 'body')">
    <span class="seg-label">{{ props.seg.label || '正文' }}</span>

    <div class="seg-text">
      <template v-for="(p, i) in parts" :key="i">
        <span v-if="p.type === 'text'">{{ p.text }}</span>
        <template v-else>
          <span class="hl" :class="hlClass(p.claim.status)">{{ p.text }}</span>
          <CiteChip
            :claim="p.claim"
            :active="state.drawer.open && state.drawer.claimId === p.claim.id"
            @open="openClaim(p.claim.id)"
          />
        </template>
      </template>
    </div>

    <div class="seg-foot">
      <span v-if="edited" class="edited-mark">人工已修改</span>
      <button
        v-if="unsupported.length"
        class="mini-badge bad"
        @click="jumpToReport('unsupported')"
      >
        {{ unsupported.length }} 处无依据，建议删除
      </button>
      <button v-if="needsCheck.length" class="mini-badge" @click="jumpToReport('needs_check')">
        {{ needsCheck.length }} 处待核验
      </button>
      <span v-if="stale.length" class="mini-badge stale">
        {{ stale.length }} 处依据因表述改动失效
      </span>
    </div>
  </div>
</template>
