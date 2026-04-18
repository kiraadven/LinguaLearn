<template>
  <div ref="homeRef" class="home" @mousemove="onHomeMove" @mouseleave="onHomeLeave">
    <section class="hero reveal is-visible">
      <div class="hero-glow hero-glow-a"></div>
      <div class="hero-glow hero-glow-b"></div>
      <div class="hero-noise"></div>

      <div class="hero-inner">
        <div class="hero-left">
          <div class="hero-badge">{{ tr('home_badge', '✨ Support 8 languages for two-way learning') }}</div>
          <h1 class="hero-title">
            <span class="brand-mark">LinguaLearn</span>
            <span>{{ tr('home_title', 'Turn foreign videos into a learning superpower') }}</span>
          </h1>
          <p class="hero-sub">
            {{ tr('home_subtitle_line1', 'Upload any foreign-language video. AI transcribes, analyzes vocabulary, and renders subtitles.') }}
            <br>
            {{ tr('home_subtitle_line2', 'Generate your personalized sentence-by-sentence intensive listening video.') }}
          </p>

          <div class="hero-btns">
            <button class="btn-primary hero-main-btn" @click="goCreate">
              {{ tr('home_start_now', 'Start Now') }} →
            </button>
            <button class="btn-ghost hero-ghost-btn" @click="scrollTo('features')">
              {{ tr('home_view_features', 'Explore Features') }}
            </button>
          </div>

          <div class="hero-metrics">
            <button
              v-for="m in heroMetrics"
              :key="m.label"
              class="metric-chip"
              @click="scrollTo(m.target)"
            >
              <div class="metric-value">{{ m.value }}</div>
              <div class="metric-label">{{ m.label }}</div>
              <div class="metric-cta">{{ tr('home_view_features', 'Explore Features') }} →</div>
            </button>
          </div>

          <div class="hero-langs">
            <div v-for="(l, i) in langs" :key="`${l.code}-${i}`" class="lang-pill" :style="`animation-delay:${i * 0.12}s`">
              <span>{{ displayFlag(l) }}</span>
              <span>{{ l.native_name || l.code }}</span>
            </div>
          </div>
        </div>

        <aside class="hero-panel">
          <div class="panel-head">
            <span class="panel-dot"></span>
            <span>{{ tr('home_steps_title', 'Complete in 5 Automatic Steps') }}</span>
          </div>

          <div class="panel-flow">
            <div
              v-for="(s, i) in steps"
              :key="`panel-${i}`"
              class="flow-item"
              :class="{ active: i === activeStep }"
              @mouseenter="activeStep = i"
            >
              <div class="flow-index">{{ String(i + 1).padStart(2, '0') }}</div>
              <div class="flow-main">
                <div class="flow-title">{{ s.title }}</div>
                <div class="flow-bar"><span :style="{ width: `${progressFor(i)}%` }"></span></div>
              </div>
            </div>
          </div>

          <div class="panel-foot">
            <span class="pulse-ring"></span>
            <div>
              <div class="panel-foot-title">{{ tr('home_feat_8_title', 'Real-time Progress') }}</div>
              <div class="panel-foot-sub">{{ tr('home_feat_8_desc', 'Track rendering progress live and cancel tasks anytime.') }}</div>
            </div>
          </div>
        </aside>
      </div>

      <button class="scroll-ind" aria-label="scroll to features" @click="scrollTo('features')">
        <span></span>
      </button>
    </section>

    <section id="features" class="section reveal">
      <div class="section-label">{{ tr('home_features_label', 'Core Features') }}</div>
      <h2 class="section-title">{{ tr('home_features_title', 'All-in-one Language Learning Workflow') }}</h2>
      <p class="section-sub">{{ tr('home_features_sub', 'From raw video to complete study materials, fully automated and easy to start.') }}</p>

      <div class="feat-grid">
        <article
          v-for="(f, i) in features"
          :key="f.titleKey"
          class="feat-card"
          @mousemove="onCardMove"
          @mouseleave="offCardMove"
        >
          <div class="feat-shine"></div>
          <div class="feat-index">{{ String(i + 1).padStart(2, '0') }}</div>
          <div class="feat-icon-wrap"><div class="feat-icon">{{ f.icon }}</div></div>
          <h3 class="feat-title">{{ f.title }}</h3>
          <p class="feat-desc">{{ f.desc }}</p>
        </article>
      </div>
    </section>

    <section id="steps" class="section reveal">
      <div class="section-label">{{ tr('home_steps_label', 'Workflow') }}</div>
      <h2 class="section-title">{{ tr('home_steps_title', 'Complete in 5 Automatic Steps') }}</h2>

      <div class="steps-track">
        <div class="track-line">
          <span :style="{ width: `${((activeStep + 1) / steps.length) * 100}%` }"></span>
        </div>

        <div class="step-nodes">
          <button
            v-for="(s, i) in steps"
            :key="`step-${i}`"
            class="step-node"
            :class="{ active: i === activeStep }"
            @click="activeStep = i"
          >
            <span class="node-num">{{ i + 1 }}</span>
            <span class="node-icon">{{ s.icon }}</span>
            <span class="node-title">{{ s.title }}</span>
            <span class="node-desc">{{ s.desc }}</span>
          </button>
        </div>
      </div>
    </section>

    <section id="langs" class="section reveal">
      <div class="section-label">{{ tr('home_langs_label', 'Supported Languages') }}</div>
      <h2 class="section-title">{{ tr('home_langs_title', '8 Languages, Learn Any Pair') }}</h2>

      <div class="lang-marquee">
        <div class="marquee-track">
          <div v-for="(l, i) in marqueeLangs" :key="`marquee-${l.code}-${i}`" class="marquee-pill">
            <span>{{ displayFlag(l) }}</span>
            <span>{{ l.native_name || l.code }}</span>
          </div>
        </div>
      </div>

      <div class="lang-grid">
        <div v-for="l in langs" :key="`lang-${l.code}`" class="lang-card">
          <div class="lang-glint"></div>
          <div class="lang-flag">{{ displayFlag(l) }}</div>
          <div class="lang-name">{{ l.native_name || l.code }}</div>
          <div class="lang-code">{{ (l.code || '').toUpperCase() }}</div>
        </div>
      </div>
    </section>

    <section class="section cta-section reveal">
      <div class="cta-card">
        <h2 class="section-title">{{ tr('home_cta_title', 'Ready to begin?') }}</h2>
        <p class="cta-sub">{{ tr('home_cta_sub', 'Create an account, upload your first video, and start for free.') }}</p>
        <button class="btn-primary cta-btn" @click="goCreate">
          {{ tr('home_cta_btn', 'Start for Free') }} →
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { apiFetch } from '../composables/useApi.js'
import { useAuth } from '../composables/useAuth.js'
import { useI18n } from '../i18n.js'

