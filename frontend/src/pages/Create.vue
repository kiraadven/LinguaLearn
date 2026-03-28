<template>
  <div class="create-page page-inner">
    <div class="page-header">
      <h1>生成学习视频</h1>
      <p>上传视频，配置布局与样式，AI 自动生成逐句精听视频</p>
    </div>

    <div v-if="!isLoggedIn" class="empty-state">
      <div style="font-size:64px">🔒</div>
      <p style="font-size:18px;font-weight:700">请先登录</p>
      <button class="btn-primary" @click="openAuth()">登录 / 注册</button>
    </div>

    <div v-else>
      <div class="member-tip card">
        <div class="member-tip-left">
          <img src="/premium-badge.svg" alt="VIP" class="member-tip-logo">
          <div>
            <div class="member-tip-title">
              {{ isMember ? '当前为会员' : '当前为非会员' }}
            </div>
            <div class="member-tip-sub" v-if="user?.membership">
              今日已生成 {{ user.membership.usage?.videos_generated_today ?? 0 }} 个
              <template v-if="user.membership.limits?.daily_video_limit !== null">
                / 最多 {{ user.membership.limits?.daily_video_limit }} 个
              </template>
              ，单视频最长 {{ Math.floor((user.membership.limits?.max_video_seconds || 300) / 60) }} 分钟
            </div>
          </div>
        </div>
        <button class="btn-ghost" style="font-size:12px;padding:7px 12px" @click="openMembership()">
          {{ isMember ? '管理会员' : '开通会员' }}
        </button>
      </div>

      <!-- Preset bar -->
      <div class="preset-bar" v-if="presets.length>0">
        <select class="input" v-model="selectedPresetId" style="flex:1;max-width:240px;margin-bottom:0;font-size:13px">
          <option value="">— 选择预设 —</option>
          <option v-for="p in presets" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <button class="btn-ghost" style="padding:7px 12px;font-size:12px" @click="applyPreset">加载</button>
        <button class="btn-ghost" style="padding:7px 10px;font-size:12px;color:var(--err);border-color:rgba(248,113,113,.3)" @click="deletePreset">删除</button>
      </div>

      <div v-if="!jobRunning || jobDone">
        <!-- ── SECTION 1: Basic Config ── -->
        <div class="section-label">基础配置</div>
        <div class="config-grid">
          <!-- Upload -->
          <div class="card config-card">
            <div class="card-title">📁 上传视频</div>
            <div :class="['upload-zone',{over:dragOver}]"
                 @click="$refs.fileInput.click()"
                 @dragover.prevent="dragOver=true"
                 @dragleave="dragOver=false"
                 @drop.prevent="onDrop">
              <input ref="fileInput" type="file" accept="video/*" style="display:none" @change="onFileChange">
              <div v-if="!selectedFile" style="text-align:center">
                <div style="font-size:44px;margin-bottom:10px">📹</div>
                <div style="font-weight:600;margin-bottom:4px">点击或拖拽视频文件</div>
                <div style="font-size:12px;color:var(--text3)">MP4、MOV、AVI 等格式</div>
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
                    @click.stop="clearFile">✕ 移除</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Language -->
          <div class="card config-card">
            <div class="card-title">🌐 语言 & 分辨率</div>
            <label class="label">源语言（视频语言）</label>
            <select class="input" v-model="srcLang" @change="timeline.sourceLang=srcLang" style="margin-bottom:12px">
              <option v-for="l in langs" :key="l.code" :value="l.code">{{ l.flag }} {{ l.native_name }}</option>
            </select>
            <label class="label">目标语言（你的母语）</label>
            <select class="input" v-model="tgtLang" @change="timeline.targetLang=tgtLang" style="margin-bottom:12px">
              <option v-for="l in langs" :key="l.code" :value="l.code">{{ l.flag }} {{ l.native_name }}</option>
            </select>
            <label class="label">视频分辨率</label>
            <select class="input" v-model="resolution" @change="onResolutionChange">
              <option value="1080p">1080p（推荐，更清晰）</option>
              <option value="720p">720p（更快，省空间）</option>
            </select>
          </div>

          <!-- Words -->
          <div class="card config-card">
            <div class="card-title">📚 词汇 & 表达</div>
            <label class="label">关键词：{{ numWords===0?'不限制':numWords+' 个/句' }}</label>
            <input type="range" class="slider" v-model.number="numWords" @input="tl.timeline.numWords=numWords" min="0" max="12" style="margin-bottom:20px">
            <label class="label">实用表达：{{ numExprs===0?'不限制':numExprs+' 个/句' }}</label>
            <input type="range" class="slider" v-model.number="numExprs" @input="tl.timeline.numExprs=numExprs" min="0" max="8">
          </div>
        </div>

        <!-- ── SECTION 2: Canvas Layout Editor (Konva) ── -->
        <div class="section-label">布局编辑器
          <span style="font-size:11px;color:var(--text3);font-weight:400;margin-left:8px">点击元素选中后拖拽定位，或从工具栏添加新元素</span>
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
        <div class="section-label">字幕样式主题
          <span style="font-size:11px;color:var(--text3);font-weight:400;margin-left:8px">选择视频字幕的视觉风格模版</span>
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
            {{ submitting?'提交中...':'🚀 开始生成学习视频' }}
          </button>
          <div class="preset-save-wrap">
            <button class="btn-ghost" style="padding:13px 18px;font-size:13px" @click="openPresetSaveDialog">
              💾 保存为预设
            </button>
            <div class="preset-save-tip">保存当前布局和样式，下次一键复用，省去重复调参时间。</div>
          </div>
        </div>
      </div>

      <!-- Naming Dialog -->
      <Teleport to="body">
        <div v-if="showNameDialog" class="modal-overlay" @click.self="onNameCancel" style="z-index:300">
          <div class="modal-box" style="max-width:420px">
            <button class="modal-close" @click="onNameCancel">✕</button>
            <div style="font-size:20px;font-weight:800;margin-bottom:6px;color:var(--text)">为视频命名</div>
            <div style="font-size:13px;color:var(--text3);margin-bottom:20px">给这个学习视频起个名字，便于之后查找。留空时 AI 将自动生成名称。</div>
            <label class="label">视频名称（选填）</label>
            <input class="input" v-model="videoName" placeholder="例如：TED演讲·科技改变未来" @keyup.enter="onNameConfirm" style="margin-bottom:20px">
            <div style="display:flex;gap:10px">
              <button class="btn-primary" style="flex:1;padding:12px" @click="onNameConfirm">确认开始生成 →</button>
              <button class="btn-ghost" style="padding:12px 20px" @click="onNameCancel">取消</button>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- Preset Name Dialog -->
      <Teleport to="body">
        <div v-if="showPresetNameDialog" class="modal-overlay" @click.self="onPresetSaveCancel" style="z-index:301">
          <div class="modal-box" style="max-width:440px">
            <button class="modal-close" @click="onPresetSaveCancel">✕</button>
            <div style="font-size:20px;font-weight:800;margin-bottom:6px;color:var(--text)">保存为预设</div>
            <div style="font-size:13px;color:var(--text3);margin-bottom:18px">
              输入一个好记的名称，后续可一键加载这套布局、样式和参数配置。
            </div>
            <label class="label">预设名称</label>
            <input
              ref="presetNameInput"
              class="input"
              v-model="presetName"
              placeholder="例如：英文精听·通勤模板"
              @keyup.enter="savePreset"
              style="margin-bottom:18px"
            >
            <div style="display:flex;gap:10px">
              <button class="btn-primary" style="flex:1;padding:12px" @click="savePreset">保存预设</button>
              <button class="btn-ghost" style="padding:12px 20px" @click="onPresetSaveCancel">取消</button>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- Watermark Dialog -->
      <WatermarkDialog :visible="showWatermarkDialog" @close="showWatermarkDialog=false" @add="onAddWatermark" />

      <!-- Progress -->
      <div v-if="jobRunning && !jobDone" class="card progress-card">
        <div class="card-title">⚡ 处理进度</div>
        <div class="step-bar">
          <template v-for="i in 5" :key="i">
            <div :class="['step-dot', i<currentStep?'done':i===currentStep?'active':'']">{{ i }}</div>
            <div v-if="i<5" :class="['step-ln', i<currentStep?'done':'']"></div>
          </template>
        </div>
        <div class="cur-step"><span class="pulse-dot"></span><span>{{ stepName }}</span></div>
        <div v-if="currentStep>=5" style="margin-top:14px">
          <PBar label="片段渲染" :pct="clipsPct" color="linear-gradient(90deg,var(--accent),var(--accent2))"/>
          <PBar label="视频写入" :pct="writePct" color="linear-gradient(90deg,var(--accent3),var(--accent4))" style="margin-top:10px"/>
        </div>
        <div class="log-box" ref="logBox">
          <div v-for="(l,i) in logs" :key="i" :class="['log-line',logClass(l)]">{{ l }}</div>
        </div>
        <div style="margin-top:14px">
          <button class="btn-ghost" style="padding:8px 18px;font-size:13px;color:var(--err);border-color:rgba(248,113,113,.3)" @click="cancelJob">取消任务</button>
        </div>
      </div>

      <!-- Done -->
      <div v-if="jobDone" class="card" style="padding:36px;text-align:center;margin-top:20px">
        <div style="font-size:52px;margin-bottom:12px">🎉</div>
        <div style="font-size:18px;font-weight:700;margin-bottom:8px">视频生成完成！</div>
        <button class="btn-primary" @click="$router.push('/results')">查看学习结果 →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted, nextTick, watch } from 'vue'
