import { computed, ref } from 'vue'

const TOOLTIP_W = 300

function normalizePronunciations(pronunciations, fallbackPhonetic, fallbackAudio) {
  const out = []
  const seen = new Set()
  const pushOne = (p) => {
    if (!p || typeof p !== 'object') return
    const phonetic = String(p.phonetic || '').trim()
    const audio = String(p.audio || '').trim()
    const dialects = Array.isArray(p.dialects) ? p.dialects.map(x => String(x || '').trim()).filter(Boolean) : []
    if (!phonetic && !audio) return
    const key = `${phonetic}__${audio}__${dialects.join('|')}`
    if (seen.has(key)) return
    seen.add(key)
    out.push({ phonetic, audio, dialects })
  }
  if (Array.isArray(pronunciations)) {
    pronunciations.forEach(pushOne)
  }
  pushOne({ phonetic: fallbackPhonetic, audio: fallbackAudio, dialects: [] })
  return out
}

function normalizeDictionaryPayload(raw) {
  if (!raw || typeof raw !== 'object') return null
  const pronunciations = normalizePronunciations(raw.pronunciations, raw.phonetic, raw.audio)
  const meanings = Array.isArray(raw.meanings) ? raw.meanings : []
  const translated = Array.isArray(raw.translated_meanings) ? raw.translated_meanings : []
  const audio = String(raw.audio || pronunciations.find(p => p.audio)?.audio || '').trim()
  const phonetic = String(raw.phonetic || pronunciations.find(p => p.phonetic)?.phonetic || '').trim()
  return {
    ...raw,
    provider: String(raw.provider || '').trim(),
    dataset: String(raw.dataset || '').trim(),
    phonetic,
    audio,
    pronunciations,
    meanings: meanings.map((m) => ({
      pos: String(m?.pos || '').trim(),
      definition: String(m?.definition || '').trim(),
      example: String(m?.example || '').trim(),
      synonyms: Array.isArray(m?.synonyms) ? m.synonyms.map(x => String(x || '').trim()).filter(Boolean) : [],
    })),
    translated_meanings: translated.map(x => String(x || '').trim()),
  }
}

