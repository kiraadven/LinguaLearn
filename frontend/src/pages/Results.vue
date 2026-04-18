<template>
  <div class="results-page page-inner">
    <!-- Aurora glow orbs -->
    <div class="rs-glow rs-glow-a"></div>
    <div class="rs-glow rs-glow-b"></div>

    <div class="rs-inner">
      <!-- Compact header (no big title) -->
      <div class="rs-header">
        <div class="rs-header-left">
          <div class="rs-badge">📚 {{ t.results_title }}</div>
          <p class="rs-sub">{{ t.results_subtitle }}</p>
        </div>
        <button class="rs-create-btn" @click="$router.push('/create')">
          + {{ t.nav_create }}
        </button>
      </div>

      <div v-if="!isLoggedIn" class="empty-state">
        <div class="empty-icon">🔒</div>
        <p class="empty-title">{{ t.create_login_required }}</p>
        <button class="btn-primary" @click="openAuth()">{{ t.nav_login_register }}</button>
      </div>
      <div v-else-if="loading" class="empty-state">
        <div class="spin-lg">⟳</div>
        <p class="empty-sub">{{ t.results_loading }}</p>
      </div>
      <div v-else-if="jobs.length === 0" class="empty-state">
        <div class="empty-icon">📭</div>
        <p class="empty-title">{{ t.results_empty }}</p>
        <p class="empty-sub">{{ t.results_go_create }}</p>
        <button class="btn-primary" @click="$router.push('/create')">{{ t.nav_create }}</button>
      </div>
      <div v-else>
        <!-- Filter bar -->
        <div class="filter-bar">
          <button v-for="f in filterItems" :key="f.val"
            :class="['filter-btn', { active: jobFilter === f.val }]"
            @click="jobFilter = f.val">{{ f.label }}
          </button>
          <button class="filter-btn refresh-btn" @click="loadJobs" :title="t.results_loading">
            ⟳
          </button>
        </div>

        <!-- Job grid -->
        <div class="job-grid">
          <div v-for="j in filteredJobs" :key="j.id" class="job-card" :class="'status-' + j.status">
            <!-- Main clickable area -->
            <div class="jc-body" @click="onJobCardClick(j)">
              <div class="jc-top">
                <span :class="['jc-status-dot', statusDotClass(j.status)]"></span>
                <span class="jc-name">{{ j.name || j.video_filename || j.id.slice(0, 12) }}</span>
                <span v-if="j.status === 'done'" class="jc-arrow">›</span>
                <span v-else-if="j.status === 'running'" class="jc-arrow spin-inline">⟳</span>
                <span v-else-if="j.status === 'queued'" class="jc-arrow muted">⏳</span>
              </div>
              <div class="jc-meta">
                <span :class="['jc-status-label', statusDotClass(j.status)]">{{ statusLabel(j.status) }}</span>
                <span class="meta-sep">·</span>
                <span>{{ j.source_lang || '?' }} → {{ j.target_lang || '?' }}</span>
                <span class="meta-sep">·</span>
                <span>{{ fmtDate(j.created_at) }}</span>
              </div>
              <p v-if="j.error" class="jc-error">{{ j.error }}</p>
            </div>

            <!-- Actions row -->
            <div class="jc-actions">
              <template v-if="renamingId === j.id">
                <input class="input rename-input" v-model="renameVal" :placeholder="t.results_rename"
                  @keyup.enter="confirmRename(j)" @keyup.escape="renamingId = null">
                <button class="act-btn ok-btn" @click="confirmRename(j)">✓</button>
                <button class="act-btn" @click="renamingId = null">✕</button>
              </template>
              <template v-else>
                <button class="act-btn" @click.stop="startRename(j)" :title="t.results_rename">✏️</button>
                <button class="act-btn del-btn" @click.stop="deleteJob(j)" :title="t.results_delete">🗑️</button>
                <a v-if="j.status === 'done' && j.result?.full_video"
                   :href="`/api/jobs/${j.id}/download/${encodeURIComponent(j.result.full_video)}`"
                   download class="act-btn dl-btn" :title="t.results_download">⬇</a>
              </template>
            </div>
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

const jobs       = ref([])
const loading    = ref(false)
const jobFilter  = ref('all')
const renamingId = ref(null)
const renameVal  = ref('')

