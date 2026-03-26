<template>
  <div class="home">
    <!-- Hero -->
    <section class="hero">
      <div class="hero-badge fade-up">✨ 支持 8 种语言双向互学</div>
      <h1 class="hero-title fade-up" style="animation-delay:.1s">
        <span class="grad-text">LinguaLearn</span><br>
        <span style="color:var(--text)">把外语视频变成学习利器</span>
      </h1>
      <p class="hero-sub fade-up" style="animation-delay:.2s">
        上传任意外语视频，AI 自动转录、分析词汇、渲染字幕，<br>生成专属的「逐句精听」学习视频
      </p>
      <div class="hero-btns fade-up" style="animation-delay:.3s">
        <button class="btn-primary" style="font-size:15px;padding:14px 36px" @click="goCreate">
          立即开始 →
        </button>
        <button class="btn-ghost" style="font-size:15px;padding:14px 36px" @click="scrollTo('features')">
          了解功能
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
      <div class="section-label">核心功能</div>
      <h2 class="section-title">一站式语言学习解决方案</h2>
      <p class="section-sub">从原始视频到完整学习材料，全程自动化，零门槛上手</p>
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
      <div class="section-label">处理流程</div>
      <h2 class="section-title">五步自动完成</h2>
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
      <div class="section-label">支持语言</div>
      <h2 class="section-title">8 种语言，任意互学</h2>
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
        <h2 class="section-title" style="margin-bottom:12px">准备好了吗？</h2>
        <p style="color:var(--text2);margin-bottom:32px">注册账号，上传你的第一个视频，免费体验</p>
        <button class="btn-primary" style="font-size:16px;padding:16px 48px" @click="goCreate">
          免费开始使用 →
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiFetch } from '../composables/useApi.js'
import { useAuth } from '../composables/useAuth.js'

const router   = useRouter()
const openAuth = inject('openAuth')
const { isLoggedIn } = useAuth()

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

const features = [
  {icon:'🎙️',title:'本地 Whisper 转录',desc:'使用 OpenAI Whisper 本地模型，支持 7 种语言，带单词级时间戳，精准切割每一句话'},
  {icon:'✂️',title:'LLM 智能分句',desc:'大语言模型辅助，根据语义边界切分句子，自动对齐时间戳，每句 5–30 词'},
  {icon:'🧠',title:'AI 词汇深度分析',desc:'DeepSeek 并行分析，提取关键词（含音标、释义、难度）和实用表达'},
  {icon:'🎬',title:'灵活 Part 结构',desc:'自由配置每个 Part 的重复次数和慢速选项，原速 → 慢速精学 → 原速巩固'},
  {icon:'📐',title:'可视化布局编辑器',desc:'拖拽/缩放字幕框、单词框、表达框，实时预览位置，支持多套命名预设配置'},
  {icon:'▶️',title:'视频文稿同步预览',desc:'分屏播放：视频播放时文稿自动高亮当前句，点击句子前 ▶ 可重复播放该句'},
  {icon:'🎨',title:'样式深度个性化',desc:'字体族、字号倍率、行间距、背景主题、文字颜色……让每一帧都符合你的审美'},
  {icon:'📊',title:'实时进度 & 取消',desc:'WebSocket 推送逐帧渲染进度，卡住时一键取消，不再对着空白屏发愁'},
  {icon:'📝',title:'Markdown 学习笔记',desc:'自动生成结构化文字稿：原文、译文、音标表格、实用表达，可导入笔记软件'},
]

const steps = [
  {icon:'🎵',title:'音频转录',desc:'Whisper 提取音频，生成带时间戳的文字'},
  {icon:'✂️',title:'智能分句',desc:'按语义切割，精准对齐每句的起止时间'},
  {icon:'🧠',title:'词汇分析',desc:'AI 并行分析所有句子，提取词汇和表达'},
  {icon:'📝',title:'生成文字稿',desc:'导出 Markdown 格式学习笔记'},
  {icon:'🎬',title:'渲染视频',desc:'FFmpeg 纯硬件流水线合成最终视频，ASS 字幕实时烧录，无需第三方渲染库'},
]

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
