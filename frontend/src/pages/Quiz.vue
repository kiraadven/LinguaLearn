<template>
  <div class="quiz-page page-inner">
    <!-- Phase 1: Job selection -->
    <template v-if="phase === 'select'">
      <div class="page-header">
        <h1>学习成果自测</h1>
        <p>选择一个已完成的视频，开始默写测试</p>
      </div>

      <div v-if="!isLoggedIn" class="empty-state">
        <div class="empty-icon">🔒</div>
        <p class="empty-title">请先登录</p>
        <button class="btn-primary" @click="openAuth()">登录 / 注册</button>
      </div>
      <div v-else-if="jobsLoading" class="empty-state">
        <div style="font-size:32px;animation:spin 1s linear infinite">⟳</div>
        <p style="margin-top:12px;color:var(--text3)">加载中...</p>
      </div>
      <div v-else-if="doneJobs.length === 0" class="empty-state">
        <div class="empty-icon">📭</div>
        <p class="empty-title">暂无已完成的视频</p>
        <p class="empty-sub">先去生成视频页面创建学习内容</p>
        <button class="btn-primary" @click="$router.push('/create')">去生成视频</button>
      </div>
      <div v-else class="job-grid">
        <div v-for="j in doneJobs" :key="j.id" class="quiz-job-card" @click="selectJob(j)">
          <div class="qjc-icon">📝</div>
          <div class="qjc-info">
            <div class="qjc-name">{{ j.name || j.video_filename || j.id.slice(0,12) }}</div>
            <div class="qjc-meta">
              {{ j.source_lang || '?' }} → {{ j.target_lang || '?' }}
              · {{ fmtDate(j.created_at) }}
            </div>
          </div>
          <div class="qjc-arrow">›</div>
        </div>
      </div>

      <!-- Review book section -->
      <div v-if="isLoggedIn && reviewWords.length > 0" class="review-section" ref="reviewSectionRef">
        <div class="review-section-hdr">
          <h2>复习单词本 <span class="review-count">{{ reviewWords.length }}</span></h2>
          <button class="btn-flashcard" @click="startFlashcard">🃏 闪卡复习</button>
        </div>
        <div class="review-grid">
          <div v-for="w in reviewWords" :key="w.id" class="review-card" :class="{mastered: w.mastered}">
            <div class="rc-word">
              <template v-for="(token, ti) in getReviewLookupTokens(w)" :key="`${w.id}_${ti}`">
                <span v-if="token.lookup"
                      class="dict-word"
                      @mouseover="onWordHoverToken(token, getReviewWordTargetLang(w), $event)"
                      @mouseleave="onWordLeave($event)">{{ token.text }}</span>
                <span v-else>{{ token.text }}</span>
              </template>
            </div>
            <div class="rc-meaning">{{ w.meaning }}</div>
            <div class="rc-actions">
              <button v-if="!w.mastered" class="rc-btn ok" @click="markMastered(w)" title="标记已掌握">✓</button>
              <button class="rc-btn del" @click="removeReviewWord(w)" title="删除">✕</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Dictionary tooltip -->
      <Teleport to="body">
        <Transition name="dt">
          <div v-if="dictTooltip.visible"
               :class="['dict-tooltip', { 'left-side': dictTooltip.side === 'left' }]"
               :style="dictTooltipStyle"
               @mouseenter="cancelDictHide"
               @mouseleave="scheduleDictHide">
            <div v-if="dictTooltip.loading" class="dt-loading">
              <span class="dt-spin">⟳</span> 查询中…
            </div>
            <div v-else-if="dictTooltip.notFound" class="dt-not-found">
              未找到 "{{ dictTooltip.word }}"
            </div>
            <template v-else-if="dictTooltip.data">
              <div class="dt-head">
                <span class="dt-word">{{ dictTooltip.data.word }}</span>
                <span v-if="dictTooltip.data.phonetic" class="dt-phonetic">{{ dictTooltip.data.phonetic }}</span>
                <button v-if="dictTooltip.data.audio" class="dt-audio" @click="playDictAudio" title="播放发音">🔊</button>
              </div>
              <div v-for="(m, i) in dictTooltip.data.meanings" :key="i" class="dt-meaning">
                <span v-if="m.pos" class="dt-pos">{{ m.pos }}</span>
                <p class="dt-def">{{ m.definition }}</p>
                <p v-if="dictTooltip.data.translated_meanings?.[i]" class="dt-def-trans">{{ dictTooltip.data.translated_meanings[i] }}</p>
                <p v-if="m.example" class="dt-ex">"{{ m.example }}"</p>
                <p v-if="m.synonyms?.length" class="dt-syns">
                  同义: <span v-for="s in m.synonyms" :key="s" class="dt-syn">{{ s }}</span>
                </p>
              </div>
            </template>
          </div>
        </Transition>
      </Teleport>

      <!-- Flashcard overlay -->
      <Teleport to="body">
        <div v-if="flashcardActive" class="flashcard-overlay" @click.self="flashcardActive=false">
          <div class="flashcard-modal">
            <div class="fc-header">
              <span class="fc-progress">{{ fcIndex + 1 }} / {{ fcWords.length }}</span>
              <span class="fc-title">🃏 闪卡复习</span>
              <button class="fc-close" @click="flashcardActive=false">✕</button>
            </div>

            <div class="fc-progress-bar">
              <div class="fc-progress-fill" :style="{width: ((fcIndex+1)/fcWords.length*100)+'%'}"></div>
            </div>

            <div :class="['fc-card', {flipped: fcFlipped}]" @click="fcFlipped=!fcFlipped">
              <div class="fc-front">
                <div class="fc-label">{{ fcCurrentWord?.word_type === 'expression' ? '表达' : '单词' }}</div>
                <div class="fc-word">{{ fcCurrentWord?.word }}</div>
                <div class="fc-hint">点击翻转查看释义</div>
              </div>
              <div class="fc-back">
                <div class="fc-meaning-big">{{ fcCurrentWord?.meaning }}</div>
                <div class="fc-word-small">{{ fcCurrentWord?.word }}</div>
              </div>
            </div>

            <div class="fc-actions">
              <button class="fc-btn fc-prev" @click="fcPrev" :disabled="fcIndex === 0">← 上一个</button>
              <div class="fc-center-btns">
                <button v-if="!fcCurrentWord?.mastered" class="fc-btn fc-mastered" @click="fcMarkMastered">✓ 已掌握</button>
                <button v-else class="fc-btn fc-unmastered" @click="fcUnmarkMastered">↩ 取消掌握</button>
              </div>
              <button class="fc-btn fc-next" @click="fcNext" :disabled="fcIndex === fcWords.length - 1">下一个 →</button>
            </div>

            <div class="fc-stats">
              已掌握 <strong>{{ fcMasteredCount }}</strong> / {{ fcWords.length }}
            </div>
          </div>
        </div>
      </Teleport>
    </template>

    <!-- Phase 2: Quiz in progress -->
    <template v-if="phase === 'quiz'">
      <div class="quiz-header">
        <button class="back-btn" @click="exitQuiz">← 退出</button>
        <div class="quiz-title">{{ quizJobName }}</div>
        <div class="quiz-lang-badge">{{ quizSourceLang }} → {{ quizTargetLang }}</div>
      </div>

      <!-- Progress bar -->
      <div class="progress-bar-wrap">
        <div class="progress-bar" :style="{width: progressPct + '%'}"></div>
        <span class="progress-text">{{ currentIndex + 1 }} / {{ quizItems.length }} ({{ progressPct }}%)</span>
      </div>

      <!-- Question card -->
      <div class="question-card" :class="feedbackClass">
        <div class="q-type-badge">{{ currentItem?.type === 'word' ? '词汇' : '表达' }}</div>
        <div class="q-meaning">{{ currentItem?.meaning }}</div>
        <!-- Underline typing area — click to focus the hidden input -->
        <div class="q-hint" @click="focusInput">
          <span v-for="(ch, ci) in hintChars" :key="ci" :class="['hint-char', {space: ch === ' '}]">
            <template v-if="ch === ' '">&nbsp;&nbsp;</template>
            <template v-else>
              <span class="typed-ch">{{ userAnswer[ci] || '' }}</span>
              <span :class="['underline', { 'cursor-line': ci === userAnswer.length && !showingFeedback }]"></span>
            </template>
          </span>
        </div>
        <!-- Hidden input captures keystrokes; visually invisible -->
        <input ref="answerInput" v-model="userAnswer" class="q-input-hidden"
               @keyup.enter="checkAnswer"
               @input="autoSkipSpaces"
               :disabled="showingFeedback" />
        <div class="q-submit-row">
          <button class="q-submit" @click="checkAnswer" :disabled="showingFeedback || !userAnswer.trim()">确认</button>
        </div>
        <!-- Feedback -->
        <Transition name="fb">
          <div v-if="showingFeedback" :class="['feedback', feedbackClass]">
            <template v-if="lastCorrect">
              <span class="fb-icon">✓</span> 正确！
            </template>
            <template v-else>
              <span class="fb-icon">✗</span> 正确答案: <strong>{{ currentItem?.word }}</strong>
            </template>
          </div>
        </Transition>
      </div>
    </template>

    <!-- Phase 3: Score results -->
    <template v-if="phase === 'score'">
      <div class="score-page">
        <div class="score-circle" :class="scoreGrade">
          <div class="score-num">{{ score }}</div>
          <div class="score-label">分</div>
        </div>
        <div class="score-slogan">{{ scoreSlogan }}</div>
        <div class="score-stats">
          <div class="stat"><span class="stat-num correct-color">{{ correctCount }}</span><span class="stat-label">正确</span></div>
          <div class="stat"><span class="stat-num wrong-color">{{ wrongCount }}</span><span class="stat-label">错误</span></div>
          <div class="stat"><span class="stat-num">{{ quizItems.length }}</span><span class="stat-label">总题数</span></div>
        </div>

        <div class="score-actions">
          <button class="btn-primary" @click="retryQuiz">重新测试</button>
          <button class="btn-ghost" @click="phase = 'select'; loadReviewWords()">返回选择</button>
        </div>

        <!-- Full word dictation summary table — always visible -->
        <div class="summary-wrap">
          <div class="summary-title">
            <span class="summary-icon">📋</span>
            本次默写汇总
            <span class="summary-badge">{{ answers.length }} 题</span>
            <span v-if="wrongItems.length > 0" class="summary-badge err-badge">{{ wrongItems.length }} 错误</span>
          </div>
          <div class="summary-table-scroll">
            <table class="summary-table">
              <thead>
                <tr>
                  <th class="col-num">#</th>
                  <th class="col-type">类型</th>
                  <th class="col-meaning">含义 / 释义</th>
                  <th class="col-answer">正确答案</th>
                  <th class="col-user">你的答案</th>
                  <th class="col-result">结果</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(a, i) in answers" :key="i" :class="a.correct ? 'row-ok' : 'row-err'">
                  <td class="col-num">{{ i + 1 }}</td>
                  <td class="col-type">
                    <span :class="['type-badge', a.type === 'word' ? 'type-word' : 'type-expr']">
                      {{ a.type === 'word' ? '词汇' : '表达' }}
                    </span>
                  </td>
                  <td class="col-meaning">{{ a.meaning }}</td>
                  <td class="col-answer">{{ a.word }}</td>
                  <td class="col-user">
                    <span v-if="a.correct" class="user-correct">{{ a.userAnswer }}</span>
                    <span v-else class="user-wrong">{{ a.userAnswer || '（未作答）' }}</span>
                  </td>
                  <td class="col-result">
                    <span :class="['result-icon', a.correct ? 'r-ok' : 'r-err']">
                      {{ a.correct ? '✓' : '✗' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch, nextTick } from 'vue'
import { useAuth } from '../composables/useAuth.js'
import { apiFetch } from '../composables/useApi.js'

const { isLoggedIn } = useAuth()
const openAuth = inject('openAuth')
const toast = inject('toast')

// ── Constants ──
const SCORE_SLOGANS = {
  perfect: '太棒了！满分通过，你是学霸！',
  excellent: '非常优秀！继续保持！',
  good: '做得不错！离满分就差一点了！',
  pass: '及格了！再努力一下会更好！',
  fail: '别灰心！多复习几遍一定能掌握！',
}

// ── State ──
const phase = ref('select')
const jobsLoading = ref(false)
const doneJobs = ref([])
const reviewWords = ref([])

// Quiz state
const quizJobId = ref('')
const quizJobName = ref('')
const quizSourceLang = ref('')
const quizTargetLang = ref('')
const quizItems = ref([])
const currentIndex = ref(0)
const userAnswer = ref('')
const showingFeedback = ref(false)
const lastCorrect = ref(false)
const feedbackClass = ref('')
const answerInput = ref(null)
const answers = ref([])  // {word, meaning, type, userAnswer, correct}

// Score state

// Flashcard state
const flashcardActive = ref(false)
const fcWords = ref([])
const fcIndex = ref(0)
const fcFlipped = ref(false)

const fcCurrentWord = computed(() => fcWords.value[fcIndex.value] || null)
const fcMasteredCount = computed(() => fcWords.value.filter(w => w.mastered).length)

// ── Computed ──
const currentItem = computed(() => quizItems.value[currentIndex.value])
const progressPct = computed(() => Math.round((currentIndex.value / quizItems.value.length) * 100))
const correctCount = computed(() => answers.value.filter(a => a.correct).length)
const wrongCount = computed(() => answers.value.filter(a => !a.correct).length)
const score = computed(() => {
  if (!answers.value.length) return 0
  return Math.round((correctCount.value / answers.value.length) * 100)
})
const scoreGrade = computed(() => {
  const s = score.value
  if (s === 100) return 'perfect'
  if (s >= 80) return 'excellent'
  if (s >= 70) return 'good'
  if (s >= 60) return 'pass'
  return 'fail'
})
const scoreSlogan = computed(() => SCORE_SLOGANS[scoreGrade.value])
const wrongItems = computed(() => answers.value.filter(a => !a.correct))

const hintChars = computed(() => {
  if (!currentItem.value) return []
  const word = currentItem.value.word
  const lang = quizSourceLang.value
  // CJK languages: split by character
  if (['zh', 'ja', 'ko'].includes(lang)) {
    return [...word]
  }
  // Latin/Cyrillic: split by letter, preserve spaces
  return [...word].map(ch => ch === ' ' ? ' ' : '_')
})

function focusInput() {
  answerInput.value?.focus()
}

function autoSkipSpaces() {
  // When typing advances cursor to a space position in hintChars, auto-insert the space
  // so the user doesn't have to type it manually between words
  const chars = hintChars.value
  let pos = userAnswer.value.length
  let extra = ''
  while (pos < chars.length && chars[pos] === ' ') {
    extra += ' '
    pos++
  }
  if (extra) {
    userAnswer.value += extra
  }
}

// ── Flashcard methods ──

function startFlashcard() {
  fcWords.value = [...reviewWords.value]
  fcIndex.value = 0
  fcFlipped.value = false
  flashcardActive.value = true
}

function fcNext() {
  if (fcIndex.value < fcWords.value.length - 1) {
    fcIndex.value++
    fcFlipped.value = false
  }
}

function fcPrev() {
  if (fcIndex.value > 0) {
    fcIndex.value--
    fcFlipped.value = false
  }
}

async function fcMarkMastered() {
  const w = fcCurrentWord.value
  if (!w || w.mastered) return
  try {
    await apiFetch(`/api/review-words/${w.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mastered: 1 }),
    })
    w.mastered = 1
    // Sync back to reviewWords
    const rv = reviewWords.value.find(x => x.id === w.id)
    if (rv) rv.mastered = 1
  } catch {}
}

async function fcUnmarkMastered() {
  const w = fcCurrentWord.value
  if (!w || !w.mastered) return
  try {
    await apiFetch(`/api/review-words/${w.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mastered: 0 }),
    })
    w.mastered = 0
    const rv = reviewWords.value.find(x => x.id === w.id)
    if (rv) rv.mastered = 0
  } catch {}
}

