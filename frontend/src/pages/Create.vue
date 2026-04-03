<template>
  <div class="create-page page-inner">
    <div class="page-header">
      <h1>{{ t.create_title }}</h1>
      <p>{{ t.create_subtitle }}</p>
    </div>

    <div v-if="!isLoggedIn" class="empty-state">
      <div style="font-size:64px">🔒</div>
      <p style="font-size:18px;font-weight:700">{{ t.create_login_required }}</p>
      <button class="btn-primary" @click="openAuth()">{{ t.nav_login_register }}</button>
    </div>

    <div v-else>
      <div class="member-tip card">
        <div class="member-tip-left">
          <img src="/premium-badge.svg" alt="VIP" class="member-tip-logo">
          <div>
            <div class="member-tip-title">
              {{ isMember ? t.create_member_tier_member : t.create_member_tier_free }}
            </div>
            <div class="member-tip-sub" v-if="user?.membership">
              {{ t.create_member_today_usage }} {{ user.membership.usage?.videos_generated_today ?? 0 }} {{ t.create_count_unit }}
              <template v-if="user.membership.limits?.daily_video_limit !== null">
                / {{ t.create_member_daily_limit }} {{ user.membership.limits?.daily_video_limit }} {{ t.create_count_unit }}
              </template>
              ，{{ t.create_member_max_minutes }} {{ Math.floor((user.membership.limits?.max_video_seconds || 300) / 60) }} {{ t.create_minute }}
            </div>
          </div>
        </div>
        <button class="btn-ghost" style="font-size:12px;padding:7px 12px" @click="openMembership()">
          {{ isMember ? t.nav_manage_membership : t.nav_upgrade_membership }}
        </button>
      </div>

      <!-- Preset bar -->
      <div class="preset-bar" v-if="presets.length>0">
        <select class="input" v-model="selectedPresetId" style="flex:1;max-width:240px;margin-bottom:0;font-size:13px">
          <option value="">— {{ t.create_select_preset }} —</option>
          <option v-for="p in presets" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <button class="btn-ghost" style="padding:7px 12px;font-size:12px" @click="applyPreset">{{ t.create_load }}</button>
        <button class="btn-ghost" style="padding:7px 10px;font-size:12px;color:var(--err);border-color:rgba(248,113,113,.3)" @click="deletePreset">{{ t.create_delete }}</button>
      </div>

      <div v-if="!jobRunning || jobDone">
        <!-- ── SECTION 1: Basic Config ── -->
        <div class="section-label">{{ t.create_basic_config }}</div>
        <div class="config-grid">
          <!-- Upload -->
          <div class="card config-card">
            <div class="card-title">📁 {{ t.create_video_upload }}</div>
            <div :class="['upload-zone',{over:dragOver}]"
                 @click="$refs.fileInput.click()"
                 @dragover.prevent="dragOver=true"
                 @dragleave="dragOver=false"
                 @drop.prevent="onDrop">
              <input ref="fileInput" type="file" accept="video/*" style="display:none" @change="onFileChange">
              <div v-if="!selectedFile" style="text-align:center">
                <div style="font-size:44px;margin-bottom:10px">📹</div>
                <div style="font-weight:600;margin-bottom:4px">{{ t.create_click_or_drag }}</div>
                <div style="font-size:12px;color:var(--text3)">{{ t.create_video_formats }}</div>
              </div>
              <div v-else style="width:100%">
                <video v-if="videoPreviewUrl" :src="videoPreviewUrl" controls muted playsinline
                  style="width:100%;border-radius:8px;max-height:180px;object-fit:contain;background:#000;display:block;margin-bottom:8px"
                  @click.stop></video>
                <div style="display:flex;align-items:center;gap:8px;padding:0 4px">
                  <div style="font-size:22px">✅</div>
                  <div style="flex:1;min-width:0">
                    <div style="font-weight:600;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ selectedFile.name }}</div>
                    <div style="font-size:11px;color:var(--text3)">{{ fmtSize(selectedFile.size) }}</div>
                  </div>
                  <button style="font-size:12px;color:var(--err);background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);border-radius:6px;padding:4px 8px;cursor:pointer"
                    @click.stop="clearFile">✕ {{ t.create_remove }}</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Language -->
          <div class="card config-card">
            <div class="card-title">🌐 {{ t.create_lang_resolution }}</div>
            <label class="label">{{ t.create_source_lang }}</label>
            <select class="input" v-model="srcLang" @change="tl.timeline.sourceLang=srcLang" style="margin-bottom:12px">
              <option v-for="l in langs" :key="l.code" :value="l.code">{{ l.flag }} {{ l.native_name }}</option>
            </select>
            <label class="label">{{ t.create_target_lang }}</label>
            <select class="input" v-model="tgtLang" @change="tl.timeline.targetLang=tgtLang" style="margin-bottom:12px">
              <option v-for="l in langs" :key="l.code" :value="l.code">{{ l.flag }} {{ l.native_name }}</option>
            </select>
            <label class="label">{{ t.create_resolution }}</label>
            <select class="input" v-model="resolution" @change="onResolutionChange">
              <option value="1080p">{{ t.create_resolution_1080p }}</option>
              <option value="720p">{{ t.create_resolution_720p }}</option>
            </select>
          </div>

          <!-- Words -->
          <div class="card config-card">
            <div class="card-title">📚 {{ t.create_vocab_expr }}</div>
            <label class="label">{{ t.create_max_words }}：{{ numWords===0?t.create_unlimited:`${numWords} ${t.create_per_sentence}` }}</label>
            <input type="range" class="slider" v-model.number="numWords" @input="tl.timeline.numWords=numWords" min="0" max="12" style="margin-bottom:20px">
            <label class="label">{{ t.create_max_exprs }}：{{ numExprs===0?t.create_unlimited:`${numExprs} ${t.create_per_sentence}` }}</label>
            <input type="range" class="slider" v-model.number="numExprs" @input="tl.timeline.numExprs=numExprs" min="0" max="8">
          </div>
        </div>

        <!-- ── SECTION 2: Canvas Layout Editor (Konva) ── -->
        <div class="section-label">{{ t.create_layout }}
          <span style="font-size:11px;color:var(--text3);font-weight:400;margin-left:8px">{{ t.create_layout_help }}</span>
        </div>
        <div class="card canvas-card">
          <div class="canvas-editor-wrap">
            <!-- Left: Parts sidebar -->
            <PartsSidebar
              :parts="tl.parts.value"
              :allElements="tl.elements.value"
              :currentPartIdx="currentPartIdx"
              @selectPart="currentPartIdx=$event"
              @addPart="onAddPart"
              @copyPart="onCopyPart"
              @removePart="onRemovePart"
              @movePart="onMovePart"
              @toggleVisibility="(partId, elId, vis) => tl.setPartVisibility(partId, elId, vis)"
            />

            <!-- Center: Konva Canvas -->
            <div class="canvas-center">
              <ToolbarPanel
                :zoom="editor.canvasZoom.value"
                :isAnimating="animPreview.isPlaying.value"
                :isMember="isMember"
                @addElement="onAddElement"
                @zoomIn="editor.zoomIn()"
                @zoomOut="editor.zoomOut()"
                @zoomReset="editor.zoomReset()"
                @previewAnimation="onPreviewAnimation"
              />
              <div class="canvas-outer">
                <KonvaCanvas
                  :videoSrc="videoPreviewUrl"
                  :timeline="tl.timeline"
                  :currentPartId="currentPartId"
                  :previewContent="tl.previewContent.value"
                  :editor="editor"
                  :zoom="editor.canvasZoom.value"
                  @select="editor.selectElement($event)"
                  @deselect="editor.clearSelection()"
                />
              </div>
            </div>

            <!-- Right: Properties panel -->
            <PropertiesPanel
              :selectedElement="editor.selectedElement.value"
              :watermarkLocked="selectedWatermarkLocked"
              :sourceLang="srcLang"
              :targetLang="tgtLang"
              :numWords="numWords"
              :numExprs="numExprs"
              :applyPatch="patchCurrentPartElement"
              :applyStylePatch="patchCurrentPartElementStyle"
              @update="onUpdateElement"
              @updateStyle="onUpdateElementStyle"
              @setAnimation="(id, type) => onSetAnimation(id, type)"
              @previewAnimation="onPreviewAnimation"
              @remove="onRemoveElement"
            />
          </div>
        </div>

        <!-- ── SECTION 3: Style Theme ── -->
        <div class="section-label">{{ t.create_style_theme }}
          <span style="font-size:11px;color:var(--text3);font-weight:400;margin-left:8px">{{ t.create_style_help }}</span>
        </div>
        <div class="card style-card">
          <StyleThemePanel
            :currentStyleId="tl.timeline.styleId"
            :currentFont="tl.timeline.defaultFont"
            @applyTheme="onApplyTheme"
            @setFont="tl.setGlobalFont($event)"
          />
        </div>

        <!-- ── SUBMIT ── -->
        <div class="submit-row">
          <button class="btn-primary" style="font-size:15px;padding:14px 40px" :disabled="submitting" @click="submit">
            {{ submitting ? t.create_submit_loading : `🚀 ${t.create_submit}` }}
          </button>
          <div class="preset-save-wrap">
            <button class="btn-ghost" style="padding:13px 18px;font-size:13px" @click="openPresetSaveDialog">
              💾 {{ t.create_save_preset }}
            </button>
            <div class="preset-save-tip">{{ t.create_preset_desc }}</div>
          </div>
        </div>
      </div>

      <!-- Naming Dialog -->
      <Teleport to="body">
        <div v-if="showNameDialog" class="modal-overlay" @click.self="onNameCancel" style="z-index:300">
          <div class="modal-box" style="max-width:420px">
            <button class="modal-close" @click="onNameCancel">✕</button>
            <div style="font-size:20px;font-weight:800;margin-bottom:6px;color:var(--text)">{{ t.create_naming_title }}</div>
            <div style="font-size:13px;color:var(--text3);margin-bottom:20px">{{ t.create_name_desc }}</div>
            <label class="label">{{ t.create_naming_placeholder }}</label>
            <input class="input" v-model="videoName" :placeholder="t.create_naming_placeholder" @keyup.enter="onNameConfirm" style="margin-bottom:20px">
            <div style="display:flex;gap:10px">
              <button class="btn-primary" style="flex:1;padding:12px" @click="onNameConfirm">{{ t.create_confirm_start }}</button>
              <button class="btn-ghost" style="padding:12px 20px" @click="onNameCancel">{{ t.create_cancel }}</button>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- Preset Name Dialog -->
      <Teleport to="body">
        <div v-if="showPresetNameDialog" class="modal-overlay" @click.self="onPresetSaveCancel" style="z-index:301">
          <div class="modal-box" style="max-width:440px">
            <button class="modal-close" @click="onPresetSaveCancel">✕</button>
            <div style="font-size:20px;font-weight:800;margin-bottom:6px;color:var(--text)">{{ t.create_save_preset }}</div>
            <div style="font-size:13px;color:var(--text3);margin-bottom:18px">
              {{ t.create_preset_desc }}
            </div>
            <label class="label">{{ t.create_preset_name }}</label>
            <input
              ref="presetNameInput"
              class="input"
              v-model="presetName"
              :placeholder="t.create_preset_name"
              @keyup.enter="savePreset"
              style="margin-bottom:18px"
            >
            <div style="display:flex;gap:10px">
              <button class="btn-primary" style="flex:1;padding:12px" @click="savePreset">{{ t.create_save_preset_btn }}</button>
              <button class="btn-ghost" style="padding:12px 20px" @click="onPresetSaveCancel">{{ t.create_cancel }}</button>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- Watermark Dialog -->
      <WatermarkDialog :visible="showWatermarkDialog" @close="showWatermarkDialog=false" @add="onAddWatermark" />

      <!-- Progress -->
      <div v-if="jobRunning && !jobDone" class="card progress-card">
        <div class="card-title">{{ t.create_progress }}</div>
        <div class="step-bar">
          <template v-for="i in 5" :key="i">
            <div :class="['step-dot', i<currentStep?'done':i===currentStep?'active':'']">{{ i }}</div>
            <div v-if="i<5" :class="['step-ln', i<currentStep?'done':'']"></div>
          </template>
        </div>
        <div class="cur-step"><span class="pulse-dot"></span><span>{{ stepName }}</span></div>
        <div v-if="currentStep>=5" style="margin-top:14px">
          <PBar :label="t.create_segment_render" :pct="clipsPct" color="linear-gradient(90deg,var(--accent),var(--accent2))"/>
          <PBar :label="t.create_video_write" :pct="writePct" color="linear-gradient(90deg,var(--accent3),var(--accent4))" style="margin-top:10px"/>
        </div>
        <div class="log-box" ref="logBox">
          <div v-for="(l,i) in logs" :key="i" :class="['log-line',logClass(l)]">{{ l }}</div>
        </div>
        <div style="margin-top:14px">
          <button class="btn-ghost" style="padding:8px 18px;font-size:13px;color:var(--err);border-color:rgba(248,113,113,.3)" @click="cancelJob">{{ t.create_cancel_job }}</button>
        </div>
      </div>

      <!-- Done -->
      <div v-if="jobDone" class="card" style="padding:36px;text-align:center;margin-top:20px">
        <div style="font-size:52px;margin-bottom:12px">🎉</div>
        <div style="font-size:18px;font-weight:700;margin-bottom:8px">{{ t.create_done }}</div>
        <button class="btn-primary" @click="$router.push('/results')">{{ t.create_view_results }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted, nextTick, watch } from 'vue'