export function useJobDetailDictionaryTooltip({
  sourceLangForLookup,
  targetLangForLookup,
  mdViewRef,
  apiFetch,
}) {
  const tooltip = ref({
    visible: false,
    loading: false,
    notFound: false,
    word: '',
    data: null,
    x: 0,
    y: 0,
    side: 'right',
    anchorX: 0,
  })
  const dictCache = {}
  let showTimer = null
  let hideTimer = null
  let hoverToken = 0
  let activeHoverKey = ''
  let requestToken = 0

  function dictCacheKey(word) {
    return `${sourceLangForLookup.value}__${targetLangForLookup.value}__${word}`
  }

  const tooltipStyle = computed(() => {
    const MARGIN = 10
    const GAP = 20
    let x
    let y
    if (tooltip.value.side === 'left') {
      x = tooltip.value.anchorX - TOOLTIP_W - GAP
      x = Math.max(MARGIN, x)
    } else {
      x = tooltip.value.anchorX + GAP
      if (x + TOOLTIP_W > window.innerWidth - MARGIN) {
        x = window.innerWidth - TOOLTIP_W - MARGIN
      }
    }
    y = tooltip.value.y - 10
    y = Math.max(MARGIN, Math.min(y, window.innerHeight - 300))
    return { left: `${x}px`, top: `${y}px`, width: `${TOOLTIP_W}px` }
  })

  function onMdHover(e) {
    const el = e.target.closest?.('.dict-word')
    if (el) {
      hoverToken += 1
      const localHover = hoverToken
      clearTimeout(hideTimer)
      clearTimeout(showTimer)
      showTimer = setTimeout(() => {
        if (localHover !== hoverToken) return
        triggerTooltip(el.dataset.word, el)
      }, 200)
      return
    }
    if (!e.target.closest?.('.dict-tooltip')) {
      clearTimeout(showTimer)
      if (tooltip.value.visible) scheduleHide()
    }
  }

  function onMdOut(e) {
    if (e.target.classList?.contains('dict-word')) {
      if (!e.relatedTarget?.closest?.('.dict-word') && !e.relatedTarget?.closest?.('.dict-tooltip')) {
        hoverToken += 1
        activeHoverKey = ''
        clearTimeout(showTimer)
        scheduleHide()
      }
    }
  }

  function onMdLeave(e) {
    hoverToken += 1
    activeHoverKey = ''
    clearTimeout(showTimer)
    if (e.relatedTarget?.closest?.('.dict-tooltip')) return
    scheduleHide()
  }

  async function onWordClick(e) {
    const el = e.target.closest?.('.dict-word')
    if (!el) return
    e.preventDefault()
    e.stopPropagation()
    clearTimeout(hideTimer)
    clearTimeout(showTimer)
    const word = (el.dataset.word || '').trim()
    if (!word) return
    try {
      await triggerTooltip(word, el)
    } catch {}
    const cacheKey = dictCacheKey(word)
    const url = tooltip.value.data?.audio || dictCache[cacheKey]?.audio
    if (url) {
      new Audio(url).play().catch(() => {})
    }
  }

  function cancelHide() {
    clearTimeout(hideTimer)
  }

  function scheduleHide() {
    hideTimer = setTimeout(() => {
      tooltip.value.visible = false
      tooltip.value.loading = false
    }, 200)
  }

  async function triggerTooltip(word, el) {
    if (!word) return
    const hoverKey = `${word}__${sourceLangForLookup.value}__${targetLangForLookup.value}__${Math.round(el?.getBoundingClientRect?.().left || 0)}`
    activeHoverKey = hoverKey

    const rect = el.getBoundingClientRect()
    tooltip.value.word = el?.dataset?.display || word
    tooltip.value.y = rect.top + rect.height / 2
    tooltip.value.notFound = false

    const containerRect = mdViewRef.value?.getBoundingClientRect()
    const wordCenterX = (rect.left + rect.right) / 2
    const centerX = containerRect
      ? (containerRect.left + containerRect.right) / 2
      : window.innerWidth / 2
    const isLeft = wordCenterX < centerX
    tooltip.value.side = isLeft ? 'left' : 'right'
    tooltip.value.anchorX = isLeft
      ? (containerRect?.left ?? rect.left)
      : (containerRect?.right ?? rect.right)

    const cacheKey = dictCacheKey(word)
    if (dictCache[cacheKey] !== undefined) {
      if (activeHoverKey !== hoverKey) return
      tooltip.value.data = dictCache[cacheKey] || null
      tooltip.value.notFound = !dictCache[cacheKey]
      tooltip.value.loading = false
      tooltip.value.visible = true
      return
    }

    tooltip.value.loading = true
    tooltip.value.data = null
    tooltip.value.visible = true

    requestToken += 1
    const localReq = requestToken
    try {
      const srcLang = sourceLangForLookup.value || 'en'
      const tgtLang = targetLangForLookup.value || 'zh'
      const data = await apiFetch(
        `/api/dictionary/${encodeURIComponent(word)}?source_lang=${encodeURIComponent(srcLang)}&target_lang=${encodeURIComponent(tgtLang)}`
      )
      const normalized = normalizeDictionaryPayload(data)
      if (!normalized) throw new Error('invalid dictionary payload')
      dictCache[cacheKey] = normalized
      if (localReq !== requestToken || activeHoverKey !== hoverKey) return
      tooltip.value.data = normalized
      tooltip.value.notFound = false
    } catch {
      dictCache[cacheKey] = null
      if (localReq !== requestToken || activeHoverKey !== hoverKey) return
      tooltip.value.notFound = true
      tooltip.value.data = null
    } finally {
      if (localReq !== requestToken || activeHoverKey !== hoverKey) return
      tooltip.value.loading = false
    }
  }

  function playAudio() {
    const url = tooltip.value.data?.audio
    if (url) new Audio(url).play().catch(() => {})
  }

  function playPronunciationAudio(audioUrl) {
    const url = String(audioUrl || '').trim()
    if (url) new Audio(url).play().catch(() => {})
  }

  return {
    tooltip,
    tooltipStyle,
    onMdHover,
    onMdOut,
    onMdLeave,
    onWordClick,
    cancelHide,
    scheduleHide,
    playAudio,
    playPronunciationAudio,
  }
}