// ── Sound effects (Web Audio API) ──
const audioCtx = ref(null)
function getAudioCtx() {
  if (!audioCtx.value) audioCtx.value = new (window.AudioContext || window.webkitAudioContext)()
  return audioCtx.value
}

function playSound(type) {
  try {
    const ctx = getAudioCtx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    gain.gain.value = 0.15

    if (type === 'correct') {
      osc.frequency.value = 880
      osc.type = 'sine'
      gain.gain.setValueAtTime(0.15, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.3)
      // Second note (major third up)
      const osc2 = ctx.createOscillator()
      const gain2 = ctx.createGain()
      osc2.connect(gain2); gain2.connect(ctx.destination)
      osc2.frequency.value = 1108; osc2.type = 'sine'
      gain2.gain.setValueAtTime(0.12, ctx.currentTime + 0.1)
      gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4)
      osc2.start(ctx.currentTime + 0.1); osc2.stop(ctx.currentTime + 0.4)
    } else if (type === 'wrong') {
      osc.frequency.value = 300
      osc.type = 'square'
      gain.gain.setValueAtTime(0.1, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.4)
    } else if (type === 'score') {
      // Fanfare
      const notes = [523, 659, 784, 1047]
      notes.forEach((freq, i) => {
        const o = ctx.createOscillator()
        const g = ctx.createGain()
        o.connect(g); g.connect(ctx.destination)
        o.frequency.value = freq; o.type = 'sine'
        g.gain.setValueAtTime(0.12, ctx.currentTime + i * 0.15)
        g.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + i * 0.15 + 0.4)
        o.start(ctx.currentTime + i * 0.15)
        o.stop(ctx.currentTime + i * 0.15 + 0.4)
      })
    }
  } catch {}
}