import { useAuth } from '../composables/useAuth.js'
import { apiFetch } from '../composables/useApi.js'
import { useI18n } from '../i18n.js'
import { useTimeline } from '../composables/useTimeline.js'
import { useKonvaEditor } from '../composables/useKonvaEditor.js'
import { useAnimationPreview } from '../composables/useAnimationPreview.js'
import { STYLE_THEMES } from '@shared/theme-mapper.js'

// Components
import KonvaCanvas from '../components/editor/KonvaCanvas.vue'
import PartsSidebar from '../components/editor/PartsSidebar.vue'
import PropertiesPanel from '../components/editor/PropertiesPanel.vue'
import StyleThemePanel from '../components/editor/StyleThemePanel.vue'
import ToolbarPanel from '../components/editor/ToolbarPanel.vue'
import WatermarkDialog from '../components/editor/WatermarkDialog.vue'

const { isLoggedIn, user, refreshMembership } = useAuth()
const { t } = useI18n()
const openAuth = inject('openAuth', () => {})
const openMembership = inject('openMembership', () => {})
const languagePrefs = inject('languagePrefs', null)
const toast    = inject('toast')

function tr(key, fallback = '') {
  return ((t.value?.[key]) ?? fallback) || key
}

function localPref(key) {
  try {
    return localStorage.getItem(key) || ''
  } catch {
    return ''
  }
}

