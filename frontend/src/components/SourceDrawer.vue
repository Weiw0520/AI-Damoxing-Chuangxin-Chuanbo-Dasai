<script setup>
import { computed } from 'vue'
import { closeDrawer, drawerData } from '../stores/draft'
import { STATUS_TEXT } from '../utils/text'

const icon = computed(() => {
  if (!drawerData.value || drawerData.value.mode !== 'claim') return ''
  const s = drawerData.value.claim.status
  return s === 'supported' ? '✓' : '!'
})
</script>

<template>
  <template v-if="drawerData">
    <div class="drawer-mask" @click="closeDrawer"></div>

    <aside class="drawer">
      <div class="drawer-head">
        <div>
          <span class="drawer-kicker">{{ drawerData.kicker }}</span>
          <h3>{{ drawerData.title }}</h3>
        </div>
        <button class="icon-btn" aria-label="关闭" @click="closeDrawer">×</button>
      </div>

      <div class="drawer-body">
        <!-- ---------------- 来源原文视图 ---------------- -->
        <template v-if="drawerData.mode === 'source'">
          <dl class="meta-table">
            <dt>来源编号</dt>
            <dd>{{ drawerData.source.id }}</dd>
            <dt>出版方</dt>
            <dd>{{ drawerData.source.publisher }}</dd>
            <dt>链接</dt>
            <dd>
              <a
                v-if="drawerData.source.url"
                :href="drawerData.source.url"
                target="_blank"
                rel="noopener"
                >{{ drawerData.source.url }}</a
              >
              <span v-else style="color: var(--ink-4)">未提供</span>
            </dd>
          </dl>

          <span class="drawer-section-title">原文片段</span>
          <div class="quote-box">{{ drawerData.source.snippet }}</div>

          <div class="warn-line" style="margin-top: 4px">
            <span>!</span>
            <span>本工具只引用你提交的资料。若对来源本身有疑问，请点开链接核对原始页面。</span>
          </div>
        </template>

        <!-- ---------------- 依据核验视图 ---------------- -->
        <template v-else>
          <dl class="meta-table">
            <dt>核验项</dt>
            <dd>#{{ drawerData.no }}　段落「{{ drawerData.seg.label || '正文' }}」</dd>
            <dt>来源编号</dt>
            <dd>
              <template v-if="drawerData.claim.cite_ids.length">
                {{ drawerData.claim.cite_ids.join('、') }}
              </template>
              <span v-else style="color: var(--red)">当前段落未附依据</span>
            </dd>
            <dt>判定</dt>
            <dd>{{ STATUS_TEXT[drawerData.claim.status] }}</dd>
          </dl>

          <div class="verdict" :class="drawerData.statusClass">
            <span class="verdict-icon">{{ icon }}</span>
            <span>{{ drawerData.claim.reason }}</span>
          </div>

          <span class="drawer-section-title">资料原文</span>

          <template v-if="drawerData.quotes.length">
            <div v-for="(q, i) in drawerData.quotes" :key="i">
              <div class="quote-box">
                <span class="quote-label">{{ q.sourceLabel }} · {{ q.sourceTitle }}</span>
                <template v-for="(p, j) in q.parts" :key="j">
                  <mark v-if="p.mark">{{ p.text }}</mark>
                  <template v-else>{{ p.text }}</template>
                </template>
              </div>

              <div v-if="!q.matched" class="warn-line" style="margin-top: -6px">
                <span>!</span>
                <span>
                  这段原文里找不到与该表述直接对应的句子。这正是它被标为「{{
                    STATUS_TEXT[drawerData.claim.status]
                  }}」的原因——引文存在，但不足以支撑当前说法。
                </span>
              </div>

              <dl
                v-if="q.hasSource"
                class="meta-table"
                style="margin-top: -6px; margin-bottom: 16px"
              >
                <dt>出版方</dt>
                <dd>{{ q.publisher }}</dd>
                <dt>链接</dt>
                <dd>
                  <a v-if="q.url" :href="q.url" target="_blank" rel="noopener">{{ q.url }}</a>
                  <span v-else style="color: var(--ink-4)">资料未提供可访问链接</span>
                </dd>
              </dl>
            </div>
          </template>

          <!-- No client-side verdicts: C owns reviewReason, status, and evidence. -->
          <div v-else class="quote-box quote-empty" :class="{ 'is-blank': drawerData.blankGap }">
            <template v-if="drawerData.claim.status === 'edited_needs_review'">
              人工修改后的当前段落没有沿用旧依据，需重新复核。修改前的内容和依据保存在服务端历史中。
            </template>
            <template v-else>
              当前段落没有可展示的原文依据。请按上方服务端说明补充资料，并在发布前核实。
            </template>
          </div>

          <template v-if="drawerData.claim.suggest">
            <span class="drawer-section-title">建议表述</span>
            <div
              class="quote-box"
              style="border-left-color: var(--gold); font-family: var(--sans); font-size: 13px"
            >
              {{ drawerData.claim.suggest }}
            </div>
          </template>

          <details v-if="drawerData.promptExcerpt" style="margin-top: 6px">
            <summary style="cursor: pointer; font-size: 11.5px; color: var(--ink-3)">
              查看判定所用的提示词（{{ drawerData.promptVersion }}）
            </summary>
            <div class="prompt-box" style="margin-top: 8px">{{ drawerData.promptExcerpt }}</div>
          </details>
        </template>
      </div>

      <div class="drawer-foot">
        <template v-if="drawerData.mode === 'claim'">
          <p class="field-hint">此处展示服务端保存的依据与状态；人工确认回写暂不支持。编辑文案后请保存并重新复核。</p>
        </template>
      </div>
    </aside>
  </template>
</template>
