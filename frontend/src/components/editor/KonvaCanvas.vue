<template>
  <div class="konva-canvas-wrapper" ref="wrapperRef" :style="wrapperDimStyle">
    <!-- Video background or placeholder -->
    <div class="canvas-bg-layer" :style="canvasStyle">
      <!-- Static frame capture from random video timestamp -->
      <img v-if="frameSrc" :src="frameSrc" class="canvas-frame" />
      <div v-else-if="!videoSrc" class="canvas-placeholder">
        <span>16 : 9</span>
      </div>
      <!-- Hidden video used for frame capture; not displayed -->
      <video v-if="videoSrc" ref="videoRef" :src="videoSrc"
             muted playsinline
             class="canvas-video-hidden"
             @loadedmetadata="onVideoMetadata"
             @seeked="onVideoSeeked" />
      <!-- Grid overlay -->
      <div class="canvas-grid" />
    </div>

    <!-- Konva overlay -->
    <v-stage ref="stageRef"
             :config="stageConfig"
             @click="onStageClick"
             class="konva-overlay"
             :style="canvasStyle">

      <!-- Elements layer -->
      <v-layer ref="elementsLayerRef">
        <v-group v-for="item in renderedElements" :key="item.elementId"
                 :config="groupConfig(item)"
                 @click="onElementClick(item.elementId, $event)"
                 @dragend="onElementDragEnd(item.elementId, $event)"
                 @transformend="onElementTransformEnd(item.elementId, $event)">
          <!-- Render each Konva node from the element renderer -->
          <component v-for="(node, ni) in item.nodes" :key="ni"
                     :is="'v-' + node.type.toLowerCase()"
                     :config="node.config" />
        </v-group>
      </v-layer>

      <!-- Transformer layer -->
      <v-layer>
        <v-transformer ref="transformerRef"
                       :config="editor.transformerConfig.value" />
      </v-layer>
    </v-stage>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { renderElement } from '@shared/konva-renderer.js'

// Video frame capture
const frameSrc = ref('')
const videoRef = ref(null)

const props = defineProps({
  videoSrc: { type: String, default: '' },
  timeline: { type: Object, required: true },
  currentPartId: { type: String, default: '' },
  previewContent: { type: Object, default: () => ({}) },
  editor: { type: Object, required: true }, // useKonvaEditor instance
  zoom: { type: Number, default: 1.0 },
})

const emit = defineEmits(['select', 'deselect'])

const wrapperRef = ref(null)
const stageRef = ref(null)
const elementsLayerRef = ref(null)

watch(() => props.videoSrc, () => { frameSrc.value = '' })

function onVideoMetadata() {
  const v = videoRef.value
  if (!v || !v.duration) return
  // Seek to a random frame between 10%–80% of duration
  const t = v.duration * (0.1 + Math.random() * 0.7)
  v.currentTime = t
}

function onVideoSeeked() {
  const v = videoRef.value
  if (!v) return
  try {
    const canvas = document.createElement('canvas')
    canvas.width = v.videoWidth || 1280
    canvas.height = v.videoHeight || 720
    const ctx = canvas.getContext('2d')
    ctx.drawImage(v, 0, 0, canvas.width, canvas.height)
    frameSrc.value = canvas.toDataURL('image/jpeg', 0.85)
  } catch {}
}

// Canvas dimensions — match actual video resolution, scale down via CSS transform
// This makes the editor pixel-identical to the rendered video output.
const displayWidth = 640 // CSS display width in pixels

const actualWidth = computed(() => props.timeline.resolution?.width || 1920)
const actualHeight = computed(() => props.timeline.resolution?.height || 1080)
const displayScale = computed(() => displayWidth / actualWidth.value)

const stageConfig = computed(() => ({
  width: actualWidth.value,
  height: actualHeight.value,
}))

const canvasStyle = computed(() => ({
  width: `${actualWidth.value}px`,
  height: `${actualHeight.value}px`,
  transform: `scale(${displayScale.value * props.zoom})`,
  transformOrigin: 'top left',
}))

const wrapperDimStyle = computed(() => ({
  width: `${displayWidth * props.zoom}px`,
  height: `${displayScale.value * actualHeight.value * props.zoom}px`,
}))

// Connect editor refs
const transformerRef = ref(null)

watch(stageRef, (v) => { props.editor.stageRef.value = v })

onMounted(() => {
  props.editor.stageRef.value = stageRef.value
  nextTick(() => {
    if (transformerRef.value) {
      props.editor.transformerRef.value = transformerRef.value
    }
  })
})

