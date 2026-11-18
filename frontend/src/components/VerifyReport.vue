<script setup>
import { computed } from 'vue'
import { claimsList, openClaim, openSource, state } from '../stores/draft'
import { STATUS_CLASS, STATUS_TEXT } from '../utils/text'

const groups = [
  { key: 'needs_check', title: '待核验 · 需要人工判断' },
  { key: 'unsupported', title: '无依据 · 建议删除或补充来源' },
  { key: 'verified', title: '有据可查' },
]

const blocks = computed(() => {
  // 序号按「全部核验项」的顺序编号，不按分组重新数 —— 与抽屉里的 #08 对得上
  const list = claimsList.value.map((x, i) => ({ ...x, no: String(i + 1).padStart(2, '0') }))
  return groups
    .filter((g) => !state.filter || state.filter === g.key)
    .map((g) => ({ ...g, items: list.filter((x) => x.claim.status === g.key) }))
    .filter((g) => g.items.length)
})
</script>

<template>
  <div class="report">
    <div v-if="!blocks.length" class="empty-mini">
      该分类下暂无条目，点「核验报告」查看全部。
    </div>

    <div v-for="g in blocks" :key="g.key" class="report-group">
      <h4>{{ g.title }}（{{ g.items.length }}）</h4>

      <div
        v-for="it in g.items"
        :key="it.claim.id"
        class="check-item"
        :class="STATUS_CLASS[it.claim.status]"
        @click="openClaim(it.claim.id)"
      >
        <div class="ci-main">
          <div class="ci-claim">{{ it.claim.anchor }}</div>
          <div class="ci-reason">{{ it.claim.reason }}</div>
          <div class="ci-meta">
            <span>#{{ it.no }}</span>
            <span>段落：{{ it.seg.label || '正文' }}</span>
            <template v-if="it.claim.cite_ids.length">
              <span
                v-for="id in it.claim.cite_ids"
                :key="id"
                class="ci-src"
                @click.stop="openSource(id)"
                >{{ id }}</span
              >
            </template>
            <span v-else style="color: var(--red)">无来源</span>
          </div>
        </div>

        <span class="status-pill" :class="STATUS_CLASS[it.claim.status]">
          {{ STATUS_TEXT[it.claim.status] }}
        </span>
      </div>
    </div>
  </div>
</template>