// ── Methods ──
async function loadJobs() {
  if (!isLoggedIn.value) return
  jobsLoading.value = true
  try {
    const d = await apiFetch('/api/jobs')
    doneJobs.value = (d.jobs || [])
      .filter(j => j.status === 'done')
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } catch (e) {
    toast('加载失败: ' + e.message, 'err')
  } finally {
    jobsLoading.value = false
  }
}

async function loadReviewWords() {
  if (!isLoggedIn.value) return
  try {
    const d = await apiFetch('/api/review-words')
    reviewWords.value = d.words || []
  } catch {}
}

async function selectJob(j) {
  try {
    const data = await apiFetch(`/api/jobs/${j.id}/quiz-data`)
    const allItems = [
      ...data.words.map(w => ({ ...w, type: 'word' })),
      ...data.expressions.map(e => ({ ...e, type: 'expression' })),
    ]
    if (allItems.length === 0) {
      toast('该视频没有可测试的词汇数据', 'err')
      return
    }
    // Shuffle
    for (let i = allItems.length - 1; i > 0; i--) {
      const j2 = Math.floor(Math.random() * (i + 1));
      [allItems[i], allItems[j2]] = [allItems[j2], allItems[i]]
    }
    quizItems.value = allItems
    quizJobId.value = j.id
    quizJobName.value = j.name || j.video_filename || j.id.slice(0, 12)
    quizSourceLang.value = data.source_lang
    quizTargetLang.value = data.target_lang
    currentIndex.value = 0
    answers.value = []
    userAnswer.value = ''
    showingFeedback.value = false
    phase.value = 'quiz'
    await nextTick()
    answerInput.value?.focus()
  } catch (e) {
    toast('加载测试数据失败: ' + e.message, 'err')
  }
}

