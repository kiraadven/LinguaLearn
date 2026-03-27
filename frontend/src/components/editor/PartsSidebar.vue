<template>
  <div class="parts-sidebar">
    <div class="sidebar-hdr">Part 列表</div>

    <div v-for="(p, i) in parts" :key="p.id"
         :class="['part-chip', { active: currentPartIdx === i }]"
         @click="$emit('selectPart', i)">

      <!-- Header row: title + action buttons -->
      <div style="display:flex;align-items:flex-start;justify-content:space-between">
        <div class="part-chip-title">
          Part {{ i + 1 }}
          <span style="font-size:10px;color:var(--text3);font-weight:400">
            {{ visibleCount(p) }} 元素
          </span>
        </div>
        <div style="display:flex;gap:2px;flex-shrink:0">
          <button class="part-action-btn" @click.stop="$emit('copyPart', p.id)" title="复制">⿻</button>
          <button v-if="parts.length > 1" class="del-part" @click.stop="$emit('removePart', p.id)" title="删除">✕</button>
        </div>
      </div>

      <!-- Repeat control -->
      <div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap;align-items:center">
        <label style="font-size:11px;color:var(--text2);display:flex;align-items:center;gap:3px;cursor:pointer">
          重复
          <input type="number" class="input" v-model.number="p.repeat" min="1" max="5"
                 style="width:40px;padding:3px 6px;font-size:11px;margin-bottom:0;text-align:center"
                 @click.stop>
        </label>
      </div>

      <!-- Speed slider -->
      <div style="margin-top:6px" @click.stop>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px">
          <span style="font-size:11px;color:var(--text2)">速度</span>
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
      + 添加 Part
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  parts: { type: Array, required: true },
  allElements: { type: Array, required: true },
  currentPartIdx: { type: Number, default: 0 },
})

defineEmits(['selectPart', 'addPart', 'copyPart', 'removePart', 'toggleVisibility'])

const TYPE_COLORS = {
  subtitle: '#a78bfa',
  wordbox: '#38bdf8',
  exprbox: '#f472b6',
  watermark: '#94a3b8',
}
const TYPE_LABELS = {
  subtitle: '字幕',
  wordbox: '词框',
  exprbox: '表达框',
  watermark: '水印',
}

function elementColor(type) {
  return TYPE_COLORS[type] || '#94a3b8'
}

function elementLabel(el) {
  return TYPE_LABELS[el.type] || el.type
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
.part-chip.active {
  border-color: var(--accent);
  background: rgba(167,139,250,.06);
}
.part-chip-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text1);
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