import { useAuth } from '../composables/useAuth.js'
import { apiFetch } from '../composables/useApi.js'
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
const openAuth = inject('openAuth')
const openMembership = inject('openMembership', () => {})
const toast    = inject('toast')

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
const srcLang      = ref('en')
const tgtLang      = ref('zh')
const resolution   = ref('1080p')
const numWords     = ref(6)
const numExprs     = ref(4)

// Sync basic config → timeline
watch(srcLang, v => { tl.timeline.sourceLang = v })
watch(tgtLang, v => { tl.timeline.targetLang = v })
watch(numWords, v => { tl.timeline.numWords = v })
watch(numExprs, v => { tl.timeline.numExprs = v })

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
      toast('开通会员后可自定义水印；非会员成片会自动添加默认 LinguaLearn 水印', 'warn')
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
    toast('非会员不可自定义水印', 'warn')
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
    toast('默认 LinguaLearn 水印仅会员可删除', 'warn')
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
    toast('默认水印仅会员可编辑', 'warn')
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
  if (!stage) { toast('画布尚未初始化', 'warn'); return }

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

  if (elementNodes.length === 0) { toast('没有可预览的元素', 'warn'); return }

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
  if (!name) { toast('请输入预设名称','warn'); return }
  const cfg = tl.toJSON() // Save entire timeline JSON as preset
  const fd = new FormData()
  fd.append('name', name)
  fd.append('config_json', JSON.stringify(cfg))
  try {
    await fetch('/api/config/presets', { method:'POST',
      headers:{ Authorization:'Bearer '+localStorage.getItem('ll_token') }, body:fd })
    toast(`预设「${name}」已保存`, 'ok')
    presetName.value = ''
    showPresetNameDialog.value = false
    await loadPresets()
  } catch(e) { toast('保存失败','err') }
}