function checkAnswer() {
  if (showingFeedback.value || !userAnswer.value.trim()) return
  const item = currentItem.value
  const correct = userAnswer.value.trim().toLowerCase() === item.word.toLowerCase()
  answers.value.push({
    word: item.word,
    meaning: item.meaning,
    type: item.type,
    userAnswer: userAnswer.value.trim(),
    correct,
  })
  lastCorrect.value = correct
  feedbackClass.value = correct ? 'fb-correct' : 'fb-wrong'
  showingFeedback.value = true
  playSound(correct ? 'correct' : 'wrong')

  setTimeout(() => {
    showingFeedback.value = false
    feedbackClass.value = ''
    userAnswer.value = ''
    if (currentIndex.value + 1 < quizItems.value.length) {
      currentIndex.value++
      nextTick(() => answerInput.value?.focus())
    } else {
      finishQuiz()
    }
  }, correct ? 800 : 1500)
}

async function finishQuiz() {
  phase.value = 'score'
  playSound('score')

  // Save wrong items to review book
  if (wrongItems.value.length > 0 && isLoggedIn.value) {
    try {
      await apiFetch('/api/review-words', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: quizJobId.value,
          words: wrongItems.value.map(w => ({
            word: w.word,
            meaning: w.meaning,
            source_lang: quizSourceLang.value,
            target_lang: quizTargetLang.value,
            word_type: w.type,
          })),
        }),
      })
    } catch (e) {
      console.error('Save review words failed:', e)
    }
  }
}

function retryQuiz() {
  // Re-shuffle
  const items = [...quizItems.value]
  for (let i = items.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]]
  }
  quizItems.value = items
  currentIndex.value = 0
  answers.value = []
  userAnswer.value = ''
  showingFeedback.value = false
  feedbackClass.value = ''
  phase.value = 'quiz'
  nextTick(() => answerInput.value?.focus())
}

function exitQuiz() {
  if (answers.value.length > 0 && !confirm('确定退出？当前进度将丢失。')) return
  phase.value = 'select'
  loadReviewWords()
}