const familiarFromPref = languagePrefs?.familiarLang?.value || localPref('ll_familiar_lang') || 'zh-Hans'
const learningFromPref = languagePrefs?.learningLang?.value || localPref('ll_learning_lang') || (familiarFromPref === 'en' ? 'zh-Hans' : 'en')
const initialLearning = learningFromPref === familiarFromPref
  ? (familiarFromPref === 'en' ? 'zh-Hans' : 'en')
  : learningFromPref

// ── Inline sub-component ──
const PBar = {
  props: ['label','pct','color'],
  template: `<div>
    <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text2);margin-bottom:6px;font-weight:600">
      <span>{{ label }}</span><span>{{ pct }}%</span>
    </div>
    <div style="height:6px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden">
      <div :style="{width:pct+'%',height:'100%',borderRadius:'3px',background:color,transition:'width .5s',boxShadow:'0 0 8px rgba(167,139,250,.4)'}"></div>
    </div>
  </div>`
}

// ── Timeline (single source of truth) ──
const tl = useTimeline()

// ── Editor State — declared before editor so closure is safe ──
const currentPartIdx = ref(0)
const currentPartId = computed(() => tl.timeline.parts[currentPartIdx.value]?.id || '')
const currentAnimation = ref('fade')
const isMember = computed(() => user.value?.membership?.tier === 'member')
const selectedWatermarkLocked = computed(() => isLockedWatermarkId(editor.selectedElement.value?.id))

