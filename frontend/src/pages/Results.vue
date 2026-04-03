<template>
  <div class="results-page page-inner">
    <div class="page-header">
      <h1>{{ t.results_title }}</h1>
      <p>{{ t.results_subtitle }}</p>
    </div>

    <div v-if="!isLoggedIn" class="empty-state">
      <div class="empty-icon">🔒</div>
      <p class="empty-title">{{ t.create_login_required }}</p>
      <button class="btn-primary" @click="openAuth()">{{ t.nav_login_register }}</button>
    </div>
    <div v-else-if="loading" class="empty-state">
      <div style="font-size:32px;animation:spin 1s linear infinite">⟳</div>
      <p class="empty-sub" style="margin-top:12px">{{ t.results_loading }}</p>
    </div>
    <div v-else-if="jobs.length===0" class="empty-state">
      <div class="empty-icon">📭</div>
      <p class="empty-title">{{ t.results_empty }}</p>
      <p class="empty-sub">{{ t.results_go_create }}</p>
      <button class="btn-primary" @click="$router.push('/create')">{{ t.nav_create }}</button>
    </div>
    <div v-else>
      <!-- Filter bar -->
      <div class="filter-bar">
        <button v-for="f in filterItems" :key="f.val"
          :class="['filter-btn', {active: jobFilter===f.val}]"
          @click="jobFilter=f.val">{{ f.label }}
        </button>
        <button class="filter-btn" @click="loadJobs" :title="t.results_loading" style="margin-left:auto">⟳ {{ t.results_loading }}</button>
      </div>

      <!-- Job list -->
      <div class="job-grid">
        <div v-for="j in filteredJobs" :key="j.id" class="job-card">
          <!-- Clickable area -->
          <div class="job-card-body" @click="onJobCardClick(j)"
               :style="{cursor: (j.status==='done'||j.status==='running'||j.status==='queued')?'pointer':'default'}">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
              <div :class="['jc-dot', statusDotClass(j.status)]"></div>
              <div class="jc-name">{{ j.name || j.video_filename || j.id.slice(0,12) }}</div>
              <div v-if="j.status==='done'" class="jc-arrow">›</div>
            <div v-else-if="j.status==='running'" class="jc-arrow" style="animation:spin .8s linear infinite">⟳</div>
            <div v-else-if="j.status==='queued'" class="jc-arrow" style="opacity:.5">⏳</div>
            </div>
            <div class="jc-meta">
              <span :class="statusDotClass(j.status)">{{ statusLabel(j.status) }}</span>
              · {{ j.source_lang||'?' }} → {{ j.target_lang||'?' }}
              · {{ fmtDate(j.created_at) }}
            </div>
            <p v-if="j.error" style="font-size:12px;color:var(--err);margin-top:6px">{{ j.error }}</p>
          </div>

          <!-- Actions row -->
          <div class="job-card-actions">
            <template v-if="renamingId===j.id">
              <input class="input rename-input" v-model="renameVal" :placeholder="t.results_rename" @keyup.enter="confirmRename(j)" @keyup.escape="renamingId=null">
              <button class="act-btn ok-btn" @click="confirmRename(j)">✓</button>
              <button class="act-btn" @click="renamingId=null">✕</button>
            </template>
            <template v-else>
              <button class="act-btn" @click.stop="startRename(j)" :title="t.results_rename">✏️</button>
              <button class="act-btn del-btn" @click.stop="deleteJob(j)" :title="t.results_delete">🗑️</button>
              <a v-if="j.status==='done' && j.result?.full_video"
                 :href="`/api/jobs/${j.id}/download/${encodeURIComponent(j.result.full_video)}`"
                 download class="act-btn dl-act" :title="t.results_download">⬇</a>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'
import { apiFetch } from '../composables/useApi.js'
import { useI18n } from '../i18n.js'

const { isLoggedIn } = useAuth()
const openAuth = inject('openAuth')
const toast    = inject('toast')
const router   = useRouter()
const { t, uiLang } = useI18n()

const jobs      = ref([])
const loading   = ref(false)
const jobFilter = ref('all')
const renamingId = ref(null)
const renameVal  = ref('')

const filterItems = computed(() => ([
  {val:'all', label: t.value.results_all},
  {val:'done', label: t.value.results_done},
  {val:'running', label: t.value.results_processing},
  {val:'error', label: t.value.results_failed},
]))

const filteredJobs = computed(() => {
  if (jobFilter.value === 'all') return jobs.value
  return jobs.value.filter(j => j.status === jobFilter.value)
})

async function loadJobs() {
  if (!isLoggedIn.value) return
  loading.value = true
  try {
    const d = await apiFetch('/api/jobs')
    jobs.value = (d.jobs || []).sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } catch(e) {
    toast(`${t.value.results_load_failed}: ${e.message}`, 'err')
  } finally {
    loading.value = false
  }
}

