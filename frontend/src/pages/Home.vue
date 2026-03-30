<template>
  <div class="home">
    <!-- Hero -->
    <section class="hero">
      <div class="hero-badge fade-up">{{ tr('home_badge', '✨ Support 8 languages for two-way learning') }}</div>
      <h1 class="hero-title fade-up" style="animation-delay:.1s">
        <span class="grad-text">LinguaLearn</span><br>
        <span style="color:var(--text)">{{ tr('home_title', 'Turn foreign videos into a learning superpower') }}</span>
      </h1>
      <p class="hero-sub fade-up" style="animation-delay:.2s">
        {{ tr('home_subtitle_line1', 'Upload any foreign-language video. AI transcribes, analyzes vocabulary, and renders subtitles.') }}<br>{{ tr('home_subtitle_line2', 'Generate your personalized sentence-by-sentence intensive listening video.') }}
      </p>
      <div class="hero-btns fade-up" style="animation-delay:.3s">
        <button class="btn-primary" style="font-size:15px;padding:14px 36px" @click="goCreate">
          {{ tr('home_start_now', 'Start Now') }} →
        </button>
        <button class="btn-ghost" style="font-size:15px;padding:14px 36px" @click="scrollTo('features')">
          {{ tr('home_view_features', 'Explore Features') }}
        </button>
      </div>
      <!-- Floating lang pills -->
      <div class="hero-langs fade-up" style="animation-delay:.4s">
        <div v-for="(l,i) in langs" :key="l.code" class="lang-pill"
             :style="`animation-delay:${i*0.15}s`">
          {{ l.flag }} {{ l.native_name }}
        </div>
      </div>
      <!-- Scroll indicator -->
      <div class="scroll-ind">
        <div class="scroll-arrow"></div>
      </div>
    </section>

    <!-- Features -->
    <section class="section" id="features">
      <div class="section-label">{{ tr('home_features_label', 'Core Features') }}</div>
      <h2 class="section-title">{{ tr('home_features_title', 'All-in-one Language Learning Workflow') }}</h2>
      <p class="section-sub">{{ tr('home_features_sub', 'From raw video to complete study materials, fully automated and easy to start.') }}</p>
      <div class="feat-grid">
        <div v-for="f in features" :key="f.icon" class="feat-card"
             @mousemove="on3D" @mouseleave="off3D">
          <div class="feat-glow"></div>
          <div class="feat-icon">{{ f.icon }}</div>
          <div class="feat-title">{{ f.title }}</div>
          <div class="feat-desc">{{ f.desc }}</div>
        </div>
      </div>
    </section>

    <!-- Steps -->
    <section class="section">
      <div class="section-label">{{ tr('home_steps_label', 'Workflow') }}</div>
      <h2 class="section-title">{{ tr('home_steps_title', 'Complete in 5 Automatic Steps') }}</h2>
      <div class="steps-row">
        <div v-for="(s,i) in steps" :key="i" class="step-item">
          <div class="step-num">{{ i+1 }}</div>
          <div class="step-connector" v-if="i<steps.length-1"></div>
          <div class="step-content">
            <div class="step-icon">{{ s.icon }}</div>
            <div class="step-title">{{ s.title }}</div>
            <div class="step-desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Languages -->
    <section class="section">
      <div class="section-label">{{ tr('home_langs_label', 'Supported Languages') }}</div>
      <h2 class="section-title">{{ tr('home_langs_title', '8 Languages, Learn Any Pair') }}</h2>
      <div class="lang-grid">
        <div v-for="l in langs" :key="l.code" class="lang-card">
          <div class="lang-flag">{{ l.flag }}</div>
          <div class="lang-name">{{ l.native_name }}</div>
          <div class="lang-code">{{ l.code.toUpperCase() }}</div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="section" style="text-align:center;padding-bottom:120px">
      <div class="cta-card">
        <h2 class="section-title" style="margin-bottom:12px">{{ tr('home_cta_title', 'Ready to begin?') }}</h2>
        <p style="color:var(--text2);margin-bottom:32px">{{ tr('home_cta_sub', 'Create an account, upload your first video, and start for free.') }}</p>
        <button class="btn-primary" style="font-size:16px;padding:16px 48px" @click="goCreate">
          {{ tr('home_cta_btn', 'Start for Free') }} →
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiFetch } from '../composables/useApi.js'
import { useAuth } from '../composables/useAuth.js'
import { useI18n } from '../i18n.js'

const router   = useRouter()
const openAuth = inject('openAuth')
const { isLoggedIn } = useAuth()
const { t } = useI18n()

function tr(key, fallback = '') {
  return t.value?.[key] || fallback || key
}

function goCreate() {
  if (!isLoggedIn.value) { openAuth(); return }
  router.push('/create')
}

function scrollTo(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
}

