<script setup>
/**
 * 右栏：文件。
 *
 * 行为对齐常见的桌面工作台：
 *   · 左边缘可拖动改宽（240–560），拖动宽度跨草稿保留
 *   · 可收起成一条图标轨，鼠标悬停才显示文件名 —— 收起来时不占地方，也不丢入口
 *   · 文件以浏览器式标签页打开，一个标签一份内容
 *   · 内容顶端右侧是「下载」和「编辑」；只有文案正文可编辑，
 *     另外三份是导出产物，改它们没有意义（下次导出会被覆盖）
 *
 * 编辑为什么逐段而不是一个大文本框：依据靠 anchor 定位，整篇一起改就不知道
 * 哪一段变了，anchor 也就无从校正。逐段改，每段自己的依据还能对上。
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import {
  FILE_TABS,
  activeFile,
  activeFileContent,
  claimsList,
  closeFile,
  copyAll,
  currentText,
  doExport,
  fileTabs,
  hasEdits,
  openFile,
  openSource,
  save,
  setEdit,
  setEditMode,
  setPanelWidth,
  showFileList,
  state,
  togglePanel,
} from '../stores/draft'

/* ---------------------------------------------------------------- 拖宽 */
const resizing = ref(false)
const dragFrom = ref(0)
const dragWidth = ref(0)

function onResizeDown(e) {
  resizing.value = true
  dragFrom.value = e.clientX
  dragWidth.value = state.panel.width
  // 拖动期间整页禁用选择，否则鼠标一快就把正文刷蓝，松手还留着选区
  document.body.classList.add('is-resizing')
  window.addEventListener('mousemove', onResizeMove)
  window.addEventListener('mouseup', onResizeUp)
  e.preventDefault()
}

function onResizeMove(e) {
  if (!resizing.value) return
  // 拖的是左边缘：鼠标往左移动，右栏变宽
  setPanelWidth(dragWidth.value + (dragFrom.value - e.clientX))
}

function onResizeUp() {
  resizing.value = false
  document.body.classList.remove('is-resizing')
  window.removeEventListener('mousemove', onResizeMove)
  window.removeEventListener('mouseup', onResizeUp)
}

onBeforeUnmount(onResizeUp)

/* ---------------------------------------------------------------- 数据 */
const sources = computed(() => (state.result ? state.result.sources || [] : []))

/** 每份来源被几处表述引用 —— 一眼看出哪份资料是主力。 */
const useCount = computed(() => {
  const map = {}
  claimsList.value.forEach(({ claim }) => {
    ;(claim.cite_ids || []).forEach((id) => {
      map[id] = (map[id] || 0) + 1
    })
  })
  return map
})

const savedText = computed(() => {
  if (!state.savedVersion) return '尚未保存'
  return `已保存 · ${new Date(state.savedAt).toLocaleString('zh-CN')}`
})

const editing = computed(() => state.editMode && !!activeFile.value?.editable)

function tabOf(id) {
  return FILE_TABS.find((f) => f.id === id) || FILE_TABS[0]
}

function rowsOf(seg) {
  const n = currentText(seg).length
  return Math.min(16, Math.max(2, Math.ceil(n / 22) + 1))
}

/**
 * 下载。
 *
 * 有未保存的改动就先存一次：导出只认库里那一版，否则用户点了下载，
 * 拿到的却是他没看过的那一版。这条规则在右栏也照旧。
 */
async function download(f) {
  if (!state.result) return
  if (!state.savedVersion || hasEdits.value) {
    const res = await save()
    if (!res) return
  }
  doExport(f.kind === 'draft' ? 'txt' : f.fmt)
}
</script>

