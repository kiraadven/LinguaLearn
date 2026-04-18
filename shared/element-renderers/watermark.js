/**
 * Watermark Element Renderer — creates Konva nodes for text watermark
 *
 * Opacity and rotation are applied on the Konva group (not the text node).
 * Keep geometry strict to element.size so server output matches saved preset.
 */
import { getFontFamily } from '../font-registry.js'

function estimateCharWidthFactor(text) {
  if (!text) return 0.56
  const cjkRe = /[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]/
  return cjkRe.test(text) ? 1.0 : 0.56
}

function fitFontSizeToBox(text, requestedFontSize, boxW, boxH) {
  const safeText = String(text || '')
  const req = Math.max(1, Number(requestedFontSize || 1))
  const widthFactor = estimateCharWidthFactor(safeText)
  const textLen = Math.max(1, safeText.length)

  // width ≈ fontSize * widthFactor * textLen
  const maxByWidth = Math.max(8, (boxW - 4) / (widthFactor * textLen))
  // lineHeight = 1.3 * fontSize
  const maxByHeight = Math.max(8, (boxH - 4) / 1.3)

  return Math.max(8, Math.min(req, maxByWidth, maxByHeight))
}

export function createWatermarkNodes(element, _content, containerSize) {
  const { width: cw, height: ch } = containerSize
  const style = element.style || {}
  const pos = element.position || { x: 0.85, y: 0.95 }
  const size = element.size || { w: 0.14, h: 0.04 }

  const x = pos.x * cw
  const y = pos.y * ch

  const fontFamily = getFontFamily(style.fontFamily || 'system')
  const text = style.text || 'LinguaLearn'
  const requestedFontSize = style.fontSize || Math.max(12, ch * 0.02)
  const color = style.color || '#ffffff'
  const strokeColor = style.strokeColor || 'rgba(0,0,0,0.3)'
  const strokeWidth = style.strokeWidth || 0

  // Strict box size from timeline preset (percentage of canvas).
  const w = Math.max(1, size.w * cw)
  const h = Math.max(1, size.h * ch)
  const fontSize = fitFontSizeToBox(text, requestedFontSize, w, h)

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
      ellipsis: false,
    },
  })

  return { x, y, w, h, nodes }
}