const langs = ref([
  {code:'en',native_name:'English',flag:'🇺🇸'},
  {code:'zh',native_name:'中文',flag:'🇨🇳'},
  {code:'ja',native_name:'日本語',flag:'🇯🇵'},
  {code:'ko',native_name:'한국어',flag:'🇰🇷'},
  {code:'de',native_name:'Deutsch',flag:'🇩🇪'},
  {code:'fr',native_name:'Français',flag:'🇫🇷'},
  {code:'es',native_name:'Español',flag:'🇪🇸'},
  {code:'ru',native_name:'Русский',flag:'🇷🇺'},
])

onMounted(async () => {
  try {
    const d = await apiFetch('/api/languages')
    if (d.languages?.length) langs.value = d.languages
  } catch {}
})

const featureDefs = [
  {icon:'🎙️',titleKey:'home_feat_1_title',descKey:'home_feat_1_desc',fallbackTitle:'Local Whisper Transcription',fallbackDesc:'Run local Whisper models with word-level timestamps for precise sentence segmentation.'},
  {icon:'✂️',titleKey:'home_feat_2_title',descKey:'home_feat_2_desc',fallbackTitle:'LLM Smart Sentence Split',fallbackDesc:'Split by semantics and auto-align timestamps for natural learning chunks.'},
  {icon:'🧠',titleKey:'home_feat_3_title',descKey:'home_feat_3_desc',fallbackTitle:'AI Vocabulary Analysis',fallbackDesc:'Extract key words, phonetics, meanings, and useful expressions automatically.'},
  {icon:'🎬',titleKey:'home_feat_4_title',descKey:'home_feat_4_desc',fallbackTitle:'Flexible Part Structure',fallbackDesc:'Customize repeats and speed per part for listen-slow-listen workflows.'},
  {icon:'📐',titleKey:'home_feat_5_title',descKey:'home_feat_5_desc',fallbackTitle:'Visual Layout Editor',fallbackDesc:'Drag and resize subtitle/word/expression boxes with real-time preview.'},
  {icon:'▶️',titleKey:'home_feat_6_title',descKey:'home_feat_6_desc',fallbackTitle:'Transcript Sync Preview',fallbackDesc:'Transcript highlights in real time while video plays.'},
  {icon:'🎨',titleKey:'home_feat_7_title',descKey:'home_feat_7_desc',fallbackTitle:'Style Personalization',fallbackDesc:'Fonts, spacing, themes, and colors to match your learning style.'},
  {icon:'📊',titleKey:'home_feat_8_title',descKey:'home_feat_8_desc',fallbackTitle:'Real-time Progress',fallbackDesc:'Track rendering progress live and cancel tasks anytime.'},
  {icon:'📝',titleKey:'home_feat_9_title',descKey:'home_feat_9_desc',fallbackTitle:'Markdown Notes',fallbackDesc:'Generate structured notes with source text, translation, vocabulary, and expressions.'},
]