function startRename(j) {
  renamingId.value = j.id
  renameVal.value  = j.name || j.video_filename || ''
}

async function confirmRename(j) {
  const name = renameVal.value.trim()
  if (!name) { renamingId.value = null; return }
  try {
    const fd = new FormData(); fd.append('name', name)
    await fetch(`/api/jobs/${j.id}`, {
      method: 'PATCH',
      headers: { Authorization: 'Bearer ' + localStorage.getItem('ll_token') },
      body: fd
    })
    j.name = name
    toast(t.value.results_renamed, 'ok')
  } catch { toast(t.value.results_rename_failed, 'err') }
  renamingId.value = null
}

async function deleteJob(j) {
  const label = j.name || j.video_filename || j.id.slice(0, 12)
  if (!confirm(`${t.value.results_delete_confirm}\n${label}`)) return
  try {
    const r = await fetch(`/api/jobs/${j.id}`, {
      method: 'DELETE',
      headers: { Authorization: 'Bearer ' + localStorage.getItem('ll_token') }
    })
    if (!r.ok) throw new Error()
    jobs.value = jobs.value.filter(x => x.id !== j.id)
    toast(t.value.results_deleted, 'ok')
  } catch { toast(t.value.results_delete_failed, 'err') }
}

function statusLabel(s) {
  return {
    done: t.value.results_status_done,
    running: t.value.results_status_running,
    error: t.value.results_status_failed,
    queued: t.value.results_status_queued,
    cancelled: t.value.create_cancel,
  }[s] || s
}
function statusDotClass(s) {
  return {done:'dot-ok', running:'dot-run', error:'dot-err', queued:'dot-wait', cancelled:'dot-wait'}[s] || 'dot-wait'
}
function fmtDate(s) { return s ? new Date(s).toLocaleDateString(uiLang.value || 'en-US') : '—' }

function onJobCardClick(j) {
  if (j.status === 'done' || j.status === 'running' || j.status === 'queued') {
    router.push('/results/' + j.id)
  }
}

watch(isLoggedIn, v => { if (v) loadJobs() }, { immediate: true })
</script>

<style scoped>
.results-page { padding: 32px 24px 80px; max-width: 1200px; margin: 0 auto; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 30px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 6px; color: var(--text); }
.page-header p { color: var(--text2); font-size: 14px; }

.empty-state { text-align: center; padding: 100px 24px; display: flex; flex-direction: column; align-items: center; gap: 12px; }
.empty-icon { font-size: 72px; }
.empty-title { font-size: 18px; font-weight: 700; color: var(--text); }
.empty-sub { color: var(--text2); font-size: 14px; margin-bottom: 8px; }

.filter-bar { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 20px; }
.filter-btn { padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;
  color: var(--text3); background: transparent; border: 1px solid transparent; transition: all .15s; cursor: pointer; }
.filter-btn:hover { color: var(--text); background: var(--bg3); }
.filter-btn.active { color: var(--accent); background: rgba(99,102,241,.08); border-color: rgba(99,102,241,.2); }

.job-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }

.job-card {
  background: var(--card); border: 1px solid var(--border); border-radius: var(--r);
  overflow: hidden; box-shadow: var(--shadow); transition: all .2s;
}
.job-card:hover { box-shadow: var(--shadow2); border-color: rgba(99,102,241,.25); }

.job-card-body { padding: 16px 16px 12px; }
.jc-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
.jc-name { font-size: 14px; font-weight: 700; color: var(--text); flex: 1; min-width: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.jc-arrow { color: var(--text3); font-size: 20px; }
.jc-meta { font-size: 11px; color: var(--text3); }

.job-card-actions {
  display: flex; align-items: center; gap: 6px; padding: 8px 12px;
  background: var(--bg3); border-top: 1px solid var(--border);
}
.rename-input { flex: 1; padding: 5px 9px; font-size: 12px; margin-bottom: 0; }
.act-btn {
  padding: 5px 10px; border-radius: 6px; font-size: 12px; cursor: pointer;
  background: transparent; border: 1px solid var(--border); color: var(--text3);
  transition: all .15s; text-decoration: none; display: inline-flex; align-items: center;
}
.act-btn:hover { background: var(--bg2); color: var(--text); }
.ok-btn { color: var(--ok); border-color: rgba(16,185,129,.3); }
.ok-btn:hover { background: rgba(16,185,129,.1); }
.del-btn:hover { background: rgba(239,68,68,.08); color: var(--err); border-color: rgba(239,68,68,.2); }
.dl-act { margin-left: auto; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