const editor = useKonvaEditor(tl, () => currentPartId.value)
const animPreview = useAnimationPreview(editor.stageRef)

// ── Basic Config State ──
const fileInput    = ref(null)
const selectedFile = ref(null)
const videoPreviewUrl = ref('')
const dragOver     = ref(false)
const langs        = ref([])
const srcLang      = ref(initialLearning)
const tgtLang      = ref(familiarFromPref)
const resolution   = ref('1080p')
const numWords     = ref(6)
const numExprs     = ref(4)

// Sync basic config → timeline
watch(srcLang, v => { tl.timeline.sourceLang = v }, { immediate: true })
watch(tgtLang, v => { tl.timeline.targetLang = v }, { immediate: true })
watch(numWords, v => { tl.timeline.numWords = v }, { immediate: true })
watch(numExprs, v => { tl.timeline.numExprs = v }, { immediate: true })

// Clear selection when switching parts so transformer doesn't persist on hidden elements
watch(currentPartId, () => editor.clearSelection())

// ── Dialogs ──
const showWatermarkDialog = ref(false)
const showPresetNameDialog = ref(false)
const presetNameInput = ref(null)

function ensureFreeDefaultWatermark() {
  if (isMember.value) return

  // 非会员编辑器中不显示任何水印（成片由后端自动注入默认 LinguaLearn 水印）
  const watermarkEls = tl.timeline.elements.filter(e => e.type === 'watermark')
  if (!watermarkEls.length) return
  for (const el of watermarkEls) {
    if (editor.selectedElementId.value === el.id) {
      editor.clearSelection()
    }
    tl.removeElement(el.id)
  }
}

function isLockedWatermarkId(elementId) {
  if (isMember.value) return false
  const el = tl.timeline.elements.find(e => e.id === elementId)
  return el?.type === 'watermark'
}

// ── Element Operations ──

function onAddElement(type) {
  if (type === 'watermark') {
    if (!isMember.value) {
      ensureFreeDefaultWatermark()
      toast(tr('create_watermark_member_only', 'Custom watermark is for members only'), 'warn')
      openMembership()
      return
    }
    showWatermarkDialog.value = true
    return
  }
  // Check if element type already exists — add to current part if so
  const existing = tl.timeline.elements.find(e => e.type === type)
  if (existing) {
    const partId = currentPartId.value
    tl.setPartVisibility(partId, existing.id, true)
    editor.selectElement(existing.id)
    return
  }

  const el = tl.addElement(type)
  if (el) {
    // Make visible in current part
    tl.setPartVisibility(currentPartId.value, el.id, true)
    editor.selectElement(el.id)
  }
}

