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
    <div v-else-if="job.status !== 'done'" class="jd-center">
      <p style="font-size:48px">{{ job.status==='error'?'❌':'⚙️' }}</p>
      <p style="font-weight:700;margin-top:8px">{{ job.step_name || job.status }}</p>
      <p v-if="job.error" style="color:var(--err);font-size:13px;margin-top:6px">{{ job.error }}</p>
    </div>

    <div v-else-if="job" class="jd-body">

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
            <div class="tc-list" ref="tcListEl">
              <div v-if="!segments.length && !segLoading" class="tc-empty">暂无文稿数据</div>
              <div v-for="(s, i) in segments" :key="i"
                   :ref="el => segRefs[i] = el"
                   :class="['tc-item', {active: i === activeSeg}]"
                   @click="jumpTo(s.start)">
                <button class="tc-ts" @click.stop="jumpTo(s.start)">▶ {{ fmtTime(s.start) }}</button>
                <div class="tc-texts">
                  <p class="tc-orig">{{ s.text }}</p>
                  <p v-if="sentences[i]?.chinese_translation" class="tc-trans">{{ sentences[i].chinese_translation }}</p>
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
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <a v-if="job.result?.markdown"
               :href="`/api/jobs/${jobId}/download/${encodeURIComponent(job.result.markdown)}`"
               download class="dl-chip">⬇ 下载笔记</a>
          </div>
        </div>

        <!-- Introduction -->
        <div v-if="intro" class="intro-card">
          <div class="intro-label">内容简介</div>
          <p class="intro-text">{{ intro }}</p>
        </div>

        <!-- Per-sentence cards -->
        <div v-for="(s, i) in sentences" :key="i" :id="`sent-${i}`" class="sent-card">
          <div class="sent-head" @click="jumpTo(segments[i]?.start || 0)">
            <span class="sent-idx">{{ i + 1 }}</span>
            <p class="sent-orig">{{ s.original_text }}</p>
            <span v-if="segments[i]" class="sent-ts" @click.stop="jumpTo(segments[i].start)">
              ▶ {{ fmtTime(segments[i].start) }}
            </span>
          </div>
          <p class="sent-trans">{{ s.chinese_translation }}</p>

          <!-- Vocabulary table -->
          <div v-if="s.key_words?.length" class="vocab-wrap">
            <div class="vocab-label">📚 重难点词汇</div>
            <table class="vocab-table">
              <thead><tr><th>词汇</th><th>发音</th><th>释义</th><th>难度</th></tr></thead>
              <tbody>
                <tr v-for="w in s.key_words" :key="w.word">
                  <td class="vocab-word">{{ w.word }}</td>
                  <td class="vocab-phonetic">{{ w.phonetic }}</td>
                  <td class="vocab-trans">{{ w.translation }}</td>
                  <td class="vocab-diff">
                    <span v-for="n in 5" :key="n" :style="{color: n<=w.difficulty?'#f59e0b':'#e2e8f0',fontSize:'10px'}">★</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Expressions -->
          <div v-if="s.useful_expressions?.length" class="expr-wrap">
            <div class="expr-label">💬 实用表达</div>
            <div class="expr-list">
              <div v-for="e in s.useful_expressions" :key="e.english" class="expr-item">
                <span class="expr-en">{{ e.english }}</span>
                <span class="expr-sep">—</span>
                <span class="expr-cn">{{ e.chinese }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch } from '../composables/useApi.js'

const route  = useRoute()
const router = useRouter()
const jobId  = route.params.id

const job        = ref(null)
const loading    = ref(true)
const videoEl    = ref(null)
const videoError = ref('')
const segments   = ref([])
const sentences  = ref([])
const segLoading = ref(false)
const activeSeg  = ref(-1)
const segRefs    = ref([])
const tcListEl   = ref(null)
const transcriptOpen = ref(true)
const intro      = ref('')

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
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

async function loadSegments() {
  segLoading.value = true
  try {
    const d = await apiFetch(`/api/jobs/${jobId}/segments`)
    segments.value = Array.isArray(d) ? d : []
  } catch { segments.value = [] }
  finally { segLoading.value = false }
}

