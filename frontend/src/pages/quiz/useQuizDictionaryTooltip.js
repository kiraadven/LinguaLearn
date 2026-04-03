import { computed, ref } from 'vue'
import { normalizeLookupToken, tokenizeForDictionary } from '../../composables/useDictionaryLookup.js'

const DICT_TOOLTIP_W = 300

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
  const audio = String(raw.audio || pronunciations.find(p => p.audio)?.audio || '').trim()
  const phonetic = String(raw.phonetic || pronunciations.find(p => p.phonetic)?.phonetic || '').trim()
  return {
    ...raw,
    provider: String(raw.provider || '').trim(),
    dataset: String(raw.dataset || '').trim(),
    phonetic,
    audio,
    pronunciations,
    meanings: Array.isArray(raw.meanings) ? raw.meanings : [],
    translated_meanings: Array.isArray(raw.translated_meanings) ? raw.translated_meanings : [],
  }
}

export function useQuizDictionaryTooltip({
  apiFetch,
  quizSourceLang,
  quizTargetLang,
}) {
  const reviewSectionRef = ref(null)
  const dictTooltip = ref({
    visible: false,
    loading: false,
    notFound: false,
    word: '',
    data: null,
    y: 0,
    side: 'right',
    anchorX: 0,
  })
  const dictCache = {}
  let dictShowTimer = null
  let dictHideTimer = null
  let dictHoverToken = 0
  let dictActiveHoverKey = ''
  let dictRequestToken = 0

  const dictTooltipStyle = computed(() => {
    const MARGIN = 10
    const GAP = 20
    let x
    let y
    if (dictTooltip.value.side === 'left') {
      x = dictTooltip.value.anchorX - DICT_TOOLTIP_W - GAP
      x = Math.max(MARGIN, x)
    } else {
      x = dictTooltip.value.anchorX + GAP
      x = Math.min(x, window.innerWidth - DICT_TOOLTIP_W - MARGIN)
    }
    y = dictTooltip.value.y - 10
    y = Math.max(MARGIN, Math.min(y, window.innerHeight - 300))
    return { left: `${x}px`, top: `${y}px`, width: `${DICT_TOOLTIP_W}px` }
  })

  function onWordHoverToken(token, sourceLang, targetLang, event) {
    const el = event.currentTarget
    dictHoverToken += 1
    const localHover = dictHoverToken
    clearTimeout(dictHideTimer)
    clearTimeout(dictShowTimer)
    dictShowTimer = setTimeout(() => {
      if (localHover !== dictHoverToken) return
      triggerDictTooltip(token, sourceLang, targetLang, el)
    }, 200)
  }

  function onWordLeave(event) {
    if (!event.relatedTarget?.closest?.('.dict-tooltip')) {
      dictHoverToken += 1
      dictActiveHoverKey = ''
      clearTimeout(dictShowTimer)
      if (dictTooltip.value.visible) scheduleDictHide()
    }
  }

  function cancelDictHide() {
    clearTimeout(dictHideTimer)
  }

  function scheduleDictHide() {
    dictHideTimer = setTimeout(() => {
      dictTooltip.value.visible = false
      dictTooltip.value.loading = false
    }, 200)
  }

  function getReviewWordTargetLang(reviewWord) {
    return localStorage.getItem('ll_familiar_lang') || quizTargetLang.value || reviewWord?.target_lang || reviewWord?.targetLang || 'zh'
  }

  function getReviewWordSourceLang(reviewWord) {
    return reviewWord?.source_lang || reviewWord?.sourceLang || quizSourceLang.value || localStorage.getItem('ll_learning_lang') || 'en'
  }

  function getReviewLookupTokens(reviewWord) {
    const raw = String(reviewWord?.word || '')
    if (!raw) return []
    const sourceLang = getReviewWordSourceLang(reviewWord)
    return tokenizeForDictionary(raw, sourceLang)
  }

  async function triggerDictTooltip(token, sourceLang, targetLang, el) {
    const rawWord = token?.text || ''
    const word = token?.lookup || normalizeLookupToken(rawWord, sourceLang)
    if (!word) return
    const hoverKey = `${word}__${sourceLang}__${targetLang}__${Math.round(el?.getBoundingClientRect?.().left || 0)}`
    dictActiveHoverKey = hoverKey
    const rect = el.getBoundingClientRect()
    dictTooltip.value.word = rawWord || word
    dictTooltip.value.y = rect.top + rect.height / 2
    dictTooltip.value.notFound = false

    const containerRect = reviewSectionRef.value?.getBoundingClientRect()
    const wordCenterX = rect.left + rect.width / 2
    const centerX = containerRect ? (containerRect.left + containerRect.right) / 2 : window.innerWidth / 2
    const isLeft = wordCenterX < centerX
    dictTooltip.value.side = isLeft ? 'left' : 'right'
    dictTooltip.value.anchorX = isLeft
      ? (containerRect?.left ?? rect.left)
      : (containerRect?.right ?? rect.right)

    const cacheKey = `${word}__${sourceLang}__${targetLang}`
    if (dictCache[cacheKey] !== undefined) {
      if (dictActiveHoverKey !== hoverKey) return
      dictTooltip.value.data = dictCache[cacheKey] || null
      dictTooltip.value.notFound = !dictCache[cacheKey]
      dictTooltip.value.loading = false
      dictTooltip.value.visible = true
      return
    }

    dictTooltip.value.loading = true
    dictTooltip.value.data = null
    dictTooltip.value.visible = true

    dictRequestToken += 1
    const localReq = dictRequestToken
    try {
      const data = await apiFetch(
        `/api/dictionary/${encodeURIComponent(word)}?source_lang=${encodeURIComponent(sourceLang)}&target_lang=${encodeURIComponent(targetLang)}`
      )
      const normalized = normalizeDictionaryPayload(data)
      if (!normalized) throw new Error('invalid dictionary payload')
      dictCache[cacheKey] = normalized
      if (localReq !== dictRequestToken || dictActiveHoverKey !== hoverKey) return
      dictTooltip.value.data = normalized
      dictTooltip.value.notFound = false
    } catch {
      dictCache[cacheKey] = null
      if (localReq !== dictRequestToken || dictActiveHoverKey !== hoverKey) return
      dictTooltip.value.notFound = true
      dictTooltip.value.data = null
    } finally {
      if (localReq !== dictRequestToken || dictActiveHoverKey !== hoverKey) return
      dictTooltip.value.loading = false
    }
  }

  function playDictAudio() {
    const url = dictTooltip.value.data?.audio
    if (url) new Audio(url).play().catch(() => {})
  }

  function playDictPronunciationAudio(audioUrl) {
    const url = String(audioUrl || '').trim()
    if (url) new Audio(url).play().catch(() => {})
  }

  return {
    reviewSectionRef,
    dictTooltip,
    dictTooltipStyle,
    onWordHoverToken,
    onWordLeave,
    cancelDictHide,
    scheduleDictHide,
    getReviewWordTargetLang,
    getReviewWordSourceLang,
    getReviewLookupTokens,
    playDictAudio,
    playDictPronunciationAudio,
  }
}