const router = useRouter()
const openAuth = inject('openAuth')
const { isLoggedIn } = useAuth()
const { t } = useI18n()

const homeRef = ref(null)
const activeStep = ref(0)

let stepTimer = null
let revealObserver = null

function tr(key, fallback = '') {
  return ((t.value?.[key]) ?? fallback) || key
}

function goCreate() {
  if (!isLoggedIn.value) {
    openAuth?.()
    return
  }
  router.push('/create')
}

function scrollTo(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
}

const langs = ref([
  { code: 'en', native_name: 'English', flag: '🇺🇸' },
  { code: 'zh-Hans', native_name: '中文（简体）', flag: '🇨🇳' },
  { code: 'zh-Hant', native_name: '中文（繁體）', flag: '🇭🇰' },
  { code: 'ja', native_name: '日本語', flag: '🇯🇵' },
  { code: 'ko', native_name: '한국어', flag: '🇰🇷' },
  { code: 'de', native_name: 'Deutsch', flag: '🇩🇪' },
  { code: 'fr', native_name: 'Français', flag: '🇫🇷' },
  { code: 'es', native_name: 'Español', flag: '🇪🇸' },
  { code: 'ru', native_name: 'Русский', flag: '🇷🇺' },
])

const featureDefs = [
  { icon: '🌍', titleKey: 'home_feat_1_title', descKey: 'home_feat_1_desc', fallbackTitle: '8-Language Cross Learning', fallbackDesc: 'Learn across 8 major languages with flexible direction between your familiar and target language.' },
  { icon: '🎞️', titleKey: 'home_feat_2_title', descKey: 'home_feat_2_desc', fallbackTitle: 'Customize Any Video into Study Material', fallbackDesc: 'Turn any video into structured learning material based on your language goals and pacing.' },
  { icon: '🧩', titleKey: 'home_feat_3_title', descKey: 'home_feat_3_desc', fallbackTitle: 'User-Friendly Visual Editor', fallbackDesc: 'Drag, resize, and preview subtitle and vocabulary panels with an intuitive editing workflow.' },
  { icon: '🎧', titleKey: 'home_feat_4_title', descKey: 'home_feat_4_desc', fallbackTitle: 'High-Focus Listening Training Video', fallbackDesc: 'Generate repeatable, sentence-focused listening drills designed for deep concentration practice.' },
  { icon: '📤', titleKey: 'home_feat_5_title', descKey: 'home_feat_5_desc', fallbackTitle: 'Exportable Notes and Learning Videos', fallbackDesc: 'Export learning notes, PDF handouts, and completed study videos for review anywhere.' },
  { icon: '🧠', titleKey: 'home_feat_6_title', descKey: 'home_feat_6_desc', fallbackTitle: 'FSRT Smart Review Recommendations', fallbackDesc: 'Use interval-based FSRT scheduling to recommend what you should review next at the right time.' },
]

