<template>
  <div class="props-sidebar">
    <div class="sidebar-hdr">{{ selectedElement ? `${typeLabel(selectedElement.type)} ${tr('props_properties', 'Properties')}` : tr('props_element_properties', 'Element Properties') }}</div>

    <!-- No selection hint -->
    <div v-if="!selectedElement" class="no-selection">
      {{ tr('props_no_selection_1', 'Click an element on canvas') }}<br>{{ tr('props_no_selection_2', 'to edit position / size / style') }}
    </div>

    <!-- Properties form -->
    <div v-else class="props-form">
      <!-- Position & Size -->
      <div v-if="!isLockedWatermark" class="prop-row2">
        <div>
          <label class="label">X %</label>
          <input type="number" class="input input-sm"
                 :value="pct(selectedElement.position.x)"
                 @change="updatePos('x', $event.target.value)"
                 min="-200" max="300" step="1">
        </div>
        <div>
          <label class="label">Y %</label>
          <input type="number" class="input input-sm"
                 :value="pct(selectedElement.position.y)"
                 @change="updatePos('y', $event.target.value)"
                 min="-200" max="300" step="1">
        </div>
        <div>
          <label class="label">{{ tr('props_width_pct', 'Width %') }}</label>
          <input type="number" class="input input-sm"
                 :value="pct(selectedElement.size.w)"
                 @change="updateSize('w', $event.target.value)"
                 min="1" max="300" step="1">
        </div>
        <div>
          <label class="label">{{ tr('props_height_pct', 'Height %') }}</label>
          <input type="number" class="input input-sm"
                 :value="pct(selectedElement.size.h)"
                 @change="updateSize('h', $event.target.value)"
                 min="1" max="300" step="1">
        </div>
      </div>

      <!-- Rotation (watermark only) -->
      <template v-if="selectedElement.type === 'watermark'">
        <template v-if="isLockedWatermark">
          <div class="wm-lock-tip" style="margin-top:8px">
            {{ tr('props_watermark_locked_tip', 'Fixed for free plan.') }}
          </div>
        </template>
        <template v-else>
          <label class="label" style="margin-top:8px">{{ tr('props_rotation', 'Rotation') }}：{{ (selectedElement.rotation || 0).toFixed(0) }}°</label>
          <input type="range" class="slider"
                 :value="selectedElement.rotation || 0"
                 @input="onPatchElement(selectedElement.id, { rotation: Number($event.target.value) })"
                 min="-180" max="180" step="1" style="margin-bottom:6px">

          <!-- Watermark opacity -->
          <label class="label">{{ tr('props_opacity', 'Opacity') }}：{{ ((selectedElement.opacity ?? 0.5) * 100).toFixed(0) }}%</label>
          <input type="range" class="slider"
                 :value="selectedElement.opacity ?? 0.5"
                 @input="onPatchElement(selectedElement.id, { opacity: Number($event.target.value) })"
                 min="0" max="1" step="0.05" style="margin-bottom:6px">

          <!-- Watermark text & color -->
          <div style="margin-bottom:8px">
            <label class="label">{{ tr('props_watermark_text', 'Watermark Text') }}</label>
            <input type="text" class="input"
                   :value="selectedElement.style.text"
                   @change="onPatchStyle(selectedElement.id, { text: $event.target.value })"
                   placeholder="LinguaLearn">
          </div>
          <ColorPicker :label="tr('props_text_color', 'Text Color')" :value="selectedElement.style.color || '#ffffff'"
                       @update="onPatchStyle(selectedElement.id, { color: $event })" />
          <label class="label">{{ tr('props_font_size', 'Font Size') }}：{{ selectedElement.style.fontSize || 16 }}px</label>
          <input type="range" class="slider"
                 :value="selectedElement.style.fontSize || 16"
                 @input="onPatchStyle(selectedElement.id, { fontSize: Number($event.target.value) })"
                 min="8" max="160" step="1">
        </template>
      </template>

      <!-- Content box (subtitle / wordbox / exprbox) properties -->
      <template v-else>
        <!-- Background opacity (separate bgOpacity property) -->
        <label class="label" style="margin-top:8px">{{ tr('props_bg_opacity', 'Background Opacity') }}：{{ bgAlphaPct }}%</label>
        <input type="range" class="slider"
               :value="bgAlpha"
               @input="onPatchStyle(selectedElement.id, { bgOpacity: Number($event.target.value) })"
               min="0" max="1" step="0.05" style="margin-bottom:6px">

        <!-- Font scale -->
        <label class="label">{{ tr('props_font_scale', 'Font Scale') }}：{{ (selectedElement.style.fontScale || 1).toFixed(2) }}x</label>
        <input type="range" class="slider"
               :value="selectedElement.style.fontScale || 1"
               @input="onPatchStyle(selectedElement.id, { fontScale: Number($event.target.value) })"
               min="0.1" max="5.0" step="0.05" style="margin-bottom:10px">

        <template v-if="selectedElement.type === 'subtitle'">
          <label class="label">{{ tr('props_source_line_height', 'Source Line Height') }}：{{ subtitleSrcLineHeightVal.toFixed(1) }}x</label>
          <input type="range" class="slider"
                 :value="subtitleSrcLineHeightVal"
                 @input="onSourceLineSpacingInput($event.target.value)"
                 min="0.5" max="6.0" step="0.1" style="margin-bottom:8px">

          <label class="label">{{ tr('props_target_line_height', 'Target Line Height') }}：{{ subtitleTgtLineHeightVal.toFixed(1) }}x</label>
          <input type="range" class="slider"
                 :value="subtitleTgtLineHeightVal"
                 @input="onTargetLineSpacingInput($event.target.value)"
                 min="0.5" max="6.0" step="0.1" style="margin-bottom:10px">
        </template>

        <template v-else>
          <label class="label">{{ tr('props_word_spacing', 'Word Spacing') }}：{{ wordSpacingVal.toFixed(2) }}x</label>
          <input type="range" class="slider"
                 :value="wordSpacingVal"
                 @input="onWordSpacingInput($event.target.value)"
                 min="0.05" max="6.0" step="0.05" style="margin-bottom:10px">
        </template>

        <!-- Animation picker (per element) -->
        <div class="anim-label">{{ tr('props_animation', 'Animation') }}</div>
        <div class="anim-grid">
          <button v-for="a in ANIMATIONS" :key="a.type"
                  :class="['anim-btn', { active: currentAnimType === a.type }]"
                  @click="onPickAnimation(a.type)">
            {{ tr(a.labelKey, a.fallback) }}
          </button>
        </div>

        <!-- Animation duration (per element) -->
        <div v-if="currentAnimType !== 'none'" style="margin-top:8px">
          <label class="label">{{ tr('props_animation_duration', 'Animation Duration') }}：{{ currentAnimDuration }}ms</label>
          <input type="range" class="slider"
                 :value="currentAnimDuration"
                 @input="onSetAnimDuration(Number($event.target.value))"
                 min="50" max="6000" step="50" style="margin-bottom:6px">
        </div>

      </template>

      <!-- Word list panel (for wordbox) -->
      <WordListPanel v-if="selectedElement.type === 'wordbox'"
                     :sourceLang="sourceLang"
                     :targetLang="targetLang"
                     :numWords="numWords"
                     :numExprs="numExprs" />

      <!-- Delete button -->
      <button v-if="!isLockedWatermark" class="remove-btn" @click="$emit('remove', selectedElement.id)">
        🗑️ {{ tr('props_remove_element', 'Remove from Canvas') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ColorPicker from './ColorPicker.vue'
import WordListPanel from './WordListPanel.vue'
import { useI18n } from '../../i18n.js'

const props = defineProps({
  selectedElement: { type: Object, default: null },
  watermarkLocked: { type: Boolean, default: false },
  sourceLang: { type: String, default: 'en' },
  targetLang: { type: String, default: 'zh' },
  numWords: { type: Number, default: 6 },
  numExprs: { type: Number, default: 4 },
  applyPatch: { type: Function, default: null },
  applyStylePatch: { type: Function, default: null },
})

const emit = defineEmits(['update', 'updateStyle', 'setAnimation', 'previewAnimation', 'remove'])
const { t } = useI18n()

function tr(key, fallback = '') {
  return t.value?.[key] || fallback || key
}

const ANIMATIONS = [
  { type: 'fade',       labelKey: 'anim_fade', fallback: 'Fade' },
  { type: 'slide_up',   labelKey: 'anim_slide_up', fallback: 'Slide Up' },
  { type: 'slide_left', labelKey: 'anim_slide_left', fallback: 'Slide Left' },
  { type: 'slide_right',labelKey: 'anim_slide_right', fallback: 'Slide Right' },
  { type: 'pop',        labelKey: 'anim_pop', fallback: 'Pop' },
  { type: 'none',       labelKey: 'anim_none', fallback: 'None' },
]

const TYPE_LABELS = {
  subtitle: { key: 'create_el_subtitle', fallback: 'Subtitle' },
  wordbox: { key: 'create_el_wordbox', fallback: 'Word Box' },
  exprbox: { key: 'create_el_exprbox', fallback: 'Expression Box' },
  watermark: { key: 'create_el_watermark', fallback: 'Watermark' },
}

function typeLabel(type) {
  const item = TYPE_LABELS[type]
  if (!item) return type
  return tr(item.key, item.fallback)
}
function pct(v) { return Math.round((v || 0) * 1000) / 10 }
const isLockedWatermark = computed(() =>
  props.selectedElement?.type === 'watermark' && props.watermarkLocked
)

function onPatchElement(id, patch) {
  if (isLockedWatermark.value) return
  if (!id || !patch) return
  if (typeof props.applyPatch === 'function') {
    props.applyPatch(id, patch)
    return
  }
  emit('update', id, patch)
}

function onPatchStyle(id, patch) {
  if (isLockedWatermark.value) return
  if (!id || !patch) return
  if (typeof props.applyStylePatch === 'function') {
    props.applyStylePatch(id, patch)
    return
  }
  emit('updateStyle', id, patch)
}

function updatePos(axis, val) {
  const v = Number(val) / 100
  const pos = { ...props.selectedElement.position, [axis]: v }
  onPatchElement(props.selectedElement.id, { position: pos })
}

function updateSize(dim, val) {
  const v = Number(val) / 100
  const size = { ...props.selectedElement.size, [dim]: v }
  onPatchElement(props.selectedElement.id, { size })
}

// ── Background opacity ──
// Use bgOpacity if set; otherwise fall back to parsing rgba alpha from bgColor

const bgAlpha = computed(() => {
  const style = props.selectedElement?.style
  if (style?.bgOpacity !== undefined) return style.bgOpacity
  const bg = style?.bgColor || 'rgba(0,0,0,0.8)'
  const m = bg.match(/rgba?\([^)]+\)/)
  if (!m) return 0.8
  const parts = m[0].replace(/rgba?\(/, '').replace(')', '').split(',').map(s => s.trim())
  return parts.length >= 4 ? parseFloat(parts[3]) : 1.0
})

const bgAlphaPct = computed(() => Math.round(bgAlpha.value * 100))

// ── Per-element animation ──

const subtitleSrcLineHeightVal = computed(() => {
  const style = props.selectedElement?.style || {}
  return (
    style.sourceLineHeight ??
    style.srcLineHeight ??
    style.lineHeight ??
    1.3
  )
})

const subtitleTgtLineHeightVal = computed(() => {
  const style = props.selectedElement?.style || {}
  return (
    style.targetLineHeight ??
    style.tgtLineHeight ??
    style.lineHeight ??
    1.3
  )
})

const wordSpacingVal = computed(() => {
  const style = props.selectedElement?.style || {}
  return style.wordSpacing ?? style.lineHeight ?? 1.0
})

function onSourceLineSpacingInput(rawVal) {
  if (!props.selectedElement) return
  const v = Number(rawVal)
  onPatchStyle(props.selectedElement.id, { sourceLineHeight: v })
}

function onTargetLineSpacingInput(rawVal) {
  if (!props.selectedElement) return
  const v = Number(rawVal)
  onPatchStyle(props.selectedElement.id, { targetLineHeight: v })
}

function onWordSpacingInput(rawVal) {
  if (!props.selectedElement) return
  const v = Number(rawVal)
  onPatchStyle(props.selectedElement.id, { wordSpacing: v })
}

const currentAnimType = computed(() =>
  props.selectedElement?.animation?.enter?.type || 'fade'
)

const currentAnimDuration = computed(() =>
  props.selectedElement?.animation?.enter?.duration ?? 400
)

function onPickAnimation(animType) {
  emit('setAnimation', props.selectedElement.id, animType)
  emit('previewAnimation', props.selectedElement.id)
}

function onSetAnimDuration(ms) {
  onPatchElement(props.selectedElement.id, {
    animation: { enter: { duration: ms } }
  })
}
</script>

<style scoped>
.props-sidebar {
  position: relative;
  z-index: 3;
  pointer-events: auto;
  width: 220px;
  min-width: 190px;
  padding: 10px;
  border-left: 1px solid rgba(255,255,255,.06);
  overflow-y: auto;
  max-height: 480px;
}
.sidebar-hdr {
  font-size: 12px;
  font-weight: 700;
  color: var(--text2);
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: .5px;
}
.no-selection {
  color: var(--text3);
  font-size: 12px;
  text-align: center;
  padding: 20px 0;
  line-height: 1.7;
}
.wm-lock-tip {
  margin-top: 8px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(148,163,184,.35);
  background: rgba(15,23,42,.55);
  color: var(--text2);
  font-size: 12px;
  line-height: 1.5;
}
.prop-row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.anim-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text3);
  margin: 8px 0 6px;
  text-transform: uppercase;
  letter-spacing: .5px;
}
.anim-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  margin-bottom: 10px;
}
.anim-btn {
  padding: 5px 4px;
  border-radius: 5px;
  border: 1px solid rgba(255,255,255,.1);
  background: rgba(255,255,255,.04);
  color: var(--text2);
  font-size: 11px;
  cursor: pointer;
  transition: all .15s;
  text-align: center;
}
.anim-btn:hover { background: rgba(167,139,250,.15); border-color: rgba(167,139,250,.3); }
.anim-btn.active { background: rgba(167,139,250,.2); border-color: #a78bfa; color: #a78bfa; font-weight: 600; }
.remove-btn {
  width: 100%;
  margin-top: 10px;
  padding: 7px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid rgba(248,113,113,.3);
  color: var(--err);
  font-size: 12px;
  cursor: pointer;
  transition: all .15s;
}
.remove-btn:hover { background: rgba(248,113,113,.1); }

</style>
