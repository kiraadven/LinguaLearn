#!/usr/bin/env node
/**
 * Konva Render Worker — Node.js sidecar for server-side PNG rendering
 *
 * Reads Timeline JSON + sentences data from stdin, renders each element
 * as a transparent PNG using node-canvas (same shared renderers as browser).
 *
 * The shared renderers output Konva-compatible config objects. This worker
 * interprets those configs and draws them directly on node-canvas, avoiding
 * the need for a full Konva Stage (which requires DOM in some versions).
 *
 * Usage:
 *   echo '{"timeline":{...},"sentences":[...]}' | node konva_render_worker.mjs /output/dir
 *
 * Output: per-element PNGs + result JSON on stdout
 */

import { createCanvas, loadImage, registerFont as canvasRegisterFont } from 'canvas'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sharedDir = path.resolve(__dirname, '..', 'shared')

// Import shared renderers
const { renderElement } = await import(path.join(sharedDir, 'konva-renderer.js'))
const { registerFonts, FONT_FILES } = await import(path.join(sharedDir, 'font-registry.js'))

/**
 * Read all stdin as a string
 */
function readStdin() {
  return new Promise((resolve, reject) => {
    let data = ''
    process.stdin.setEncoding('utf-8')
    process.stdin.on('data', chunk => { data += chunk })
    process.stdin.on('end', () => resolve(data))
    process.stdin.on('error', reject)
  })
}

/**
 * Parse an rgba color string to components.
 * Handles: 'rgba(r,g,b,a)', 'rgb(r,g,b)', '#rrggbb', '#rgb', named colors
 */
function parseColor(colorStr) {
  if (!colorStr) return { r: 0, g: 0, b: 0, a: 1 }

  // rgba(r,g,b,a)
  const rgbaMatch = colorStr.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)/)
  if (rgbaMatch) {
    return {
      r: parseInt(rgbaMatch[1]),
      g: parseInt(rgbaMatch[2]),
      b: parseInt(rgbaMatch[3]),
      a: rgbaMatch[4] !== undefined ? parseFloat(rgbaMatch[4]) : 1,
    }
  }

  // Hex colors
  if (colorStr.startsWith('#')) {
    let hex = colorStr.slice(1)
    if (hex.length === 3) hex = hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2]
    return {
      r: parseInt(hex.slice(0,2), 16),
      g: parseInt(hex.slice(2,4), 16),
      b: parseInt(hex.slice(4,6), 16),
      a: 1,
    }
  }

  // Fallback
  return { r: 255, g: 255, b: 255, a: 1 }
}

/**
 * Draw a rounded rectangle on canvas context
 */
function roundedRect(ctx, x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + w - r, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + r)
  ctx.lineTo(x + w, y + h - r)
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
  ctx.lineTo(x + r, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - r)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
  ctx.closePath()
}

/**
 * Render Konva node configs to a PNG buffer using node-canvas.
 *
 * Supports: Rect (with cornerRadius), Text (with wrapping), Line
 *
 * @param {Array} nodes - Array of { type, config } Konva node configs
 * @param {number} w - Width in pixels
 * @param {number} h - Height in pixels
 * @returns {Buffer} PNG buffer
 */
