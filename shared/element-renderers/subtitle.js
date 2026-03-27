/**
 * Subtitle Element Renderer — creates Konva nodes for subtitle overlay
 * Shows source language text + translation
 *
 * Content area (innerW/innerH) uses ACTUAL box dimensions so resizing the box
 * changes the text area.  Font sizes are still anchored to canvas height so
 * text stays readable.  fontScale slider now has a visible effect because
 * adaptiveFontSize no longer caps against a tiny fixed refH.
 */
import { getFontFamily } from '../font-registry.js'
import { adaptiveFontSize } from '../text-layout.js'

export function createSubtitleNodes(element, content, containerSize) {
  const { width: cw, height: ch } = containerSize
  const style = element.style || {}
  const pos = element.position || { x: 0.05, y: 0.76 }
  const size = element.size || { w: 0.9, h: 0.14 }

  // Actual pixel position/size (used for group placement and clip)
  const x = pos.x * cw
  const y = pos.y * ch
  const w = size.w * cw
  const h = size.h * ch

  const fontFamily = getFontFamily(style.fontFamily || 'system')
  const fontScale = style.fontScale || 1.0
  const borderRadius = style.borderRadius ?? 8
  const padding = Math.max(8, h * 0.10)   // use ACTUAL box height

  const srcText = content?.text || 'Source language sentence goes here.'
  const tgtText = content?.translation || '翻译文本显示在这里'

  const innerW = w - padding * 2   // use ACTUAL box width
  const innerH = h - padding * 2   // use ACTUAL box height

  // Font sizes based on fixed reference, not element size — large enough to be readable
  const baseSrcSize = Math.max(16, ch * 0.045)
  const baseTgtSize = Math.max(13, ch * 0.036)
  const srcFontSize = adaptiveFontSize(srcText, baseSrcSize, innerW, innerH * 0.52, fontScale)
  const tgtFontSize = adaptiveFontSize(tgtText, baseTgtSize, innerW, innerH * 0.42, fontScale * 0.85)

  const srcY = padding
  const tgtY = padding + innerH * 0.54

  const nodes = []

  // Background rect — fills actual box size; bgOpacity overrides rgba alpha
  const bgFill = (() => {
    const col = style.bgColor || 'rgba(0,0,0,0.78)'
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

  // Source text
  nodes.push({
    type: 'Text',
    config: {
      x: padding, y: srcY,
      width: innerW,
      height: innerH * 0.50,
      text: srcText,
      fontSize: srcFontSize,
      fontFamily,
      fontStyle: 'bold',
      fill: style.textColor || '#ffffff',
      align: 'center',
      verticalAlign: 'middle',
      wrap: 'word',
      lineHeight: 1.3,
    },
  })

  // Translation text (no divider line)
  nodes.push({
    type: 'Text',
    config: {
      x: padding, y: tgtY,
      width: innerW,
      height: innerH * 0.44,
      text: tgtText,
      fontSize: tgtFontSize,
      fontFamily,
      fill: style.translationColor || '#94a3b8',
      align: 'center',
      verticalAlign: 'top',
      wrap: 'word',
      lineHeight: 1.3,
    },
  })

  return { x, y, w, h, nodes }
}