<template>
  <aside class="col col-right" :class="{ 'is-collapsed': state.panel.collapsed }">
    <div
      v-if="!state.panel.collapsed"
      class="right-resizer"
      :class="{ 'is-active': resizing }"
      title="拖动调整宽度"
      @mousedown="onResizeDown"
    ></div>

    <!-- 收起态：图标轨，悬停才出文件名 -->
    <div v-if="state.panel.collapsed" class="rail">
      <button class="rail-btn" title="展开文件栏" @click="togglePanel">‹</button>

      <button
        v-for="f in fileTabs"
        :key="f.id"
        class="rail-file"
        @click="openFile(f.id)"
      >
        <span class="rf-ext">{{ f.ext }}</span>
        <span class="rail-tip">{{ f.name }}</span>
      </button>

      <button
        v-for="s in sources"
        :key="s.id"
        class="rail-file is-src"
        @click="openSource(s.id)"
      >
        <span class="rf-ext">{{ s.id }}</span>
        <span class="rail-tip">{{ s.title }}</span>
      </button>
    </div>

    <template v-else>
      <div class="right-head">
        <div class="rh-text">
          <h2>文件</h2>
          <span class="right-sub">本次产物与来源</span>
        </div>
        <button class="icon-btn" title="收起文件栏" @click="togglePanel">›</button>
      </div>

      <!-- 浏览器式标签栏：第一个是固定的「全部文件」，相当于首页，
           不会被关掉，标签开多了也能一键回到清单 -->
      <div v-if="state.panel.tabs.length" class="ftabs">
        <button
          class="ftab is-home"
          :class="{ 'is-active': !state.panel.active }"
          title="全部文件"
          @click="showFileList"
        >
          <span class="ftab-name">全部文件</span>
        </button>

        <button
          v-for="id in state.panel.tabs"
          :key="id"
          class="ftab"
          :class="{ 'is-active': state.panel.active === id }"
          @click="state.panel.active = id"
        >
          <span class="ftab-ext">{{ tabOf(id).ext }}</span>
          <span class="ftab-name">{{ tabOf(id).name }}</span>
          <span class="ftab-x" title="关闭" @click.stop="closeFile(id)">×</span>
        </button>
      </div>

      <!-- 打开的文件 -->
      <template v-if="activeFile">
        <div class="fview-bar">
          <div class="fv-title">
            {{ activeFile.name }}
            <span class="fv-ext">{{ activeFile.ext }}</span>
          </div>
          <div class="fv-actions">
            <button class="btn btn-ghost btn-xs" :disabled="state.saving || state.exporting || state.creatingFromBrief" @click="download(activeFile)">下载</button>
            <button
              v-if="activeFile.editable"
              class="btn btn-xs"
              :class="editing ? 'btn-primary' : 'btn-ghost'"
              @click="setEditMode(!state.editMode)"
            >
              {{ editing ? '完成编辑' : '编辑' }}
            </button>
          </div>
        </div>

        <div class="fview-scroll">
          <template v-if="editing">
            <div v-for="seg in state.result.segments" :key="seg.id" class="fe-seg">
              <span class="fe-label">{{ seg.label || '正文' }}</span>
              <textarea
                class="fe-input"
                :aria-label="seg.label + '正文编辑'"
                :disabled="state.saving || state.exporting || state.creatingFromBrief"
                :value="currentText(seg)"
                :rows="rowsOf(seg)"
                @input="setEdit(seg.id, $event.target.value)"
              ></textarea>
            </div>
            <p class="fe-hint">
              改动保存后才进入导出。改了带依据的句子，对应依据会标记为失效，需要重新核对。
            </p>
          </template>

          <pre v-else class="fview-text">{{ activeFileContent }}</pre>
        </div>

        <div v-if="editing" class="fview-foot">
          <button class="btn btn-ghost" @click="copyAll">复制全文</button>
          <button class="btn btn-primary" :disabled="state.saving || state.creatingFromBrief" @click="save">
            {{ state.saving ? '保存中…' : '保存草稿' }}
          </button>
        </div>
      </template>

      <!-- 没打开文件时：文件清单 -->
      <div v-else class="right-scroll">
        <section class="rp-block">
          <h3>
            导出产物
            <span class="rp-count">{{ fileTabs.length }}</span>
          </h3>

          <div v-if="!state.result" class="empty-mini">生成文案后，这里出现可下载的文件。</div>

          <template v-else>
            <button v-for="f in fileTabs" :key="f.id" class="file-item" @click="openFile(f.id)">
              <span class="fi-ext">{{ f.ext }}</span>
              <span class="fi-body">
                <b>{{ f.name }}</b>
                <span>{{ f.desc }}</span>
              </span>
              <span class="fi-dl">↗</span>
            </button>

            <p class="rp-note">
              点文件在右栏打开；下载使用服务端最新版 TXT，文件名带草稿编号。当前预览为页面正文。
            </p>
          </template>
        </section>

        <section class="rp-block">
          <h3>
            来源清单
            <span class="rp-count">{{ sources.length }}</span>
          </h3>

          <div v-if="!sources.length" class="empty-mini">本次没有引用任何来源。</div>

          <button v-for="s in sources" :key="s.id" class="src-item" @click="openSource(s.id)">
            <span class="si-id">{{ s.label }}</span>
            <span class="si-body">
              <b>{{ s.title }}</b>
              <span>
                {{ s.publisher }}
                <template v-if="useCount[s.id]"> · 支撑 {{ useCount[s.id] }} 处</template>
              </span>
            </span>
          </button>

          <p v-if="sources.length" class="rp-note">点开看原文片段；工具只引用你提交的资料。</p>
        </section>

        <section class="rp-block">
          <h3>草稿</h3>
          <dl class="meta-table">
            <dt>编号</dt>
            <dd>{{ state.draftId || '未创建' }}</dd>
            <dt>保存时间</dt>
            <dd>{{ savedText }}</dd>
            <dt>模型</dt>
            <dd>{{ state.result ? state.result.model : '—' }}</dd>
            <dt>模式</dt>
            <dd>{{ state.mode }}</dd>
          </dl>
        </section>
      </div>
    </template>
  </aside>
</template>
