/**
 * Expression Box Element Renderer — creates Konva nodes for expressions overlay
 * Shows useful expressions with translation.
 *
 * Content area uses ACTUAL box dimensions so resizing the box changes how many
 * items fit and how wide the text area is.  Font sizes are still anchored to
 * canvas height so they stay readable regardless of box size.
 */
import { getFontFamily } from '../font-registry.js'

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

  // Fixed single-line row height (no wrapping → no overlap)
  const rowH = exprFontSize + transSize + 14
  let curY = padding

  expressions.forEach((item) => {
    if (curY + rowH > h - 4) return   // small buffer for clip boundary; no longer requires a full padding gap at bottom

    // Expression (bold, single line with ellipsis to prevent overlap)
    nodes.push({
      type: 'Text',
      config: {
        x: padding, y: curY,
        width: innerW,
        text: item.english || item.expression || '',
        fontSize: exprFontSize,
        fontFamily,
        fontStyle: 'bold',
        fill: style.expressionColor || style.accentColor || '#f472b6',
        wrap: 'none',
        ellipsis: true,
      },
    })
    curY += exprFontSize + 4

    // Translation (single line with ellipsis)
    if (item.chinese || item.translation) {
      nodes.push({
        type: 'Text',
        config: {
          x: padding + 4, y: curY,
          width: innerW - 4,
          text: `› ${item.chinese || item.translation || ''}`,
          fontSize: transSize,
          fontFamily,
          fill: style.translationColor || '#94a3b8',
          wrap: 'none',
          ellipsis: true,
        },
      })
      curY += transSize + 4
    }

    // Gap between expressions
    curY += rowGap
  })

  return { x, y, w, h, nodes }
}
