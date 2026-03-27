<template>
  <div class="jd-page">

    <!-- Sticky top bar -->
    <div class="jd-topbar">
      <button class="back-btn" @click="$router.push('/results')">← 返回</button>
      <div class="jd-title" :title="jobName">{{ jobName }}</div>
      <button class="toggle-btn" @click="transcriptOpen = !transcriptOpen" :title="transcriptOpen?'隐藏文稿':'显示文稿'">
        <span>{{ transcriptOpen ? '⟩ 隐藏文稿' : '⟨ 显示文稿' }}</span>
      </button>
    </div>

    <!-- Loading / error -->
    <div v-if="loading" class="jd-center"><div class="spin">⟳</div><p>加载中...</p></div>
    <div v-else-if="!job" class="jd-center"><p>任务不存在</p></div>

    <!-- ── Live progress view (running / queued) ── -->
    <div v-else-if="job.status === 'running' || job.status === 'queued'" class="jd-progress-view">
      <div class="prog-card">
        <div class="prog-title">⚡ 处理进度</div>
        <div class="step-bar">
          <template v-for="i in 5" :key="i">
            <div :class="['step-dot', i < liveStep ? 'done' : i === liveStep ? 'active' : '']">{{ i }}</div>
            <div v-if="i < 5" :class="['step-ln', i < liveStep ? 'done' : '']"></div>
          </template>
        </div>
        <div class="cur-step"><span class="pulse-dot"></span><span>{{ liveStepName }}</span></div>
        <div v-if="liveStep >= 5" style="margin-top:14px">
          <div class="pbar-row"><span>片段渲染</span><span>{{ liveClipsPct }}%</span></div>
          <div class="pbar-track"><div class="pbar-fill" :style="{width: liveClipsPct+'%', background: 'linear-gradient(90deg,var(--accent),var(--accent2))'}"></div></div>
          <div class="pbar-row" style="margin-top:8px"><span>视频写入</span><span>{{ liveWritePct }}%</span></div>
          <div class="pbar-track"><div class="pbar-fill" :style="{width: liveWritePct+'%', background: 'linear-gradient(90deg,var(--accent3,#10b981),var(--accent4,#059669))'}"></div></div>
        </div>
        <div class="log-box" ref="liveLogBox">
          <div v-for="(l, i) in liveLogs" :key="i" :class="['log-line', logClass(l)]">{{ l }}</div>
        </div>
        <div v-if="job.status === 'running'" style="margin-top:14px;text-align:center">
          <button class="cancel-btn" @click="cancelJob">取消任务</button>
        </div>
      </div>
    </div>

    <!-- ── Error view ── -->
    <div v-else-if="job.status === 'error'" class="jd-center">
      <p style="font-size:48px">❌</p>
      <p style="font-weight:700;margin-top:8px">处理失败</p>
      <p v-if="job.error" style="color:var(--err);font-size:13px;margin-top:6px">{{ job.error }}</p>
    </div>

    <div v-else class="jd-body">

      <!-- ── Main row ── -->
      <div :class="['jd-main', {wide: !transcriptOpen}]">

        <!-- Video column -->
        <div class="jd-video-col">
          <div class="video-wrap">
            <video ref="videoEl" controls preload="metadata"
              :src="`/api/jobs/${jobId}/stream/${encodeURIComponent(job.result.full_video)}`"
              class="jd-video"
              @timeupdate="onTimeUpdate"
              @error="videoError='视频加载失败'">
            </video>
            <div v-if="videoError" class="video-err">⚠️ {{ videoError }}</div>
          </div>
          <div class="video-meta-row">
            <div class="video-meta-info">
              <div class="vm-name">{{ jobName }}</div>
              <div class="vm-sub">{{ job.result?.source_lang||'?' }} → {{ job.result?.target_lang||'?' }}
                · {{ job.result?.sentences_count||'?' }} 句</div>
            </div>
            <a :href="`/api/jobs/${jobId}/download/${encodeURIComponent(job.result.full_video)}`"
               download class="dl-chip">⬇ 下载视频</a>
          </div>
        </div>

        <!-- Transcript panel -->
        <Transition name="panel">
          <div v-if="transcriptOpen" class="jd-transcript-col">
            <div class="tc-header">
              <span class="tc-title">文稿同步</span>
              <div v-if="segments.length" class="sync-dot">● 实时同步</div>
              <div v-else-if="segLoading" style="font-size:11px;color:var(--text3)">加载中...</div>
            </div>
            <div class="tc-list" @mouseover="onMdHover" @mouseleave="onMdLeave">
              <div v-if="!segments.length && !segLoading" class="tc-empty">暂无文稿数据</div>
              <div v-for="(s, i) in segments" :key="i"
                   :ref="el => segRefs[i] = el"
                   :class="['tc-item', {active: i === activeSeg}]"
                   @click="jumpTo(s.video_start ?? s.start)">
                <button class="tc-ts" @click.stop="jumpTo(s.video_start ?? s.start)">▶ {{ fmtTime(s.video_start ?? s.start) }}</button>
                <div class="tc-texts">
                  <p class="tc-orig" v-html="s._html || s.text"></p>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <!-- ── Learning Notes ── -->
      <div class="jd-notes">
        <div class="notes-hdr">
          <span class="notes-hdr-title">📚 学习笔记</span>
          <a v-if="job.result?.markdown"
             :href="`/api/jobs/${jobId}/download/${encodeURIComponent(job.result.markdown)}`"
             download class="dl-chip">⬇ 下载笔记</a>
        </div>
        <div v-if="!markdownHtml" class="md-empty">暂无学习笔记</div>
        <div v-else class="md-view" v-html="markdownHtml"
             @mouseover="onMdHover" @mouseout="onMdOut" @mouseleave="onMdLeave"></div>
      </div>
    </div>

    <!-- Dictionary tooltip (teleported to body to avoid z-index/overflow issues) -->
    <Teleport to="body">
      <Transition name="dt">
        <div v-if="tooltip.visible"
             class="dict-tooltip"
             :style="tooltipStyle"
             @mouseenter="cancelHide"
             @mouseleave="scheduleHide">
          <div v-if="tooltip.loading" class="dt-loading">
            <span class="dt-spin">⟳</span> 查询中…
          </div>
          <div v-else-if="tooltip.notFound" class="dt-not-found">
            未找到 "{{ tooltip.word }}"
          </div>
          <template v-else-if="tooltip.data">
            <div class="dt-head">
              <span class="dt-word">{{ tooltip.data.word }}</span>
              <span v-if="tooltip.data.phonetic" class="dt-phonetic">{{ tooltip.data.phonetic }}</span>
              <button v-if="tooltip.data.audio" class="dt-audio" @click="playAudio" title="播放发音">🔊</button>
            </div>
            <div v-for="(m, i) in tooltip.data.meanings" :key="i" class="dt-meaning">
              <span v-if="m.pos" class="dt-pos">{{ m.pos }}</span>
              <p class="dt-def">{{ m.definition }}</p>
              <p v-if="tooltip.data.translated_meanings?.[i]" class="dt-def-trans">{{ tooltip.data.translated_meanings[i] }}</p>
              <p v-if="m.example" class="dt-ex">"{{ m.example }}"</p>
              <p v-if="m.synonyms?.length" class="dt-syns">
                同义: <span v-for="s in m.synonyms" :key="s" class="dt-syn">{{ s }}</span>
              </p>
            </div>
          </template>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { apiFetch } from '../composables/useApi.js'

