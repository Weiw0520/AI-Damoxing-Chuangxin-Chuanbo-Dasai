<script setup>
import { closeExport, doExport, hasEdits, saveThenExport, state } from '../stores/draft'
</script>
<template>
  <div v-if="state.exportOpen" class="modal-mask" @click.self="closeExport">
    <div class="modal" role="dialog" aria-modal="true" aria-label="导出文案">
      <div class="modal-head"><h3>导出文案</h3><button class="icon-btn" aria-label="关闭" :disabled="state.exporting" @click="closeExport">×</button></div>
      <div class="modal-body">
        <div v-if="hasEdits" class="warn-line">有未保存的修改，请先保存再下载。</div>
        <p class="field-hint">只下载同一草稿在服务端最后保存的 UTF-8 TXT，保留待核验标记。Markdown 与独立报告导出暂不支持。</p>
        <p v-if="state.exportError" role="alert" class="form-error">{{ state.exportError }}</p>
        <div class="export-opts"><button class="export-opt" :disabled="hasEdits || state.exporting || state.saving" @click="doExport"><span class="eo-ext">.txt</span><span><b>{{ state.exporting ? '下载中…' : '下载服务端 TXT' }}</b><span>来自数据库最后保存的正文与状态标记</span></span></button></div>
      </div>
      <div class="modal-foot"><button v-if="hasEdits" class="btn btn-primary" :disabled="state.saving" @click="saveThenExport">先保存，再导出</button><button class="btn btn-ghost" :disabled="state.exporting" @click="closeExport">取消</button></div>
    </div>
  </div>
</template>