const stepDefs = [
  { icon: '📥', titleKey: 'home_step_1_title', descKey: 'home_step_1_desc', fallbackTitle: 'Import Your Learning Video', fallbackDesc: 'Start with any video you want to turn into a focused study session.' },
  { icon: '🔎', titleKey: 'home_step_2_title', descKey: 'home_step_2_desc', fallbackTitle: 'Extract Key Learning Content', fallbackDesc: 'The system automatically identifies the parts you should focus on.' },
  { icon: '🗂️', titleKey: 'home_step_3_title', descKey: 'home_step_3_desc', fallbackTitle: 'Build Word & Sentence Cards', fallbackDesc: 'Useful vocabulary and sentence-level practice are organized for review.' },
  { icon: '🎯', titleKey: 'home_step_4_title', descKey: 'home_step_4_desc', fallbackTitle: 'Compose Focused Listening Training', fallbackDesc: 'Create intensive listening segments for high-focus, repeatable practice.' },
  { icon: '✅', titleKey: 'home_step_5_title', descKey: 'home_step_5_desc', fallbackTitle: 'Export Your Study Package', fallbackDesc: 'Output a complete package: learning video plus structured study materials.' },
]

const features = computed(() =>
  featureDefs.map(item => ({
    ...item,
    title: tr(item.titleKey, item.fallbackTitle),
    desc: tr(item.descKey, item.fallbackDesc),
  }))
)

const steps = computed(() =>
  stepDefs.map(item => ({
    ...item,
    title: tr(item.titleKey, item.fallbackTitle),
    desc: tr(item.descKey, item.fallbackDesc),
  }))
)

function displayFlag(lang) {
  const code = String(lang?.code || '').trim()
  if (code === 'zh-Hans' || code === 'zh-Hant') return '🇨🇳'
  return lang?.flag || '🌐'
}

const groupedLanguageCount = computed(() => {
  const groups = new Set()
  for (const lang of langs.value) {
    const code = String(lang?.code || '').trim()
    groups.add(code === 'zh-Hans' || code === 'zh-Hant' ? 'zh' : code)
  }
  return groups.size
})

const heroMetrics = computed(() => [
  { value: `${groupedLanguageCount.value}`, label: tr('home_langs_label', 'Supported Languages'), target: 'langs' },
  { value: `${steps.value.length}`, label: tr('home_steps_label', 'Workflow'), target: 'steps' },
  { value: `${features.value.length}`, label: tr('home_features_label', 'Core Features'), target: 'features' },
])

