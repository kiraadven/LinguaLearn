/**
 * Konva Renderer — isomorphic rendering engine
 * Used by both browser (vue-konva preview) and Node.js (konva-node export)
 *
 * This module takes Timeline JSON + content data and produces Konva node configurations.
 * In browser: configs are used to create vue-konva components
 * In Node.js: configs are used to create konva-node nodes → PNG export
 */

import { createSubtitleNodes } from './element-renderers/subtitle.js'
import { createWordboxNodes } from './element-renderers/wordbox.js'
import { createExprboxNodes } from './element-renderers/exprbox.js'
import { createWatermarkNodes } from './element-renderers/watermark.js'
import { STYLE_THEMES } from './theme-mapper.js'

/** Element type → renderer function mapping */
const RENDERERS = {
  subtitle:  createSubtitleNodes,
  wordbox:   createWordboxNodes,
  exprbox:   createExprboxNodes,
  watermark: createWatermarkNodes,
}

/**
 * PREVIEW_DATA — example content for editor preview (8 languages)
 */
export const PREVIEW_DATA = {
  en: {
    sentence: "The acquisition of language is a remarkable phenomenon that reveals the incredible cognitive capabilities of the human mind.",
    translations: {
      zh: "语言习得是一种非凡的现象，揭示了人类心智令人难以置信的认知能力。",
      ja: "言語習得は、人間の心の驚くべき認知能力を明らかにする注目すべき現象です。",
      ko: "언어 습득은 인간 마음의 놀라운 인지 능력을 드러내는 주목할 만한 현상입니다.",
      de: "Der Spracherwerb ist ein bemerkenswertes Phänomen, das die kognitiven Fähigkeiten des menschlichen Geistes offenbart.",
      fr: "L'acquisition du langage révèle les incroyables capacités cognitives de l'esprit humain.",
      es: "La adquisición del lenguaje revela las increíbles capacidades cognitivas de la mente humana.",
      ru: "Освоение языка — это замечательный феномен, который демонстрирует когнитивную адаптивность человеческого мозга.",
    },
    words: [
      { word: "acquisition", phonetic: "/ˌækwɪˈzɪʃən/", translation: "习得；获取" },
      { word: "remarkable", phonetic: "/rɪˈmɑːrkəbl/", translation: "非凡的；显著的" },
      { word: "phenomenon", phonetic: "/fɪˈnɒmɪnən/", translation: "现象；奇迹" },
      { word: "cognitive", phonetic: "/ˈkɒɡnɪtɪv/", translation: "认知的" },
      { word: "capability", phonetic: "/ˌkeɪpəˈbɪlɪti/", translation: "能力；才能" },
      { word: "incredible", phonetic: "/ɪnˈkredɪbl/", translation: "难以置信的" },
    ],
    expressions: [
      { english: "in the long run", chinese: "从长远来看" },
      { english: "on the other hand", chinese: "另一方面" },
      { english: "as a result of", chinese: "由于…的结果" },
    ],
  },
  zh: {
    sentence: "人类语言的习得是一种非凡的认知现象，展示了大脑令人难以置信的神经可塑性和学习能力。",
    translations: {
      en: "The acquisition of human language is an extraordinary cognitive phenomenon demonstrating the brain's incredible neuroplasticity.",
      ja: "人間の言語習得は脳の神経可塑性と学習能力を示す認知現象です。",
    },
    words: [
      { word: "认知", phonetic: "rèn zhī", translation: "cognition" },
      { word: "非凡", phonetic: "fēi fán", translation: "extraordinary" },
      { word: "可塑性", phonetic: "kě sù xìng", translation: "plasticity" },
      { word: "习得", phonetic: "xí dé", translation: "acquisition" },
      { word: "展示", phonetic: "zhǎn shì", translation: "demonstrate" },
      { word: "现象", phonetic: "xiàn xiàng", translation: "phenomenon" },
    ],
    expressions: [
      { english: "令人难以置信", chinese: "incredibly hard to believe" },
      { english: "展示了…能力", chinese: "demonstrates the ability" },
      { english: "一种…现象", chinese: "a kind of phenomenon" },
    ],
  },
  ja: {
    sentence: "言語習得は人間の認知能力の驚くべき側面であり、脳の信じられないほどの適応力と可塑性を示しています。",
    translations: {
      en: "Language acquisition is a remarkable aspect of human cognitive ability.",
      zh: "语言习得是人类认知能力的显著方面，展示了大脑的适应性和可塑性。",
    },
    words: [
      { word: "習得", phonetic: "しゅうとく", translation: "acquisition" },
      { word: "認知", phonetic: "にんち", translation: "cognition" },
      { word: "驚くべき", phonetic: "おどろくべき", translation: "remarkable" },
      { word: "適応力", phonetic: "てきおうりょく", translation: "adaptability" },
      { word: "可塑性", phonetic: "かそせい", translation: "plasticity" },
      { word: "側面", phonetic: "そくめん", translation: "aspect" },
    ],
    expressions: [
      { english: "〜を示している", chinese: "demonstrates ~" },
      { english: "驚くべき〜", chinese: "remarkable ~" },
      { english: "〜の側面", chinese: "aspect of ~" },
    ],
  },
  ko: {
    sentence: "언어 습득은 인간 인지 능력의 놀라운 측면으로, 뇌의 적응력과 가소성을 보여줍니다.",
    translations: {
      en: "Language acquisition is a remarkable aspect of human cognitive ability.",
      zh: "语言习得是人类认知能力的显著方面。",
    },
    words: [
      { word: "습득", phonetic: "seub-deug", translation: "acquisition" },
      { word: "인지", phonetic: "in-ji", translation: "cognition" },
      { word: "놀라운", phonetic: "nol-la-un", translation: "remarkable" },
      { word: "적응력", phonetic: "jeog-eung-lyeog", translation: "adaptability" },
      { word: "가소성", phonetic: "ga-so-seong", translation: "plasticity" },
      { word: "측면", phonetic: "cheug-myeon", translation: "aspect" },
    ],
    expressions: [
      { english: "보여줍니다", chinese: "demonstrates" },
      { english: "놀라운 측면", chinese: "remarkable aspect" },
      { english: "믿기 어려운", chinese: "hard to believe" },
    ],
  },
  de: {
    sentence: "Der Spracherwerb ist ein bemerkenswertes Phänomen, das die kognitive Anpassungsfähigkeit des menschlichen Gehirns demonstriert.",
    translations: {
      en: "Language acquisition demonstrates the cognitive adaptability of the human brain.",
      zh: "语言习得展示了人类大脑令人难以置信的认知适应性和神经可塑性。",
    },
    words: [
      { word: "Spracherwerb", phonetic: "/ˈʃpraːxɛɐ̯ˌvɛrp/", translation: "language acquisition" },
      { word: "bemerkenswert", phonetic: "/bəˈmɛrkənsvɛrt/", translation: "remarkable" },
      { word: "Plastizität", phonetic: "/plastiˈtsɪtɛːt/", translation: "plasticity" },
      { word: "demonstriert", phonetic: "/demoːnˈstriːrt/", translation: "demonstrates" },
      { word: "kognitiv", phonetic: "/kɔɡniˈtiːf/", translation: "cognitive" },
      { word: "unglaublich", phonetic: "/ʊnˈɡlaʊ̯plɪç/", translation: "incredible" },
    ],
    expressions: [
      { english: "das...demonstriert", chinese: "which demonstrates" },
      { english: "ein...Phänomen", chinese: "a phenomenon" },
      { english: "des menschlichen", chinese: "of the human" },
    ],
  },
  fr: {
    sentence: "L'acquisition du langage est un phénomène remarquable qui démontre l'adaptabilité cognitive du cerveau humain.",
    translations: {
      en: "Language acquisition demonstrates the cognitive adaptability of the human brain.",
      zh: "语言习得展示了人类大脑令人难以置信的认知适应性和神经可塑性。",
    },
    words: [
      { word: "acquisition", phonetic: "/akizisjɔ̃/", translation: "acquisition" },
      { word: "remarquable", phonetic: "/ʁəmaʁkabl/", translation: "remarkable" },
      { word: "plasticité", phonetic: "/plastisite/", translation: "plasticity" },
      { word: "adaptabilité", phonetic: "/adaptabilite/", translation: "adaptability" },
      { word: "démontre", phonetic: "/demɔ̃tʁ/", translation: "demonstrates" },
      { word: "incroyable", phonetic: "/ɛ̃kʁwajabl/", translation: "incredible" },
    ],
    expressions: [
      { english: "qui démontre", chinese: "which demonstrates" },
      { english: "un phénomène remarquable", chinese: "a remarkable phenomenon" },
      { english: "du cerveau humain", chinese: "of the human brain" },
    ],
  },
  es: {
    sentence: "La adquisición del lenguaje es un fenómeno notable que demuestra la adaptabilidad cognitiva del cerebro humano.",
    translations: {
      en: "Language acquisition demonstrates the cognitive adaptability of the human brain.",
      zh: "语言习得展示了人类大脑令人难以置信的认知适应性和神经可塑性。",
    },
    words: [
      { word: "adquisición", phonetic: "/adkiˈsjon/", translation: "acquisition" },
      { word: "notable", phonetic: "/noˈtaβle/", translation: "remarkable" },
      { word: "plasticidad", phonetic: "/plastiθiˈðað/", translation: "plasticity" },
      { word: "adaptabilidad", phonetic: "/adaptaβiliˈðað/", translation: "adaptability" },
      { word: "demuestra", phonetic: "/deˈmwestra/", translation: "demonstrates" },
      { word: "increíble", phonetic: "/iŋkɾeˈiβle/", translation: "incredible" },
    ],
    expressions: [
      { english: "que demuestra", chinese: "which demonstrates" },
      { english: "un fenómeno notable", chinese: "a remarkable phenomenon" },
      { english: "del cerebro humano", chinese: "of the human brain" },
    ],
  },
  ru: {
    sentence: "Освоение языка — это замечательный феномен, который демонстрирует когнитивную адаптивность человеческого мозга.",
    translations: {
      en: "Language acquisition demonstrates cognitive adaptability of the human brain.",
      zh: "语言习得是一种非凡的现象，展示了人类大脑的认知适应性和神经可塑性。",
    },
    words: [
      { word: "освоение", phonetic: "/əsˈvoːɪnɪjə/", translation: "acquisition" },
      { word: "замечательный", phonetic: "/zəmɪˈtʃætəlnɪj/", translation: "remarkable" },
      { word: "феномен", phonetic: "/fɪˈnɔːmɪn/", translation: "phenomenon" },
      { word: "демонстрирует", phonetic: "/dɪˈmɒnstreɪts/", translation: "demonstrates" },
      { word: "адаптивность", phonetic: "/ədˈæptɪvnəs/", translation: "adaptability" },
      { word: "нейропластичность", phonetic: "/ˈnjʊroʊˈplæstɪsɪti/", translation: "neural plasticity" },
    ],
    expressions: [
      { english: "замечательный феномен", chinese: "remarkable phenomenon" },
      { english: "демонстрирует способность", chinese: "demonstrates ability" },
      { english: "человеческого мозга", chinese: "of the human brain" },
    ],
  },
}

