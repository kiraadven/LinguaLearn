<template>
  <div class="style-theme-panel">
    <!-- Style Gallery -->
    <div style="margin-bottom:20px">
      <div class="section-title">{{ tr('create_visual_style', 'Visual Style') }}</div>
      <div class="style-gallery">
        <div v-for="theme in themes" :key="theme.id"
             :class="['style-card-item', { active: currentStyleId === theme.id }]"
             @click="$emit('applyTheme', theme.id)"
            :title="theme.desc">
          <div class="style-swatch-bg" :style="{ background: theme.preview_colors?.bg || '#111' }">
            <span class="style-swatch-src" :style="{ color: theme.preview_colors?.src || '#fff' }">Aa</span>
            <span class="style-swatch-tgt" :style="{ color: theme.preview_colors?.tgt || '#aaa' }">{{ tr('style_translation_mark', 'Tr') }}</span>
            <div class="style-swatch-box" :style="{ background: theme.preview_colors?.box_bg || '#222' }">
              <span :style="{ color: theme.preview_colors?.src || '#fff', fontSize: '8px', fontWeight: 600 }">KEY</span>
            </div>
          </div>
          <div class="style-card-name">{{ theme.name }}</div>
          <div v-if="currentStyleId === theme.id" class="style-check">✓</div>
        </div>
      </div>

    </div>

    <!-- Font Picker -->
    <div>
      <div class="section-title">{{ tr('create_font', 'Font') }}</div>
      <div class="font-grid">
        <div v-for="font in fontList" :key="font.val"
             :class="['font-chip', { active: currentFont === font.val }]"
             @click="$emit('setFont', font.val)">
          <span class="font-sample" :style="{ fontFamily: font.css }">AaBb</span>
          <span class="font-label">{{ font.label }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { FONTS } from '@shared/font-registry.js'
import { getThemeList } from '@shared/theme-mapper.js'
import { useI18n } from '../../i18n.js'

defineProps({
  currentStyleId: { type: String, default: 'ink_wash' },
  currentFont: { type: String, default: 'system' },
})

defineEmits(['applyTheme', 'setFont'])
const { t } = useI18n()

function tr(key, fallback = '') {
  return t.value?.[key] || fallback || key
}

const themes = getThemeList()
const fontList = FONTS
</script>

<style scoped>
.section-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text2);
  margin-bottom: 12px;
}
.style-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
  gap: 8px;
}
.style-card-item {
  border: 1.5px solid rgba(255,255,255,.06);
  border-radius: 8px;
  padding: 6px;
  cursor: pointer;
  transition: all .15s;
  position: relative;
  background: rgba(255,255,255,.02);
}
.style-card-item:hover { border-color: rgba(167,139,250,.3); }
.style-card-item.active { border-color: var(--accent); background: rgba(167,139,250,.06); }
.style-swatch-bg {
  width: 100%;
  aspect-ratio: 16/9;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 4px;
}
.style-swatch-src { font-size: 14px; font-weight: 700; }
.style-swatch-tgt { font-size: 10px; }
.style-swatch-box { border-radius: 3px; margin-top: 4px; padding: 2px 5px; }
.style-card-name {
  font-size: 10px;
  text-align: center;
  color: var(--text2);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.style-check {
  position: absolute;
  top: 4px; right: 4px;
  width: 16px; height: 16px;
  background: var(--accent);
  color: #fff;
  border-radius: 50%;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.bg-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text2);
  cursor: pointer;
}
.bg-toggle-hint {
  width: 100%;
  font-size: 10px;
  color: var(--text3);
  margin-left: 20px;
}
.anim-btn {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,.1);
  background: rgba(255,255,255,.03);
  color: var(--text2);
  font-size: 12px;
  cursor: pointer;
  transition: all .15s;
}
.anim-btn:hover { border-color: rgba(167,139,250,.3); }
.anim-btn.active { border-color: var(--accent); background: rgba(167,139,250,.1); color: var(--accent); }
.font-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 6px;
}
.font-chip {
  padding: 8px 8px 6px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,.06);
  background: rgba(255,255,255,.02);
  cursor: pointer;
  transition: all .15s;
  text-align: center;
}
.font-chip:hover { border-color: rgba(167,139,250,.3); }
.font-chip.active { border-color: var(--accent); background: rgba(167,139,250,.06); }
.font-sample {
  display: block;
  font-size: 16px;
  color: var(--text1);
  margin-bottom: 3px;
  min-height: 24px;
  line-height: 1.4;
}
.font-label { font-size: 9px; color: var(--text3); }
</style>