const marqueeLangs = computed(() => [...langs.value, ...langs.value])

function progressFor(index) {
  if (index < activeStep.value) return 100
  if (index === activeStep.value) return 72
  return 16
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function onHomeMove(e) {
  const root = homeRef.value
  if (!root) return
  const rect = root.getBoundingClientRect()
  const x = clamp(((e.clientX - rect.left) / rect.width) * 100, 0, 100)
  const y = clamp(((e.clientY - rect.top) / rect.height) * 100, 0, 100)
  root.style.setProperty('--pointer-x', `${x.toFixed(2)}%`)
  root.style.setProperty('--pointer-y', `${y.toFixed(2)}%`)
}

function onHomeLeave() {
  const root = homeRef.value
  if (!root) return
  root.style.setProperty('--pointer-x', '50%')
  root.style.setProperty('--pointer-y', '18%')
}

function onCardMove(e) {
  const card = e.currentTarget
  const rect = card.getBoundingClientRect()
  const x = (e.clientX - rect.left) / rect.width
  const y = (e.clientY - rect.top) / rect.height
  const rotateX = (0.5 - y) * 10
  const rotateY = (x - 0.5) * 12

  card.style.setProperty('--mx', `${(x * 100).toFixed(1)}%`)
  card.style.setProperty('--my', `${(y * 100).toFixed(1)}%`)
  card.style.transform = `perspective(900px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-8px)`
}

function offCardMove(e) {
  const card = e.currentTarget
  card.style.transform = ''
  card.style.setProperty('--mx', '50%')
  card.style.setProperty('--my', '50%')
}

function setupReveal() {
  if (!homeRef.value) return

  const items = homeRef.value.querySelectorAll('.reveal')
  if (!items.length) return

  if (!('IntersectionObserver' in window)) {
    items.forEach(item => item.classList.add('is-visible'))
    return
  }

  revealObserver = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          revealObserver?.unobserve(entry.target)
        }
      })
    },
    { threshold: 0.15, rootMargin: '0px 0px -8% 0px' }
  )

  items.forEach(item => revealObserver?.observe(item))
}

onMounted(async () => {
  try {
    const data = await apiFetch('/api/languages')
    if (Array.isArray(data.languages) && data.languages.length) {
      langs.value = data.languages
    }
  } catch {}

  setupReveal()

  stepTimer = window.setInterval(() => {
    if (!steps.value.length) return
    activeStep.value = (activeStep.value + 1) % steps.value.length
  }, 2600)
})

onBeforeUnmount(() => {
  if (stepTimer) window.clearInterval(stepTimer)
  revealObserver?.disconnect()
})
</script>

<style scoped>
.home {
  --pointer-x: 50%;
  --pointer-y: 18%;
  --hero-ink: #091225;
  --hero-ink-soft: #16233f;
  --hero-amber: #f59e0b;
  --hero-cyan: #06b6d4;
  --hero-sky: #38bdf8;

  min-height: 100vh;
  font-family: 'Avenir Next', 'Manrope', 'SF Pro Display', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.reveal {
  opacity: 0;
  transform: translateY(26px) scale(0.985);
  transition: opacity 0.75s ease, transform 0.75s cubic-bezier(0.2, 0.65, 0.2, 1);
}

.reveal.is-visible {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.hero {
  position: relative;
  min-height: calc(100vh - 60px);
  padding: 80px 24px 110px;
  overflow: clip;
}

.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(760px 420px at var(--pointer-x) var(--pointer-y), rgba(56, 189, 248, 0.2), transparent 68%),
    radial-gradient(580px 300px at 76% 86%, rgba(245, 158, 11, 0.15), transparent 72%),
    linear-gradient(135deg, rgba(9, 18, 37, 0.03), rgba(22, 35, 63, 0.02));
  pointer-events: none;
}

.hero-glow {
  position: absolute;
  border-radius: 999px;
  filter: blur(70px);
  opacity: 0.38;
  pointer-events: none;
  mix-blend-mode: multiply;
}

.hero-glow-a {
  width: 360px;
  height: 360px;
  left: -120px;
  top: 30px;
  background: rgba(6, 182, 212, 0.36);
  animation: driftA 11s ease-in-out infinite;
}

.hero-glow-b {
  width: 340px;
  height: 340px;
  right: -100px;
  top: 120px;
  background: rgba(245, 158, 11, 0.26);
  animation: driftB 13s ease-in-out infinite;
}

.hero-noise {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.2;
  background-image: radial-gradient(rgba(9, 18, 37, 0.08) 0.7px, transparent 0.7px);
  background-size: 3px 3px;
  mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.65), rgba(0, 0, 0, 0));
}

