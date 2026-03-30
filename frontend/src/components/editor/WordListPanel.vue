<template>
  <div class="word-list-panel">
    <div class="wlp-title">{{ tr('wordlist_title', 'Word Box Content') }}</div>
    <div class="wlp-row">
      <span class="wlp-label">{{ tr('wordlist_language', 'Language') }}</span>
      <span class="wlp-val">{{ sourceLang }} → {{ targetLang }}</span>
    </div>
    <div class="wlp-row">
      <span class="wlp-label">{{ tr('create_max_words', 'Max Words per Sentence') }}</span>
      <span class="wlp-val">{{ numWords === 0 ? tr('create_unlimited', 'Unlimited') : numWords + ' ' + tr('create_per_sentence', '/sentence') }}</span>
    </div>
    <div class="wlp-row">
      <span class="wlp-label">{{ tr('create_max_exprs', 'Max Expressions per Sentence') }}</span>
      <span class="wlp-val">{{ numExprs === 0 ? tr('create_unlimited', 'Unlimited') : numExprs + ' ' + tr('create_per_sentence', '/sentence') }}</span>
    </div>
    <div class="wlp-hint">{{ tr('wordlist_hint', 'Word box content is automatically extracted by AI from the video') }}</div>
  </div>
</template>

<script setup>
import { useI18n } from '../../i18n.js'

defineProps({
  sourceLang: { type: String, default: 'en' },
  targetLang: { type: String, default: 'zh' },
  numWords:   { type: Number, default: 3 },
  numExprs:   { type: Number, default: 2 },
})

const { t } = useI18n()

function tr(key, fallback = '') {
  return t.value?.[key] || fallback || key
}
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
