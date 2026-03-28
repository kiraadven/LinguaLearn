<template>
  <div class="word-list-panel">
    <div class="wlp-title">词框内容</div>
    <div class="wlp-row">
      <span class="wlp-label">语言</span>
      <span class="wlp-val">{{ sourceLang }} → {{ targetLang }}</span>
    </div>
    <div class="wlp-row">
      <span class="wlp-label">关键词数</span>
      <span class="wlp-val">{{ numWords === 0 ? '不限' : numWords + ' 个/句' }}</span>
    </div>
    <div class="wlp-row">
      <span class="wlp-label">实用表达数</span>
      <span class="wlp-val">{{ numExprs === 0 ? '不限' : numExprs + ' 个/句' }}</span>
    </div>
    <div class="wlp-hint">词框内容由 AI 根据视频自动提取</div>
  </div>
</template>

<script setup>
defineProps({
  sourceLang: { type: String, default: 'en' },
  targetLang: { type: String, default: 'zh' },
  numWords:   { type: Number, default: 3 },
  numExprs:   { type: Number, default: 2 },
})
</script>

<style scoped>
.word-list-panel {
  margin-top: 10px;
  padding: 10px;
  background: rgba(255,255,255,.03);
  border: 1px solid rgba(255,255,255,.07);
  border-radius: 8px;
}
.wlp-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: .5px;
  margin-bottom: 8px;
}
.wlp-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 4px;
}
.wlp-label { color: var(--text3); }
.wlp-val   { color: var(--accent); font-weight: 600; }
.wlp-hint  {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text3);
  line-height: 1.5;
}
</style>