.hero-inner {
  position: relative;
  max-width: 1220px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1.05fr minmax(320px, 470px);
  align-items: center;
  gap: 40px;
  z-index: 1;
}

.hero-left {
  max-width: 720px;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 999px;
  margin-bottom: 22px;
  font-size: 12px;
  letter-spacing: 0.6px;
  font-weight: 700;
  color: var(--hero-ink-soft);
  border: 1px solid rgba(15, 23, 42, 0.12);
  background: linear-gradient(120deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0.5));
  backdrop-filter: blur(8px);
}

.hero-title {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  font-size: clamp(40px, 6.8vw, 82px);
  line-height: 1.05;
  letter-spacing: -0.03em;
  color: var(--hero-ink);
  text-wrap: balance;
}

.hero-title > span:last-child {
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  background-size: 180% 100%;
  animation: shimmerMove 9s linear infinite;
}

.brand-mark {
  background: linear-gradient(115deg, var(--hero-ink) 0%, var(--hero-cyan) 58%, var(--hero-amber) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  background-size: 200% 100%;
  animation: shimmerMove 8s linear infinite;
}

.hero-sub {
  margin-top: 22px;
  max-width: 620px;
  font-size: clamp(15px, 2vw, 18px);
  line-height: 1.78;
  color: rgba(9, 18, 37, 0.75);
}

.hero-btns {
  margin-top: 30px;
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}

.hero-main-btn {
  padding: 14px 38px;
  font-size: 15px;
  border-radius: 14px;
  box-shadow: 0 10px 35px rgba(14, 116, 144, 0.32);
  background: linear-gradient(125deg, #0f4c81, #0ea5e9 62%, #f59e0b 110%);
}

.hero-main-btn:hover {
  transform: translateY(-3px) scale(1.02);
  box-shadow: 0 16px 40px rgba(14, 116, 144, 0.38);
}

.hero-ghost-btn {
  padding: 14px 32px;
  font-size: 15px;
  border-radius: 14px;
  border-color: rgba(15, 23, 42, 0.2);
  color: var(--hero-ink-soft);
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(6px);
}

.hero-metrics {
  margin-top: 26px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.metric-chip {
  position: relative;
  overflow: hidden;
  cursor: pointer;
  text-align: left;
  padding: 14px 14px 12px;
  border-radius: 16px;
  border: 1px solid rgba(13, 59, 102, 0.16);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.95), rgba(241, 248, 255, 0.76));
  backdrop-filter: blur(8px);
  box-shadow: 0 8px 20px rgba(13, 59, 102, 0.1);
  transition: transform 0.24s ease, box-shadow 0.24s ease, border-color 0.24s ease;
}

.metric-chip::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 14% 14%, rgba(11, 120, 209, 0.18), transparent 55%);
  opacity: 0;
  transition: opacity 0.24s ease;
}

.metric-chip:hover {
  transform: translateY(-4px);
  border-color: rgba(11, 120, 209, 0.42);
  box-shadow: 0 14px 34px rgba(11, 120, 209, 0.18);
}

.metric-chip:hover::after {
  opacity: 1;
}

