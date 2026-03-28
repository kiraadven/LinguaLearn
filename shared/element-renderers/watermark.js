/**
 * Watermark Element Renderer — creates Konva nodes for text watermark
 *
 * Opacity and rotation are applied on the Konva group (not the text node).
 * Keep geometry strict to element.size so server output matches saved preset.
 */
import { getFontFamily } from '../font-registry.js'

export function createWatermarkNodes(element, _content, containerSize) {
  const { width: cw, height: ch } = containerSize
  const style = element.style || {}
  const pos = element.position || { x: 0.85, y: 0.95 }
  const size = element.size || { w: 0.14, h: 0.04 }

  const x = pos.x * cw
  const y = pos.y * ch

  const fontFamily = getFontFamily(style.fontFamily || 'system')
  const text = style.text || 'LinguaLearn'
  const fontSize = style.fontSize || Math.max(12, ch * 0.02)
  const color = style.color || '#ffffff'
  const strokeColor = style.strokeColor || 'rgba(0,0,0,0.3)'
  const strokeWidth = style.strokeWidth || 0

  // Strict box size from timeline preset (percentage of canvas).
  const w = Math.max(1, size.w * cw)
  const h = Math.max(1, size.h * ch)

  const nodes = []

  nodes.push({
    type: 'Text',
    config: {
      x: 0, y: 0,
      width: w,
      height: h,
      text,
      fontSize,
      fontFamily,
      fill: color,
      stroke: strokeWidth > 0 ? strokeColor : undefined,
      strokeWidth: strokeWidth > 0 ? strokeWidth : undefined,
      align: 'center',
      verticalAlign: 'middle',
      wrap: 'none',
      ellipsis: true,
    },
  })

  return { x, y, w, h, nodes }
}
