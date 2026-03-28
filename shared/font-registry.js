/**
 * Font Registry — shared between browser and Node.js
 * Browser: fonts loaded via Google Fonts CDN (no-op here)
 * Node.js: registerFont() for canvas
 */

export const FONTS = [
  { val: 'system',          label: '系统默认',        css: 'system-ui, -apple-system, sans-serif' },
  { val: 'noto-serif',      label: 'Noto Serif SC',   css: "'Noto Serif SC', serif" },
  { val: 'xiaowei',         label: '小薇体',          css: "'ZCOOL XiaoWei', serif" },
  { val: 'ma-shan',         label: '马善政楷书',      css: "'Ma Shan Zheng', cursive" },
  { val: 'long-cang',       label: '龙藏体',          css: "'Long Cang', cursive" },
  { val: 'zhi-mang',        label: '志莽行书',        css: "'Zhi Mang Xing', cursive" },
  { val: 'qingke',          label: '清客黄油体',      css: "'ZCOOL QingKe HuangYou', cursive" },
  { val: 'noto-jp',         label: 'Noto Sans JP',    css: "'Noto Sans JP', sans-serif" },
  { val: 'noto-kr',         label: 'Noto Sans KR',    css: "'Noto Sans KR', sans-serif" },
  { val: 'dancing',         label: 'Dancing Script',  css: "'Dancing Script', cursive" },
  { val: 'caveat',          label: 'Caveat',           css: "'Caveat', cursive" },
  { val: 'bitter',          label: 'Bitter',           css: "'Bitter', serif" },
  { val: 'quicksand',       label: 'Quicksand',        css: "'Quicksand', sans-serif" },
  { val: 'rajdhani',        label: 'Rajdhani',         css: "'Rajdhani', sans-serif" },
]

// Map from font val key to CSS font-family string
const FONT_MAP = Object.fromEntries(FONTS.map(f => [f.val, f.css]))

/**
 * Get CSS font-family string for a font key
 * @param {string} fontKey - Font key like 'system', 'noto-sans', etc.
 * @returns {string} CSS font-family value
 */
export function getFontFamily(fontKey) {
  return FONT_MAP[fontKey] || FONT_MAP['system']
}

/**
 * Map from font key to TTF file name in static/fonts/
 * Used by Node.js for canvas registerFont()
 */
export const FONT_FILES = {
  'noto-serif':   'NotoSerifSC-Regular.ttf',
  'xiaowei':      'ZCOOLXiaoWei-Regular.ttf',
  'ma-shan':      'MaShanZheng-Regular.ttf',
  'long-cang':    'LongCang-Regular.ttf',
  'zhi-mang':     'ZhiMangXing-Regular.ttf',
  'qingke':       'ZCOOLQingKeHuangYou-Regular.ttf',
  'noto-jp':      'NotoSansJP-Regular.ttf',
  'noto-kr':      'NotoSansKR-Regular.ttf',
  'dancing':      'DancingScript-Regular.ttf',
  'caveat':       'Caveat-Regular.ttf',
  'bitter':       'Bitter-Regular.ttf',
  'quicksand':    'Quicksand-Regular.ttf',
  'rajdhani':     'Rajdhani-Regular.ttf',
  // Google Fonts loaded via CDN in browser; Node.js falls back to system
}

/**
 * Register all available fonts for Node.js canvas rendering.
 * No-op in browser environments.
 * @param {string} fontsDir - Path to fonts directory (e.g. 'static/fonts/')
 */
export async function registerFonts(fontsDir) {
  const summary = {
    registeredKeys: [],
    missingKeys: [],
  }
  if (typeof window !== 'undefined') return summary // browser — no-op

  let registerFont
  try {
    const canvas = await import('canvas')
    registerFont = canvas.registerFont
  } catch {
    console.warn('[font-registry] canvas module not available, skipping font registration')
    summary.missingKeys = Object.keys(FONT_FILES)
    return summary
  }

  const path = await import('path')
  const fs = await import('fs')

  if (!fontsDir || !fs.existsSync(fontsDir)) {
    // Missing static/fonts means export will fallback to system fonts.
    summary.missingKeys = Object.keys(FONT_FILES)
    console.warn(`[font-registry] Fonts directory not found: ${fontsDir || '(empty)'}`)
    return summary
  }

  for (const font of FONTS) {
    const file = FONT_FILES[font.val]
    if (!file) continue // system font, skip

    const fontPath = path.join(fontsDir, file)
    if (fs.existsSync(fontPath)) {
      // Extract the primary family name from css string (remove quotes and fallback)
      const family = font.css.split(',')[0].replace(/'/g, '').trim()
      try {
        registerFont(fontPath, { family })
        summary.registeredKeys.push(font.val)
      } catch (e) {
        console.warn(`[font-registry] Failed to register ${family}: ${e.message}`)
        summary.missingKeys.push(font.val)
      }
    } else {
      summary.missingKeys.push(font.val)
    }
  }
  return summary
}