.metric-value {
  position: relative;
  z-index: 1;
  font-size: clamp(30px, 3vw, 36px);
  font-weight: 900;
  line-height: 1.05;
  letter-spacing: -0.02em;
  background: linear-gradient(120deg, #0f4c81 0%, #0ea5e9 58%, #f59e0b 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.metric-label {
  position: relative;
  z-index: 1;
  margin-top: 4px;
  font-size: 12px;
  color: rgba(15, 23, 42, 0.72);
  letter-spacing: 0.3px;
}

.metric-cta {
  position: relative;
  z-index: 1;
  margin-top: 7px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.38px;
  color: rgba(13, 77, 128, 0.9);
}

.hero-langs {
  margin-top: 24px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.lang-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  background: rgba(255, 255, 255, 0.65);
  color: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(8px);
  animation: floatUp 4s ease-in-out infinite;
  transition: transform 0.28s ease, border-color 0.28s ease;
}

.lang-pill:hover {
  transform: translateY(-3px);
  border-color: rgba(14, 116, 144, 0.45);
}

.hero-panel {
  position: relative;
  padding: 24px;
  border-radius: 24px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  background:
    linear-gradient(165deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0.58)),
    radial-gradient(100% 120% at 100% 0%, rgba(56, 189, 248, 0.12), transparent 70%);
  box-shadow: 0 20px 56px rgba(9, 18, 37, 0.12);
  backdrop-filter: blur(14px);
  overflow: hidden;
  animation: panelFloat 6s ease-in-out infinite;
}

.hero-panel::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at var(--pointer-x) var(--pointer-y), rgba(56, 189, 248, 0.13), transparent 55%);
  pointer-events: none;
}

.panel-head {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.35px;
  color: rgba(9, 18, 37, 0.78);
  margin-bottom: 18px;
}

.panel-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #0ea5e9;
  box-shadow: 0 0 0 5px rgba(14, 165, 233, 0.18);
  animation: dotPulse 1.8s ease-in-out infinite;
}

.panel-flow {
  display: grid;
  gap: 11px;
}

.flow-item {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.42);
  transition: all 0.25s ease;
}

.flow-item.active {
  border-color: rgba(14, 116, 144, 0.24);
  background: rgba(14, 116, 144, 0.08);
  transform: translateX(3px);
}

.flow-index {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 800;
  color: rgba(9, 18, 37, 0.74);
  background: rgba(15, 23, 42, 0.06);
}

.flow-main {
  min-width: 0;
}

.flow-title {
  font-size: 13px;
  font-weight: 700;
  color: rgba(9, 18, 37, 0.84);
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.flow-bar {
  height: 5px;
  border-radius: 999px;
  margin-top: 8px;
  background: rgba(15, 23, 42, 0.1);
  overflow: hidden;
}

.flow-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0ea5e9, #f59e0b);
  transition: width 0.42s cubic-bezier(0.22, 1, 0.36, 1);
}

.panel-foot {
  margin-top: 18px;
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding-top: 16px;
  border-top: 1px dashed rgba(15, 23, 42, 0.14);
}

.pulse-ring {
  width: 14px;
  height: 14px;
  margin-top: 3px;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.5);
  animation: ping 2s ease-out infinite;
}

.panel-foot-title {
  font-size: 12px;
  font-weight: 700;
  color: rgba(9, 18, 37, 0.84);
}

.panel-foot-sub {
  margin-top: 3px;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(9, 18, 37, 0.6);
}

.scroll-ind {
  position: absolute;
  left: 50%;
  bottom: 34px;
  transform: translateX(-50%);
  width: 34px;
  height: 52px;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.2);
  background: rgba(255, 255, 255, 0.58);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  padding-top: 10px;
}

.scroll-ind span {
  width: 4px;
  height: 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.55);
  animation: scrollDot 1.8s ease-in-out infinite;
}

.section {
  position: relative;
  max-width: 1200px;
  margin: 0 auto;
  padding: 92px 24px;
}

.section-label {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 2.9px;
  text-transform: uppercase;
  color: #0f5d8a;
  margin-bottom: 10px;
}