function onAddWatermark(config) {
  if (!isMember.value) {
    ensureFreeDefaultWatermark()
    toast(tr('create_watermark_no_custom', 'Non-members cannot customize watermark'), 'warn')
    openMembership()
    return
  }
  const el = tl.addElement('watermark', {
    opacity: config.opacity,
    rotation: config.rotation,
    style: {
      text: config.text,
      fontSize: config.fontSize,
      color: config.color,
    },
  })
  if (el) {
    // Watermarks visible in all parts
    for (const p of tl.timeline.parts) {
      tl.setPartVisibility(p.id, el.id, true)
    }
  }
}

function onRemoveElement(elementId) {
  if (isLockedWatermarkId(elementId)) {
    toast(tr('create_watermark_default_locked', 'Default watermark can only be removed by members'), 'warn')
    openMembership()
    return
  }
  if (editor.selectedElementId.value === elementId) {
    editor.clearSelection()
  }
  tl.removeElement(elementId)
}

function onAddPart() {
  const newPart = tl.addPart()
  if (newPart) {
    // Auto-switch canvas to the newly created part
    currentPartIdx.value = tl.timeline.parts.length - 1
    editor.clearSelection()
    ensureFreeDefaultWatermark()
  }
}

function onCopyPart(partId) {
  const copy = tl.copyPart(partId)
  if (copy) {
    currentPartIdx.value = tl.timeline.parts.findIndex(p => p.id === copy.id)
    editor.clearSelection()
    ensureFreeDefaultWatermark()
  }
}

function onRemovePart(partId) {
  tl.removePart(partId)
  if (currentPartIdx.value >= tl.timeline.parts.length) {
    currentPartIdx.value = tl.timeline.parts.length - 1
  }
}

function onMovePart(partId, targetPartId) {
  const selectedId = currentPartId.value
  tl.movePart(partId, targetPartId)
  const nextIdx = tl.timeline.parts.findIndex(p => p.id === selectedId)
  if (nextIdx >= 0) currentPartIdx.value = nextIdx
}

function onUpdateElement(id, patch) {
  patchCurrentPartElement(id, patch)
}

function onUpdateElementStyle(id, style) {
  patchCurrentPartElementStyle(id, style)
}

function patchCurrentPartElement(id, patch) {
  if (isLockedWatermarkId(id)) {
    ensureFreeDefaultWatermark()
    toast(tr('create_watermark_member_only_short', 'Default watermark can only be edited by members'), 'warn')
    return
  }
  const partId = currentPartId.value || tl.timeline.parts[0]?.id
  if (!partId || !id || !patch) return
  tl.updatePartElement(partId, id, patch)
}

function patchCurrentPartElementStyle(id, style) {
  patchCurrentPartElement(id, { style })
}

// ── Style Theme ──

function onApplyTheme(styleId) {
  tl.applyStyleTheme(styleId)
  currentAnimation.value = STYLE_THEMES[styleId]?.defaultAnimation || 'fade'
}

// elementId = null means apply to all; specific id = that element only
function onSetAnimation(elementId, animType) {
  currentAnimation.value = animType
  const partId = currentPartId.value
  if (elementId) {
    tl.updatePartElement(partId, elementId, { animation: { enter: { type: animType } } })
  } else {
    for (const el of tl.timeline.elements) {
      if (['subtitle', 'wordbox', 'exprbox'].includes(el.type)) {
        tl.updatePartElement(partId, el.id, { animation: { enter: { type: animType } } })
      }
    }
  }
}

function onResolutionChange() {
  tl.timeline.resolution = resolution.value === '1080p'
    ? { width: 1920, height: 1080 }
    : { width: 1280, height: 720 }
}

async function onPreviewAnimation(elementId) {
  const stageComp = editor.stageRef.value
  const stage = stageComp?.getStage?.() || stageComp
  if (!stage) { toast(tr('create_canvas_not_ready', 'Canvas is not initialized yet'), 'warn'); return }

  const Konva = (await import('konva')).default

  let elementNodes = []

  if (elementId) {
    // Preview single element
    const el = tl.getPartElement(currentPartId.value, elementId) || tl.getElementById(elementId)
    const node = stage.findOne('#' + elementId)
    if (el && node) elementNodes = [{ nodeRef: node, animation: el.animation }]
  } else {
    // Preview all content elements
    const part = tl.timeline.parts.find(p => p.id === currentPartId.value)
    for (const el of tl.timeline.elements) {
      if (!['subtitle', 'wordbox', 'exprbox'].includes(el.type)) continue
      if (part && !part.elementVisibility?.[el.id]) continue
      const node = stage.findOne('#' + el.id)
      const merged = tl.getPartElement(currentPartId.value, el.id) || el
      if (node) elementNodes.push({ nodeRef: node, animation: merged.animation })
    }
  }

  if (elementNodes.length === 0) { toast(tr('create_no_preview_elements', 'No elements available for preview'), 'warn'); return }

  animPreview.resetNodes(elementNodes)
  await animPreview.playEnterAnimation(elementNodes, Konva)
  animPreview.resetNodes(elementNodes)
}