const stepDefs = [
  {icon:'🎵',titleKey:'home_step_1_title',descKey:'home_step_1_desc',fallbackTitle:'Audio Transcription',fallbackDesc:'Extract speech with timestamps.'},
  {icon:'✂️',titleKey:'home_step_2_title',descKey:'home_step_2_desc',fallbackTitle:'Smart Sentence Split',fallbackDesc:'Split by semantics and align timing.'},
  {icon:'🧠',titleKey:'home_step_3_title',descKey:'home_step_3_desc',fallbackTitle:'Vocabulary Analysis',fallbackDesc:'Extract words and expressions automatically.'},
  {icon:'📝',titleKey:'home_step_4_title',descKey:'home_step_4_desc',fallbackTitle:'Generate Notes',fallbackDesc:'Export structured markdown notes.'},
  {icon:'🎬',titleKey:'home_step_5_title',descKey:'home_step_5_desc',fallbackTitle:'Render Video',fallbackDesc:'Compose final learning video with subtitles.'},
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

// 3D card tilt
function on3D(e) {
  const card = e.currentTarget
  const r = card.getBoundingClientRect()
  const x = (e.clientX - r.left) / r.width  - 0.5
  const y = (e.clientY - r.top)  / r.height - 0.5
  card.style.transform = `perspective(600px) rotateY(${x*10}deg) rotateX(${-y*10}deg) scale(1.03)`
}
function off3D(e) { e.currentTarget.style.transform = '' }
</script>

<style scoped>
.home { min-height: 100vh; }

.hero {
  min-height: calc(100vh - 60px);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 60px 24px 80px; position: relative;
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 16px; border-radius: 20px;
  background: rgba(167,139,250,0.1); border: 1px solid rgba(167,139,250,0.25);
  font-size: 12px; font-weight: 700; color: var(--accent);
  margin-bottom: 28px; letter-spacing: .3px;
}
.hero-title {
  font-size: clamp(40px, 7vw, 82px); font-weight: 900;
  line-height: 1.06; margin-bottom: 22px; letter-spacing: -2px;
}
.hero-sub {
  font-size: clamp(15px, 2vw, 18px); color: var(--text2);
  max-width: 520px; line-height: 1.75; margin-bottom: 40px;
}
.hero-btns { display: flex; gap: 14px; flex-wrap: wrap; justify-content: center; }
.hero-langs {
  display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; margin-top: 52px;
}
.lang-pill {
  padding: 7px 16px; border-radius: 20px;
  background: var(--bg3); border: 1px solid var(--border);
  font-size: 13px; color: var(--text2);
  animation: float 4s ease-in-out infinite; font-weight: 500;
  transition: all .2s;
}
.lang-pill:hover { border-color: var(--accent); color: var(--accent); background: rgba(99,102,241,0.05); }

.scroll-ind {
  position: absolute; bottom: 32px; left: 50%; transform: translateX(-50%);
  animation: fadeUp .6s .8s ease both;
}
.scroll-arrow {
  width: 20px; height: 20px; border-right: 2px solid var(--text3); border-bottom: 2px solid var(--text3);
  transform: rotate(45deg); animation: float 2s ease-in-out infinite;
}

.section {
  padding: 88px 24px; max-width: 1140px; margin: 0 auto;
}
.section-label {
  font-size: 11px; font-weight: 800; letter-spacing: 3px;
  color: var(--accent); text-transform: uppercase; margin-bottom: 12px;
}
.section-title {
  font-size: clamp(26px, 4vw, 44px); font-weight: 800;
  margin-bottom: 14px; letter-spacing: -0.5px;
}
.section-sub {
  font-size: 15px; color: var(--text2); margin-bottom: 48px; max-width: 500px;
}

/* FEATURES */
.feat-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px;
}
.feat-card {
  padding: 28px; border-radius: var(--r); position: relative; overflow: hidden;
  background: var(--card); border: 1px solid var(--border);
  transition: all .3s cubic-bezier(0.34, 1.56, 0.64, 1);
  transform-style: preserve-3d;
}
.feat-card:hover { border-color: rgba(99,102,241,0.3); box-shadow: 0 4px 20px rgba(99,102,241,0.08); }
.feat-glow {
  position: absolute; inset: 0; opacity: 0; transition: opacity .3s;
  background: radial-gradient(circle at 50% 50%, rgba(99,102,241,0.04), transparent 70%);
}
.feat-card:hover .feat-glow { opacity: 1; }
.feat-icon { font-size: 32px; margin-bottom: 14px; }
.feat-title { font-size: 15px; font-weight: 700; margin-bottom: 8px; }
.feat-desc { font-size: 13px; color: var(--text2); line-height: 1.65; }

/* STEPS */
.steps-row {
  display: flex; gap: 0; overflow-x: auto; padding-bottom: 8px;
  align-items: flex-start;
}
.step-item {
  display: flex; flex-direction: column; align-items: center;
  flex: 1; min-width: 140px; position: relative;
}
.step-num {
  width: 44px; height: 44px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 800; color: #fff;
  box-shadow: 0 4px 16px rgba(167,139,250,0.4); z-index: 1;
  flex-shrink: 0;
}
.step-connector {
  position: absolute; top: 22px; left: 50%; right: -50%;
  height: 2px;
  background: linear-gradient(90deg, rgba(167,139,250,0.5), rgba(167,139,250,0.1));
  z-index: 0;
}
.step-content { margin-top: 16px; text-align: center; padding: 0 8px; }
.step-icon { font-size: 24px; margin-bottom: 8px; }
.step-title { font-size: 14px; font-weight: 700; margin-bottom: 6px; }
.step-desc { font-size: 12px; color: var(--text2); line-height: 1.6; }

/* LANG GRID */
.lang-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 14px;
}
.lang-card {
  padding: 24px 16px; text-align: center; border-radius: var(--r);
  background: var(--card); border: 1px solid var(--border);
  transition: all .25s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.lang-card:hover {
  background: var(--bg3); border-color: rgba(99,102,241,0.3);
  transform: scale(1.05) translateY(-4px);
  box-shadow: 0 8px 24px rgba(99,102,241,0.10);
}
.lang-flag { font-size: 36px; margin-bottom: 10px; }
.lang-name { font-size: 13px; font-weight: 700; margin-bottom: 4px; }
.lang-code { font-size: 11px; color: var(--text3); font-weight: 600; letter-spacing: 1px; }

/* CTA */
.cta-card {
  padding: 64px 48px; border-radius: 24px;
  background: linear-gradient(135deg, rgba(99,102,241,0.06), rgba(244,63,94,0.04));
  border: 1.5px solid rgba(99,102,241,0.15);
  box-shadow: 0 0 60px rgba(99,102,241,0.06);
}
</style>