const route  = useRoute()
const jobId  = route.params.id

const job        = ref(null)
const loading    = ref(true)
const videoEl    = ref(null)
const videoError = ref('')
const segments   = ref([])
const segLoading = ref(false)
const activeSeg  = ref(-1)
const segRefs    = ref([])
const transcriptOpen = ref(true)
const markdownHtml = ref('')

// ── Live progress (for running/queued jobs) ──
const liveStep    = ref(0)
const liveStepName= ref('等待处理...')
const liveClipsPct= ref(0)
const liveWritePct= ref(0)
const liveLogs    = ref([])
const liveLogBox  = ref(null)
let ws = null

function logClass(l) {
  if (l.includes('✅') || l.includes('成功')) return 'log-ok'
  if (l.includes('❌') || l.includes('错误') || l.includes('失败')) return 'log-err'
  if (l.includes('⚠️')) return 'log-warn'
  return ''
}

function connectProgressWS() {
  if (ws) { try { ws.close() } catch {} }
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/api/ws/${jobId}`)
  ws.onmessage = async (e) => {
    const msg = JSON.parse(e.data)
    switch (msg.type) {
      case 'log':
        liveLogs.value.push(msg.data)
        await nextTick()
        if (liveLogBox.value) liveLogBox.value.scrollTop = liveLogBox.value.scrollHeight
        break
      case 'step':
        liveStep.value = msg.data.step
        liveStepName.value = msg.data.name
        if (job.value) { job.value.step = msg.data.step; job.value.step_name = msg.data.name }
        break
      case 'video_clips': liveClipsPct.value = msg.data.pct || 0; break
      case 'video_write': liveWritePct.value = msg.data.pct || 0; break
      case 'done':
        liveClipsPct.value = 100; liveWritePct.value = 100
        // Reload job to get done state
        try {
          const d = await apiFetch(`/api/jobs/${jobId}`)
          job.value = d
          if (d.status === 'done' && d.result?.full_video) {
            loadSegments()
            if (d.result.markdown) loadMarkdown(d.result.markdown)
          }
        } catch {}
        break
      case 'error':
        if (job.value) job.value.status = 'error'
        break
      case 'cancelled':
        if (job.value) job.value.status = 'cancelled'
        break
      case 'status':
        if (msg.data && job.value) {
          job.value.step = msg.data.step
          job.value.step_name = msg.data.step_name
          liveStep.value = msg.data.step || 0
          liveStepName.value = msg.data.step_name || '等待处理...'
          liveClipsPct.value = msg.data.video_clips_pct || 0
          liveWritePct.value = msg.data.video_write_pct || 0
        }
        break
    }
  }
  ws.onerror = () => { /* silent */ }
}

async function cancelJob() {
  if (!confirm('确定取消此任务？')) return
  try {
    await fetch(`/api/jobs/${jobId}`, {
      method: 'DELETE',
      headers: { Authorization: 'Bearer ' + localStorage.getItem('ll_token') }
    })
    if (job.value) job.value.status = 'cancelled'
  } catch {}
}

const jobName = computed(() =>
  job.value?.name || job.value?.video_filename || jobId.slice(0,12)
)

onMounted(async () => {
  try {
    const d = await apiFetch(`/api/jobs/${jobId}`)
    job.value = d
    if (d.status === 'done' && d.result?.full_video) {
      loadSegments()
      if (d.result.markdown) loadMarkdown(d.result.markdown)
    } else if (d.status === 'running' || d.status === 'queued') {
      liveStep.value = d.step || 0
      liveStepName.value = d.step_name || '等待处理...'
      liveClipsPct.value = d.video_clips_pct || 0
      liveWritePct.value = d.video_write_pct || 0
      connectProgressWS()
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  if (ws) { try { ws.close() } catch {} }
})

async function loadSegments() {
  segLoading.value = true
  try {
    const d = await apiFetch(`/api/jobs/${jobId}/segments`)
    const list = Array.isArray(d) ? d : []
    // Wrap English words in each segment for hover dict support
    segments.value = list.map(s => ({ ...s, _html: wrapEnglishWords(`<span>${s.text || ''}</span>`).replace(/^<span>|<\/span>$/g, '') }))
  } catch { segments.value = [] }
  finally { segLoading.value = false }
}

async function loadMarkdown(mdFile) {
  try {
    const d = await apiFetch(`/api/jobs/${jobId}/preview/${encodeURIComponent(mdFile)}`)
    const text = d.content || ''
    let html = marked.parse(text)
    if (html instanceof Promise) html = await html
    markdownHtml.value = wrapEnglishWords(html)
  } catch (e) {
    console.error('loadMarkdown error:', e)
  }
}

// ── English word wrapping ───────────────────────────────────────────────────
function wrapEnglishWords(html) {
  const parser = new DOMParser()
  const doc = parser.parseFromString(`<div>${html}</div>`, 'text/html')
  const root = doc.body.firstChild
  const SKIP = new Set(['CODE', 'PRE', 'SCRIPT', 'STYLE'])
  const RE = /\b[a-zA-Z]+(?:['''-][a-zA-Z]+)*\b/g

  function walk(node) {
    if (node.nodeType === 3) { // TEXT_NODE
      const text = node.textContent
      if (!/[a-zA-Z]/.test(text)) return
      const parts = []
      let last = 0, m, changed = false
      RE.lastIndex = 0
      while ((m = RE.exec(text)) !== null) {
        if (m.index > last) parts.push(document.createTextNode(text.slice(last, m.index)))
        const s = document.createElement('span')
        s.className = 'dict-word'
        s.dataset.word = m[0].toLowerCase()
        s.textContent = m[0]
        parts.push(s)
        last = RE.lastIndex
        changed = true
      }
      if (!changed) return
      if (last < text.length) parts.push(document.createTextNode(text.slice(last)))
      const frag = document.createDocumentFragment()
      parts.forEach(p => frag.appendChild(p))
      node.parentNode.replaceChild(frag, node)
    } else if (node.nodeType === 1) { // ELEMENT_NODE
      if (SKIP.has(node.tagName) || node.classList?.contains('dict-word')) return
      ;[...node.childNodes].forEach(walk)
    }
  }

  walk(root)
  return root.innerHTML
}

// ── Dictionary tooltip ──────────────────────────────────────────────────────
const tooltip = ref({ visible: false, loading: false, notFound: false, word: '', data: null, x: 0, y: 0 })
const dictCache = {}
let showTimer = null
let hideTimer = null

const TOOLTIP_W = 300

const tooltipStyle = computed(() => {
  const MARGIN = 10
  const GAP = 14
  let x = tooltip.value.x + GAP
  // If tooltip would go off right edge, show on left of word instead
  if (x + TOOLTIP_W > window.innerWidth - MARGIN) {
    x = tooltip.value.wordLeft - TOOLTIP_W - GAP
  }
  x = Math.max(MARGIN, x)
  // Vertically: center on word
  let y = tooltip.value.y - 10
  y = Math.max(MARGIN, Math.min(y, window.innerHeight - 300))
  return { left: `${x}px`, top: `${y}px`, width: `${TOOLTIP_W}px` }
})

function onMdHover(e) {
  const el = e.target.closest?.('.dict-word')
  if (el) {
    clearTimeout(hideTimer)
    clearTimeout(showTimer)
    showTimer = setTimeout(() => triggerTooltip(el.dataset.word, el), 200)
    return
  }
  // Mouse is over non-word area within container — schedule hide (unless over tooltip)
  if (!e.target.closest?.('.dict-tooltip')) {
    clearTimeout(showTimer)
    if (tooltip.value.visible) scheduleHide()
  }
}

function onMdOut(e) {
  // Specifically leaving a .dict-word element
  if (e.target.classList?.contains('dict-word')) {
    if (!e.relatedTarget?.closest?.('.dict-word') && !e.relatedTarget?.closest?.('.dict-tooltip')) {
      clearTimeout(showTimer)
      scheduleHide()
    }
  }
}

function onMdLeave(e) {
  clearTimeout(showTimer)
  if (e.relatedTarget?.closest?.('.dict-tooltip')) return
  scheduleHide()
}

function cancelHide() { clearTimeout(hideTimer) }
function scheduleHide() { hideTimer = setTimeout(() => { tooltip.value.visible = false }, 200) }

async function triggerTooltip(word, el) {
  if (!word) return
  const rect = el.getBoundingClientRect()
  tooltip.value.word = word
  tooltip.value.x = rect.right           // show to the right of word
  tooltip.value.wordLeft = rect.left     // backup for left-side fallback
  tooltip.value.y = rect.top + rect.height / 2
  tooltip.value.notFound = false

  if (dictCache[word] !== undefined) {
    tooltip.value.data = dictCache[word] || null
    tooltip.value.notFound = !dictCache[word]
    tooltip.value.loading = false
    tooltip.value.visible = true
    return
  }

  tooltip.value.loading = true
  tooltip.value.data = null
  tooltip.value.visible = true

  try {
    const tgtLang = job.value?.result?.target_lang || 'zh'
    const data = await apiFetch(`/api/dictionary/${encodeURIComponent(word)}?target_lang=${tgtLang}`)
    dictCache[word] = data
    tooltip.value.data = data
    tooltip.value.notFound = false
  } catch {
    dictCache[word] = null
    tooltip.value.notFound = true
    tooltip.value.data = null
  } finally {
    tooltip.value.loading = false
  }
}

function playAudio() {
  const url = tooltip.value.data?.audio
  if (url) new Audio(url).play().catch(() => {})
}

// ── Video sync ──────────────────────────────────────────────────────────────
function onTimeUpdate() {
  if (!videoEl.value || !segments.value.length) return
  const ct = videoEl.value.currentTime
  let idx = -1
  for (let i = 0; i < segments.value.length; i++) {
    const s = segments.value[i]
    const vStart = s.seg_start ?? s.start
    const vEnd   = s.seg_end   ?? s.end
    if (ct >= vStart && ct < vEnd) { idx = i; break }
  }
  if (idx !== activeSeg.value) {
    activeSeg.value = idx
    if (idx >= 0) scrollToSeg(idx)
  }
}

function scrollToSeg(idx) {
  const el = segRefs.value[idx]
  el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

function jumpTo(t) {
  if (!videoEl.value) return
  videoEl.value.currentTime = t
  videoEl.value.play()
}

function fmtTime(sec) {
  const m = Math.floor(sec / 60), s2 = Math.floor(sec % 60)
  return `${m}:${String(s2).padStart(2, '0')}`
}
</script>

<style scoped>
.jd-page { min-height: 100vh; background: var(--bg); }

/* Top bar */
.jd-topbar {
  position: sticky; top: 60px; z-index: 50;
  display: flex; align-items: center; gap: 12px; padding: 10px 24px;
  background: rgba(255,255,255,0.95); backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border); box-shadow: var(--shadow);
}
.back-btn {
  padding: 7px 14px; border-radius: 8px; background: var(--bg3);
  border: 1px solid var(--border); color: var(--text2); font-size: 13px;
  font-weight: 600; cursor: pointer; white-space: nowrap; transition: all .15s;
}
.back-btn:hover { background: var(--border); color: var(--text); }
.jd-title {
  flex: 1; font-size: 15px; font-weight: 700; color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.toggle-btn {
  padding: 7px 16px; border-radius: 20px; font-size: 12px; font-weight: 600;
  background: rgba(99,102,241,.08); border: 1px solid rgba(99,102,241,.2);
  color: var(--accent); cursor: pointer; transition: all .2s; white-space: nowrap;
}
.toggle-btn:hover { background: rgba(99,102,241,.15); }

/* Body */
.jd-center { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 80px 24px; gap: 16px; }
.spin { font-size: 36px; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.jd-body { max-width: 1400px; margin: 0 auto; padding: 20px 20px 80px; }

/* Main row */
.jd-main {
  display: grid; grid-template-columns: 60fr 40fr; gap: 16px; margin-bottom: 24px;
  transition: grid-template-columns .35s ease;
}
.jd-main.wide { grid-template-columns: 1fr; }
@media (max-width: 900px) { .jd-main { grid-template-columns: 1fr !important; } }

/* Video column */
.jd-video-col { display: flex; flex-direction: column; }
.video-wrap {
  background: #000; border-radius: 12px; overflow: hidden;
  box-shadow: 0 4px 24px rgba(0,0,0,.15);
}
.jd-video { width: 100%; display: block; max-height: 520px; object-fit: contain; }
.video-err { padding: 12px; color: var(--err); font-size: 13px; background: rgba(239,68,68,.08); }
.video-meta-row {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
  padding: 12px 4px 0;
}
.vm-name { font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
.vm-sub { font-size: 12px; color: var(--text3); }

/* Transcript panel */
.jd-transcript-col {
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  overflow: hidden; display: flex; flex-direction: column;
  max-height: 580px; box-shadow: var(--shadow);
}
.tc-header {
  display: flex; align-items: center; gap: 8px; padding: 11px 14px;
  border-bottom: 1px solid var(--border); background: var(--bg3); flex-shrink: 0;
}
.tc-title { font-size: 13px; font-weight: 700; color: var(--text); }
.sync-dot { font-size: 11px; font-weight: 600; color: var(--ok); margin-left: auto; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
.tc-list { flex: 1; overflow-y: auto; }
.tc-empty { text-align: center; padding: 32px; font-size: 13px; color: var(--text3); }

.tc-item {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 10px 12px; cursor: pointer; border-left: 3px solid transparent;
  border-bottom: 1px solid var(--border); transition: all .15s;
}
.tc-item:last-child { border-bottom: none; }
.tc-item:hover { background: rgba(99,102,241,.04); }
.tc-item.active { background: rgba(99,102,241,.08); border-left-color: var(--accent); }
.tc-ts {
  flex-shrink: 0; padding: 3px 8px; border-radius: 10px;
  background: var(--bg3); border: 1px solid var(--border);
  color: var(--text3); font-size: 11px; font-weight: 700;
  cursor: pointer; white-space: nowrap; transition: all .15s;
}
.tc-ts:hover, .tc-item.active .tc-ts { background: var(--accent); color: #fff; border-color: var(--accent); }
.tc-texts { flex: 1; min-width: 0; }
.tc-orig { font-size: 13px; color: var(--text); line-height: 1.5; margin: 0; }
.tc-item.active .tc-orig { color: var(--text); font-weight: 600; }

/* Slide transition */
.panel-enter-active, .panel-leave-active { transition: all .3s ease; overflow: hidden; }
.panel-enter-from { opacity: 0; transform: translateX(20px); }
.panel-leave-to { opacity: 0; transform: translateX(20px); }

/* ── Notes section (Feishu/Notion style doc) ── */
.jd-notes {
  padding-top: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.notes-hdr {
  width: 100%; max-width: 860px;
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
  gap: 10px; margin-bottom: 16px;
}
.notes-hdr-title {
  font-size: 15px; font-weight: 700; color: var(--text2);
  letter-spacing: .3px; text-transform: uppercase; font-size: 12px;
}
.md-empty { text-align: center; padding: 64px; color: var(--text3); font-size: 14px; }

/* DL chip */
.dl-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 6px 12px; border-radius: 8px;
  background: rgba(99,102,241,.08); border: 1px solid rgba(99,102,241,.2);
  color: var(--accent); font-size: 12px; font-weight: 600; transition: all .2s;
  white-space: nowrap; text-decoration: none;
}
.dl-chip:hover { background: rgba(99,102,241,.15); }

/* ── Markdown doc view (Feishu-inspired) ── */
.md-view {
  width: 100%; max-width: 860px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 48px 64px 56px;
  box-shadow: 0 2px 16px rgba(0,0,0,.06);
  line-height: 1.85;
  color: var(--text);
  font-size: 15px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
}
@media (max-width: 960px) { .md-view { padding: 32px 36px 40px; } }
@media (max-width: 700px) { .md-view { padding: 24px 20px 32px; } }

/* h1: document title style */
.md-view :deep(h1) {
  font-size: 28px; font-weight: 800; margin: 0 0 28px;
  color: var(--text);
  padding-bottom: 16px;
  border-bottom: 2px solid var(--border);
  letter-spacing: -.3px;
}
/* h2: section heading with left accent */
.md-view :deep(h2) {
  font-size: 19px; font-weight: 700; margin: 36px 0 14px;
  color: var(--text);
  display: flex; align-items: center; gap: 10px;
}
.md-view :deep(h2)::before {
  content: '';
  display: inline-block; width: 4px; height: 1em;
  background: var(--accent); border-radius: 2px; flex-shrink: 0;
}
/* h3: subsection */
.md-view :deep(h3) {
  font-size: 16px; font-weight: 700; margin: 24px 0 10px;
  color: var(--text);
}
.md-view :deep(h4) {
  font-size: 14px; font-weight: 600; margin: 16px 0 8px; color: var(--text2);
}
.md-view :deep(p) {
  margin: 0 0 14px; color: var(--text); line-height: 1.85;
}
/* Blockquote: Feishu style — accent left bar + subtle bg */
.md-view :deep(blockquote) {
  border-left: 3px solid var(--accent);
  margin: 16px 0; padding: 12px 18px;
  background: rgba(99,102,241,.05); border-radius: 0 8px 8px 0;
}
.md-view :deep(blockquote p) { margin: 0; color: var(--text2); font-style: italic; }
/* Tables */
.md-view :deep(table) {
  width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px;
  border-radius: 8px; overflow: hidden; border: 1px solid var(--border);
}
.md-view :deep(thead tr) {
  background: rgba(99,102,241,.07);
}
.md-view :deep(th) {
  padding: 10px 14px; font-weight: 600;
  text-align: left; font-size: 12.5px; color: var(--text2);
  border-bottom: 1px solid var(--border);
  letter-spacing: .4px; text-transform: uppercase;
}
.md-view :deep(td) {
  padding: 9px 14px; border-bottom: 1px solid var(--border);
  vertical-align: middle; color: var(--text); font-size: 14px;
}
.md-view :deep(tr:last-child td) { border-bottom: none; }
.md-view :deep(tr:hover td) { background: rgba(99,102,241,.03); }
/* Lists */
.md-view :deep(ul), .md-view :deep(ol) { padding-left: 24px; margin: 8px 0 14px; }
.md-view :deep(li) { margin-bottom: 6px; line-height: 1.75; color: var(--text); }
.md-view :deep(ul li)::marker { color: var(--accent); }
/* Inline elements */
.md-view :deep(strong) { font-weight: 700; color: var(--text); }
.md-view :deep(em) { font-style: italic; color: var(--text2); }
/* Inline code */
.md-view :deep(code) {
  background: rgba(99,102,241,.1); border: none;
  border-radius: 5px; padding: 2px 7px; font-size: 13px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  color: var(--accent);
}
/* Code blocks */
.md-view :deep(pre) {
  background: var(--bg3); border: 1px solid var(--border);
  border-radius: 10px; padding: 18px 20px; margin: 16px 0;
  overflow-x: auto;
}
.md-view :deep(pre code) {
  background: none; border: none; padding: 0; font-size: 13px;
  color: var(--text); line-height: 1.65;
}
/* HR */
.md-view :deep(hr) {
  border: none; height: 1px; margin: 32px 0;
  background: linear-gradient(90deg, transparent, var(--border) 20%, var(--border) 80%, transparent);
}
.md-view :deep(div[align="center"]) { text-align: center; }

/* ── Hoverable English words (markdown + transcript) ── */
.md-view :deep(.dict-word),
.tc-orig :deep(.dict-word) {
  cursor: pointer;
  border-bottom: 1px dashed var(--text3);
  transition: color .12s, border-color .12s;
}
.md-view :deep(.dict-word:hover),
.tc-orig :deep(.dict-word:hover) {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

/* ── Dictionary tooltip card ── */
.dict-tooltip {
  position: fixed;
  z-index: 9999;
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 0 12px 12px 0;
  padding: 14px 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,.18), 0 2px 8px rgba(0,0,0,.1);
  pointer-events: auto;
  transform: translateY(-50%);
}
/* Connecting line from tooltip back toward the word */
.dict-tooltip::before {
  content: '';
  position: absolute;
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  width: 12px;
  height: 2px;
  background: var(--accent);
  opacity: 0.7;
}

/* Tooltip enter/leave transition */
.dt-enter-active { transition: opacity .14s ease, transform .14s ease; }
.dt-leave-active { transition: opacity .1s ease; }
.dt-enter-from   { opacity: 0; transform: translateY(-50%) translateX(-6px); }
.dt-leave-to     { opacity: 0; }

.dt-loading {
  font-size: 13px; color: var(--text3); display: flex; align-items: center; gap: 6px;
}
.dt-spin { display: inline-block; animation: spin .9s linear infinite; }
.dt-not-found { font-size: 12px; color: var(--text3); }

.dt-head {
  display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap;
}
.dt-word    { font-size: 17px; font-weight: 700; color: var(--text); }
.dt-phonetic { font-size: 12px; color: var(--text3); font-family: monospace; flex: 1; }
.dt-audio {
  background: none; border: none; cursor: pointer; font-size: 14px;
  padding: 2px 5px; border-radius: 6px; color: var(--text3); transition: all .15s;
}
.dt-audio:hover { background: var(--bg3); color: var(--accent); }

.dt-meaning { margin-bottom: 9px; }
.dt-meaning:last-child { margin-bottom: 0; }

.dt-pos {
  display: inline-block; padding: 1px 7px; border-radius: 10px; margin-bottom: 4px;
  font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .4px;
  background: rgba(99,102,241,.1); color: var(--accent);
}
.dt-def { font-size: 13px; color: var(--text); margin: 0 0 3px; line-height: 1.5; }
.dt-def-trans { font-size: 12px; color: var(--accent); margin: 0 0 4px; line-height: 1.4; font-weight: 600; }
.dt-ex  { font-size: 12px; color: var(--text3); font-style: italic; margin: 0 0 3px; }
.dt-syns { font-size: 11px; color: var(--text3); margin: 0; }
.dt-syn {
  display: inline-block; margin: 1px 3px 1px 0; padding: 1px 5px;
  background: var(--bg3); border-radius: 4px; font-size: 11px;
}

/* ── Live progress view ── */
.jd-progress-view {
  max-width: 700px; margin: 40px auto; padding: 0 20px;
}
.prog-card {
  background: var(--card); border: 1px solid var(--border); border-radius: 16px;
  padding: 32px 36px; box-shadow: var(--shadow2);
}
.prog-title {
  font-size: 18px; font-weight: 800; color: var(--text); margin-bottom: 24px;
}
.step-bar {
  display: flex; align-items: center; margin-bottom: 20px;
}
.step-dot {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; flex-shrink: 0;
  background: var(--bg3); border: 2px solid var(--border); color: var(--text3);
  transition: all .3s;
}
.step-dot.done { background: var(--accent); border-color: var(--accent); color: #fff; }
.step-dot.active {
  background: rgba(99,102,241,.15); border-color: var(--accent); color: var(--accent);
  box-shadow: 0 0 0 4px rgba(99,102,241,.2); animation: pulse-step 1.5s infinite;
}
@keyframes pulse-step { 0%,100%{box-shadow:0 0 0 4px rgba(99,102,241,.2)} 50%{box-shadow:0 0 0 8px rgba(99,102,241,.05)} }
.step-ln {
  flex: 1; height: 2px; background: var(--border); transition: background .3s;
}
.step-ln.done { background: var(--accent); }
.cur-step {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 600; color: var(--accent); margin-bottom: 16px;
}
.pulse-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--accent);
  animation: blink 1s step-end infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
.pbar-row {
  display: flex; justify-content: space-between; font-size: 12px; color: var(--text2);
  margin-bottom: 6px; font-weight: 600;
}
.pbar-track {
  height: 6px; background: rgba(255,255,255,.06); border-radius: 3px; overflow: hidden;
}
.pbar-fill {
  height: 100%; border-radius: 3px; transition: width .5s; box-shadow: 0 0 8px rgba(167,139,250,.4);
}
.log-box {
  margin-top: 16px; background: var(--bg3); border: 1px solid var(--border); border-radius: 8px;
  padding: 12px 14px; max-height: 280px; overflow-y: auto; font-family: monospace;
  font-size: 12px; line-height: 1.7;
}
.log-line { color: var(--text2); }
.log-line.log-ok { color: var(--ok); }
.log-line.log-err { color: var(--err); }
.log-line.log-warn { color: #f59e0b; }
.cancel-btn {
  padding: 8px 20px; border-radius: 8px; border: 1px solid rgba(248,113,113,.3);
  background: transparent; color: var(--err); font-size: 13px; cursor: pointer; transition: all .15s;
}
.cancel-btn:hover { background: rgba(248,113,113,.1); }
</style>
