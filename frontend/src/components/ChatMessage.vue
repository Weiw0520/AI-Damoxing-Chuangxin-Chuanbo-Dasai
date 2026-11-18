<script setup>
/**
 * 对话里的一条消息。四种形态：
 *   material    用户提交的资料（右侧气泡，长了就折起来）
 *   instruction 用户这一轮的要求（右侧气泡，短）
 *   reply       AI 的回话（左侧，带本轮动作与改动对照）
 *   draft       文案卡片（左侧，DraftCard 自己渲染）
 */
import { computed, ref } from 'vue'
import DraftCard from './DraftCard.vue'

const props = defineProps({ item: { type: Object, required: true } })

const expanded = ref(false)
const LIMIT = 220

const full = computed(() => props.item.text || '')
const long = computed(() => full.value.length > LIMIT)
const shown = computed(() =>
  expanded.value || !long.value ? full.value : full.value.slice(0, LIMIT) + '…'
)

/** 气泡里的改动对照只留一段：整段贴出来会把对话顶得很长，完整对照在「修改记录」里。 */
const CLIP = 260
function clip(s) {
  const t = String(s || '')
  return t.length > CLIP ? t.slice(0, CLIP) + '…' : t
}

const PLATFORM = { xiaohongshu: '小红书', wechat: '微信公众号', douyin: '抖音口播' }

/** 后端 applied 是机器可读的枚举，这里翻成人话——评委不看代码。 */
const APPLIED = {
  drop_unsupported: '已删除无依据的表述',
  drop_segment: '已删掉整段',
  drop_tags: '已删掉话题标签',
  shorten: '已压缩篇幅',
  soften: '已改为保守表述',
  explain: '只解释了依据，正文未动',
  expand: '没有补写',
  unknown: '没听懂，正文未动',
}

/**
 * 动作名不等于真的改了：说「删掉无依据的」，而这份稿子本来就没有无依据的表述，
 * 后端照样回 drop_unsupported，但版本号没动。这时候不能写「已删除」。
 * 老记录没有 changed 字段，退回看有没有 diff。
 */
const badge = computed(() => {
  const a = props.item.applied
  if (!a) return ''
  const touched = props.item.changed != null ? props.item.changed : !!props.item.diff
  if (!touched) {
    return a === 'explain' || a === 'expand' || a === 'unknown' ? APPLIED[a] : '没有可改的地方'
  }
  return APPLIED[a] || a
})
</script>

<template>
  <DraftCard v-if="item.kind === 'draft'" />

  <div v-else-if="item.kind === 'material'" class="msg msg-user">
    <div class="bubble bubble-material">
      <div class="b-head">
        <span class="b-kicker">资料原文</span>
        <span class="b-tag">{{ PLATFORM[item.platform] || '小红书' }}</span>
      </div>

      <p class="b-text">{{ shown }}</p>

      <button v-if="long" class="link-btn b-more" @click="expanded = !expanded">
        {{ expanded ? '收起' : `展开全文（${full.length} 字）` }}
      </button>

      <div v-if="item.requirement" class="b-req">
        <span class="b-req-label">需求</span>
        <span>{{ item.requirement }}</span>
      </div>
    </div>
  </div>

  <div v-else-if="item.kind === 'instruction'" class="msg msg-user">
    <div class="bubble bubble-instruction">{{ item.text }}</div>
  </div>

  <div v-else class="msg msg-ai" :id="'msg-' + item.id">
    <div class="avatar">AI</div>
    <div class="bubble bubble-reply">
      <p class="b-text">{{ item.text }}</p>

      <div v-if="item.diff" class="diff">
        <div class="diff-row del"><span class="diff-sign">−</span><span>{{ clip(item.diff.before) }}</span></div>
        <div class="diff-row ins"><span class="diff-sign">+</span><span>{{ clip(item.diff.after) }}</span></div>
      </div>

      <div class="b-foot">
        <span v-if="badge" class="b-applied">{{ badge }}</span>
        <span v-if="item.at" class="b-time">{{ item.at }}</span>
      </div>
    </div>
  </div>
</template>