const filterItems = computed(() => ([
  { val: 'all',     label: t.value.results_all },
  { val: 'done',    label: t.value.results_done },
  { val: 'running', label: t.value.results_processing },
  { val: 'error',   label: t.value.results_failed },
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
  } catch (e) {
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
      body: fd,
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
      headers: { Authorization: 'Bearer ' + localStorage.getItem('ll_token') },
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
  return { done: 'dot-ok', running: 'dot-run', error: 'dot-err', queued: 'dot-wait', cancelled: 'dot-wait' }[s] || 'dot-wait'
}

function fmtDate(s) {
  return s ? new Date(s).toLocaleDateString(uiLang.value || 'en-US') : '—'
}

function onJobCardClick(j) {
  if (j.status === 'done' || j.status === 'running' || j.status === 'queued') {
    router.push('/results/' + j.id)
  }
}

watch(isLoggedIn, v => { if (v) loadJobs() }, { immediate: true })
</script>

<style scoped>
.results-page {
  padding: 28px 24px 80px;
  max-width: 1200px;
  margin: 0 auto;
  position: relative;
}

/* Aurora orbs */
.rs-glow {
  position: fixed;
  border-radius: 50%;
  filter: blur(90px);
  pointer-events: none;
  z-index: 0;
}
.rs-glow-a { width: 460px; height: 460px; top: -80px; right: -100px; background: radial-gradient(circle, rgba(11,120,209,0.12), transparent 70%); animation: rsDrift 16s ease-in-out infinite; }
.rs-glow-b { width: 380px; height: 380px; bottom: 60px; left: -80px; background: radial-gradient(circle, rgba(242,168,44,0.1), transparent 70%); animation: rsDrift 20s ease-in-out infinite reverse; }
@keyframes rsDrift { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(28px); } }

.rs-inner { position: relative; z-index: 1; }

/* Compact header */
.rs-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}
.rs-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid rgba(11,120,209,0.2);
  background: linear-gradient(120deg, rgba(255,255,255,0.88), rgba(240,249,255,0.75));
  backdrop-filter: blur(8px);
  font-size: 13px;
  font-weight: 700;
  color: #0d4d80;
  margin-bottom: 6px;
}
.rs-sub { font-size: 13px; color: var(--text3); }
.rs-create-btn {
  padding: 9px 20px;
  border-radius: 12px;
  background: linear-gradient(135deg, #0b78d1, #06b6d4);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  border: none;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 4px 16px rgba(11,120,209,0.28);
  transition: transform 0.18s, box-shadow 0.18s;
  flex-shrink: 0;
}
.rs-create-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(11,120,209,0.35); }

/* Empty states */
.empty-state { text-align: center; padding: 100px 24px; display: flex; flex-direction: column; align-items: center; gap: 12px; }
.empty-icon { font-size: 72px; }
.empty-title { font-size: 18px; font-weight: 700; color: var(--text); }
.empty-sub { color: var(--text2); font-size: 14px; margin-bottom: 8px; }
.spin-lg { font-size: 32px; animation: spin 1s linear infinite; }

/* Filter */
.filter-bar { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 20px; align-items: center; }
.filter-btn {
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text3);
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s;
}
.filter-btn:hover { color: var(--text); background: var(--bg3); }
.filter-btn.active { color: #0b78d1; background: rgba(11,120,209,0.08); border-color: rgba(11,120,209,0.2); }
.refresh-btn { margin-left: auto; opacity: 0.6; }
.refresh-btn:hover { opacity: 1; }

/* Job grid */
.job-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.job-card {
  border-radius: 16px;
  border: 1px solid rgba(148,163,184,0.25);
  background:
    radial-gradient(120% 100% at 0% 0%, rgba(11,120,209,0.06), transparent 50%),
    linear-gradient(160deg, rgba(255,255,255,0.96), rgba(248,252,255,0.9));
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 16px rgba(13,59,102,0.06);
  overflow: hidden;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.job-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 14px 36px rgba(11,120,209,0.14);
  border-color: rgba(11,120,209,0.28);
}
.job-card.status-done { border-color: rgba(11,120,209,0.18); }
.job-card.status-error { border-color: rgba(239,68,68,0.2); background: linear-gradient(160deg, rgba(254,242,242,0.9), rgba(255,255,255,0.95)); }

.jc-body {
  padding: 16px 16px 12px;
  cursor: pointer;
}

.jc-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.jc-status-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
.jc-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.jc-arrow { color: var(--text3); font-size: 18px; }
.spin-inline { animation: spin 0.8s linear infinite; }
.muted { opacity: 0.5; }

.jc-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 11px;
  color: var(--text3);
}
.jc-status-label { font-weight: 600; }
.meta-sep { opacity: 0.5; }
.jc-error { font-size: 12px; color: var(--err); margin-top: 6px; }

/* AI entry bar */
.jc-ai-bar {
  padding: 8px 12px 6px;
  border-top: 1px solid rgba(11,120,209,0.1);
  background: linear-gradient(90deg, rgba(11,120,209,0.04), rgba(6,182,212,0.03));
}
.ai-entry-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(11,120,209,0.12), rgba(6,182,212,0.08));
  border: 1px solid rgba(11,120,209,0.2);
  color: #0d4d80;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.18s;
}
.ai-entry-btn:hover {
  background: linear-gradient(135deg, rgba(11,120,209,0.2), rgba(6,182,212,0.14));
  border-color: rgba(11,120,209,0.35);
  transform: translateY(-1px);
}

/* Actions */
.jc-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  background: rgba(248,250,252,0.8);
  border-top: 1px solid rgba(148,163,184,0.15);
}
.rename-input { flex: 1; padding: 4px 8px; font-size: 12px; margin-bottom: 0; }
.act-btn {
  padding: 4px 9px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  background: transparent;
  border: 1px solid rgba(148,163,184,0.25);
  color: var(--text3);
  transition: all 0.15s;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}
.act-btn:hover { background: rgba(255,255,255,0.8); color: var(--text); }
.ok-btn { color: var(--ok); border-color: rgba(16,185,129,0.3); }
.ok-btn:hover { background: rgba(16,185,129,0.1); }
.del-btn:hover { background: rgba(239,68,68,0.08); color: var(--err); border-color: rgba(239,68,68,0.2); }
.dl-btn { margin-left: auto; }

@keyframes spin { to { transform: rotate(360deg); } }
</style>