/**
 * Get preview content for a given source/target language pair.
 *
 * @param {string} srcLang - Source language code
 * @param {string} tgtLang - Target language code
 * @param {number} numWords - Number of words to show (0 = all)
 * @param {number} numExprs - Number of expressions to show (0 = all)
 * @returns {{ text, translation, words, expressions }}
 */
export function getPreviewContent(srcLang, tgtLang, numWords = 3, numExprs = 2) {
  const data = PREVIEW_DATA[srcLang] || PREVIEW_DATA.en
  const translation = data.translations?.[tgtLang] || data.translations?.en || '翻译文本'
  const words = numWords > 0 ? data.words.slice(0, numWords) : data.words
  const expressions = numExprs > 0 ? data.expressions.slice(0, numExprs) : data.expressions

  return {
    text: data.sentence,
    translation,
    words,
    expressions,
  }
}

/**
 * Render a single element to Konva node configs.
 *
 * @param {object} element - Timeline element object
 * @param {object} content - Content data (sentence-specific or preview)
 * @param {{ width: number, height: number }} containerSize - pixel dimensions
 * @returns {{ x, y, w, h, nodes: Array }|null}
 */
/**
 * Merge theme style into element style, preserving per-element overrides like fontFamily/fontScale.
 */
export function getEffectiveStyle(element, styleId) {
  if (!styleId) return element.style
  const theme = STYLE_THEMES[styleId]
  const section = theme?.[element.type]
  if (!section) return element.style
  return {
    ...element.style,
    ...section,
    fontFamily: element.style.fontFamily,
    fontScale: element.style.fontScale,
  }
}