function applyPreset() {
  const id = parseInt(selectedPresetId.value)
  const p = presets.value.find(p=>p.id===id)
  if (!p) { toast('请先选择预设','warn'); return }
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
    toast(`已加载「${p.name}」`,'ok')
  } catch { toast('加载失败','err') }
}

async function deletePreset() {
  const id = parseInt(selectedPresetId.value)
  if (!id) { toast('请先选择预设','warn'); return }
  const p = presets.value.find(p=>p.id===id)
  if (!confirm(`确定删除「${p?.name}」？`)) return
  try {
    await fetch(`/api/config/presets/${id}`, { method:'DELETE',
      headers:{ Authorization:'Bearer '+localStorage.getItem('ll_token') } })
    selectedPresetId.value = ''; toast('已删除','ok'); await loadPresets()
  } catch { toast('删除失败','err') }
}

// ── Submit & Progress ──
const jobRunning  = ref(false)
const jobDone     = ref(false)
const submitting  = ref(false)
const currentJobId= ref(null)
const currentStep = ref(0)
const stepName    = ref('准备中...')
const clipsPct    = ref(0)
const writePct    = ref(0)
const logs        = ref([])
const logBox      = ref(null)
const showNameDialog = ref(false)
const videoName   = ref('')
let ws = null

async function submit() {
  if (!selectedFile.value) { toast('请先选择视频文件','warn'); return }
  if (srcLang.value===tgtLang.value) { toast('源语言和目标语言不能相同','warn'); return }
  if (tl.timeline.parts.length===0) { toast('请至少添加一个 Part','warn'); return }
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
        : (d.detail || '提交失败')
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
    logs.value = []; stepName.value = '等待处理...'
    toast('任务已提交 🚀','ok')
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
      case 'done':  clipsPct.value=100; writePct.value=100; jobDone.value=true; toast('视频生成完成！🎉','ok'); break
      case 'error': toast('处理失败: '+msg.data,'err'); jobRunning.value=false; break
      case 'cancelled': toast('任务已取消','warn'); jobRunning.value=false; break
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
  if (!currentJobId.value||!confirm('确定取消？')) return
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
    {code:'en',native_name:'English',flag:'🇺🇸'},{code:'zh',native_name:'中文',flag:'🇨🇳'},
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
