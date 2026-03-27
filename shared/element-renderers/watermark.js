/**
 * Watermark Element Renderer — creates Konva nodes for text watermark
 *
 * Opacity and rotation are applied on the Konva group (not the text node).
 * Width auto-expands so long text is never clipped.
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

  // Width: auto-expand to fit text content (estimate: ~0.62 * fontSize per char + padding)
  const estimatedTextW = text.length * fontSize * 0.62 + 20
  const minW = size.w * cw
  const w = Math.max(minW, estimatedTextW)

  // Height: always fit the font size so text is never clipped
  const h = Math.max(size.h * ch, fontSize + 10)

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
    },
  })

  return { x, y, w, h, nodes }
}
