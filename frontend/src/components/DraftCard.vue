<script setup>
/**
 * 对话里的「产物卡片」。
 *
 * 原来它是整个右半屏（ResultPanel）。三栏之后它变成 AI 的一条消息：
 * 头部是版本号，中间是核验摘要与三个标签页，底部是保存栏。
 * 类名沿用旧的那套（.result-head / .tabs / .summary / .editor-bar），
 * 样式在 main.css 里已经写好，这里只补卡片容器的边距。
 */
import PaperView from './PaperView.vue'
import VerifyReport from './VerifyReport.vue'
import EditHistory from './EditHistory.vue'
import {
  copyAll,
  hasEdits,
  jumpToReport,
  save,
  setEditMode,
  setTab,
  state,
  stats,
  visibleHistory,
} from '../stores/draft'
</script>

<template>
  <div class="msg msg-ai msg-draft">
    <div class="avatar">AI</div>

    <div class="draft-card">
      <div class="dc-head">
        <div class="dc-title">
          文案初稿
          <span class="dc-ver">已保存 · {{ state.history.length }} 条修改记录</span>
        </div>
        <div class="dc-meta">
          {{ state.mode }} ·
          {{ state.result.created_at }}
        </div>
      </div>

      <div class="summary">
        <button class="sum-item ok" @click="jumpToReport('supported')">
          <span class="sum-dot"></span><b>{{ stats.supported }}</b> 段有资料依据
        </button>
        <button class="sum-item warn" @click="jumpToReport('needs_review')">
          <span class="sum-dot"></span><b>{{ stats.needs_review }}</b> 段待核验
        </button>
        <button class="sum-item warn" @click="jumpToReport('edited_needs_review')">
          <span class="sum-dot"></span><b>{{ stats.edited_needs_review }}</b> 段修改后待复核
        </button>
        <span class="sum-meta">{{ stats.total }} 段文案</span>
      </div>

      <div
        v-if="state.result.notice"
        class="notice"
        :class="{ 'is-bad': state.result.notice.level === 'bad' }"
      >
        <span class="n-icon">{{ state.result.notice.level === 'bad' ? '⚠' : '!' }}</span>
        <span>{{ state.result.notice.text }}</span>
      </div>

      <div class="result-head">
        <div class="tabs">
          <button
            class="tab"
            :class="{ 'is-active': state.activeTab === 'copy' }"
            @click="setTab('copy')"
          >
            文案
          </button>
          <button
            class="tab"
            :class="{ 'is-active': state.activeTab === 'report' }"
            @click="setTab('report')"
          >
            核验报告
            <span v-if="stats.pending" class="tab-badge">{{ stats.pending }}</span>
          </button>
          <button
            class="tab"
            :class="{ 'is-active': state.activeTab === 'history' }"
            @click="setTab('history')"
          >
            修改记录
            <span class="tab-badge gray">{{ visibleHistory.length }}</span>
          </button>
        </div>

        <div class="result-actions">
          <!-- 正文在这里只读。改写入口统一收到右栏「文案正文」那份文件里，
               免得同一段文字在屏幕上两个地方都能改，谁是真的说不清。 -->
          <button class="btn btn-ghost btn-xs" @click="setEditMode(true)">在右栏编辑</button>
        </div>
      </div>

      <div v-show="state.activeTab === 'copy'" class="tabpane">
        <PaperView />

        <div class="editor-bar">
          <div v-if="hasEdits" class="dirty-hint">
            <span class="dirty-dot"></span>
            <template v-if="state.saveError">
              保存失败（{{ state.saveError }}）。修改仍在页面上，可重试，或先「复制全文」避免丢失。
            </template>
            <template v-else>有未保存的修改，导出的将是上一次保存的版本</template>
          </div>

          <div class="editor-btns">
            <button class="btn btn-ghost" @click="copyAll">复制全文</button>
            <button class="btn btn-primary" :disabled="state.saving" @click="save">
              {{ state.saving ? '保存中…' : '保存草稿' }}
            </button>
          </div>
        </div>
      </div>

      <div v-show="state.activeTab === 'report'" class="tabpane">
        <VerifyReport />
      </div>

      <div v-show="state.activeTab === 'history'" class="tabpane">
        <EditHistory />
      </div>
    </div>
  </div>
</template>
