import { ref, computed } from 'vue'
import { TRANSLATIONS } from './i18n/translations.js'
import { EXTRA_TRANSLATIONS } from './i18n/extraTranslations.js'

const SUPPORTED_LANGS = ['en', 'zh-Hans', 'zh-Hant', 'ja', 'ko', 'de', 'fr', 'es', 'ru']

function normalizeUILangCode(lang) {
  const v = String(lang || '').trim()
  if (!v) return ''
  const low = v.toLowerCase()
  if (low === 'zh') return 'zh-Hans'
  if (low === 'zh-hans' || low === 'zh-cn' || low === 'zh-sg') return 'zh-Hans'
  if (low === 'zh-hant' || low === 'zh-tw' || low === 'zh-hk' || low === 'zh-mo') return 'zh-Hant'
  return v
}

function translationDictLang(uiLangCode) {
  return normalizeUILangCode(uiLangCode)
}

function resolveInitialUILang() {
  if (typeof localStorage === 'undefined') return 'zh-Hans'
  const explicit = normalizeUILangCode(localStorage.getItem('ll_ui_lang'))
  if (explicit && SUPPORTED_LANGS.includes(explicit)) return explicit
  const familiar = normalizeUILangCode(localStorage.getItem('ll_familiar_lang'))
  if (familiar && SUPPORTED_LANGS.includes(familiar)) return familiar
  return 'zh-Hans'
}

// Module-level singleton
const uiLang = ref(resolveInitialUILang())
const RUNTIME_TRANSLATION_LANGS = new Set(['ja', 'ko', 'de', 'fr', 'es', 'ru'])
const RUNTIME_STORE_KEY = 'll_runtime_i18n_v3'
const runtimeTranslations = ref(loadRuntimeTranslations())
const runtimeLoading = new Set()

function loadRuntimeTranslations() {
  if (typeof localStorage === 'undefined') return {}
  try {
    const raw = localStorage.getItem(RUNTIME_STORE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function saveRuntimeTranslations() {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(RUNTIME_STORE_KEY, JSON.stringify(runtimeTranslations.value || {}))
  } catch {}
}

function buildStaticDict(dictLang) {
  return {
    ...(TRANSLATIONS[dictLang] || {}),
    ...(EXTRA_TRANSLATIONS[dictLang] || {}),
  }
}

function buildMissingUiEntries(dictLang) {
  if (!RUNTIME_TRANSLATION_LANGS.has(dictLang)) return {}
  const base = buildStaticDict(dictLang)
  const en = buildStaticDict('en')
  const zh = buildStaticDict('zh-Hans')
  const cached = runtimeTranslations.value?.[dictLang] || {}

  const missing = {}
  for (const [k, enVal] of Object.entries(en)) {
    const cachedVal = cached[k]
    if (
      typeof cachedVal === 'string' &&
      cachedVal.trim() &&
      (String(cachedVal) !== String(enVal) || String(zh[k] || '') === String(enVal))
    ) {
      continue
    }
    const cur = base[k]
    // 需要补全的条件：
    // 1) 本语言压根没有该 key；或
    // 2) 当前值与英文一致，但中文值不同（高概率是英文回退）
    if (
      cur === undefined ||
      (String(cur) === String(enVal) && String(zh[k] || '') !== String(enVal))
    ) {
      if (typeof enVal === 'string' && enVal.trim()) {
        missing[k] = enVal
      }
    }
  }
  return missing
}

async function hydrateRuntimeTranslationsFor(dictLang) {
  if (!RUNTIME_TRANSLATION_LANGS.has(dictLang)) return
  if (runtimeLoading.has(dictLang)) return
  const entries = buildMissingUiEntries(dictLang)
  const keys = Object.keys(entries)
  if (!keys.length) return

  runtimeLoading.add(dictLang)
  try {
    const chunkSize = 60
    const merged = { ...(runtimeTranslations.value?.[dictLang] || {}) }
    for (let i = 0; i < keys.length; i += chunkSize) {
      const partKeys = keys.slice(i, i + chunkSize)
      const payload = {}
      for (const k of partKeys) payload[k] = entries[k]
      const resp = await fetch('/api/i18n/ui-translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_lang: dictLang, entries: payload }),
      })
      if (!resp.ok) continue
      const data = await resp.json()
      const tr = data?.translations
      if (tr && typeof tr === 'object') {
        Object.assign(merged, tr)
      }
    }
    runtimeTranslations.value = {
      ...(runtimeTranslations.value || {}),
      [dictLang]: merged,
    }
    saveRuntimeTranslations()
  } catch {
    // 静默失败：保留静态文案
  } finally {
    runtimeLoading.delete(dictLang)
  }
}

// All translations (8 languages x all UI strings)
for (const lang of []) {
  EXTRA_TRANSLATIONS[lang] = {
    ...(EXTRA_TRANSLATIONS.en || {}),
    ...(EXTRA_TRANSLATIONS[lang] || {}),
  }
}

export function useI18n() {
  function setLang(lang) {
    const normalized = normalizeUILangCode(lang)
    if (SUPPORTED_LANGS.includes(normalized)) {
      uiLang.value = normalized
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('ll_ui_lang', normalized)
      }
      const dictLang = translationDictLang(normalized)
      hydrateRuntimeTranslationsFor(dictLang)
    }
  }

  const t = computed(() => {
    const dictLang = translationDictLang(uiLang.value)
    return ({
      ...(TRANSLATIONS.en || {}),
      ...(EXTRA_TRANSLATIONS.en || {}),
      ...(TRANSLATIONS[dictLang] || {}),
      ...(EXTRA_TRANSLATIONS[dictLang] || {}),
      ...(runtimeTranslations.value?.[dictLang] || {}),
    })
  })

  // 初次加载时自动补全一次
  const initialDictLang = translationDictLang(uiLang.value)
  hydrateRuntimeTranslationsFor(initialDictLang)

  return { uiLang, t, setLang, SUPPORTED_LANGS }
}
