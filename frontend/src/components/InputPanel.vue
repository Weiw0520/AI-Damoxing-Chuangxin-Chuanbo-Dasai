<script setup>
import CaseCards from './CaseCards.vue'
import { addSource, generate, removeSource, resetInput, setPlatform, setRequirement, state } from '../stores/draft'
const platforms = ['小红书', '微信公众号', '抖音口播']
</script>
<template>
  <div class="newchat">
    <div class="nc-head">
      <div class="nc-seal">校</div>
      <div><h2>提交资料，开始新草稿</h2><p>每份资料保留标题、原文与链接。当前为模拟联调，尚未完成真实 AI 核验。</p></div>
    </div>
    <div class="nc-block">
      <div class="panel-head"><h2>① 示例资料</h2><button class="link-btn" @click="resetInput">清空</button></div>
      <CaseCards />
    </div>
    <div class="field">
      <div class="field-top"><span class="field-label">② 独立来源资料</span><button class="link-btn" @click="addSource">＋ 添加资料</button></div>
      <section v-for="(source, index) in state.inputSources" :key="index" class="source-input">
        <div class="field-top"><b>资料 {{ index + 1 }}</b><button v-if="state.inputSources.length > 1" class="link-btn" @click="removeSource(index)">移除资料 {{ index + 1 }}</button></div>
        <label class="field-label" :for="`source-title-${index}`">资料 {{ index + 1 }} 标题</label>
        <input :id="`source-title-${index}`" v-model="source.title" type="text" placeholder="资料标题（必填）" />
        <label class="field-label" :for="`source-text-${index}`">资料 {{ index + 1 }} 原文</label>
        <textarea :id="`source-text-${index}`" v-model="source.text" rows="4" placeholder="粘贴这一份资料的原文（必填）"></textarea>
        <label class="field-label" :for="`source-url-${index}`">资料 {{ index + 1 }} 链接（选填）</label>
        <input :id="`source-url-${index}`" v-model="source.url" type="url" placeholder="https://…" />
      </section>
      <p class="field-hint">请直接粘贴原文。服务端文件解析暂不支持，链接仅用于追溯，不会自动抓取网页。</p>
    </div>
    <div class="field">
      <label class="field-label" for="inRequirement">传播需求</label>
      <textarea id="inRequirement" rows="3" :value="state.requirement" placeholder="填写宣传需求（必填）" @input="setRequirement($event.target.value)"></textarea>
    </div>
    <div class="field">
      <label class="field-label">目标平台</label>
      <div class="platform-row"><button v-for="platform in platforms" :key="platform" class="platform" :class="{ 'is-active': state.platform === platform }" @click="setPlatform(platform)">{{ platform }}</button></div>
      <p class="field-hint">平台随请求保存；模拟生成器尚不生成真实平台风格。</p>
    </div>
    <div v-if="state.formError" role="alert" class="form-error">{{ state.formError }}</div>
    <button class="btn btn-generate" :disabled="state.phase === 'generating' || state.loadingDraft" @click="generate"><span class="btn-label">生成文案并核对依据</span><span class="btn-kbd">Ctrl ↵</span></button>
    <p class="nc-foot">创建后可查看原文引用、逐段编辑、保存，并下载服务端 TXT。多轮追问暂不支持。</p>
  </div>
</template>
