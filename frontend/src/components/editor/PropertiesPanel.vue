<template>
  <div class="props-sidebar">
    <div class="sidebar-hdr">{{ selectedElement ? typeLabel(selectedElement.type) + ' 属性' : '元素属性' }}</div>

    <!-- No selection hint -->
    <div v-if="!selectedElement" class="no-selection">
      点击画布中的元素<br>以编辑位置 / 大小 / 样式
    </div>

    <!-- Properties form -->
    <div v-else class="props-form">
      <!-- Position & Size -->
      <div class="prop-row2">
        <div>
          <label class="label">X %</label>
          <input type="number" class="input input-sm"
                 :value="pct(selectedElement.position.x)"
                 @change="updatePos('x', $event.target.value)"
                 min="0" max="99" step="0.5">
        </div>
        <div>
          <label class="label">Y %</label>
          <input type="number" class="input input-sm"
                 :value="pct(selectedElement.position.y)"
                 @change="updatePos('y', $event.target.value)"
                 min="0" max="99" step="0.5">
        </div>
        <div>
          <label class="label">宽 %</label>
          <input type="number" class="input input-sm"
                 :value="pct(selectedElement.size.w)"
                 @change="updateSize('w', $event.target.value)"
                 min="3" max="100" step="0.5">
        </div>
        <div>
          <label class="label">高 %</label>
          <input type="number" class="input input-sm"
                 :value="pct(selectedElement.size.h)"
                 @change="updateSize('h', $event.target.value)"
                 min="2" max="100" step="0.5">
        </div>
      </div>

      <!-- Rotation (watermark only) -->
      <template v-if="selectedElement.type === 'watermark'">
        <label class="label" style="margin-top:8px">旋转：{{ (selectedElement.rotation || 0).toFixed(0) }}°</label>
        <input type="range" class="slider"
               :value="selectedElement.rotation || 0"
               @input="$emit('update', selectedElement.id, { rotation: Number($event.target.value) })"
               min="-180" max="180" step="1" style="margin-bottom:6px">

        <!-- Watermark opacity -->
        <label class="label">透明度：{{ ((selectedElement.opacity ?? 0.5) * 100).toFixed(0) }}%</label>
        <input type="range" class="slider"
               :value="selectedElement.opacity ?? 0.5"
               @input="$emit('update', selectedElement.id, { opacity: Number($event.target.value) })"
               min="0" max="1" step="0.05" style="margin-bottom:6px">

        <!-- Watermark text & color -->
        <div style="margin-bottom:8px">
          <label class="label">水印文字</label>
          <input type="text" class="input"
                 :value="selectedElement.style.text"
                 @change="$emit('updateStyle', selectedElement.id, { text: $event.target.value })"
                 placeholder="LinguaLearn">
        </div>
        <ColorPicker label="文字色" :value="selectedElement.style.color || '#ffffff'"
                     @update="$emit('updateStyle', selectedElement.id, { color: $event })" />
        <label class="label">字号：{{ selectedElement.style.fontSize || 16 }}px</label>
        <input type="range" class="slider"
               :value="selectedElement.style.fontSize || 16"
               @input="$emit('updateStyle', selectedElement.id, { fontSize: Number($event.target.value) })"
               min="8" max="64" step="1">
      </template>

      <!-- Content box (subtitle / wordbox / exprbox) properties -->
      <template v-else>
        <!-- Background opacity (separate bgOpacity property) -->
        <label class="label" style="margin-top:8px">背景透明度：{{ bgAlphaPct }}%</label>
        <input type="range" class="slider"
               :value="bgAlpha"
               @input="$emit('updateStyle', selectedElement.id, { bgOpacity: Number($event.target.value) })"
               min="0" max="1" step="0.05" style="margin-bottom:6px">

        <!-- Font scale -->
        <label class="label">字号倍率：{{ (selectedElement.style.fontScale || 1).toFixed(1) }}x</label>
        <input type="range" class="slider"
               :value="selectedElement.style.fontScale || 1"
               @input="$emit('updateStyle', selectedElement.id, { fontScale: Number($event.target.value) })"
               min="0.5" max="2.5" step="0.1" style="margin-bottom:10px">

        <!-- Animation picker (per element) -->
        <div class="anim-label">动画效果</div>
        <div class="anim-grid">
          <button v-for="a in ANIMATIONS" :key="a.type"
                  :class="['anim-btn', { active: currentAnimType === a.type }]"
                  @click="onPickAnimation(a.type)">
            {{ a.label }}
          </button>
        </div>

        <!-- Animation duration (per element) -->
        <div v-if="currentAnimType !== 'none'" style="margin-top:8px">
          <label class="label">动画时长：{{ currentAnimDuration }}ms</label>
          <input type="range" class="slider"
                 :value="currentAnimDuration"
                 @input="onSetAnimDuration(Number($event.target.value))"
                 min="100" max="1200" step="50" style="margin-bottom:6px">
        </div>

      </template>

      <!-- Delete button -->
      <button class="remove-btn" @click="$emit('remove', selectedElement.id)">
        🗑️ 从画布移除此元素
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ColorPicker from './ColorPicker.vue'

const props = defineProps({
  selectedElement: { type: Object, default: null },
})

const emit = defineEmits(['update', 'updateStyle', 'setAnimation', 'previewAnimation', 'remove'])

const ANIMATIONS = [
  { type: 'fade',       label: '淡入' },
  { type: 'slide_up',   label: '上滑' },
  { type: 'slide_left', label: '左滑' },
  { type: 'slide_right',label: '右滑' },
  { type: 'pop',        label: '弹出' },
  { type: 'none',       label: '无' },
]

const TYPE_LABELS = {
  subtitle: '字幕',
  wordbox: '词框',
  exprbox: '表达框',
  watermark: '水印',
}

function typeLabel(type) { return TYPE_LABELS[type] || type }
function pct(v) { return Math.round((v || 0) * 1000) / 10 }

function updatePos(axis, val) {
  const v = Number(val) / 100
  const pos = { ...props.selectedElement.position, [axis]: v }
  emit('update', props.selectedElement.id, { position: pos })
}

function updateSize(dim, val) {
  const v = Number(val) / 100
  const size = { ...props.selectedElement.size, [dim]: v }
  emit('update', props.selectedElement.id, { size })
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
  emit('update', props.selectedElement.id, {
    animation: { enter: { duration: ms } }
  })
}
</script>

<style scoped>
.props-sidebar {
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