export function renderElement(element, content, containerSize, styleId) {
  const renderer = RENDERERS[element.type]
  if (!renderer) {
    console.warn(`[konva-renderer] Unknown element type: ${element.type}`)
    return null
  }
  const effectiveElement = styleId
    ? { ...element, style: getEffectiveStyle(element, styleId) }
    : element
  return renderer(effectiveElement, content, containerSize)
}

/**
 * Render all visible elements for a given part.
 *
 * @param {object} timeline - Complete Timeline JSON
 * @param {string} partId - Part ID to render
 * @param {object} content - Content data
 * @param {{ width: number, height: number }} containerSize - pixel dimensions
 * @returns {Array<{ elementId, x, y, w, h, nodes, zIndex }>}
 */
export function renderPart(timeline, partId, content, containerSize) {
  const part = timeline.parts.find(p => p.id === partId)
  if (!part) return []

  const results = []
  // Sort elements by zIndex
  const sortedElements = [...timeline.elements].sort((a, b) => (a.zIndex || 0) - (b.zIndex || 0))

  for (const element of sortedElements) {
    // Check visibility in this part
    const isVisible = part.elementVisibility?.[element.id]
    if (!isVisible) continue
    if (element.visible === false) continue

    // Prepare content based on element type
    let elementContent = content
    if (element.type === 'subtitle') {
      elementContent = { text: content?.text, translation: content?.translation }
    } else if (element.type === 'wordbox') {
      elementContent = { words: content?.words }
    } else if (element.type === 'exprbox') {
      elementContent = { expressions: content?.expressions }
    }

    const effectiveStyleId = part.styleId || timeline.styleId || null
    const result = renderElement(element, elementContent, containerSize, effectiveStyleId)
    if (result) {
      results.push({
        elementId: element.id,
        elementType: element.type,
        zIndex: element.zIndex || 0,
        animation: element.animation,
        ...result,
      })
    }
  }

  return results
}

