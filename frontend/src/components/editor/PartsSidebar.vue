<template>
  <div class="parts-sidebar">
    <div class="sidebar-hdr">{{ tr('create_part_list', 'Part List') }}</div>

    <div v-for="(p, i) in parts" :key="p.id"
         :class="['part-chip', { active: currentPartIdx === i, dragging: dragPartId === p.id, 'drag-over': dragOverPartId === p.id && dragPartId !== p.id }]"
         draggable="true"
         @dragstart="onDragStart(p.id, $event)"
         @dragend="onDragEnd"
         @dragenter.prevent="onDragEnter(p.id)"
         @dragover.prevent
         @drop="onDrop(p.id)"
         @click="$emit('selectPart', i)">

      <!-- Header row: title + action buttons -->
      <div style="display:flex;align-items:flex-start;justify-content:space-between">
        <div class="part-chip-title" style="display:flex;align-items:center;gap:6px">
          <span class="drag-handle" :title="tr('parts_drag_sort', 'Drag to reorder')">⋮⋮</span>
          Part {{ i + 1 }}
          <span style="font-size:10px;color:var(--text3);font-weight:400">
            {{ visibleCount(p) }} {{ tr('parts_elements', 'elements') }}
          </span>
        </div>
        <div style="display:flex;gap:2px;flex-shrink:0">
          <button class="part-action-btn" @click.stop="$emit('copyPart', p.id)" :title="tr('parts_copy', 'Copy')">⿻</button>
          <button v-if="parts.length > 1" class="del-part" @click.stop="$emit('removePart', p.id)" :title="tr('parts_delete', 'Delete')">✕</button>
        </div>
      </div>

      <!-- Repeat control -->
      <div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap;align-items:center">
        <label style="font-size:11px;color:var(--text2);display:flex;align-items:center;gap:3px;cursor:pointer">
          {{ tr('create_repeat', 'Repeat') }}
          <input type="number" class="input" v-model.number="p.repeat" min="1" max="5"
                 style="width:40px;padding:3px 6px;font-size:11px;margin-bottom:0;text-align:center"
                 @click.stop>
        </label>
      </div>

      <!-- Speed slider -->
      <div style="margin-top:6px" @click.stop>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px">
          <span style="font-size:11px;color:var(--text2)">{{ tr('create_speed', 'Speed') }}</span>
          <span style="font-size:11px;font-weight:700;color:var(--accent)">{{ Number(p.speed || 1).toFixed(2) }}×</span>
        </div>
        <input type="range" v-model.number="p.speed" min="0.25" max="2.0" step="0.05"
               style="width:100%;accent-color:var(--accent);cursor:pointer" @click.stop>
        <div style="display:flex;justify-content:space-between;font-size:9px;color:var(--text3)">
          <span>0.25×</span><span>1×</span><span>2×</span>
        </div>
      </div>

      <!-- Element visibility checkboxes -->
      <div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap">
        <label v-for="el in allElements" :key="el.id"
               style="font-size:11px;display:flex;align-items:center;gap:3px;cursor:pointer"
               :style="{ color: p.elementVisibility?.[el.id] ? elementColor(el.type) : 'var(--text3)' }"
               @click.stop>
          <input type="checkbox"
                 :checked="p.elementVisibility?.[el.id]"
                 @change="$emit('toggleVisibility', p.id, el.id, $event.target.checked)"
                 :style="`accent-color:${elementColor(el.type)}`">
          {{ elementLabel(el) }}
        </label>
      </div>
    </div>

    <button class="add-part" @click="$emit('addPart')" :disabled="parts.length >= 4">
      {{ tr('create_add_part', '+ Add Part') }}
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from '../../i18n.js'

const props = defineProps({
  parts: { type: Array, required: true },
  allElements: { type: Array, required: true },
  currentPartIdx: { type: Number, default: 0 },
})

const emit = defineEmits(['selectPart', 'addPart', 'copyPart', 'removePart', 'toggleVisibility', 'movePart'])
const { t } = useI18n()

function tr(key, fallback = '') {
  return t.value?.[key] || fallback || key
}

const dragPartId = ref(null)
const dragOverPartId = ref(null)

function onDragStart(partId, e) {
  dragPartId.value = partId
  dragOverPartId.value = partId
  if (e?.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', partId)
  }
}

function onDrop(targetPartId) {
  if (!dragPartId.value || dragPartId.value === targetPartId) return
  emit('movePart', dragPartId.value, targetPartId)
  dragOverPartId.value = null
}

function onDragEnter(partId) {
  if (!dragPartId.value) return
  dragOverPartId.value = partId
}

function onDragEnd() {
  dragPartId.value = null
  dragOverPartId.value = null
}

const TYPE_COLORS = {
  subtitle: '#a78bfa',
  wordbox: '#38bdf8',
  exprbox: '#f472b6',
  watermark: '#94a3b8',
}
const TYPE_LABELS = {
  subtitle: 'create_el_subtitle',
  wordbox: 'create_el_wordbox',
  exprbox: 'create_el_exprbox',
  watermark: 'create_el_watermark',
}

function elementColor(type) {
  return TYPE_COLORS[type] || '#94a3b8'
}

function elementLabel(el) {
  return tr(TYPE_LABELS[el.type], el.type)
}

function visibleCount(part) {
  if (!part.elementVisibility) return 0
  return Object.values(part.elementVisibility).filter(Boolean).length
}
</script>

<style scoped>
.parts-sidebar {
  width: 200px;
  min-width: 170px;
  padding: 10px;
  border-right: 1px solid rgba(255,255,255,.06);
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
.part-chip {
  background: rgba(255,255,255,.03);
  border: 1px solid rgba(255,255,255,.06);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all .15s;
}
.part-chip.dragging { opacity: .55; }
.part-chip.drag-over {
  border-color: rgba(167,139,250,.7);
  box-shadow: 0 0 0 1px rgba(167,139,250,.35) inset;
}
.part-chip.active {
  border-color: var(--accent);
  background: rgba(167,139,250,.06);
}
.part-chip-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text1);
}
.drag-handle {
  font-size: 11px;
  color: var(--text3);
  line-height: 1;
  cursor: grab;
  user-select: none;
}
.part-action-btn {
  padding: 2px 5px;
  font-size: 11px;
  border: 1px solid rgba(255,255,255,.1);
  border-radius: 4px;
  background: transparent;
  color: var(--text3);
  cursor: pointer;
}
.part-action-btn:hover { background: rgba(255,255,255,.08); color: var(--text1); }
.del-part {
  padding: 2px 5px;
  font-size: 11px;
  border: 1px solid rgba(248,113,113,.2);
  border-radius: 4px;
  background: transparent;
  color: var(--err);
  cursor: pointer;
}
.del-part:hover { background: rgba(248,113,113,.1); }
.add-part {
  width: 100%;
  padding: 8px;
  border-radius: 8px;
  border: 1px dashed rgba(167,139,250,.3);
  background: transparent;
  color: var(--accent);
  font-size: 12px;
  cursor: pointer;
  transition: all .15s;
}
.add-part:hover { background: rgba(167,139,250,.06); }
.add-part:disabled { opacity: .4; cursor: not-allowed; }
</style>