.section-title {
  font-size: clamp(28px, 4.2vw, 46px);
  line-height: 1.12;
  font-weight: 800;
  color: #0d1b34;
  letter-spacing: -0.02em;
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.section-sub {
  margin-top: 14px;
  margin-bottom: 40px;
  max-width: 640px;
  font-size: 15px;
  line-height: 1.75;
  color: rgba(13, 27, 52, 0.68);
}

.feat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(255px, 1fr));
  gap: 16px;
}

.feat-card {
  --mx: 50%;
  --my: 50%;

  position: relative;
  padding: 20px 20px 22px;
  border-radius: 18px;
  border: 1px solid rgba(15, 23, 42, 0.11);
  background: linear-gradient(155deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.88));
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.06);
  transform-style: preserve-3d;
  transition: transform 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease;
  overflow: hidden;
}

.feat-card:hover {
  border-color: rgba(14, 116, 144, 0.28);
  box-shadow: 0 20px 36px rgba(14, 116, 144, 0.13);
}

.feat-shine {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at var(--mx) var(--my), rgba(56, 189, 248, 0.2), transparent 44%);
  opacity: 0;
  transition: opacity 0.24s ease;
  pointer-events: none;
}

.feat-card:hover .feat-shine {
  opacity: 1;
}

.feat-index {
  position: absolute;
  top: 16px;
  right: 16px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.8px;
  color: rgba(13, 27, 52, 0.35);
}

.feat-icon-wrap {
  width: 50px;
  height: 50px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(140deg, rgba(14, 116, 144, 0.14), rgba(245, 158, 11, 0.13));
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.07);
}

.feat-icon {
  font-size: 25px;
  transform: translateZ(26px);
}

.feat-title {
  margin-top: 14px;
  margin-bottom: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #0d1b34;
}

.feat-desc {
  font-size: 13px;
  line-height: 1.68;
  color: rgba(13, 27, 52, 0.7);
}

.steps-track {
  margin-top: 26px;
}

.track-line {
  width: 100%;
  height: 5px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.1);
  overflow: hidden;
}

.track-line span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0ea5e9, #22c55e 45%, #f59e0b 100%);
  transition: width 0.45s ease;
}

.step-nodes {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.step-node {
  border: 1px solid rgba(15, 23, 42, 0.1);
  background: rgba(255, 255, 255, 0.74);
  border-radius: 14px;
  padding: 14px 12px;
  text-align: left;
  transition: all 0.26s ease;
}

.step-node:hover {
  transform: translateY(-3px);
  border-color: rgba(14, 116, 144, 0.25);
}

.step-node.active {
  border-color: rgba(14, 116, 144, 0.3);
  background: linear-gradient(150deg, rgba(14, 116, 144, 0.1), rgba(34, 197, 94, 0.06));
  box-shadow: 0 10px 24px rgba(14, 116, 144, 0.12);
}

.node-num {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 800;
  color: rgba(13, 27, 52, 0.75);
  background: rgba(15, 23, 42, 0.07);
}

.node-icon {
  display: inline-block;
  margin-left: 8px;
  font-size: 16px;
}

.node-title {
  display: block;
  margin-top: 10px;
  font-size: 13px;
  font-weight: 700;
  color: rgba(13, 27, 52, 0.88);
}

.node-desc {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(13, 27, 52, 0.64);
}

.lang-marquee {
  margin-top: 20px;
  border-top: 1px solid rgba(15, 23, 42, 0.09);
  border-bottom: 1px solid rgba(15, 23, 42, 0.09);
  padding: 14px 0;
  overflow: hidden;
  mask-image: linear-gradient(to right, transparent, black 10%, black 90%, transparent);
}

.marquee-track {
  width: fit-content;
  display: flex;
  gap: 10px;
  animation: marqueeMove 25s linear infinite;
}

.marquee-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  border: 1px solid rgba(15, 23, 42, 0.09);
  border-radius: 999px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.84);
  color: rgba(13, 27, 52, 0.74);
  font-size: 13px;
}

.lang-grid {
  margin-top: 26px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 14px;
}

.lang-card {
  position: relative;
  overflow: hidden;
  padding: 20px 14px;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  background: rgba(255, 255, 255, 0.8);
  text-align: center;
  transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
}