// ── Presets ──
const presets = ref([])
const selectedPresetId = ref('')
const presetName       = ref('')

function openPresetSaveDialog() {
  presetName.value = ''
  showPresetNameDialog.value = true
  nextTick(() => presetNameInput.value?.focus?.())
}

function onPresetSaveCancel() {
  showPresetNameDialog.value = false
}

async function loadPresets() {
  if (!isLoggedIn.value) return
  try {
    const d = await apiFetch('/api/config/presets')
    presets.value = d.presets||[]
  } catch {}
}

async function savePreset() {
  const name = presetName.value.trim()
  if (!name) { toast(tr('create_input_preset_name', 'Please enter a preset name'),'warn'); return }
  const cfg = tl.toJSON() // Save entire timeline JSON as preset
  const fd = new FormData()
  fd.append('name', name)
  fd.append('config_json', JSON.stringify(cfg))
  try {
    await fetch('/api/config/presets', { method:'POST',
      headers:{ Authorization:'Bearer '+localStorage.getItem('ll_token') }, body:fd })
    toast(`${tr('create_save_preset', 'Save as Preset')} "${name}"`, 'ok')
    presetName.value = ''
    showPresetNameDialog.value = false
    await loadPresets()
  } catch(e) { toast(tr('create_preset_save_failed', 'Save failed'),'err') }
}

function applyPreset() {
  const id = parseInt(selectedPresetId.value)
  const p = presets.value.find(p=>p.id===id)
  if (!p) { toast(tr('create_select_preset_first', 'Please select a preset first'),'warn'); return }
  try {
    const cfg = JSON.parse(p.config_json)
    // Detect format: if cfg.version exists, it's new timeline format
    if (cfg.version) {
      tl.fromJSON(cfg)
    } else {
      // Legacy format — migrate
      tl.fromLegacy(cfg)
    }
    // Sync local state from timeline
    srcLang.value = tl.timeline.sourceLang
    tgtLang.value = tl.timeline.targetLang
    resolution.value = tl.timeline.resolution.width >= 1920 ? '1080p' : '720p'
    numWords.value = tl.timeline.numWords
    numExprs.value = tl.timeline.numExprs
    ensureFreeDefaultWatermark()
    toast(`${tr('create_load', 'Load')} "${p.name}"`,'ok')
  } catch { toast(tr('create_preset_load_failed', 'Load failed'),'err') }
}

async function deletePreset() {
  const id = parseInt(selectedPresetId.value)
  if (!id) { toast(tr('create_select_preset_first', 'Please select a preset first'),'warn'); return }
  const p = presets.value.find(p=>p.id===id)
  if (!confirm(`${tr('create_delete', 'Delete')} "${p?.name}"?`)) return
  try {
    await fetch(`/api/config/presets/${id}`, { method:'DELETE',
      headers:{ Authorization:'Bearer '+localStorage.getItem('ll_token') } })
    selectedPresetId.value = ''; toast(tr('create_preset_deleted', 'Deleted'),'ok'); await loadPresets()
  } catch { toast(tr('create_preset_delete_failed', 'Delete failed'),'err') }
}

// ── Submit & Progress ──
const jobRunning  = ref(false)
const jobDone     = ref(false)
const submitting  = ref(false)
const currentJobId= ref(null)
const currentStep = ref(0)
const stepName    = ref(tr('create_preparing', 'Preparing...'))
const clipsPct    = ref(0)
const writePct    = ref(0)
const logs        = ref([])
const logBox      = ref(null)
const showNameDialog = ref(false)
const videoName   = ref('')
let ws = null

async function submit() {
  if (!selectedFile.value) { toast(tr('create_select_video_first', 'Please select a video file first'),'warn'); return }
  if (srcLang.value===tgtLang.value) { toast(tr('create_src_tgt_diff', 'Source and target languages must be different'),'warn'); return }
  if (tl.timeline.parts.length===0) { toast(tr('create_need_part', 'Please add at least one Part'),'warn'); return }
  videoName.value = ''
  showNameDialog.value = true
}

function onNameCancel() { showNameDialog.value = false }

async function onNameConfirm() {
  showNameDialog.value = false
  await doSubmit(videoName.value.trim())
}

