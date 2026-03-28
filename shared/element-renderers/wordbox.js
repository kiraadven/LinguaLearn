/**
 * Wordbox Element Renderer — creates Konva nodes for vocabulary box
 * Shows key words with phonetic and translation.
 *
 * Layout uses FIXED reference dimensions so font sizes don't change when the box is resized.
 * The group is clipped to actual element size.
 */
import { getFontFamily } from '../font-registry.js'

export function createWordboxNodes(element, content, containerSize) {
  const { width: cw, height: ch } = containerSize
  const style = element.style || {}
  const pos = element.position || { x: 0.75, y: 0.005 }
  const size = element.size || { w: 0.245, h: 0.65 }

  // Actual pixel coords for group placement
  const x = pos.x * cw
  const y = pos.y * ch
  const w = size.w * cw
  const h = size.h * ch

  const fontFamily = getFontFamily(style.fontFamily || 'system')
  const fontScale = style.fontScale || 1.0
  const borderRadius = style.borderRadius ?? 10
  const padding = Math.max(8, w * 0.07)
  const innerW = w - padding * 2   // use ACTUAL box width for text area
  // Word/entry spacing (user-configurable). Keep backward compatibility with legacy lineHeight.
  const rowSpacing = style.wordSpacing ?? style.lineHeight ?? 1.0
  const rowGap = Math.max(0, Math.round(rowSpacing * 8))   // gap between word entries

  const words = content?.words || []

  const nodes = []

  // Background — fills actual box size; bgOpacity overrides rgba alpha
  const bgFill = (() => {
    const col = style.bgColor || 'rgba(20,10,50,0.88)'
    const op = style.bgOpacity
    if (op !== undefined) {
      const m = col.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
      return { fill: m ? `rgb(${m[1]},${m[2]},${m[3]})` : col, opacity: op }
    }
    return { fill: col, opacity: undefined }
  })()
  nodes.push({
    type: 'Rect',
    config: {
      x: 0, y: 0,
      width: w, height: h,
      fill: bgFill.fill,
      ...(bgFill.opacity !== undefined ? { opacity: bgFill.opacity } : {}),
      cornerRadius: borderRadius,
    },
  })

  // Font sizes based on reference height — large enough to be readable
  const wordFontSize  = Math.max(15, ch * 0.042) * fontScale
  const phoneticSize  = Math.max(11, ch * 0.030) * fontScale
  const transSize     = Math.max(12, ch * 0.034) * fontScale

  // Row height = word + phonetic + translation + gap
  const rowH = wordFontSize + phoneticSize + transSize + 14
  let curY = padding

  words.forEach((item) => {
    if (curY + rowH > h - 4) return  // small buffer for clip boundary; no longer requires a full padding gap at bottom

    // Word (bold, accent color)
    nodes.push({
      type: 'Text',
      config: {
        x: padding, y: curY,
        width: innerW,
        text: item.word || '',
        fontSize: wordFontSize,
        fontFamily,
        fontStyle: 'bold',
        fill: style.wordColor || style.accentColor || '#a78bfa',
      },
    })
    curY += wordFontSize + 2

    // Phonetic (small, muted italic)
    if (item.phonetic) {
      nodes.push({
        type: 'Text',
        config: {
          x: padding, y: curY,
          width: innerW,
          text: item.phonetic,
          fontSize: phoneticSize,
          fontFamily,
          fontStyle: 'italic',
          fill: style.phoneticColor || '#94a3b8',
        },
      })
      curY += phoneticSize + 2
    }

    // Translation
    if (item.translation) {
      nodes.push({
        type: 'Text',
        config: {
          x: padding, y: curY,
          width: innerW,
          text: item.translation,
          fontSize: transSize,
          fontFamily,
          fill: style.translationColor || '#f1f5f9',
        },
      })
      curY += transSize
    }

    // Gap between words
    curY += rowGap
  })

  return { x, y, w, h, nodes }
}