/**
 * Create a default Timeline JSON with standard elements.
 *
 * @param {object} opts - { sourceLang, targetLang, resolution, styleId }
 * @returns {object} Complete Timeline JSON
 */
export function createDefaultTimeline(opts = {}) {
  const {
    sourceLang = 'en',
    targetLang = 'zh',
    resolution = { width: 1920, height: 1080 },
    styleId = 'neon_cyberpunk',
  } = opts

  return {
    version: 1,
    resolution,
    defaultFont: 'system',
    styleId,
    sourceLang,
    targetLang,
    numWords: 3,
    numExprs: 2,

    elements: [
      {
        id: 'subtitle_1',
        type: 'subtitle',
        visible: true,
        position: { x: 0.05, y: 0.76 },
        size: { w: 0.90, h: 0.14 },
        rotation: 0,
        opacity: 1.0,
        zIndex: 10,
        style: {
          bgColor: 'rgba(10,10,21,0.92)',
          bgStyle: 'dark',
          textColor: '#00ffff',
          translationColor: '#ff0080',
          fontFamily: 'system',
          fontScale: 1.0,
          borderRadius: 4,
        },
        animation: {
          enter: { type: 'pop', duration: 300, easing: 'easeOutCubic' },
          exit: { type: 'fade', duration: 200, easing: 'easeInCubic' },
        },
      },
      {
        id: 'wordbox_1',
        type: 'wordbox',
        visible: true,
        position: { x: 0.75, y: 0.005 },
        size: { w: 0.245, h: 0.65 },
        rotation: 0,
        opacity: 1.0,
        zIndex: 8,
        style: {
          bgColor: 'rgba(10,10,21,0.95)',
          wordColor: '#00ffff',
          phoneticColor: '#ff00ff',
          translationColor: '#ffffff',
          accentColor: '#00ffff',
          headerColor: '#ff0080',
          fontFamily: 'system',
          fontScale: 1.0,
          borderRadius: 4,
        },
        animation: {
          enter: { type: 'pop', duration: 300, easing: 'easeOutCubic' },
          exit: { type: 'fade', duration: 200, easing: 'easeInCubic' },
        },
      },
      {
        id: 'exprbox_1',
        type: 'exprbox',
        visible: true,
        position: { x: 0.005, y: 0.005 },
        size: { w: 0.245, h: 0.55 },
        rotation: 0,
        opacity: 1.0,
        zIndex: 8,
        style: {
          bgColor: 'rgba(10,10,21,0.95)',
          expressionColor: '#ff0080',
          translationColor: '#ffffff',
          accentColor: '#ff0080',
          headerColor: '#00ffff',
          fontFamily: 'system',
          fontScale: 1.0,
          borderRadius: 4,
        },
        animation: {
          enter: { type: 'pop', duration: 300, easing: 'easeOutCubic' },
          exit: { type: 'fade', duration: 200, easing: 'easeInCubic' },
        },
      },
    ],

    parts: [
      {
        id: 'p_1',
        repeat: 1,
        speed: 1.0,
        styleId: null,
        elementVisibility: {
          subtitle_1: true,
          wordbox_1: false,
          exprbox_1: false,
        },
      },
    ],
  }
}
