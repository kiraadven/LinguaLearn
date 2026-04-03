const HANZI_RE = /[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]/u
const ALNUM_CLASS = 'A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-яЁёЀ-ӿ0-9'
const LATIN_CYR_TOKEN_RE = new RegExp(`[${ALNUM_CLASS}]+(?:[’'-][${ALNUM_CLASS}]+)*`, 'g')
const JAPANESE_TOKEN_RE = new RegExp(`[\\u3040-\\u30ff\\u3400-\\u9fff\\u3005\\u30fc]+|[${ALNUM_CLASS}]+(?:[’'-][${ALNUM_CLASS}]+)*`, 'g')
const KOREAN_TOKEN_RE = new RegExp(`[\\u1100-\\u11ff\\u3130-\\u318f\\uac00-\\ud7af]+|[${ALNUM_CLASS}]+(?:[’'-][${ALNUM_CLASS}]+)*`, 'g')

function normalizeTokenLang(lang) {
  const raw = String(lang || '').trim()
  if (!raw) return 'en'
  if (raw === 'zh-Hans' || raw === 'zh-Hant' || raw === 'zh') return 'zh'
  const low = raw.toLowerCase()
  if (low.startsWith('zh')) return 'zh'
  if (low.startsWith('ja')) return 'ja'
  if (low.startsWith('ko')) return 'ko'
  if (low.startsWith('de')) return 'de'
  if (low.startsWith('fr')) return 'fr'
  if (low.startsWith('es')) return 'es'
  if (low.startsWith('ru')) return 'ru'
  return 'en'
}

export function normalizeLookupToken(raw, sourceLang = 'en') {
  const mode = normalizeTokenLang(sourceLang)
  let text = String(raw || '').replace(/[’]/g, "'").trim()
  if (!text) return ''
  text = text.replace(
    /^[\s"'“”‘’`~!@#$%^&*()_+\-=[\]{};:,.<>/?，。！？；：（）【】《》、]+|[\s"'“”‘’`~!@#$%^&*()_+\-=[\]{};:,.<>/?，。！？；：（）【】《》、]+$/g,
    ''
  )
  if (!text) return ''
  if (!['zh', 'ja', 'ko'].includes(mode)) {
    text = text.toLowerCase()
  }
  return text
}

function splitByRegex(text, tokenRe, sourceLang) {
  const tokens = []
  let last = 0
  let m
  tokenRe.lastIndex = 0
  while ((m = tokenRe.exec(text)) !== null) {
    if (m.index > last) tokens.push({ text: text.slice(last, m.index), lookup: null })
    const tokenText = m[0]
    const lookup = normalizeLookupToken(tokenText, sourceLang)
    tokens.push({ text: tokenText, lookup: lookup || null })
    last = tokenRe.lastIndex
  }
  if (last < text.length) tokens.push({ text: text.slice(last), lookup: null })
  return tokens
}

export function tokenizeForDictionary(raw, sourceLang = 'en') {
  const text = String(raw || '')
  if (!text) return []

  const mode = normalizeTokenLang(sourceLang)
  if (mode === 'zh') {
    return Array.from(text).map(ch => {
      if (HANZI_RE.test(ch)) {
        const lookup = normalizeLookupToken(ch, sourceLang)
        return { text: ch, lookup: lookup || null }
      }
      return { text: ch, lookup: null }
    })
  }

  if (mode === 'ja') {
    const tokens = splitByRegex(text, JAPANESE_TOKEN_RE, sourceLang)
    return tokens.length ? tokens : [{ text, lookup: normalizeLookupToken(text, sourceLang) || null }]
  }

  if (mode === 'ko') {
    const tokens = splitByRegex(text, KOREAN_TOKEN_RE, sourceLang)
    return tokens.length ? tokens : [{ text, lookup: normalizeLookupToken(text, sourceLang) || null }]
  }

  const tokens = splitByRegex(text, LATIN_CYR_TOKEN_RE, sourceLang)
  return tokens.length ? tokens : [{ text, lookup: normalizeLookupToken(text, sourceLang) || null }]
}

export function wrapDictionaryWords(html, sourceLang = 'en') {
  const parser = new DOMParser()
  const doc = parser.parseFromString(`<div>${html}</div>`, 'text/html')
  const root = doc.body.firstChild
  const SKIP = new Set(['CODE', 'PRE', 'SCRIPT', 'STYLE'])

  function walk(node) {
    if (node.nodeType === 3) {
      const text = node.textContent || ''
      if (!text.trim()) return
      const tokens = tokenizeForDictionary(text, sourceLang)
      if (!tokens.some(t => t.lookup)) return
      const frag = document.createDocumentFragment()
      for (const token of tokens) {
        if (!token.text) continue
        if (!token.lookup) {
          frag.appendChild(document.createTextNode(token.text))
          continue
        }
        const span = document.createElement('span')
        span.className = 'dict-word'
        span.dataset.word = token.lookup
        span.dataset.display = token.text
        span.textContent = token.text
        frag.appendChild(span)
      }
      node.parentNode.replaceChild(frag, node)
      return
    }
    if (node.nodeType === 1) {
      if (SKIP.has(node.tagName) || node.classList?.contains('dict-word')) return
      ;[...node.childNodes].forEach(walk)
    }
  }

  walk(root)
  return root.innerHTML
}