function renderNodesToPNG(nodes, w, h) {
  const canvas = createCanvas(Math.ceil(w), Math.ceil(h))
  const ctx = canvas.getContext('2d')

  // Transparent background
  ctx.clearRect(0, 0, w, h)

  for (const nodeConf of nodes) {
    const c = nodeConf.config || {}
    const globalAlpha = c.opacity !== undefined ? c.opacity : 1

    ctx.save()
    ctx.globalAlpha = globalAlpha

    switch (nodeConf.type) {
      case 'Rect': {
        const rx = c.x || 0
        const ry = c.y || 0
        const rw = c.width || 0
        const rh = c.height || 0
        const cr = c.cornerRadius || 0

        if (c.fill) {
          const color = parseColor(c.fill)
          ctx.fillStyle = `rgba(${color.r},${color.g},${color.b},${color.a})`
          if (cr > 0) {
            roundedRect(ctx, rx, ry, rw, rh, cr)
            ctx.fill()
          } else {
            ctx.fillRect(rx, ry, rw, rh)
          }
        }
        if (c.stroke) {
          ctx.strokeStyle = c.stroke
          ctx.lineWidth = c.strokeWidth || 1
          if (cr > 0) {
            roundedRect(ctx, rx, ry, rw, rh, cr)
            ctx.stroke()
          } else {
            ctx.strokeRect(rx, ry, rw, rh)
          }
        }
        break
      }

      case 'Text': {
        drawTextNode(ctx, c)
        break
      }

      case 'Line': {
        const points = c.points || []
        if (points.length >= 4) {
          ctx.beginPath()
          ctx.moveTo(points[0], points[1])
          for (let pi = 2; pi < points.length; pi += 2) {
            ctx.lineTo(points[pi], points[pi + 1])
          }
          if (c.stroke) {
            ctx.strokeStyle = c.stroke
            ctx.lineWidth = c.strokeWidth || 1
            ctx.stroke()
          }
        }
        break
      }

      default:
        // console.error(`[render] Unknown node type: ${nodeConf.type}`)
        break
    }

    ctx.restore()
  }

  return canvas.toBuffer('image/png')
}

/**
 * Render Konva node configs to a canvas object (not buffer).
 * Used when we need post-transforms (rotation/opacity) before encoding PNG.
 */
function renderNodesToCanvas(nodes, w, h) {
  const canvas = createCanvas(Math.ceil(w), Math.ceil(h))
  const ctx = canvas.getContext('2d')

  ctx.clearRect(0, 0, w, h)

  for (const nodeConf of nodes) {
    const c = nodeConf.config || {}
    const globalAlpha = c.opacity !== undefined ? c.opacity : 1

    ctx.save()
    ctx.globalAlpha = globalAlpha

    switch (nodeConf.type) {
      case 'Rect': {
        const rx = c.x || 0
        const ry = c.y || 0
        const rw = c.width || 0
        const rh = c.height || 0
        const cr = c.cornerRadius || 0

        if (c.fill) {
          const color = parseColor(c.fill)
          ctx.fillStyle = `rgba(${color.r},${color.g},${color.b},${color.a})`
          if (cr > 0) {
            roundedRect(ctx, rx, ry, rw, rh, cr)
            ctx.fill()
          } else {
            ctx.fillRect(rx, ry, rw, rh)
          }
        }
        if (c.stroke) {
          ctx.strokeStyle = c.stroke
          ctx.lineWidth = c.strokeWidth || 1
          if (cr > 0) {
            roundedRect(ctx, rx, ry, rw, rh, cr)
            ctx.stroke()
          } else {
            ctx.strokeRect(rx, ry, rw, rh)
          }
        }
        break
      }

      case 'Text': {
        drawTextNode(ctx, c)
        break
      }

      case 'Line': {
        const points = c.points || []
        if (points.length >= 4) {
          ctx.beginPath()
          ctx.moveTo(points[0], points[1])
          for (let pi = 2; pi < points.length; pi += 2) {
            ctx.lineTo(points[pi], points[pi + 1])
          }
          if (c.stroke) {
            ctx.strokeStyle = c.stroke
            ctx.lineWidth = c.strokeWidth || 1
            ctx.stroke()
          }
        }
        break
      }
      default:
        break
    }

    ctx.restore()
  }

  return canvas
}