async function markMastered(w) {
  try {
    await apiFetch(`/api/review-words/${w.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mastered: 1 }),
    })
    w.mastered = 1
    toast('已标记掌握', 'ok')
  } catch {}
}

async function removeReviewWord(w) {
  try {
    await apiFetch(`/api/review-words/${w.id}`, { method: 'DELETE' })
    reviewWords.value = reviewWords.value.filter(x => x.id !== w.id)
  } catch {}
}

function fmtDate(s) { return s ? new Date(s).toLocaleDateString('zh-CN') : '-' }

// ── Dictionary tooltip (review book) ───────────────────────────────────────
const reviewSectionRef = ref(null)
const dictTooltip = ref({ visible: false, loading: false, notFound: false, word: '', data: null, y: 0, side: 'right', anchorX: 0 })
const dictCache = {}
let dictShowTimer = null
let dictHideTimer = null
let dictHoverToken = 0
let dictActiveHoverKey = ''
let dictRequestToken = 0
const DICT_TOOLTIP_W = 300

const dictTooltipStyle = computed(() => {
  const MARGIN = 10
  const GAP = 20
  let x, y
  if (dictTooltip.value.side === 'left') {
    x = dictTooltip.value.anchorX - DICT_TOOLTIP_W - GAP
    x = Math.max(MARGIN, x)
  } else {
    x = dictTooltip.value.anchorX + GAP
    x = Math.min(x, window.innerWidth - DICT_TOOLTIP_W - MARGIN)
  }
  y = dictTooltip.value.y - 10
  y = Math.max(MARGIN, Math.min(y, window.innerHeight - 300))
  return { left: `${x}px`, top: `${y}px`, width: `${DICT_TOOLTIP_W}px` }
})

function onWordHoverToken(token, targetLang, event) {
  const el = event.currentTarget
  dictHoverToken += 1
  const localHover = dictHoverToken
  clearTimeout(dictHideTimer)
  clearTimeout(dictShowTimer)
  dictShowTimer = setTimeout(() => {
    // Ignore stale hover timers.
    if (localHover !== dictHoverToken) return
    triggerDictTooltip(token, targetLang, el)
  }, 200)
}

function onWordLeave(event) {
  if (!event.relatedTarget?.closest?.('.dict-tooltip')) {
    dictHoverToken += 1
    dictActiveHoverKey = ''
    clearTimeout(dictShowTimer)
    if (dictTooltip.value.visible) scheduleDictHide()
  }
}

function cancelDictHide() { clearTimeout(dictHideTimer) }
function scheduleDictHide() {
  dictHideTimer = setTimeout(() => {
    dictTooltip.value.visible = false
    dictTooltip.value.loading = false
  }, 200)
}

function getReviewWordTargetLang(reviewWord) {
  return reviewWord?.target_lang || reviewWord?.targetLang || quizTargetLang.value || 'zh'
}

function normalizeDictToken(raw) {
  return String(raw || '')
    .replace(/[’]/g, "'")
    .replace(/^'+|'+$/g, '')
    .toLowerCase()
}

function getReviewLookupTokens(reviewWord) {
  const raw = String(reviewWord?.word || '')
  if (!raw) return []

  const sourceLang = reviewWord?.source_lang || reviewWord?.sourceLang || quizSourceLang.value || 'en'
  // CJK languages: keep as one token (no whitespace word boundaries)
  if (['zh', 'ja', 'ko'].includes(sourceLang)) {
    const lookup = normalizeDictToken(raw)
    return [{ text: raw, lookup: lookup || null }]
  }

  const tokens = []
  const RE = /[A-Za-zÀ-ÖØ-öø-ÿА-Яа-яЁё]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿА-Яа-яЁё]+)*/g
  let last = 0
  let m
  RE.lastIndex = 0
  while ((m = RE.exec(raw)) !== null) {
    if (m.index > last) tokens.push({ text: raw.slice(last, m.index), lookup: null })
    const text = m[0]
    const lookup = normalizeDictToken(text)
    tokens.push({ text, lookup: lookup || null })
    last = RE.lastIndex
  }
  if (last < raw.length) tokens.push({ text: raw.slice(last), lookup: null })
  return tokens.length ? tokens : [{ text: raw, lookup: normalizeDictToken(raw) || null }]
}

async function triggerDictTooltip(token, targetLang, el) {
  const rawWord = token?.text || ''
  const word = token?.lookup || normalizeDictToken(rawWord)
  if (!word) return
  const hoverKey = `${word}__${targetLang}__${Math.round(el?.getBoundingClientRect?.().left || 0)}`
  dictActiveHoverKey = hoverKey
  const rect = el.getBoundingClientRect()
  dictTooltip.value.word = rawWord || word
  dictTooltip.value.y = rect.top + rect.height / 2
  dictTooltip.value.notFound = false

  const containerRect = reviewSectionRef.value?.getBoundingClientRect()
  const wordCenterX = rect.left + rect.width / 2
  const centerX = containerRect ? (containerRect.left + containerRect.right) / 2 : window.innerWidth / 2
  const isLeft = wordCenterX < centerX
  dictTooltip.value.side = isLeft ? 'left' : 'right'
  dictTooltip.value.anchorX = isLeft
    ? (containerRect?.left ?? rect.left)
    : (containerRect?.right ?? rect.right)

  const cacheKey = `${word}__${targetLang}`
  if (dictCache[cacheKey] !== undefined) {
    if (dictActiveHoverKey !== hoverKey) return
    dictTooltip.value.data = dictCache[cacheKey] || null
    dictTooltip.value.notFound = !dictCache[cacheKey]
    dictTooltip.value.loading = false
    dictTooltip.value.visible = true
    return
  }

  dictTooltip.value.loading = true
  dictTooltip.value.data = null
  dictTooltip.value.visible = true

  dictRequestToken += 1
  const localReq = dictRequestToken
  try {
    const data = await apiFetch(`/api/dictionary/${encodeURIComponent(word)}?target_lang=${targetLang}`)
    dictCache[cacheKey] = data
    // Drop stale responses from previous hover/request.
    if (localReq !== dictRequestToken || dictActiveHoverKey !== hoverKey) return
    dictTooltip.value.data = data
    dictTooltip.value.notFound = false
  } catch {
    dictCache[cacheKey] = null
    if (localReq !== dictRequestToken || dictActiveHoverKey !== hoverKey) return
    dictTooltip.value.notFound = true
    dictTooltip.value.data = null
  } finally {
    if (localReq !== dictRequestToken || dictActiveHoverKey !== hoverKey) return
    dictTooltip.value.loading = false
  }
}

function playDictAudio() {
  const url = dictTooltip.value.data?.audio
  if (url) new Audio(url).play().catch(() => {})
}

watch(isLoggedIn, v => { if (v) { loadJobs(); loadReviewWords() } }, { immediate: true })
</script>

<style scoped>
.quiz-page { padding: 32px 24px 80px; max-width: 900px; margin: 0 auto; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 30px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 6px; color: var(--text); }
.page-header p { color: var(--text2); font-size: 14px; }

.empty-state { text-align: center; padding: 100px 24px; display: flex; flex-direction: column; align-items: center; gap: 12px; }
.empty-icon { font-size: 72px; }
.empty-title { font-size: 18px; font-weight: 700; color: var(--text); }
.empty-sub { color: var(--text2); font-size: 14px; }

/* Job selection grid */
.job-grid { display: flex; flex-direction: column; gap: 10px; }
.quiz-job-card {
  display: flex; align-items: center; gap: 14px; padding: 16px 20px;
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  cursor: pointer; transition: all .2s; box-shadow: var(--shadow);
}
.quiz-job-card:hover { border-color: rgba(99,102,241,.3); box-shadow: var(--shadow2); transform: translateY(-1px); }
.qjc-icon { font-size: 28px; }
.qjc-info { flex: 1; min-width: 0; }
.qjc-name { font-size: 15px; font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.qjc-meta { font-size: 12px; color: var(--text3); margin-top: 4px; }
.qjc-arrow { font-size: 24px; color: var(--text3); }

/* Review section */
.review-section { margin-top: 40px; }
.review-section h2 { font-size: 18px; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 8px; }
.review-count {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 24px; height: 24px; padding: 0 8px; border-radius: 12px;
  background: rgba(99,102,241,.1); color: var(--accent); font-size: 12px; font-weight: 700;
}
.review-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
.review-card {
  padding: 14px 16px; background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  position: relative; transition: all .2s;
}
.review-card.mastered { opacity: 0.5; }
.rc-word { font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
.rc-meaning { font-size: 12px; color: var(--text3); }
.rc-actions { position: absolute; top: 8px; right: 8px; display: flex; gap: 4px; }
.rc-btn {
  width: 24px; height: 24px; border-radius: 6px; border: 1px solid var(--border);
  background: var(--bg3); font-size: 11px; cursor: pointer; display: flex;
  align-items: center; justify-content: center; transition: all .15s;
}
.rc-btn.ok:hover { background: rgba(16,185,129,.1); color: var(--ok); border-color: rgba(16,185,129,.3); }
.rc-btn.del:hover { background: rgba(239,68,68,.08); color: var(--err); border-color: rgba(239,68,68,.2); }

/* Quiz header */
.quiz-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 24px;
}
.back-btn {
  padding: 7px 14px; border-radius: 8px; background: var(--bg3);
  border: 1px solid var(--border); color: var(--text2); font-size: 13px;
  font-weight: 600; cursor: pointer; transition: all .15s;
}
.back-btn:hover { background: var(--border); color: var(--text); }
.quiz-title { flex: 1; font-size: 16px; font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.quiz-lang-badge {
  padding: 4px 10px; border-radius: 8px; font-size: 11px; font-weight: 600;
  background: rgba(99,102,241,.08); color: var(--accent); border: 1px solid rgba(99,102,241,.2);
}

/* Progress bar */
.progress-bar-wrap {
  position: relative; height: 32px; background: var(--bg3); border-radius: 16px;
  border: 1px solid var(--border); margin-bottom: 32px; overflow: hidden;
}
.progress-bar {
  height: 100%; border-radius: 16px;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  transition: width .4s ease;
}
.progress-text {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: var(--text);
}

/* Question card */
.question-card {
  background: var(--card); border: 2px solid var(--border); border-radius: 16px;
  padding: 40px 32px; text-align: center; box-shadow: var(--shadow2);
  transition: border-color .3s; position: relative;
}
.question-card.fb-correct { border-color: var(--ok); }
.question-card.fb-wrong { border-color: var(--err); }

.q-type-badge {
  display: inline-block; padding: 3px 12px; border-radius: 10px;
  font-size: 11px; font-weight: 600; letter-spacing: .5px;
  background: rgba(99,102,241,.08); color: var(--accent); margin-bottom: 16px;
}
.q-meaning { font-size: 22px; font-weight: 700; color: var(--text); margin-bottom: 20px; line-height: 1.4; }
/* Hint underline area */
.q-hint {
  display: flex; flex-wrap: wrap; justify-content: center; align-items: flex-end;
  gap: 6px; margin-bottom: 28px; min-height: 52px; cursor: text;
}
.hint-char {
  display: inline-flex; flex-direction: column; align-items: center;
  min-width: 22px;
}
.hint-char.space { min-width: 14px; }
.typed-ch {
  display: block; height: 28px; line-height: 28px;
  font-size: 20px; font-weight: 700; color: var(--accent);
  min-width: 22px; text-align: center;
}
.underline {
  display: block; width: 100%; min-width: 22px; height: 2px;
  background: var(--text3); border-radius: 1px; margin-top: 2px;
}
.cursor-line {
  background: var(--accent);
  animation: blink-cursor 1s step-end infinite;
}
@keyframes blink-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* Hidden input (captures keystrokes) */
.q-input-hidden {
  position: absolute; opacity: 0; pointer-events: none;
  width: 1px; height: 1px; top: 0; left: 0;
}

.q-submit-row { display: flex; justify-content: center; margin-top: 8px; }
.q-submit {
  padding: 12px 36px; border-radius: 10px;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff; font-size: 14px; font-weight: 700; cursor: pointer;
  border: none; transition: all .2s;
}
.q-submit:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(99,102,241,.3); }
.q-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* Feedback */
.feedback {
  margin-top: 20px; padding: 12px 20px; border-radius: 10px; font-size: 15px; font-weight: 700;
}
.feedback.fb-correct { background: rgba(16,185,129,.1); color: var(--ok); }
.feedback.fb-wrong { background: rgba(239,68,68,.08); color: var(--err); }
.fb-icon { font-size: 18px; }
.fb-enter-active { transition: all .2s ease; }
.fb-enter-from { opacity: 0; transform: translateY(8px); }

/* Score page */
.score-page { text-align: center; padding: 40px 20px; }
.score-circle {
  width: 160px; height: 160px; border-radius: 50%; margin: 0 auto 24px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  box-shadow: 0 8px 40px rgba(0,0,0,.12);
}
.score-circle.perfect { background: linear-gradient(135deg, #10b981, #059669); }
.score-circle.excellent { background: linear-gradient(135deg, #6366f1, #8b5cf6); }
.score-circle.good { background: linear-gradient(135deg, #3b82f6, #6366f1); }
.score-circle.pass { background: linear-gradient(135deg, #f59e0b, #f97316); }
.score-circle.fail { background: linear-gradient(135deg, #ef4444, #f97316); }
.score-num { font-size: 48px; font-weight: 800; color: #fff; line-height: 1; }
.score-label { font-size: 14px; color: rgba(255,255,255,.8); font-weight: 600; }

.score-slogan { font-size: 20px; font-weight: 700; color: var(--text); margin-bottom: 24px; }
.score-stats {
  display: flex; justify-content: center; gap: 40px; margin-bottom: 32px;
}
.stat { display: flex; flex-direction: column; align-items: center; }
.stat-num { font-size: 28px; font-weight: 800; }
.stat-label { font-size: 12px; color: var(--text3); margin-top: 4px; }
.correct-color { color: var(--ok); }
.wrong-color { color: var(--err); }

.score-actions { display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; margin-bottom: 32px; }

/* Word dictation summary table */
.summary-wrap {
  max-width: 800px; margin: 0 auto;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 14px; overflow: hidden; box-shadow: var(--shadow);
  text-align: left;
}
.summary-title {
  padding: 14px 20px; font-size: 14px; font-weight: 700; color: var(--text);
  background: var(--bg3); border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 8px;
}
.summary-icon { font-size: 16px; }
.summary-badge {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 2px 9px; border-radius: 10px; font-size: 11px; font-weight: 700;
  background: rgba(99,102,241,.1); color: var(--accent);
}
.err-badge { background: rgba(239,68,68,.08); color: var(--err); }
.summary-table-scroll { overflow-x: auto; }
.summary-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.summary-table thead tr { background: var(--bg3); }
.summary-table th {
  padding: 10px 14px; font-size: 11px; font-weight: 700; letter-spacing: .4px;
  color: var(--text3); text-transform: uppercase; border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.summary-table td { padding: 10px 14px; border-bottom: 1px solid var(--border); vertical-align: middle; }
.summary-table tr:last-child td { border-bottom: none; }
.row-ok { background: rgba(16,185,129,.03); }
.row-err { background: rgba(239,68,68,.04); }
.row-ok:hover { background: rgba(16,185,129,.07); }
.row-err:hover { background: rgba(239,68,68,.07); }

.col-num { width: 36px; text-align: center; color: var(--text3); font-size: 11px; }
.col-type { width: 56px; }
.col-meaning { color: var(--text2); }
.col-answer { font-weight: 700; color: var(--text); }
.col-user { }
.col-result { width: 48px; text-align: center; }

.type-badge {
  display: inline-block; padding: 2px 8px; border-radius: 8px; font-size: 10px; font-weight: 700;
}
.type-word { background: rgba(99,102,241,.1); color: var(--accent); }
.type-expr { background: rgba(244,114,182,.1); color: #f472b6; }

.user-correct { color: var(--ok); font-weight: 600; }
.user-wrong { color: var(--err); font-weight: 600; text-decoration: line-through; text-decoration-color: rgba(239,68,68,.5); }
.result-icon { font-size: 15px; font-weight: 800; }
.r-ok { color: var(--ok); }
.r-err { color: var(--err); }

.panel-enter-active, .panel-leave-active { transition: all .3s ease; }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateY(-10px); }

/* Review section header */
.review-section-hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.review-section-hdr h2 { font-size: 18px; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 8px; margin: 0; }
.btn-flashcard {
  padding: 7px 14px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff; border: none; transition: all .2s;
}
.btn-flashcard:hover { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(99,102,241,.3); }

/* Flashcard overlay */
.flashcard-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.65); z-index: 500;
  display: flex; align-items: center; justify-content: center; padding: 24px;
  backdrop-filter: blur(4px);
}
.flashcard-modal {
  background: var(--card); border: 1px solid var(--border); border-radius: 20px;
  width: 100%; max-width: 480px; padding: 28px;
  box-shadow: 0 24px 80px rgba(0,0,0,.4);
}
.fc-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;
}
.fc-title { font-size: 15px; font-weight: 700; color: var(--text); }
.fc-progress { font-size: 12px; font-weight: 700; color: var(--accent); padding: 3px 10px; border-radius: 10px; background: rgba(99,102,241,.1); }
.fc-close { width: 28px; height: 28px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg3); color: var(--text3); font-size: 12px; cursor: pointer; }
.fc-close:hover { color: var(--text); }

.fc-progress-bar { height: 4px; background: var(--bg3); border-radius: 2px; overflow: hidden; margin-bottom: 24px; }
.fc-progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); border-radius: 2px; transition: width .4s ease; }

/* Flip card */
.fc-card {
  perspective: 1000px;
  height: 220px; cursor: pointer; margin-bottom: 24px;
  position: relative;
}
.fc-front, .fc-back {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border-radius: 14px; padding: 24px;
  backface-visibility: hidden;
  transition: transform .45s cubic-bezier(.4,.2,.2,1);
}
.fc-front {
  background: linear-gradient(135deg, rgba(99,102,241,.12), rgba(139,92,246,.08));
  border: 1.5px solid rgba(99,102,241,.2);
  transform: rotateY(0deg);
}
.fc-back {
  background: linear-gradient(135deg, rgba(16,185,129,.1), rgba(99,102,241,.08));
  border: 1.5px solid rgba(16,185,129,.2);
  transform: rotateY(180deg);
}
.fc-card.flipped .fc-front { transform: rotateY(-180deg); }
.fc-card.flipped .fc-back { transform: rotateY(0deg); }

.fc-label { font-size: 10px; font-weight: 700; letter-spacing: .8px; text-transform: uppercase; color: var(--accent); margin-bottom: 12px; }
.fc-word { font-size: 32px; font-weight: 800; color: var(--text); text-align: center; line-height: 1.2; }
.fc-hint { font-size: 12px; color: var(--text3); margin-top: 16px; }
.fc-meaning-big { font-size: 22px; font-weight: 700; color: var(--text); text-align: center; line-height: 1.4; margin-bottom: 10px; }
.fc-word-small { font-size: 14px; color: var(--text3); font-style: italic; }

.fc-actions { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.fc-btn {
  padding: 9px 16px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer;
  border: 1px solid var(--border); background: var(--bg3); color: var(--text2); transition: all .15s;
}
.fc-btn:hover:not(:disabled) { background: var(--border); color: var(--text); }
.fc-btn:disabled { opacity: .35; cursor: not-allowed; }
.fc-prev, .fc-next { flex: 1; }
.fc-center-btns { display: flex; gap: 8px; flex-shrink: 0; }
.fc-mastered { background: rgba(16,185,129,.1); color: var(--ok); border-color: rgba(16,185,129,.3); }
.fc-mastered:hover { background: rgba(16,185,129,.2) !important; }
.fc-unmastered { background: rgba(239,68,68,.08); color: var(--err); border-color: rgba(239,68,68,.2); font-size: 12px; }
.fc-unmastered:hover { background: rgba(239,68,68,.14) !important; }

.fc-stats { text-align: center; font-size: 12px; color: var(--text3); }
.fc-stats strong { color: var(--ok); }

/* ── Review book hoverable words ── */
.rc-word .dict-word {
  cursor: pointer;
  border-bottom: 1px dashed var(--text3);
  transition: color .12s, border-color .12s;
  display: inline-block;
}
.rc-word .dict-word:hover {
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
.dict-tooltip.left-side {
  border-left: 1px solid var(--border);
  border-right: 3px solid var(--accent);
  border-radius: 12px 0 0 12px;
}
.dict-tooltip::before {
  content: '';
  position: absolute;
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  width: 48px;
  height: 2px;
  background: linear-gradient(to left, var(--accent) 20%, rgba(99,102,241,0.15) 100%);
  border-radius: 1px;
}
.dict-tooltip.left-side::before {
  right: auto;
  left: 100%;
  background: linear-gradient(to right, var(--accent) 20%, rgba(99,102,241,0.15) 100%);
}
.dict-tooltip::after {
  content: '';
  position: absolute;
  right: calc(100% + 45px);
  top: 50%;
  transform: translateY(-50%);
  width: 5px;
  height: 5px;
  background: var(--accent);
  border-radius: 50%;
  opacity: 0.6;
}
.dict-tooltip.left-side::after {
  right: auto;
  left: calc(100% + 45px);
}

.dt-enter-active { transition: opacity .14s ease, transform .14s ease; }
.dt-leave-active { transition: opacity .1s ease; }
.dt-enter-from   { opacity: 0; transform: translateY(-50%) translateX(-6px); }
.dt-leave-to     { opacity: 0; }

.dt-loading { font-size: 13px; color: var(--text3); display: flex; align-items: center; gap: 6px; }
.dt-spin { display: inline-block; animation: spin .9s linear infinite; }
.dt-not-found { font-size: 12px; color: var(--text3); }
.dt-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.dt-word { font-size: 17px; font-weight: 700; color: var(--text); }
.dt-phonetic { font-size: 12px; color: var(--text3); font-family: monospace; flex: 1; }
.dt-audio { background: none; border: none; cursor: pointer; font-size: 14px; padding: 2px 5px; border-radius: 6px; color: var(--text3); transition: all .15s; }
.dt-audio:hover { background: var(--bg3); color: var(--accent); }
.dt-meaning { margin-bottom: 9px; }
.dt-meaning:last-child { margin-bottom: 0; }
.dt-pos { display: inline-block; padding: 1px 7px; border-radius: 10px; margin-bottom: 4px; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .4px; background: rgba(99,102,241,.1); color: var(--accent); }
.dt-def { font-size: 13px; color: var(--text); margin: 0 0 3px; line-height: 1.5; }
.dt-def-trans { font-size: 12px; color: var(--accent); margin: 0 0 4px; line-height: 1.4; font-weight: 600; }
.dt-ex  { font-size: 12px; color: var(--text3); font-style: italic; margin: 0 0 3px; }
.dt-syns { font-size: 11px; color: var(--text3); margin: 0; }
.dt-syn { display: inline-block; margin: 1px 3px 1px 0; padding: 1px 5px; background: var(--bg3); border-radius: 4px; font-size: 11px; }

@keyframes spin { to { transform: rotate(360deg); } }
</style>
