<script setup>
import { computed } from 'vue'
import { closeExport, doExport, hasEdits, saveThenExport, state } from '../stores/draft'
import { toast } from '../utils/toast'

const dirty = computed(() => hasEdits.value)

const options = [
  {
    fmt: 'md',
    ext: '.md',
    title: '文案 + 核验说明（推荐）',
    desc: '正文、逐条核验表格、来源清单、人工修改记录、生成信息',
  },
  {
    fmt: 'txt',
    ext: '.txt',
    title: '纯文案',
    desc: '只有正文，末尾附待核验提示，方便直接贴到平台',
  },
  {
    fmt: 'report',
    ext: '.md',
    title: '仅核验报告',
    desc: '给主编或审核人看的依据清单，不含正文',
  },
]

function pick(fmt) {
  if (!state.savedVersion) {
    toast('请先保存草稿，再导出')
    return
  }
  doExport(fmt)
}
</script>

<template>
  <div v-if="state.exportOpen" class="modal-mask" @click.self="closeExport">
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-head">
        <h3>导出文案</h3>
        <button class="icon-btn" aria-label="关闭" @click="closeExport">×</button>
      </div>

      <div class="modal-body">
        <div v-if="!state.savedVersion" class="warn-line">
          <span>!</span>
          <span>
            当前草稿<strong>尚未保存</strong>。请先保存，导出文件才会带上草稿编号与版本号——评委据此确认「导出的就是最后确认的版本」。
          </span>
        </div>

        <div v-else-if="dirty" class="warn-line">
          <span>!</span>
          <span>
            页面上有未保存的修改。现在导出只会输出<strong>最后一次保存的 v{{ state.savedVersion }}</strong>，你刚改的内容不会出现在文件里。
          </span>
        </div>

        <div class="export-opts">
          <button v-for="o in options" :key="o.fmt" class="export-opt" @click="pick(o.fmt)">
            <span class="eo-ext">{{ o.ext }}</span>
            <span>
              <b>{{ o.title }}</b>
              <span>{{ o.desc }}</span>
            </span>
          </button>
        </div>
      </div>

      <div class="modal-foot">
        <button v-if="!state.savedVersion" class="btn btn-primary" @click="saveThenExport">
          先保存草稿
        </button>
        <button v-else-if="dirty" class="btn btn-primary" @click="saveThenExport">
          先保存，再导出 v{{ state.savedVersion + 1 }}
        </button>
        <button class="btn btn-ghost" @click="closeExport">取消</button>
      </div>
    </div>
  </div>
</template>
