<template>
  <div class="memory-panel" :class="{ collapsed: !expanded }">
    <div class="mp-header" @click="expanded = !expanded">
      <span class="mp-icon">🧠</span>
      <span class="mp-title">学习记录</span>
      <span class="mp-toggle">{{ expanded ? '▲' : '▼' }}</span>
    </div>

    <div v-if="expanded" class="mp-body">
      <!-- Loading -->
      <div v-if="loading" class="mp-loading">加载中...</div>

      <!-- Error -->
      <div v-else-if="error" class="mp-error">{{ error }}</div>

      <template v-else-if="data">
        <!-- Learner info -->
        <div class="mp-section">
          <div class="mp-label">学习者</div>
          <div class="mp-value">{{ data.name }} · {{ data.level }} · {{ data.total_sessions }} 次课</div>
        </div>

        <!-- Course progress (for job-specific view) -->
        <div v-if="data.course_progress?.total_sentences" class="mp-section">
          <div class="mp-label">本课进度</div>
          <div class="mp-progress-bar">
            <div
              class="mp-progress-fill"
              :style="{ width: progressPct + '%' }"
            ></div>
          </div>
          <div class="mp-value mp-small">
            {{ data.course_progress.sentences_covered }}/{{ data.course_progress.total_sentences }} 句 ·
            平均掌握 {{ (data.course_progress.avg_mastery * 100).toFixed(0) }}%
          </div>

          <!-- Per-sentence mastery dots -->
          <div class="mp-dots">
            <div
              v-for="(_, i) in Array(data.course_progress.total_sentences)"
              :key="i"
              class="mp-dot"
              :style="{ background: getDotColor(data.course_progress.per_sentence?.[i]?.mastery) }"
              :title="`句子${i+1}: 掌握${((data.course_progress.per_sentence?.[i]?.mastery || 0)*100).toFixed(0)}%`"
            ></div>
          </div>
        </div>

        <!-- Quiz summary -->
        <div class="mp-section">
          <div class="mp-label">Quiz 情况</div>
          <div v-if="data.quiz_summary?.last_quiz_date" class="mp-value">
            完成率 {{ (data.quiz_summary.completion_rate * 100).toFixed(0) }}%
            <span v-if="data.quiz_summary.completion_rate < 0.5" class="mp-warn">⚠ 较低</span>
          </div>
          <div v-else class="mp-value mp-dim">暂无 Quiz 记录</div>
          <div v-if="data.quiz_summary?.error_words?.length" class="mp-tags">
            <span class="mp-tag mp-tag-warn" v-for="w in data.quiz_summary.error_words.slice(0,5)" :key="w">
              {{ w }}
            </span>
          </div>
        </div>

        <!-- Interests & weak areas -->
        <div class="mp-section">
          <div class="mp-label">学习画像</div>
          <div v-if="data.learner_graph?.interests?.length" class="mp-tags">
            <span class="mp-tag" v-for="tag in data.learner_graph.interests.slice(0,5)" :key="tag">
              {{ tag }}
            </span>
          </div>
          <div v-if="data.learner_graph?.weak_areas?.length" class="mp-value mp-small" style="margin-top:4px">
            弱项词汇：{{ data.learner_graph.weak_areas.join(', ') }}
          </div>
          <div v-if="!data.learner_graph?.interests?.length && !data.learner_graph?.weak_areas?.length" class="mp-value mp-dim">
            通过多次上课积累画像
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'

const props = defineProps({
  learnerId: { type: String, required: true },
  jobId: { type: String, default: '' },
})

const expanded = ref(false)
const loading = ref(false)
const error = ref('')
const data = ref(null)

const AI_TUTOR_PORT = 8080

const progressPct = computed(() => {
  if (!data.value?.course_progress?.total_sentences) return 0
  const { sentences_covered, total_sentences } = data.value.course_progress
  return Math.round((sentences_covered / total_sentences) * 100)
})

function getDotColor(mastery) {
  if (!mastery) return 'var(--text4, #555)'
  if (mastery >= 0.8) return '#10b981'
  if (mastery >= 0.5) return '#f59e0b'
  return '#ef4444'
}

async function fetchMemory() {
  if (!props.learnerId) return
  loading.value = true
  error.value = ''
  try {
    const params = props.jobId ? `?job_id=${encodeURIComponent(props.jobId)}` : ''
    const url = `http://${location.hostname}:${AI_TUTOR_PORT}/ai-tutor/learner/${encodeURIComponent(props.learnerId)}/memory${params}`
    const resp = await fetch(url)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    data.value = await resp.json()
  } catch (e) {
    error.value = '加载失败: ' + e.message
  } finally {
    loading.value = false
  }
}

watch(() => props.learnerId, fetchMemory)
watch(() => expanded.value, (val) => { if (val && !data.value) fetchMemory() })
onMounted(fetchMemory)
</script>

<style scoped>
.memory-panel {
  background: var(--surface2, #1e1e2e);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 10px;
  overflow: hidden;
  font-size: 13px;
}

.mp-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  background: var(--surface3, #252538);
}

.mp-icon { font-size: 16px; }
.mp-title { flex: 1; font-weight: 600; color: var(--text1, #eee); }
.mp-toggle { color: var(--text3, #888); font-size: 11px; }

.mp-body {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mp-loading, .mp-error { color: var(--text3, #888); font-size: 12px; }
.mp-error { color: var(--err, #ef4444); }

.mp-section {}
.mp-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent, #a78bfa);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}
.mp-value { color: var(--text1, #eee); line-height: 1.5; }
.mp-small { font-size: 12px; color: var(--text2, #bbb); }
.mp-dim { color: var(--text3, #888); font-style: italic; }
.mp-warn { color: #f59e0b; font-size: 11px; margin-left: 4px; }

.mp-progress-bar {
  height: 6px;
  background: var(--surface4, #333);
  border-radius: 3px;
  overflow: hidden;
  margin: 4px 0;
}
.mp-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent, #a78bfa), var(--accent2, #818cf8));
  border-radius: 3px;
  transition: width 0.4s;
}

.mp-dots {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}
.mp-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  cursor: default;
  transition: transform 0.15s;
}
.mp-dot:hover { transform: scale(1.4); }

.mp-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.mp-tag {
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--surface4, #333);
  color: var(--text2, #bbb);
  font-size: 11px;
}
.mp-tag-warn { background: rgba(239,68,68,0.15); color: #f87171; }
</style>
