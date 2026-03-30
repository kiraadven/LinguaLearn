<template>
  <div class="toolbar-panel">
    <!-- Drag chips for adding elements -->
    <div style="font-size:11px;color:var(--text3);margin-right:8px">{{ tr('toolbar_add_elements', 'Add Elements:') }}</div>
    <button v-for="item in elementTypes" :key="item.type"
            class="add-chip"
            :style="{ background: item.bgChip, border: `1.5px solid ${item.color}`, color: item.color }"
            @click="$emit('addElement', item.type)">
      {{ item.icon }} {{ item.label }}
    </button>

    <!-- Zoom controls -->
    <div style="margin-left:auto;display:flex;align-items:center;gap:6px">
      <!-- Animation preview button -->
      <button class="zoom-btn" @click="$emit('previewAnimation')" :title="tr('toolbar_preview_animation', 'Preview Enter Animation')" :disabled="isAnimating">
        ▶
      </button>
      <div style="width:1px;height:16px;background:rgba(255,255,255,.1);margin:0 4px" />
      <button class="zoom-btn" @click="$emit('zoomOut')">−</button>
      <span style="font-size:11px;color:var(--text3);min-width:36px;text-align:center">{{ Math.round(zoom * 100) }}%</span>
      <button class="zoom-btn" @click="$emit('zoomIn')">+</button>
      <button class="zoom-btn" @click="$emit('zoomReset')" :title="tr('toolbar_reset_zoom', 'Reset Zoom')">⟳</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from '../../i18n.js'

defineEmits(['addElement', 'zoomIn', 'zoomOut', 'zoomReset', 'previewAnimation'])

const props = defineProps({
  zoom: { type: Number, default: 1.0 },
  isAnimating: { type: Boolean, default: false },
  isMember: { type: Boolean, default: false },
})
const { t } = useI18n()

function tr(key, fallback = '') {
  return t.value?.[key] || fallback || key
}

const elementTypes = computed(() => ([
  { type: 'subtitle', label: tr('create_el_subtitle', 'Subtitle'), icon: '📝', color: '#a78bfa', bgChip: 'rgba(167,139,250,.1)' },
  { type: 'wordbox', label: tr('create_el_wordbox', 'Word Box'), icon: '📖', color: '#38bdf8', bgChip: 'rgba(56,189,248,.1)' },
  { type: 'exprbox', label: tr('create_el_exprbox', 'Expression Box'), icon: '💬', color: '#f472b6', bgChip: 'rgba(244,114,182,.1)' },
  {
    type: 'watermark',
    label: props.isMember ? tr('create_el_watermark', 'Watermark') : tr('toolbar_member_watermark', 'Upgrade to customize watermark'),
    icon: '💧',
    color: '#94a3b8',
    bgChip: 'rgba(148,163,184,.1)',
  },
]))
</script>

<style scoped>
.toolbar-panel {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255,255,255,.06);
  flex-wrap: wrap;
}
.add-chip {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
  white-space: nowrap;
}
.add-chip:hover { filter: brightness(1.2); }
.zoom-btn {
  width: 26px; height: 26px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,.1);
  background: rgba(255,255,255,.04);
  color: var(--text2);
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.zoom-btn:hover { background: rgba(255,255,255,.08); }
.zoom-btn:disabled { opacity: .4; cursor: not-allowed; }
</style>