// Effective styleId for the current part (part-level override or global)
const effectiveStyleId = computed(() => {
  const part = props.timeline.parts.find(p => p.id === props.currentPartId)
  return part?.styleId || props.timeline.styleId || null
})

// Visible elements for the current part
const visibleElements = computed(() => {
  const part = props.timeline.parts.find(p => p.id === props.currentPartId)
  if (!part) return []
  return props.timeline.elements.filter(el =>
    el.visible !== false && part.elementVisibility?.[el.id]
  )
})

// Rendered element data (Konva node configs)
const renderedElements = computed(() => {
  const containerSize = {
    width: stageConfig.value.width,
    height: stageConfig.value.height,
  }
  const part = props.timeline.parts.find(p => p.id === props.currentPartId)

  return visibleElements.value.map(el => {
    // Merge part-level overrides into the global element
    const overrides = part?.elementConfigs?.[el.id]
    // Always return a plain object (never the raw reactive element) so parts don't share data
    const mergedEl = overrides ? {
      ...el,
      ...overrides,
      position: { ...el.position, ...(overrides.position || {}) },
      size: { ...el.size, ...(overrides.size || {}) },
      style: { ...el.style, ...(overrides.style || {}) },
    } : { ...el, position: { ...el.position }, size: { ...el.size }, style: { ...el.style } }

    // Prepare content based on type
    let content = props.previewContent
    if (mergedEl.type === 'subtitle') {
      content = {
        text: content?.text ?? content?.source_text ?? content?.src_text ?? '',
        translation:
          content?.translation ??
          content?.translated_text ??
          content?.target_text ??
          content?.chinese_translation ??
          '',
      }
    } else if (mergedEl.type === 'wordbox') {
      content = { words: content?.words }
    } else if (mergedEl.type === 'exprbox') {
      content = { expressions: content?.expressions }
    } else if (mergedEl.type === 'watermark') {
      content = {}
    }

    const result = renderElement(mergedEl, content, containerSize, effectiveStyleId.value)
    return result ? {
      elementId: el.id,
      elementType: mergedEl.type,
      zIndex: mergedEl.zIndex || 0,
      animation: mergedEl.animation,
      mergedEl,
      ...result,
    } : null
  }).filter(Boolean).sort((a, b) => a.zIndex - b.zIndex)
})

// Konva Group config for each element
function groupConfig(item) {
  const el = item.mergedEl || props.timeline.elements.find(e => e.id === item.elementId)
  const cfg = {
    id: item.elementId,
    x: item.x,
    y: item.y,
    width: item.w,
    height: item.h,
    clipWidth: item.w,
    clipHeight: item.h,
    draggable: true,
  }
  if (item.elementType === 'watermark') {
    // Watermark: opacity and rotation are element-level, applied on group
    if (el?.opacity != null) cfg.opacity = el.opacity
    if (el?.rotation != null) cfg.rotation = el.rotation
  }
  return cfg
}

// Event handlers
function onElementClick(elementId, event) {
  event.cancelBubble = true
  props.editor.selectElement(elementId)
  emit('select', elementId)

  // Attach transformer
  nextTick(() => {
    const transformer = props.editor.transformerRef.value?.getNode()
    const stage = stageRef.value?.getStage()
    if (transformer && stage) {
      const node = stage.findOne('#' + elementId)
      if (node) {
        transformer.nodes([node])
        transformer.getLayer()?.batchDraw()
      }
    }
  })
}

function onElementDragEnd(elementId, event) {
  props.editor.onDragEnd(elementId, event)
}

function onElementTransformEnd(elementId, event) {
  props.editor.onTransformEnd(elementId, event)
}

function onStageClick(event) {
  if (event.target === event.target.getStage()) {
    props.editor.clearSelection()
    emit('deselect')
  }
}
</script>

<style scoped>
.konva-canvas-wrapper {
  position: relative;
  overflow: auto;
  background: #0a0a18;
  border-radius: 8px;
  border: 1.5px solid rgba(255,255,255,.06);
}
.canvas-bg-layer {
  position: absolute;
  top: 0; left: 0;
  pointer-events: none;
}
.canvas-frame {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
  border-radius: 8px;
  display: block;
}
.canvas-video-hidden {
  display: none;
}
.canvas-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #1e1e3a;
  font-size: clamp(12px, 2vw, 18px);
  font-weight: 700;
  letter-spacing: 4px;
}
.canvas-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background-image:
    linear-gradient(rgba(167,139,250,.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(167,139,250,.04) 1px, transparent 1px);
  background-size: 10% 10%;
}
.konva-overlay {
  position: absolute;
  top: 0; left: 0;
  cursor: crosshair;
}
</style>
