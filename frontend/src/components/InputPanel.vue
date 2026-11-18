<script setup>
/**
 * 中栏的空态：一份新资料的表单。
 *
 * 三栏之后它不再是「左半边的工作台」，而是新对话的第一屏 —— 所以去掉了
 * 侧栏那套 .panel / .input-scroll 结构，改成居中的一列。
 *
 * 资料除了粘贴，也可以直接上传文件或拖进来。解析在服务端做（docx 要拆 zip），
 * 这里只管把文件交出去、把读到的文字填进框里。
 */
import { ref } from 'vue'
import CaseCards from './CaseCards.vue'
import {
  generate,
  resetInput,
  setMaterial,
  setPlatform,
  setRequirement,
  state,
  uploadMaterial,
} from '../stores/draft'

const platforms = [
  { id: 'xiaohongshu', label: '小红书', disabled: false },
  { id: 'wechat', label: '微信公众号', disabled: true, title: '第二版支持' },
  { id: 'douyin', label: '抖音口播', disabled: true, title: '第二版支持' },
]

const ACCEPT = '.txt,.md,.markdown,.csv,.tsv,.json,.html,.htm,.docx'
const fileInput = ref(null)
const dragging = ref(false)

function onMaterial(e) {
  setMaterial(e.target.value)
}

function onRequirement(e) {
  setRequirement(e.target.value)
}

function pickFile() {
  fileInput.value?.click()
}

async function onFilePick(e) {
  const file = e.target.files && e.target.files[0]
  // 清空 value：同一个文件第二次选中也要能触发 change
  e.target.value = ''
  if (file) await uploadMaterial(file)
}

async function onDrop(e) {
  dragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) await uploadMaterial(file)
}

function onDragOver(e) {
  e.preventDefault()
  if (!dragging.value) dragging.value = true
}
</script>

<template>
  <div class="newchat">
    <div class="nc-head">
      <div class="nc-seal">校</div>
      <div>
        <h2>提交一份资料，开始新对话</h2>
        <p>AI 只依据你贴进来的文字写，写完逐句标来源。资料里没有的，它不会替你补。</p>
      </div>
    </div>

    <div class="nc-block">
      <div class="panel-head">
        <h2>① 示例案例</h2>
        <button class="link-btn" @click="resetInput">清空</button>
      </div>
      <CaseCards />
    </div>

    <div
      class="field"
      :class="{ 'is-drop': dragging }"
      @dragover="onDragOver"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
    >
      <div class="field-top">
        <label class="field-label" for="inMaterial">资料原文</label>
        <div class="field-tools">
          <button class="link-btn upload-btn" :disabled="state.uploading" @click="pickFile">
            {{ state.uploading ? '读取中…' : '↑ 上传文件' }}
          </button>
          <span class="counter"><span>{{ state.material.length }}</span> 字</span>
        </div>
      </div>

      <textarea
        id="inMaterial"
        rows="6"
        :value="state.material"
        :class="{ 'is-error': !!state.formError }"
        placeholder="粘贴项目资料、通稿、非遗名录条目或景区介绍，也可以把 .txt / .md / .docx 文件拖到这里。建议保留【来源】与链接，便于回溯依据。"
        @input="onMaterial"
      ></textarea>

      <input
        ref="fileInput"
        type="file"
        class="file-hidden"
        :accept="ACCEPT"
        @change="onFilePick"
      />

      <p class="field-hint">
        AI 只会依据这里的文字下判断，不引入外部知识。支持 .txt / .md / .csv / .json / .docx，单个文件不超过 5 MB。
      </p>

      <div v-if="dragging" class="drop-mask">松手即可读入这份文件</div>
    </div>

    <div class="field">
      <label class="field-label" for="inRequirement">传播需求</label>
      <textarea
        id="inRequirement"
        rows="2"
        :value="state.requirement"
        placeholder="例如：为这个项目写一篇面向年轻游客的小红书宣传文案，突出可体验的部分。"
        @input="onRequirement"
      ></textarea>
    </div>

    <div class="field">
      <label class="field-label">目标平台</label>
      <div class="platform-row">
        <button
          v-for="p in platforms"
          :key="p.id"
          class="platform"
          :class="{ 'is-active': state.platform === p.id }"
          :disabled="p.disabled"
          :title="p.title || ''"
          @click="setPlatform(p.id)"
        >
          {{ p.label }}
        </button>
      </div>
    </div>

    <div v-if="state.formError" class="form-error">{{ state.formError }}</div>

    <button class="btn btn-generate" :disabled="state.phase === 'generating'" @click="generate">
      <span class="btn-label">生成文案并核对依据</span>
      <span class="btn-kbd">⌘ ↵</span>
    </button>

    <p class="nc-foot">
      生成之后可以继续追问，比如「删掉无依据的那句」「第二段压缩一半」「把没出处的说法改保守」。
    </p>
  </div>
</template>