async function loadMarkdown(mdFile) {
  try {
    const d = await apiFetch(`/api/jobs/${jobId}/preview/${encodeURIComponent(mdFile)}`)
    const text = d.content || ''
    parseMd(text)
  } catch {}
}

// Parse the markdown format from markdown_exporter.py
function parseMd(text) {
  // Extract introduction (between ## 📖 and ## 📄)
  const introMatch = text.match(/##\s*📖[^\n]*\n+([\s\S]*?)(?=##\s*📄|##\s*🔹|$)/)
  if (introMatch) {
    intro.value = introMatch[1].replace(/>\s*\*(.+)\*/g, '$1').replace(/[>\*\-\n]/g, ' ').trim()
  }

  // Split by sentence sections ## 🔹 句子 N (or Sentence N etc.)
  const sections = text.split(/\n##\s*🔹[^\n]*\n/)
  if (sections.length < 2) return

  const parsed = []
  for (let i = 1; i < sections.length; i++) {
    const sec = sections[i]
    // Original text: > **text**
    const origMatch = sec.match(/###[^\n]*📝[^\n]*\n+>\s*\*\*([^*]+)\*\*/)
    const origText = origMatch ? origMatch[1].trim() : ''
    // Translation: > *text*
    const transMatch = sec.match(/###[^\n]*🌐[^\n]*\n+>\s*\*([^*]+)\*/)
    const transText = transMatch ? transMatch[1].trim() : ''
    // Keywords table rows: | n | **word** | phonetic | translation |
    const keyWords = []
    const tableSection = sec.match(/###[^\n]*📚[^\n]*([\s\S]*?)(?=###|$)/)
    if (tableSection) {
      const rows = tableSection[1].matchAll(/\|\s*\d+\s*\|\s*\*\*([^*]+)\*\*\s*\|\s*([^|]*)\|\s*([^|]*)\|/)
      for (const r of rows) {
        keyWords.push({ word: r[1].trim(), phonetic: r[2].trim(), translation: r[3].trim(), difficulty: 3 })
      }
    }
    // Expressions: - **expr** — *cn*
    const expressions = []
    const exprSection = sec.match(/###[^\n]*💬[^\n]*([\s\S]*?)(?=###|$)/)
    if (exprSection) {
      const rows = exprSection[1].matchAll(/-\s*\*\*([^*]+)\*\*\s*[—-]\s*\*([^*]+)\*/)
      for (const r of rows) {
        expressions.push({ english: r[1].trim(), chinese: r[2].trim() })
      }
    }
    parsed.push({
      original_text: origText,
      chinese_translation: transText,
      key_words: keyWords,
      useful_expressions: expressions,
    })
  }
  sentences.value = parsed
}

function onTimeUpdate() {
  if (!videoEl.value || !segments.value.length) return
  const ct = videoEl.value.currentTime
  let idx = -1
  for (let i = 0; i < segments.value.length; i++) {
    if (ct >= segments.value[i].start && ct < segments.value[i].end) { idx = i; break }
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
.tc-list { flex: 1; overflow-y: auto; }
.tc-empty { text-align: center; padding: 32px; font-size: 13px; color: var(--text3); }

.tc-item {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 10px 12px; cursor: pointer; border-left: 3px solid transparent;
  border-bottom: 1px solid var(--border); transition: all .15s;
}
.tc-item:last-child { border-bottom: none; }
.tc-item:hover { background: rgba(99,102,241,.04); }
.tc-item.active {
  background: rgba(99,102,241,.08); border-left-color: var(--accent);
}
.tc-ts {
  flex-shrink: 0; padding: 3px 8px; border-radius: 10px;
  background: var(--bg3); border: 1px solid var(--border);
  color: var(--text3); font-size: 11px; font-weight: 700;
  cursor: pointer; white-space: nowrap; transition: all .15s;
}
.tc-ts:hover, .tc-item.active .tc-ts {
  background: var(--accent); color: #fff; border-color: var(--accent);
}
.tc-texts { flex: 1; min-width: 0; }
.tc-orig { font-size: 13px; color: var(--text); line-height: 1.5; margin: 0 0 3px; }
.tc-trans { font-size: 11px; color: var(--text3); margin: 0; }
.tc-item.active .tc-orig { color: var(--text); font-weight: 600; }

/* Slide transition */
.panel-enter-active, .panel-leave-active { transition: all .3s ease; overflow: hidden; }
.panel-enter-from { opacity: 0; transform: translateX(20px); }
.panel-leave-to { opacity: 0; transform: translateX(20px); }

/* Notes section */
.jd-notes { padding-top: 8px; }
.notes-hdr {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
  gap: 10px; margin-bottom: 20px; padding-bottom: 14px; border-bottom: 2px solid var(--border);
}
.notes-hdr-title { font-size: 18px; font-weight: 800; color: var(--text); }

.intro-card {
  background: linear-gradient(135deg, rgba(99,102,241,.06), rgba(244,63,94,.04));
  border: 1px solid rgba(99,102,241,.15); border-radius: 12px;
  padding: 20px 24px; margin-bottom: 20px;
}
.intro-label { font-size: 11px; font-weight: 800; letter-spacing: 2px; color: var(--accent);
  text-transform: uppercase; margin-bottom: 10px; }
.intro-text { font-size: 14px; color: var(--text2); line-height: 1.75; margin: 0; }

/* Sentence cards */
.sent-card {
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  padding: 20px; margin-bottom: 14px; box-shadow: var(--shadow);
  transition: box-shadow .2s;
}
.sent-card:hover { box-shadow: var(--shadow2); }
.sent-head {
  display: flex; align-items: baseline; gap: 10px; cursor: pointer;
  margin-bottom: 8px;
}
.sent-idx {
  flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff; font-size: 11px; font-weight: 800;
  display: inline-flex; align-items: center; justify-content: center;
}
.sent-orig {
  flex: 1; font-size: 16px; font-weight: 700; color: var(--text);
  line-height: 1.45; margin: 0;
}
.sent-ts {
  flex-shrink: 0; padding: 3px 10px; border-radius: 10px;
  background: rgba(99,102,241,.08); border: 1px solid rgba(99,102,241,.2);
  color: var(--accent); font-size: 11px; font-weight: 700; cursor: pointer;
  transition: all .15s; white-space: nowrap;
}
.sent-ts:hover { background: var(--accent); color: #fff; }
.sent-trans {
  font-size: 14px; color: var(--text2); margin: 0 0 14px;
  padding-left: 34px; line-height: 1.6; font-style: italic;
}

/* Vocabulary table */
.vocab-wrap { margin-bottom: 14px; }
.vocab-label { font-size: 11px; font-weight: 700; color: var(--text3);
  letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px; }
.vocab-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.vocab-table th {
  text-align: left; padding: 7px 10px; background: var(--bg3);
  border: 1px solid var(--border); font-size: 11px; font-weight: 700;
  color: var(--text3); text-transform: uppercase; letter-spacing: .5px;
}
.vocab-table td { padding: 8px 10px; border: 1px solid var(--border); vertical-align: middle; }
.vocab-word { font-weight: 700; color: var(--accent); font-size: 14px; }
.vocab-phonetic { color: var(--text3); font-size: 12px; font-style: italic; }
.vocab-trans { color: var(--text2); }
.vocab-diff { white-space: nowrap; }
.vocab-table tr:hover td { background: var(--bg3); }

/* Expressions */
.expr-wrap { }
.expr-label { font-size: 11px; font-weight: 700; color: var(--text3);
  letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px; }
.expr-list { display: flex; flex-direction: column; gap: 6px; }
.expr-item {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 12px; border-radius: 8px;
  background: rgba(244,63,94,.04); border: 1px solid rgba(244,63,94,.12);
}
.expr-en { font-size: 13px; font-weight: 700; color: var(--accent2); }
.expr-sep { color: var(--text3); }
.expr-cn { font-size: 12px; color: var(--text2); }

/* DL chip */
.dl-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 7px 14px; border-radius: 8px;
  background: rgba(99,102,241,.08); border: 1px solid rgba(99,102,241,.2);
  color: var(--accent); font-size: 12px; font-weight: 600; transition: all .2s;
  white-space: nowrap;
}
.dl-chip:hover { background: rgba(99,102,241,.15); }
</style>
