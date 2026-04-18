/**
 * Text Layout Engine — text measurement and word-wrapping for Konva
 * Works in both browser (Konva) and Node.js (konva-node) environments
 */

const CJK_REGEX = /[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]/

/**
 * Check if text contains CJK characters
 */
export function isCJK(text) {
  return CJK_REGEX.test(text)
}

/**
 * Estimate line count for text in a given width.
 * For CJK: character-based wrapping. For Latin: word-based wrapping.
 * Uses approximate character width (no canvas measurement needed for estimates).
 *
 * @param {string} text
 * @param {number} fontSize - in pixels
 * @param {number} maxWidth - container width in pixels
 * @returns {{ lineCount: number, totalHeight: number }}
 */
export function estimateTextLayout(text, fontSize, maxWidth) {
  if (!text || maxWidth <= 0) return { lineCount: 1, totalHeight: fontSize * 1.3 }

  const lineHeight = fontSize * 1.3
  let lineCount

  if (isCJK(text)) {
    // CJK: each char ~= fontSize width
    const charsPerLine = Math.max(1, Math.floor(maxWidth / fontSize))
    lineCount = Math.ceil(text.length / charsPerLine)
  } else {
    // Latin: average char width ~= fontSize * 0.55
    const avgCharWidth = fontSize * 0.55
    const charsPerLine = Math.max(1, Math.floor(maxWidth / avgCharWidth))
    lineCount = Math.ceil(text.length / charsPerLine)
  }

  return {
    lineCount: Math.max(1, lineCount),
    totalHeight: Math.max(1, lineCount) * lineHeight,
  }
}

/**
 * Calculate adaptive font size based on text length and container dimensions.
 * Longer text → smaller font.
 *
 * @param {string} text
 * @param {number} baseFontSize - base size at "ideal" text length
 * @param {number} containerWidth
 * @param {number} containerHeight
 * @param {number} fontScale - user-configurable scale factor (default 1.0)
 * @returns {number} adjusted font size in pixels
 */
export function adaptiveFontSize(text, baseFontSize, containerWidth, containerHeight, fontScale = 1.0) {
  if (!text) return baseFontSize * fontScale

  const len = text.length
  // Scale factor: reduce font if text is long
  // "ideal" length ~30 chars for subtitle
  let scaleFactor = 1.0
  if (len > 40) scaleFactor = 0.85
  else if (len > 60) scaleFactor = 0.75
  else if (len > 80) scaleFactor = 0.65
  else if (len > 100) scaleFactor = 0.55

  const adjusted = baseFontSize * scaleFactor * fontScale

  // Ensure at least 2 lines fit in container
  const maxFontForHeight = containerHeight / 2.6
  return Math.min(adjusted, maxFontForHeight)
}

/**
 * Get Konva Text config with proper wrapping settings
 *
 * @param {object} opts
 * @param {string} opts.text
 * @param {number} opts.fontSize
 * @param {string} opts.fontFamily
 * @param {string} opts.fill - color
 * @param {number} opts.width - wrap width
 * @param {string} [opts.align='left']
 * @param {string} [opts.fontStyle='normal']
 * @returns {object} Konva.Text config object
 */
export function textConfig(opts) {
  const { text, fontSize, fontFamily, fill, width, align = 'left', fontStyle = 'normal', ...rest } = opts
  return {
    text,
    fontSize,
    fontFamily,
    fill,
    width,
    align,
    fontStyle,
    wrap: 'word',
    lineHeight: 1.3,
    ...rest,
  }
}
