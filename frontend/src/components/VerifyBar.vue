<script setup>
/**
 * 核验待办条 —— 中栏顶部那一条。
 *
 * 生成完，工具自己知道哪些表述需要人拍板。与其让用户翻「核验报告」一个个点，
 * 不如把待办顶到眼前：一条一条过，通过 / 不通过 / 跳过。
 *
 * 三个动作的语义要说清：
 *   通过   → 这条判定改成「有据可查」，并记入修改记录（谁签的字要留痕）
 *   不通过 → 改成「无依据」，正文加删除线。**不自动删句子** ——
 *            删是另一件事，得用户自己下指令，工具不替他做这个决定
 *   跳过   → 只跳过当前这一条，状态不变，之后可以「再看一遍」捞回来
 */
import { computed } from 'vue'
import {
  hideVerify,
  openClaim,
  showVerify,
  state,
  verifyCurrent,
  verifyDecide,
  verifyQueue,
  verifyRestart,
  verifySkip,
  verifySkipped,
  verifyTotal,
} from '../stores/draft'

const left = computed(() => verifyQueue.value.length)
const total = verifyTotal
const skipped = verifySkipped
const cur = verifyCurrent

/** 处理完了，但还留着一条「已完成」的条 —— 让用户知道刚做完什么。 */
const finished = computed(() => total.value > 0 && left.value === 0)
</script>

<template>
  <div v-if="total > 0 && !state.verify.hidden" class="verify-bar">
    <div class="vb-head">
      <span class="vb-dot"></span>
      <span class="vb-kicker">需要你判断</span>
      <span class="vb-progress">
        剩余 <b>{{ left }}</b> / 共 {{ total }} 条
        <template v-if="skipped">（已跳过 {{ skipped }}）</template>
      </span>
      <button class="vb-hide" title="收起" @click="hideVerify">×</button>
    </div>

    <template v-if="cur">
      <div class="vb-anchor">{{ cur.claim.anchor }}</div>
      <div class="vb-reason">{{ cur.claim.reason }}</div>

      <div class="vb-actions">
        <button class="vb-btn pass" @click="verifyDecide(true)">通过</button>
        <button class="vb-btn reject" @click="verifyDecide(false)">不通过</button>
        <button class="vb-btn skip" @click="verifySkip()">跳过这条</button>
        <button class="vb-link" @click="openClaim(cur.claim.id)">看来源原文 →</button>
      </div>
    </template>

    <div v-else-if="finished" class="vb-actions">
      <span class="vb-done">
        这一轮 {{ total }} 条都过完了<template v-if="skipped">，其中 {{ skipped }} 条被跳过</template>。
      </span>
      <button v-if="skipped" class="vb-btn skip" @click="verifyRestart">
        再看这 {{ skipped }} 条
      </button>
      <button class="vb-btn" @click="hideVerify">收起</button>
    </div>
  </div>

  <!-- 收起来之后留一个窄条，别让人以为待办消失了 -->
  <button v-else-if="total > 0 && left > 0" class="verify-chip" @click="showVerify">
    {{ left }} 条待核验，点这里逐条判断
  </button>
</template>
