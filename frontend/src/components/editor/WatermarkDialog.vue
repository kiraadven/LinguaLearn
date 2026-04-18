<template>
  <Teleport to="body">
    <div v-if="visible" class="dialog-overlay" @click.self="$emit('close')">
      <div class="dialog-box">
        <div class="dialog-title">💧 {{ tr('watermark_add', 'Add Watermark') }}</div>

        <div class="form-group">
          <label class="label">{{ tr('props_watermark_text', 'Watermark Text') }}</label>
          <input type="text" class="input" v-model="text" placeholder="LinguaLearn" @keydown.enter="confirm">
        </div>

        <div class="form-group">
          <label class="label">{{ tr('props_font_size', 'Font Size') }}: {{ fontSize }}px</label>
          <input type="range" class="slider" v-model.number="fontSize" min="8" max="160" step="1">
        </div>

        <div class="form-group">
          <label class="label">{{ tr('props_opacity', 'Opacity') }}: {{ Math.round(opacity * 100) }}%</label>
          <input type="range" class="slider" v-model.number="opacity" min="0.05" max="1" step="0.05">
        </div>

        <div class="form-group">
          <label class="label">{{ tr('props_rotation', 'Rotation') }}: {{ rotation }}°</label>
          <input type="range" class="slider" v-model.number="rotation" min="-180" max="180" step="5">
        </div>

        <div class="form-group">
          <label class="label">{{ tr('create_color', 'Color') }}</label>
          <input type="color" v-model="color" style="width:40px;height:28px;border:none;cursor:pointer">
        </div>

        <div class="dialog-actions">
          <button class="btn-cancel" @click="$emit('close')">{{ tr('create_cancel', 'Cancel') }}</button>
          <button class="btn-confirm" @click="confirm">{{ tr('watermark_confirm_add', 'Add') }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from '../../i18n.js'

defineProps({
  visible: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'add'])

const text = ref('LinguaLearn')
const fontSize = ref(20)
const opacity = ref(0.3)
const rotation = ref(-30)
const color = ref('#ffffff')
const { t } = useI18n()

function tr(key, fallback = '') {
  return ((t.value?.[key]) ?? fallback) || key
}

function confirm() {
  emit('add', {
    text: text.value,
    fontSize: fontSize.value,
    opacity: opacity.value,
    rotation: rotation.value,
    color: color.value,
  })
  emit('close')
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed; inset: 0; z-index: 300;
  background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
}
.dialog-box {
  background: var(--bg2, #1a1a2e);
  border: 1px solid rgba(255,255,255,.1);
  border-radius: 12px;
  padding: 24px;
  min-width: 320px;
  max-width: 400px;
}
.dialog-title {
  font-size: 16px; font-weight: 700; color: var(--text1);
  margin-bottom: 16px;
}
.form-group { margin-bottom: 12px; }
.dialog-actions {
  display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px;
}
.btn-cancel {
  padding: 8px 16px; border-radius: 8px;
  background: transparent; border: 1px solid rgba(255,255,255,.1);
  color: var(--text2); cursor: pointer; font-size: 13px;
}
.btn-confirm {
  padding: 8px 16px; border-radius: 8px;
  background: var(--accent, #7c3aed); border: none;
  color: #fff; cursor: pointer; font-size: 13px; font-weight: 600;
}
</style>
