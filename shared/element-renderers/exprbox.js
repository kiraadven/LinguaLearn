/**
 * Expression Box Element Renderer — creates Konva nodes for expressions overlay
 * Shows useful expressions with translation.
 *
 * Content area uses ACTUAL box dimensions so resizing the box changes how many
 * items fit and how wide the text area is.  Font sizes are still anchored to
 * canvas height so they stay readable regardless of box size.
 */
import { getFontFamily } from '../font-registry.js'
import { estimateTextLayout, isCJK } from '../text-layout.js'

export function createExprboxNodes(element, content, containerSize) {
  const { width: cw, height: ch } = containerSize
  const style = element.style || {}
  const pos = element.position || { x: 0.005, y: 0.005 }
  const size = element.size || { w: 0.245, h: 0.55 }

  // Actual pixel coords for group placement
  const x = pos.x * cw
  const y = pos.y * ch
  const w = size.w * cw
  const h = size.h * ch

  const fontFamily = getFontFamily(style.fontFamily || 'system')
  const fontScale = style.fontScale || 1.0
  const borderRadius = style.borderRadius ?? 10
  const padding = Math.max(8, w * 0.07)   // use ACTUAL box width
  const innerW = w - padding * 2           // use ACTUAL box width
  // Entry spacing (user-configurable). Keep backward compatibility with legacy lineHeight.
  const rowSpacing = style.wordSpacing ?? style.lineHeight ?? 1.0
  const rowGap = Math.max(0, Math.round(rowSpacing * 7))   // gap between expression entries

  const expressions = content?.expressions || []

  const nodes = []

  // Background — fills actual box size; bgOpacity overrides rgba alpha
  const bgFill = (() => {
    const col = style.bgColor || 'rgba(10,5,30,0.88)'
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
  const exprFontSize  = Math.max(14, ch * 0.040) * fontScale
  const transSize     = Math.max(12, ch * 0.033) * fontScale

  const exprLineHeight = 1.22
  const transLineHeight = 1.18
  const minRowPad = 4
  let curY = padding

  expressions.forEach((item) => {
    const exprText = item.english || item.expression || ''
    const transTextRaw = item.chinese || item.translation || ''
    const transText = transTextRaw ? `› ${transTextRaw}` : ''

    // Measure wrapped heights first so Chinese always starts AFTER English block.
    const exprLayout = estimateTextLayout(exprText, exprFontSize, innerW)
    const exprLines = Math.max(1, Math.min(3, exprLayout.lineCount))
    const exprH = exprLines * exprFontSize * exprLineHeight

    let transH = 0
    let transLines = 0
    if (transText) {
      const transLayout = estimateTextLayout(transText, transSize, innerW - 4)
      transLines = Math.max(1, Math.min(3, transLayout.lineCount))
      transH = transLines * transSize * transLineHeight
    }

    const rowH = exprH + (transH > 0 ? (minRowPad + transH) : 0)
    if (curY + rowH > h - 4) return   // small buffer for clip boundary

    // Expression (bold, single line with ellipsis to prevent overlap)
    nodes.push({
      type: 'Text',
      config: {
        x: padding, y: curY,
        width: innerW,
        text: exprText,
        fontSize: exprFontSize,
        fontFamily,
        fontStyle: 'bold',
        fill: style.expressionColor || style.accentColor || '#f472b6',
        wrap: isCJK(exprText) ? 'char' : 'word',
        lineHeight: exprLineHeight,
      },
    })
    curY += exprH + minRowPad

    // Translation block starts below English wrapped block to avoid overlap.
    if (transText) {
      nodes.push({
        type: 'Text',
        config: {
          x: padding + 4, y: curY,
          width: innerW - 4,
          text: transText,
          fontSize: transSize,
          fontFamily,
          fill: style.translationColor || '#94a3b8',
          wrap: isCJK(transTextRaw) ? 'char' : 'word',
          lineHeight: transLineHeight,
        },
      })
      curY += transH
    }

    // Gap between expressions
    curY += rowGap
  })

  return { x, y, w, h, nodes }
}
