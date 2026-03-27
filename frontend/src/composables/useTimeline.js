/**
 * useTimeline — Timeline JSON state management composable
 * Single source of truth for all editor state
 */
import { reactive, computed, watch, toRaw } from 'vue'
import { createDefaultTimeline, getPreviewContent } from '@shared/konva-renderer.js'
import { applyThemeToElements, STYLE_THEMES } from '@shared/theme-mapper.js'
import { FONTS } from '@shared/font-registry.js'

let _idCounter = 0
function uid(prefix = 'el') {
  return `${prefix}_${++_idCounter}`
}

export function useTimeline() {
  // ── Core State ──
  const timeline = reactive(createDefaultTimeline())

  // ── Computed ──
  const elements = computed(() => timeline.elements)
  const parts = computed(() => timeline.parts)
  const resolution = computed(() => timeline.resolution)

  // ── Element CRUD ──

  function getElementById(id) {
    return timeline.elements.find(e => e.id === id)
  }

  function addElement(type, defaults = {}) {
    const defaultConfigs = {
      subtitle: {
        position: { x: 0.05, y: 0.76 }, size: { w: 0.90, h: 0.14 }, zIndex: 10,
        style: { bgColor: 'rgba(0,0,0,0.72)', bgStyle: 'dark', textColor: '#ffffff', translationColor: '#94a3b8', fontFamily: 'system', fontScale: 1.0, borderRadius: 8 },
      },
      wordbox: {
        position: { x: 0.75, y: 0.005 }, size: { w: 0.245, h: 0.65 }, zIndex: 8,
        style: { bgColor: 'rgba(20,10,50,0.88)', wordColor: '#a78bfa', phoneticColor: '#94a3b8', translationColor: '#f1f5f9', accentColor: '#a78bfa', headerColor: '#94a3b8', fontFamily: 'system', fontScale: 1.0, borderRadius: 10 },
      },
      exprbox: {
        position: { x: 0.005, y: 0.005 }, size: { w: 0.245, h: 0.55 }, zIndex: 8,
        style: { bgColor: 'rgba(10,5,30,0.88)', expressionColor: '#f472b6', translationColor: '#94a3b8', accentColor: '#f472b6', headerColor: '#94a3b8', fontFamily: 'system', fontScale: 1.0, borderRadius: 10 },
      },
      watermark: {
        position: { x: 0.60, y: 0.92 }, size: { w: 0.18, h: 0.06 }, zIndex: 100,
        style: { text: 'LinguaLearn', fontFamily: 'system', fontSize: 16, color: '#ffffff', strokeColor: 'rgba(0,0,0,0.3)', strokeWidth: 0 },
      },
    }

    const config = defaultConfigs[type] || defaultConfigs.subtitle
    const id = uid(type)

    const element = {
      id,
      type,
      visible: true,
      position: { ...config.position },
      size: { ...config.size },
      rotation: 0,
      opacity: type === 'watermark' ? 0.5 : 1.0,
      zIndex: config.zIndex,
      style: { ...config.style },
      animation: {
        enter: { type: 'fade', duration: 300, easing: 'easeOutCubic' },
        exit: { type: 'fade', duration: 200, easing: 'easeInCubic' },
      },
      ...defaults,
    }

    timeline.elements.push(element)

    // Add to all parts' visibility (default hidden for new elements)
    for (const part of timeline.parts) {
      if (!part.elementVisibility) part.elementVisibility = {}
      part.elementVisibility[id] = false
    }

    return element
  }

  function updateElement(id, patch) {
    const el = getElementById(id)
    if (!el) return

    for (const [key, val] of Object.entries(patch)) {
      if (key === 'position' || key === 'size' || key === 'style' || key === 'animation') {
        // Deep merge for nested objects
        if (typeof val === 'object' && val !== null) {
          if (key === 'animation') {
            // Animation has enter/exit sub-objects
            for (const [subKey, subVal] of Object.entries(val)) {
              if (!el.animation) el.animation = {}
              if (typeof subVal === 'object') {
                el.animation[subKey] = { ...(el.animation[subKey] || {}), ...subVal }
              } else {
                el.animation[subKey] = subVal
              }
            }
          } else {
            el[key] = { ...(el[key] || {}), ...val }
          }
        }
      } else {
        el[key] = val
      }
    }
  }

  function removeElement(id) {
    const idx = timeline.elements.findIndex(e => e.id === id)
    if (idx === -1) return
    timeline.elements.splice(idx, 1)

    // Remove from all parts' visibility
    for (const part of timeline.parts) {
      if (part.elementVisibility) {
        delete part.elementVisibility[id]
      }
    }
  }

  // ── Part CRUD ──

  function addPart() {
    if (timeline.parts.length >= 4) return null

    const id = uid('p')
    const visibility = {}
    for (const el of timeline.elements) {
      visibility[el.id] = false
    }

    const part = {
      id,
      repeat: 1,
      speed: 1.0,
      styleId: null,
      elementVisibility: visibility,
      elementConfigs: {},
    }

    timeline.parts.push(part)
    return part
  }

  function removePart(partId) {
    if (timeline.parts.length <= 1) return
    const idx = timeline.parts.findIndex(p => p.id === partId)
    if (idx !== -1) timeline.parts.splice(idx, 1)
  }

  function copyPart(partId) {
    if (timeline.parts.length >= 4) return null
    const src = timeline.parts.find(p => p.id === partId)
    if (!src) return null

    const id = uid('p')
    const copy = {
      id,
      repeat: src.repeat,
      speed: src.speed,
      styleId: src.styleId ?? null,
      elementVisibility: { ...src.elementVisibility },
      elementConfigs: JSON.parse(JSON.stringify(src.elementConfigs || {})),
    }

    const srcIdx = timeline.parts.findIndex(p => p.id === partId)
    timeline.parts.splice(srcIdx + 1, 0, copy)
    return copy
  }

  function updatePart(partId, patch) {
    const part = timeline.parts.find(p => p.id === partId)
    if (!part) return
    Object.assign(part, patch)
  }

  function updatePartElement(partId, elementId, patch) {
    const part = timeline.parts.find(p => p.id === partId)
    if (!part) { updateElement(elementId, patch); return }

    // Lazily init elementConfigs
    if (!part.elementConfigs) part.elementConfigs = {}
    if (!part.elementConfigs[elementId]) part.elementConfigs[elementId] = {}

    const partEl = part.elementConfigs[elementId]
    for (const [key, val] of Object.entries(patch)) {
      if (key === 'position' || key === 'size' || key === 'style' || key === 'animation') {
        if (typeof val === 'object' && val !== null) {
          if (key === 'animation') {
            if (!partEl.animation) partEl.animation = {}
            for (const [subKey, subVal] of Object.entries(val)) {
              if (typeof subVal === 'object') {
                partEl.animation[subKey] = { ...(partEl.animation[subKey] || {}), ...subVal }
              } else {
                partEl.animation[subKey] = subVal
              }
            }
          } else {
            partEl[key] = { ...(partEl[key] || {}), ...val }
          }
        }
      } else {
        partEl[key] = val
      }
    }
  }

  function getPartElement(partId, elementId) {
    const globalEl = getElementById(elementId)
    if (!globalEl) return null
    const part = timeline.parts.find(p => p.id === partId)
    const overrides = part?.elementConfigs?.[elementId]
    if (!overrides) return globalEl
    return {
      ...globalEl,
      ...overrides,
      position: { ...globalEl.position, ...overrides.position },
      size: { ...globalEl.size, ...overrides.size },
      style: { ...globalEl.style, ...overrides.style },
    }
  }


  function setPartVisibility(partId, elementId, visible) {
    const part = timeline.parts.find(p => p.id === partId)
    if (!part) return
    if (!part.elementVisibility) part.elementVisibility = {}
    part.elementVisibility[elementId] = visible
  }

  function getVisibleElements(partId) {
    const part = timeline.parts.find(p => p.id === partId)
    if (!part) return []
    return timeline.elements.filter(el =>
      el.visible !== false && part.elementVisibility?.[el.id]
    )
  }

  // ── Style Theme ──

  function applyStyleTheme(styleId, partId = null) {
    const theme = STYLE_THEMES[styleId]
    if (!theme) return

    if (partId) {
      const part = timeline.parts.find(p => p.id === partId)
      if (part) part.styleId = styleId
    } else {
      timeline.styleId = styleId
    }
    // Always update global styleId and element colors for visual preview
    timeline.styleId = styleId
    applyThemeToElements(styleId, timeline.elements)
  }

  function setGlobalFont(fontKey) {
    timeline.defaultFont = fontKey
    for (const el of timeline.elements) {
      if (el.style) el.style.fontFamily = fontKey
    }
  }

  // ── Serialization ──

  function toJSON() {
    return JSON.parse(JSON.stringify(timeline))
  }

  function fromJSON(json) {
    Object.assign(timeline, json)
    // Ensure element IDs are tracked for uid counter
    for (const el of timeline.elements) {
      const match = el.id.match(/_(\d+)$/)
      if (match) _idCounter = Math.max(_idCounter, parseInt(match[1]))
    }
    for (const p of timeline.parts) {
      const match = p.id.match(/_(\d+)$/)
      if (match) _idCounter = Math.max(_idCounter, parseInt(match[1]))
    }
  }

  /**
   * Migrate from legacy Create.vue format to Timeline JSON.
   * Converts boxLayouts + style + parts + styleId + animation.
   */
  function fromLegacy(cfg) {
    const tl = createDefaultTimeline({
      sourceLang: cfg.source_lang || cfg.srcLang || 'en',
      targetLang: cfg.target_lang || cfg.tgtLang || 'zh',
      styleId: cfg.style_id || cfg.styleId || 'neon_cyberpunk',
    })

    // Map resolution
    if (cfg.resolution === '720p') {
      tl.resolution = { width: 1280, height: 720 }
    }

    tl.numWords = cfg.num_words ?? cfg.numWords ?? 3
    tl.numExprs = cfg.num_expressions ?? cfg.numExprs ?? 2

    // Map boxLayouts → elements
    const boxKeyMap = { subtitle: 'subtitle', wordbox: 'wordbox', expressionbox: 'exprbox', exprbox: 'exprbox' }
    if (cfg.boxLayouts) {
      for (const [bk, bl] of Object.entries(cfg.boxLayouts)) {
        const elType = boxKeyMap[bk] || bk
        const el = tl.elements.find(e => e.type === elType)
        if (el && bl) {
          el.position = { x: (bl.x || 0) / 100, y: (bl.y || 0) / 100 }
          el.size = { w: (bl.w || 10) / 100, h: (bl.h || 10) / 100 }
          if (bl.font_scale) el.style.fontScale = bl.font_scale
        }
      }
    }

    // Map style colors
    if (cfg.style) {
      const s = cfg.style
      const sub = tl.elements.find(e => e.type === 'subtitle')
      if (sub) {
        if (s.subtitle_bg_color) sub.style.bgColor = s.subtitle_bg_color
        if (s.subtitle_text_color) sub.style.textColor = s.subtitle_text_color
        if (s.subtitle_cn_color) sub.style.translationColor = s.subtitle_cn_color
        if (s.subtitle_bg_style) sub.style.bgStyle = s.subtitle_bg_style
        if (s.font_family) sub.style.fontFamily = s.font_family
      }

      const wb = tl.elements.find(e => e.type === 'wordbox')
      if (wb) {
        if (s.wordbox_bg) wb.style.bgColor = s.wordbox_bg
        if (s.wordbox_word_color) wb.style.wordColor = s.wordbox_word_color
        if (s.wordbox_phonetic_color) wb.style.phoneticColor = s.wordbox_phonetic_color
        if (s.wordbox_trans_color) wb.style.translationColor = s.wordbox_trans_color
        if (s.font_family) wb.style.fontFamily = s.font_family
      }

      const eb = tl.elements.find(e => e.type === 'exprbox')
      if (eb) {
        if (s.exprbox_bg) eb.style.bgColor = s.exprbox_bg
        if (s.exprbox_en_color) eb.style.expressionColor = s.exprbox_en_color
        if (s.exprbox_cn_color) eb.style.translationColor = s.exprbox_cn_color
        if (s.font_family) eb.style.fontFamily = s.font_family
      }
    }

    // Map parts
    if (cfg.parts && cfg.parts.length > 0) {
      tl.parts = cfg.parts.map(p => {
        const vis = {}
        const boxTypes = p.boxes || []
        for (const el of tl.elements) {
          const boxKey = el.type === 'exprbox' ? 'expressionbox' : el.type
          vis[el.id] = boxTypes.includes(boxKey) || boxTypes.includes(el.type)
        }
        return {
          id: p.id || uid('p'),
          repeat: p.repeat || 1,
          speed: p.speed || 1.0,
          elementVisibility: vis,
        }
      })
    }

    // Apply animation
    const anim = cfg.animation || 'fade'
    for (const el of tl.elements) {
      if (['subtitle', 'wordbox', 'exprbox'].includes(el.type) && el.animation) {
        el.animation.enter.type = anim
      }
    }

    // Apply theme (will set colors from theme, overriding above)
    if (cfg.style_id || cfg.styleId) {
      applyThemeToElements(cfg.style_id || cfg.styleId, tl.elements)
    }

    // Load into reactive state
    fromJSON(tl)
  }

  // ── Preview Content ──

  const previewContent = computed(() => {
    return getPreviewContent(
      timeline.sourceLang,
      timeline.targetLang,
      timeline.numWords,
      timeline.numExprs
    )
  })

  return {
    timeline,
    elements,
    parts,
    resolution,
    previewContent,

    // Element CRUD
    getElementById,
    addElement,
    updateElement,
    removeElement,

    // Part CRUD
    addPart,
    removePart,
    copyPart,
    updatePart,
    updatePartElement,
    getPartElement,
    setPartVisibility,
    getVisibleElements,

    // Style
    applyStyleTheme,
    setGlobalFont,

    // Serialization
    toJSON,
    fromJSON,
    fromLegacy,
  }
}
