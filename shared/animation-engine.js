/**
 * Animation Engine — data-driven animations for Konva nodes
 * Shared between browser (preview) and Node.js (export frame calculation)
 */

/**
 * Animation presets library.
 * Each preset defines { from, to } properties for Konva.Tween
 */
export const ANIMATION_PRESETS = {
  fade: {
    label: '淡入淡出',
    enter: { from: { opacity: 0 }, to: { opacity: 1 } },
    exit:  { from: { opacity: 1 }, to: { opacity: 0 } },
    defaultDuration: 300,
    defaultEasing: 'EaseOut',
  },
  slide_up: {
    label: '向上滑入',
    enter: {
      from: { opacity: 0, offsetY: 20 },
      to:   { opacity: 1, offsetY: 0 },
    },
    exit: {
      from: { opacity: 1, offsetY: 0 },
      to:   { opacity: 0, offsetY: -20 },
    },
    defaultDuration: 400,
    defaultEasing: 'EaseOut',
  },
  slide_left: {
    label: '从左滑入',
    enter: {
      from: { opacity: 0, offsetX: -30 },
      to:   { opacity: 1, offsetX: 0 },
    },
    exit: {
      from: { opacity: 1, offsetX: 0 },
      to:   { opacity: 0, offsetX: 30 },
    },
    defaultDuration: 400,
    defaultEasing: 'EaseOut',
  },
  slide_right: {
    label: '从右滑入',
    enter: {
      from: { opacity: 0, offsetX: -40 },
      to:   { opacity: 1, offsetX: 0 },
    },
    exit: {
      from: { opacity: 1, offsetX: 0 },
      to:   { opacity: 0, offsetX: -40 },
    },
    defaultDuration: 400,
    defaultEasing: 'EaseOut',
  },
  pop: {
    label: '弹出放大',
    enter: {
      from: { opacity: 0, scaleX: 0.5, scaleY: 0.5 },
      to:   { opacity: 1, scaleX: 1, scaleY: 1 },
    },
    exit: {
      from: { opacity: 1, scaleX: 1, scaleY: 1 },
      to:   { opacity: 0, scaleX: 0.8, scaleY: 0.8 },
    },
    defaultDuration: 300,
    defaultEasing: 'BackEaseOut',
  },
  none: {
    label: '无动画',
    enter: { from: {}, to: {} },
    exit:  { from: {}, to: {} },
    defaultDuration: 0,
    defaultEasing: 'Linear',
  },
}

/**
 * Easing function mapping to Konva easing names
 */
const EASING_MAP = {
  'linear':         'Linear',
  'easeIn':         'EaseIn',
  'easeOut':        'EaseOut',
  'easeInOut':      'EaseInOut',
  'easeOutCubic':   'StrongEaseOut',
  'easeInCubic':    'StrongEaseIn',
  'backEaseOut':    'BackEaseOut',
  'backEaseIn':     'BackEaseIn',
  'elasticEaseOut': 'ElasticEaseOut',
  'EaseOut':        'EaseOut',
  'EaseIn':         'EaseIn',
  'BackEaseOut':    'BackEaseOut',
  'ElasticEaseOut': 'ElasticEaseOut',
  'StrongEaseOut':  'StrongEaseOut',
  'Linear':         'Linear',
}

function resolveEasing(easing) {
  return EASING_MAP[easing] || 'EaseOut'
}

/**
 * Apply enter animation to a Konva node.
 * Returns a Konva.Tween instance (call .play() to start).
 *
 * @param {Konva.Node} node - Konva node to animate
 * @param {object} animConfig - { type, duration, easing } from timeline element
 * @param {Function} Konva - Konva module reference (for Konva.Tween + Konva.Easings)
 * @param {Function} [onFinish] - callback when animation completes
 * @returns {Konva.Tween|null}
 */
export function applyEnterAnimation(node, animConfig, Konva, onFinish) {
  if (!animConfig || animConfig.type === 'none') {
    if (onFinish) onFinish()
    return null
  }

  const preset = ANIMATION_PRESETS[animConfig.type]
  if (!preset) {
    if (onFinish) onFinish()
    return null
  }

  const duration = (animConfig.duration || preset.defaultDuration) / 1000 // Konva uses seconds
  const easingName = resolveEasing(animConfig.easing || preset.defaultEasing)

  // Set initial state
  const fromProps = preset.enter.from
  for (const [key, val] of Object.entries(fromProps)) {
    node[key](val)
  }

  // Create tween to target state
  const tweenConfig = {
    node,
    duration,
    easing: Konva.Easings[easingName] || Konva.Easings.EaseOut,
    ...preset.enter.to,
    onFinish,
  }

  return new Konva.Tween(tweenConfig)
}

/**
 * Apply exit animation to a Konva node.
 */
export function applyExitAnimation(node, animConfig, Konva, onFinish) {
  if (!animConfig || animConfig.type === 'none') {
    if (onFinish) onFinish()
    return null
  }

  const preset = ANIMATION_PRESETS[animConfig.type]
  if (!preset) {
    if (onFinish) onFinish()
    return null
  }

  const duration = (animConfig.duration || preset.defaultDuration) / 1000
  const easingName = resolveEasing(animConfig.easing || preset.defaultEasing)

  const tweenConfig = {
    node,
    duration,
    easing: Konva.Easings[easingName] || Konva.Easings.EaseIn,
    ...preset.exit.to,
    onFinish,
  }

  return new Konva.Tween(tweenConfig)
}

/**
 * Calculate animation state at a specific time (for backend frame rendering).
 * Returns property overrides to apply to the element.
 *
 * @param {object} animConfig - { type, duration, easing }
 * @param {string} direction - 'enter' or 'exit'
 * @param {number} progress - 0.0 to 1.0 (time within animation)
 * @returns {object} property overrides { opacity, scaleX, scaleY, offsetX, offsetY }
 */
export function getAnimationState(animConfig, direction, progress) {
  if (!animConfig || animConfig.type === 'none') return {}

  const preset = ANIMATION_PRESETS[animConfig.type]
  if (!preset) return {}

  const phaseData = preset[direction]
  if (!phaseData) return {}

  const result = {}
  const t = Math.max(0, Math.min(1, progress)) // clamp

  // Simple linear interpolation (easing is handled by Konva.Tween in browser)
  for (const key of Object.keys(phaseData.from)) {
    const from = phaseData.from[key]
    const to = phaseData.to[key]
    result[key] = from + (to - from) * t
  }

  return result
}

/**
 * Map animation type to FFmpeg filter parameters for video export.
 *
 * @param {object} animConfig - { type, duration }
 * @param {string} direction - 'enter' or 'exit'
 * @returns {object} { filter: string, params: object } or null
 */
export function toFFmpegFilter(animConfig, direction) {
  if (!animConfig || animConfig.type === 'none') return null

  const duration = (animConfig.duration || 300) / 1000 // seconds

  switch (animConfig.type) {
    case 'fade':
      return {
        filter: 'fade',
        params: {
          type: direction === 'enter' ? 'in' : 'out',
          duration,
        },
      }
    case 'slide_up':
      return {
        filter: 'overlay_motion',
        params: {
          direction: 'up',
          distance: 20,
          duration,
        },
      }
    case 'pop':
    case 'scale_in':
      return {
        filter: 'scale_anim',
        params: {
          fromScale: direction === 'enter' ? 0.5 : 1.0,
          toScale: direction === 'enter' ? 1.0 : 0.8,
          duration,
        },
      }
    default:
      return null
  }
}
