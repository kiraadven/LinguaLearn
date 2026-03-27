<template>
  <div class="color-row">
    <label class="label">{{ label }}</label>
    <div style="display:flex;align-items:center;gap:6px">
      <input type="color" :value="hexValue" @input="onColorInput($event.target.value)"
             style="width:28px;height:24px;border:none;padding:0;cursor:pointer;background:transparent">
      <input type="text" class="input input-sm" :value="value" @change="$emit('update', $event.target.value)"
             style="width:100%;font-size:11px">
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: String, default: '#ffffff' },
})

const emit = defineEmits(['update'])

// Extract hex from rgba or hex string for the color input
const hexValue = computed(() => {
  const v = props.value || '#ffffff'
  if (v.startsWith('#')) return v.slice(0, 7)
  // Try to extract from rgba(r,g,b,a)
  const m = v.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (m) {
    const r = parseInt(m[1]).toString(16).padStart(2, '0')
    const g = parseInt(m[2]).toString(16).padStart(2, '0')
    const b = parseInt(m[3]).toString(16).padStart(2, '0')
    return `#${r}${g}${b}`
  }
  return '#ffffff'
})

function onColorInput(hex) {
  // If original value was rgba, preserve alpha
  const v = props.value || ''
  const m = v.match(/rgba?\(\d+,\s*\d+,\s*\d+,\s*([\d.]+)\)/)
  if (m) {
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    emit('update', `rgba(${r},${g},${b},${m[1]})`)
  } else {
    emit('update', hex)
  }
}
</script>

<style scoped>
.color-row { margin-bottom: 6px; }
</style>