function drawTextNode(ctx, c) {
  const tx = c.x || 0
  const ty = c.y || 0
  const tw = c.width || 9999
  const th = c.height || 9999
  const text = c.text || ''
  const fontSize = c.fontSize || 14
  const fontFamily = c.fontFamily || 'sans-serif'
  const fontStyle = c.fontStyle || 'normal' // 'bold', 'italic', etc.
  const fill = c.fill || '#ffffff'
  const align = c.align || 'left'
  const lineHeight = (c.lineHeight || 1.3) * fontSize
  const verticalAlign = c.verticalAlign || 'top'
  const wrapMode = (c.wrap || 'word').toLowerCase()
  const useEllipsis = !!c.ellipsis

  let normalizedFamily = normalizeCanvasFontFamily(fontFamily)
  if (/\s/.test(normalizedFamily) && !/^['"].*['"]$/.test(normalizedFamily)) {
    normalizedFamily = `'${normalizedFamily}'`
  }

  let fontStr = `${fontSize}px ${normalizedFamily}`
  if (fontStyle === 'bold') fontStr = `bold ${fontStr}`
  else if (fontStyle === 'italic') fontStr = `italic ${fontStr}`
  else if (fontStyle === 'bold italic') fontStr = `bold italic ${fontStr}`

  ctx.font = fontStr
  // node-canvas falls back to 10px sans-serif on invalid font strings.
  // Keep requested size stable even when family fallback happens.
  if (!String(ctx.font || '').includes(`${fontSize}px`)) {
    let fallback = `${fontSize}px sans-serif`
    if (fontStyle === 'bold') fallback = `bold ${fallback}`
    else if (fontStyle === 'italic') fallback = `italic ${fallback}`
    else if (fontStyle === 'bold italic') fallback = `bold italic ${fallback}`
    ctx.font = fallback
  }
  ctx.fillStyle = fill
  ctx.textBaseline = 'top'

  const lines = layoutTextLines(ctx, text, tw, wrapMode, useEllipsis)
  const totalTextHeight = lines.length * lineHeight

  let yOffset = 0
  if (verticalAlign === 'middle') {
    yOffset = Math.max(0, (th - totalTextHeight) / 2)
  } else if (verticalAlign === 'bottom') {
    yOffset = Math.max(0, th - totalTextHeight)
  }

  for (let li = 0; li < lines.length; li++) {
    const lineY = ty + yOffset + li * lineHeight
    if (lineY > ty + th) break // Clip

    let lineX = tx
    if (align === 'center') {
      const metrics = ctx.measureText(lines[li])
      lineX = tx + (tw - metrics.width) / 2
    } else if (align === 'right') {
      const metrics = ctx.measureText(lines[li])
      lineX = tx + tw - metrics.width
    }

    ctx.fillText(lines[li], lineX, lineY)
  }
}

function normalizeCanvasFontFamily(family) {
  const raw = String(family || '').trim()
  if (!raw) return 'sans-serif'
  const candidates = raw
    .split(',')
    .map(s => s.trim().replace(/^['"]|['"]$/g, ''))
    .filter(Boolean)
  if (!candidates.length) return 'sans-serif'

  for (const fam of candidates) {
    const k = fam.toLowerCase()
    if (k === 'system-ui' || k === '-apple-system' || k === 'blinkmacsystemfont') continue
    return fam
  }
  return 'sans-serif'
}

/**
 * Apply element-level transform used by Konva Group (rotation/opacity) to a rendered canvas.
 * Rotation pivot follows Group default: top-left origin (0,0).
 *
 * Returns transformed canvas + offset delta to apply to overlay position.
 */
function applyElementGroupTransform(baseCanvas, rotationDeg = 0, opacity = 1) {
  const w = baseCanvas.width
  const h = baseCanvas.height
  const rot = Number(rotationDeg || 0)
  const alpha = Number(opacity ?? 1)

  // Fast path: no transform needed
  if (Math.abs(rot) < 1e-6 && Math.abs(alpha - 1) < 1e-6) {
    return { canvas: baseCanvas, dx: 0, dy: 0 }
  }

  // Opacity-only path
  if (Math.abs(rot) < 1e-6) {
    const out = createCanvas(w, h)
    const ctx = out.getContext('2d')
    ctx.globalAlpha = alpha
    ctx.drawImage(baseCanvas, 0, 0)
    return { canvas: out, dx: 0, dy: 0 }
  }

  const rad = rot * Math.PI / 180
  const cos = Math.cos(rad)
  const sin = Math.sin(rad)

  // Rotate the four corners around origin (top-left) to compute AABB.
  const p0 = { x: 0,     y: 0 }
  const p1 = { x: w*cos, y: w*sin }
  const p2 = { x: -h*sin,y: h*cos }
  const p3 = { x: w*cos - h*sin, y: w*sin + h*cos }

  const minX = Math.min(p0.x, p1.x, p2.x, p3.x)
  const minY = Math.min(p0.y, p1.y, p2.y, p3.y)
  const maxX = Math.max(p0.x, p1.x, p2.x, p3.x)
  const maxY = Math.max(p0.y, p1.y, p2.y, p3.y)

  const outW = Math.max(1, Math.ceil(maxX - minX))
  const outH = Math.max(1, Math.ceil(maxY - minY))
  const out = createCanvas(outW, outH)
  const ctx = out.getContext('2d')

  ctx.globalAlpha = alpha
  // x' = cos*x - sin*y - minX
  // y' = sin*x + cos*y - minY
  ctx.setTransform(cos, sin, -sin, cos, -minX, -minY)
  ctx.drawImage(baseCanvas, 0, 0)
  ctx.setTransform(1, 0, 0, 1, 0, 0)

  // Overlay anchor must shift by rotated bounds min corner.
  return { canvas: out, dx: minX, dy: minY }
}

/**
 * Simple word-wrapping for canvas text
 */
function wrapText(ctx, text, maxWidth) {
  if (!text) return ['']
  const words = text.split(/(\s+)/)
  const lines = []
  let currentLine = ''

  for (const word of words) {
    const testLine = currentLine + word
    const metrics = ctx.measureText(testLine)
    if (metrics.width > maxWidth && currentLine.length > 0) {
      lines.push(currentLine.trimEnd())
      currentLine = word.trimStart()
      // Handle long token with no breakpoints
      if (ctx.measureText(currentLine).width > maxWidth) {
        const broken = wrapTextByChar(ctx, currentLine, maxWidth)
        lines.push(...broken.slice(0, -1))
        currentLine = broken[broken.length - 1] || ''
      }
    } else {
      currentLine = testLine
    }
  }
  if (currentLine.trim().length || lines.length === 0) {
    lines.push(currentLine.trimEnd())
  }
  return lines.length > 0 ? lines : ['']
}

function wrapTextByChar(ctx, text, maxWidth) {
  if (!text) return ['']
  const lines = []
  let cur = ''
  for (const ch of Array.from(text)) {
    const test = cur + ch
    if (ctx.measureText(test).width > maxWidth && cur.length > 0) {
      lines.push(cur)
      cur = ch
    } else {
      cur = test
    }
  }
  if (cur.length || lines.length === 0) lines.push(cur)
  return lines
}

function truncateWithEllipsis(ctx, text, maxWidth) {
  const ellipsis = '…'
  if (maxWidth <= 0) return ''
  if (ctx.measureText(text).width <= maxWidth) return text
  if (ctx.measureText(ellipsis).width > maxWidth) return ''

  let out = ''
  for (const ch of Array.from(text)) {
    const next = out + ch
    if (ctx.measureText(next + ellipsis).width > maxWidth) break
    out = next
  }
  return out + ellipsis
}

function layoutTextLines(ctx, text, maxWidth, wrapMode = 'word', ellipsis = false) {
  if (!text) return ['']
  if (wrapMode === 'none') {
    const line = ellipsis ? truncateWithEllipsis(ctx, String(text), maxWidth) : String(text)
    return [line]
  }
  if (wrapMode === 'char') {
    return wrapTextByChar(ctx, String(text), maxWidth)
  }
  return wrapText(ctx, String(text), maxWidth)
}

/**
 * Build content object from sentence data for a specific element type.
 */
function buildContent(sentence, elementType) {
  const srcText = sentence.original_text || ''
  const tgtText = sentence.chinese_translation || sentence.translated_text || ''
  const words = sentence.key_words || []
  const exprs = sentence.useful_expressions || []

  switch (elementType) {
    case 'subtitle':
      return { text: srcText, translation: tgtText }
    case 'wordbox':
      return { words }
    case 'exprbox':
      return { expressions: exprs }
    case 'watermark':
    case 'sticker':
      return {}
    default:
      return { text: srcText, translation: tgtText, words, expressions: exprs }
  }
}

/**
 * Merge global element config with part-level overrides.
 */
function mergeElement(globalElement, override = {}) {
  return {
    ...globalElement,
    ...override,
    position: { ...(globalElement.position || {}), ...(override.position || {}) },
    size: { ...(globalElement.size || {}), ...(override.size || {}) },
    style: { ...(globalElement.style || {}), ...(override.style || {}) },
    animation: {
      ...(globalElement.animation || {}),
      ...(override.animation || {}),
      enter: {
        ...(globalElement.animation?.enter || {}),
        ...(override.animation?.enter || {}),
      },
      exit: {
        ...(globalElement.animation?.exit || {}),
        ...(override.animation?.exit || {}),
      },
    },
  }
}

function collectTimelineFontKeys(timeline) {
  const keys = new Set()
  const add = (k) => {
    if (!k || typeof k !== 'string') return
    const key = k.trim()
    if (key) keys.add(key)
  }

  for (const el of timeline?.elements || []) {
    add(el?.style?.fontFamily)
  }
  for (const p of timeline?.parts || []) {
    const cfgs = p?.elementConfigs || {}
    for (const cfg of Object.values(cfgs)) {
      add(cfg?.style?.fontFamily)
    }
  }
  return [...keys]
}

// ── Main ──

async function main() {
  const outputDir = process.argv[2]
  if (!outputDir) {
    process.stderr.write('Usage: node konva_render_worker.mjs <output_dir>\n')
    process.exit(1)
  }

  const inputStr = await readStdin()
  let input
  try {
    input = JSON.parse(inputStr)
  } catch (e) {
    process.stderr.write(`[render] Failed to parse input JSON: ${e.message}\n`)
    process.exit(1)
  }

  const { timeline, sentences, resolution } = input
  if (!timeline || !sentences) {
    process.stderr.write('[render] Input must contain "timeline" and "sentences"\n')
    process.exit(1)
  }

  const res = resolution || timeline.resolution || { width: 1920, height: 1080 }
  const containerSize = { width: res.width, height: res.height }

  // Register fonts
  const fontsDir = path.resolve(__dirname, '..', 'static', 'fonts')
  let fontSummary = { registeredKeys: [], missingKeys: [] }
  try {
    fontSummary = await registerFonts(fontsDir)
  } catch (e) {
    process.stderr.write(`[render] Font registration warning: ${e.message}\n`)
  }
  const usedKeys = collectTimelineFontKeys(timeline)
  const registered = new Set(fontSummary?.registeredKeys || [])
  const missingUsed = usedKeys.filter(k => FONT_FILES[k] && !registered.has(k))
  if (missingUsed.length > 0) {
    process.stderr.write(
      `[render] Missing font files for selected font keys: ${missingUsed.join(', ')}. ` +
      `Put matching .ttf files into ${fontsDir} to match editor preview.\n`
    )
  }

  // Ensure output directory exists
  fs.mkdirSync(outputDir, { recursive: true })

  const parts = timeline.parts || []
  const elements = timeline.elements || []
  const results = {}

  for (let si = 0; si < sentences.length; si++) {
    const sentence = sentences[si]
    results[si] = {}

    for (let pi = 0; pi < parts.length; pi++) {
      const part = parts[pi]
      const partId = String(part.id || `p_${pi}`)
      const partSafe = partId.replace(/[^a-zA-Z0-9_-]/g, '_')
      const partVisibility = part.elementVisibility || {}
      const effectiveStyleId = part.styleId || timeline.styleId || null
      results[si][partId] = {}

      const sortedElements = [...elements].sort((a, b) => (a.zIndex || 0) - (b.zIndex || 0))
      for (const globalElement of sortedElements) {
        const elementId = globalElement.id
        const isVisible = partVisibility[elementId]
        if (!isVisible) continue

        const overrides = part.elementConfigs?.[elementId] || {}
        const element = mergeElement(globalElement, overrides)
        if (element.visible === false) continue

        const content = buildContent(sentence, element.type)

        // Handle sticker separately (image-based)
        if (element.type === 'sticker') {
          const pos = element.position || { x: 0, y: 0 }
          const size = element.size || { w: 0.1, h: 0.1 }
          const stickerSrc = element.style?.src || ''
          if (stickerSrc) {
            const x_px = Math.round(pos.x * containerSize.width)
            const y_px = Math.round(pos.y * containerSize.height)
            const w_px = Math.round(size.w * containerSize.width)
            const h_px = Math.round(size.h * containerSize.height)

            try {
              const imgPath = stickerSrc.startsWith('/')
                ? path.resolve(__dirname, '..', stickerSrc.slice(1))
                : stickerSrc
              const img = await loadImage(imgPath)
              const canvas = createCanvas(w_px, h_px)
              const ctx = canvas.getContext('2d')
              ctx.globalAlpha = element.opacity ?? 1
              ctx.drawImage(img, 0, 0, w_px, h_px)

              const pngName = `s${String(si).padStart(4, '0')}_p${String(pi).padStart(2, '0')}_${partSafe}_${element.type}_${element.id}.png`
              const pngPath = path.join(outputDir, pngName)
              fs.writeFileSync(pngPath, canvas.toBuffer('image/png'))

              results[si][partId][element.id] = { path: pngPath, x: x_px, y: y_px, w: w_px, h: h_px }
            } catch (e) {
              process.stderr.write(`[render] Sticker render failed for ${element.id} (part=${partId}): ${e.message}\n`)
            }
          }
          continue
        }

        // Render element using shared renderer (with effective style id)
        const rendered = renderElement(element, content, containerSize, effectiveStyleId)
        if (!rendered || !rendered.nodes || rendered.nodes.length === 0) continue

        try {
          const baseCanvas = renderNodesToCanvas(rendered.nodes, rendered.w, rendered.h)
          const transformed = applyElementGroupTransform(
            baseCanvas,
            element.rotation || 0,
            element.opacity ?? 1,
          )
          const pngBuffer = transformed.canvas.toBuffer('image/png')

          const pngName = `s${String(si).padStart(4, '0')}_p${String(pi).padStart(2, '0')}_${partSafe}_${element.type}_${element.id}.png`
          const pngPath = path.join(outputDir, pngName)
          fs.writeFileSync(pngPath, pngBuffer)

          results[si][partId][element.id] = {
            path: pngPath,
            x: Math.round(rendered.x + transformed.dx),
            y: Math.round(rendered.y + transformed.dy),
            w: Math.round(transformed.canvas.width),
            h: Math.round(transformed.canvas.height),
          }
        } catch (e) {
          process.stderr.write(`[render] Failed to render ${element.type} for sentence ${si}, part=${partId}: ${e.message}\n`)
        }
      }
    }
  }

  // Output results as JSON to stdout
  process.stdout.write(JSON.stringify({ results }, null, 2) + '\n')
}

main().catch(e => {
  process.stderr.write(`[render] Fatal error: ${e.message}\n`)
  process.exit(1)
})