async function doSubmit(name) {
  if (!isMember.value) ensureFreeDefaultWatermark()
  submitting.value = true
  const fd = new FormData()
  fd.append('video', selectedFile.value)
  // Send timeline JSON as single field
  fd.append('timeline_json', JSON.stringify(tl.toJSON()))
  if (name) fd.append('name', name)

  let jobId = null
  try {
    const r = await fetch('/api/jobs', {
      method:'POST',
      headers:{ Authorization:'Bearer '+localStorage.getItem('ll_token') },
      body: fd
    })
    const d = await r.json()
    if (!r.ok) {
      const msg = Array.isArray(d.detail)
        ? d.detail.map(e => e.msg || JSON.stringify(e)).join('; ')
        : (d.detail || tr('create_submit_failed', 'Submit failed'))
      throw new Error(msg)
    }
    jobId = d.job_id
    if (name && jobId) {
      const nfd = new FormData(); nfd.append('name', name)
      fetch(`/api/jobs/${jobId}`, { method:'PATCH',
        headers:{Authorization:'Bearer '+localStorage.getItem('ll_token')}, body:nfd }).catch(()=>{})
    }
    currentJobId.value = jobId
    jobRunning.value = true; jobDone.value = false
    currentStep.value = 0; clipsPct.value = 0; writePct.value = 0
    logs.value = []; stepName.value = tr('create_waiting', 'Waiting...')
    toast(tr('create_task_submitted', 'Task submitted 🚀'),'ok')
  } catch(e) { console.error('doSubmit error:', e); toast(e.message,'err') }
  finally { submitting.value = false }

  // Connect WS outside the error-reporting try block so WS issues don't mask submit errors
  if (jobId) {
    try { connectWS(jobId) } catch(wsErr) { console.warn('WS connect failed, falling back to poll:', wsErr); pollJob(jobId) }
  }
}

function connectWS(jobId) {
  if (ws) { try{ws.close()}catch{} }
  const proto = location.protocol==='https:'?'wss':'ws'
  ws = new WebSocket(`${proto}://${location.host}/api/ws/${jobId}`)
  ws.onmessage = async e => {
    const msg = JSON.parse(e.data)
    switch (msg.type) {
      case 'log':
        logs.value.push(msg.data)
        await nextTick()
        if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
        break
      case 'step':  currentStep.value=msg.data.step; stepName.value=msg.data.name; break
      case 'video_clips': clipsPct.value=msg.data.pct||0; break
      case 'video_write': writePct.value=msg.data.pct||0; break
      case 'done':  clipsPct.value=100; writePct.value=100; jobDone.value=true; toast(`${tr('create_done', 'Video generated!')} 🎉`,'ok'); break
      case 'error': toast(`${tr('create_task_failed', 'Processing failed')}: ${msg.data}`,'err'); jobRunning.value=false; break
      case 'cancelled': toast(tr('create_task_cancelled', 'Task cancelled'),'warn'); jobRunning.value=false; break
    }
  }
  ws.onerror = () => pollJob(jobId)
}

function pollJob(jobId) {
  const iv = setInterval(async () => {
    try {
      const d = await apiFetch('/api/jobs/'+jobId)
      if (d.step_name) stepName.value=d.step_name
      if (d.video_clips_pct) clipsPct.value=d.video_clips_pct
      if (d.video_write_pct) writePct.value=d.video_write_pct
      if (d.status==='done'){clearInterval(iv);clipsPct.value=100;writePct.value=100;jobDone.value=true}
      if (d.status==='error'||d.status==='cancelled'){clearInterval(iv);jobRunning.value=false}
    } catch {}
  }, 3000)
}

async function cancelJob() {
  if (!currentJobId.value||!confirm(tr('create_confirm_cancel', 'Cancel this task?'))) return
  await fetch(`/api/jobs/${currentJobId.value}`, {
    method:'DELETE', headers:{Authorization:'Bearer '+localStorage.getItem('ll_token')}
  }).catch(()=>{})
}

function logClass(l) {
  if (l.includes('❌')||l.toLowerCase().includes('error')) return 'err'
  if (l.includes('✓')||l.includes('完成')) return 'ok'
  return ''
}

// ── File Handling ──
function setFile(f) {
  if (!f) return
  selectedFile.value = f
  if (videoPreviewUrl.value) URL.revokeObjectURL(videoPreviewUrl.value)
  videoPreviewUrl.value = URL.createObjectURL(f)
}
function clearFile() {
  selectedFile.value = null
  if (videoPreviewUrl.value) { URL.revokeObjectURL(videoPreviewUrl.value); videoPreviewUrl.value = '' }
}
function onFileChange(e) { const f=e.target.files[0]; if(f) setFile(f) }
function onDrop(e) { dragOver.value=false; const f=e.dataTransfer.files[0]; if(f&&f.type.startsWith('video/')) setFile(f) }
function fmtSize(b) { return b>1e9?(b/1e9).toFixed(1)+' GB':b>1e6?(b/1e6).toFixed(1)+' MB':(b/1e3).toFixed(0)+' KB' }