.lang-glint {
  position: absolute;
  top: -50%;
  left: -120%;
  width: 70%;
  height: 200%;
  transform: rotate(22deg);
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.75), transparent);
  transition: left 0.55s ease;
  pointer-events: none;
}

.lang-card:hover {
  transform: translateY(-5px);
  border-color: rgba(14, 116, 144, 0.28);
  box-shadow: 0 14px 26px rgba(14, 116, 144, 0.12);
}

.lang-card:hover .lang-glint {
  left: 160%;
}

.lang-flag {
  font-size: 32px;
  margin-bottom: 8px;
}

.lang-name {
  font-size: 13px;
  font-weight: 700;
  color: #0d1b34;
}

.lang-code {
  margin-top: 4px;
  font-size: 11px;
  letter-spacing: 1px;
  font-weight: 600;
  color: rgba(13, 27, 52, 0.48);
}

.cta-section {
  padding-bottom: 120px;
}

.cta-card {
  position: relative;
  overflow: hidden;
  text-align: center;
  border-radius: 26px;
  padding: 58px 28px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.66)),
    radial-gradient(80% 120% at 0% 100%, rgba(56, 189, 248, 0.2), transparent 60%),
    radial-gradient(80% 120% at 100% 0%, rgba(245, 158, 11, 0.16), transparent 58%);
  box-shadow: 0 22px 58px rgba(13, 27, 52, 0.09);
}

.cta-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at var(--pointer-x) var(--pointer-y), rgba(56, 189, 248, 0.16), transparent 45%);
  pointer-events: none;
}

.cta-sub {
  margin: 12px auto 30px;
  max-width: 560px;
  font-size: 15px;
  line-height: 1.75;
  color: rgba(13, 27, 52, 0.65);
}

.cta-btn {
  position: relative;
  z-index: 1;
  padding: 16px 46px;
  font-size: 16px;
  border-radius: 14px;
  background: linear-gradient(125deg, #0f4c81, #0ea5e9 62%, #f59e0b 110%);
}

@keyframes driftA {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(26px, -18px); }
}

@keyframes driftB {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(-24px, 20px); }
}

@keyframes floatUp {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

@keyframes panelFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

@keyframes shimmerMove {
  0% { background-position: 0% 50%; }
  100% { background-position: 200% 50%; }
}

@keyframes dotPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(0.78); }
}

@keyframes ping {
  0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.52); }
  70% { box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

@keyframes scrollDot {
  0% { transform: translateY(0); opacity: 1; }
  70% { transform: translateY(16px); opacity: 0.2; }
  100% { transform: translateY(0); opacity: 1; }
}

@keyframes marqueeMove {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

@media (max-width: 1120px) {
  .hero-inner {
    grid-template-columns: 1fr;
    gap: 28px;
  }

  .hero-left {
    max-width: 100%;
  }

  .hero-panel {
    max-width: 680px;
  }

  .step-nodes {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .hero {
    min-height: auto;
    padding-top: 54px;
  }

  .hero-title {
    font-size: clamp(34px, 10vw, 58px);
  }

  .hero-sub {
    font-size: 14px;
  }

  .hero-btns {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-main-btn,
  .hero-ghost-btn {
    justify-content: center;
    width: 100%;
  }

  .hero-metrics {
    grid-template-columns: 1fr;
  }

  .scroll-ind {
    display: none;
  }

  .section {
    padding: 72px 18px;
  }

  .feat-grid {
    grid-template-columns: 1fr;
  }

  .step-nodes {
    grid-template-columns: 1fr;
  }

  .lang-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .cta-card {
    padding: 46px 18px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-glow,
  .brand-mark,
  .lang-pill,
  .hero-panel,
  .panel-dot,
  .pulse-ring,
  .scroll-ind span,
  .marquee-track {
    animation: none !important;
  }

  .feat-card,
  .step-node,
  .lang-card,
  .btn-primary,
  .btn-ghost {
    transition: none !important;
  }
}
</style>
