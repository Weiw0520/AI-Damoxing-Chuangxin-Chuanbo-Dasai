<script setup>
import { computed } from 'vue'
import { applySuggest, closeDrawer, drawerData, toggleManual } from '../stores/draft'
import { STATUS_TEXT } from '../utils/text'

const icon = computed(() => {
  if (!drawerData.value || drawerData.value.mode !== 'claim') return ''
  const s = drawerData.value.claim.status
  return s === 'verified' ? '✓' : s === 'needs_check' ? '!' : '×'
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
              <span v-else style="color: var(--red)">无（模型未给出处）</span>
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
                <span class="quote-label">{{ q.sourceId }} · {{ q.sourceTitle }}</span>
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

          <!-- 没有任何引文时，必须说清「为什么没有」，而且不能一律当成编造。
               两种情况的处置完全相反：
                 · unsupported        → 话是编的，该删或该补来源
                 · needs_check 空引文 → 资料根本没写到这一处（如「能不能带孩子上手捏一个」），
                                        正文在这里留了白。这时让人去删是错的，该去补资料。 -->
          <div v-else class="quote-box quote-empty" :class="{ 'is-blank': drawerData.blankGap }">
            <template v-if="drawerData.blankGap">
              资料里没有写到这一处，正文在这里是<strong>故意留白</strong>，不是编的。要补齐这一句，得先在资料里补上对应信息（如体验项目、适合年龄），再重新生成——工具不会替你猜。
            </template>
            <template v-else>
              模型没有为这处表述提供任何来源。这通常意味着它是被「补」进来的常识或数据，应当删除或人工补充来源后再用。
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
          <button
            v-if="drawerData.claim.suggest && drawerData.claim.status !== 'verified'"
            class="btn btn-primary"
            @click="applySuggest"
          >
            采纳建议并改写
          </button>
          <button class="btn btn-ghost" @click="toggleManual">
            {{ drawerData.claim.status === 'verified' ? '标为待核验' : '人工确认可用' }}
          </button>
        </template>
      </div>
    </aside>
  </template>
</template>