// ── Mount ──
onMounted(async () => {
  if (!isLoggedIn.value) return
  try { await refreshMembership() } catch {}
  ensureFreeDefaultWatermark()
  try {
    const d = await apiFetch('/api/languages')
    if (d.languages?.length) langs.value=d.languages
  } catch {}
  if (!langs.value.length) langs.value=[
    {code:'en',native_name:'English',flag:'🇺🇸'},
    {code:'zh-Hans',native_name:'中文（简体）',flag:'🇨🇳'},
    {code:'zh-Hant',native_name:'中文（繁體）',flag:'🇭🇰'},
    {code:'ja',native_name:'日本語',flag:'🇯🇵'},{code:'ko',native_name:'한국어',flag:'🇰🇷'},
    {code:'de',native_name:'Deutsch',flag:'🇩🇪'},{code:'fr',native_name:'Français',flag:'🇫🇷'},
    {code:'es',native_name:'Español',flag:'🇪🇸'},{code:'ru',native_name:'Русский',flag:'🇷🇺'},
  ]
  await loadPresets()
})

watch(() => user.value?.membership?.tier, () => {
  ensureFreeDefaultWatermark()
})
</script>

<style scoped>
.create-page{padding:28px 24px 80px;max-width:1200px;margin:0 auto;}
.page-header{margin-bottom:24px;}
.page-header h1{font-size:30px;font-weight:800;letter-spacing:-0.5px;margin-bottom:4px;color:var(--text);}
.page-header p{color:var(--text2);font-size:14px;}
.empty-state{text-align:center;padding:80px 24px;display:flex;flex-direction:column;align-items:center;gap:12px;}

.section-label{font-size:11px;font-weight:800;letter-spacing:3px;color:var(--accent);text-transform:uppercase;margin:24px 0 12px;}

.preset-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 14px;margin-bottom:20px;background:rgba(99,102,241,.04);border:1px solid rgba(99,102,241,.15);border-radius:12px;}
.member-tip{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:10px 12px;margin-bottom:12px;
  border:1px solid rgba(16,185,129,.25);
  background:linear-gradient(135deg, rgba(16,185,129,.08), rgba(14,165,233,.06));
}
.member-tip-left{display:flex;align-items:center;gap:10px;}
.member-tip-logo{width:30px;height:30px;border-radius:8px;}
.member-tip-title{font-size:13px;font-weight:700;color:#14532d;}
.member-tip-sub{font-size:11px;color:#334155;}

.config-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-bottom:0;}
.config-card{padding:20px;}
.upload-zone{border:2px dashed var(--border);border-radius:12px;padding:28px 20px;cursor:pointer;transition:all .2s;min-height:150px;display:flex;align-items:center;justify-content:center;background:var(--bg);}
.upload-zone:hover,.upload-zone.over{border-color:var(--accent);background:rgba(99,102,241,.04);}
.slider{width:100%;accent-color:var(--accent);cursor:pointer;}

/* CANVAS EDITOR */
.canvas-card{padding:0;overflow:hidden;margin-bottom:0;}
.canvas-editor-wrap{display:grid;grid-template-columns:200px 1fr 220px;min-height:440px;}
@media(max-width:900px){.canvas-editor-wrap{grid-template-columns:1fr;}}

.canvas-center{display:flex;flex-direction:column;padding:10px;position:relative;z-index:1;}
.canvas-outer{flex:1;overflow:auto;min-height:320px;}

/* STYLE */
.style-card{padding:20px;margin-bottom:0;}

/* SUBMIT ROW */
.submit-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:22px;}
.preset-save-wrap{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.preset-save-tip{
  font-size:12px;
  color:var(--text3);
  line-height:1.45;
  padding:8px 10px;
  border-radius:10px;
  border:1px solid rgba(99,102,241,.16);
  background:rgba(99,102,241,.06);
  max-width:360px;
}

/* PROGRESS */
.progress-card{padding:28px;margin-top:20px;}
.step-bar{display:flex;align-items:center;margin-bottom:16px;}
.step-dot{width:34px;height:34px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;background:var(--bg3);border:2px solid var(--border);color:var(--text3);transition:all .3s;}
.step-dot.active{background:linear-gradient(135deg,var(--accent),var(--accent2));border-color:transparent;color:#fff;box-shadow:0 0 16px rgba(99,102,241,.35);}
.step-dot.done{background:rgba(16,185,129,.1);border-color:rgba(16,185,129,.4);color:var(--ok);}
.step-ln{flex:1;height:2px;background:var(--border);transition:background .3s;}
.step-ln.done{background:linear-gradient(90deg,var(--ok),rgba(16,185,129,.3));}
.cur-step{display:flex;align-items:center;gap:10px;font-size:14px;font-weight:600;color:var(--text2);margin-bottom:4px;}
.pulse-dot{width:8px;height:8px;border-radius:50%;background:var(--accent);animation:pulse 1.5s infinite;flex-shrink:0;}
.log-box{max-height:220px;overflow-y:auto;margin-top:14px;padding:12px;background:#1e1e2e;border-radius:8px;border:1px solid #2d2d3e;font-size:12px;line-height:1.7;}
.log-line{color:#94a3b8;}
.log-line.ok{color:#10b981;}
.log-line.err{color:#ef4444;}
</style>
