<template>
  <div class="membership-page">
    <div class="mg-glow mg-glow-a"></div>
    <div class="mg-glow mg-glow-b"></div>
    <div class="mg-glow mg-glow-c"></div>

    <div class="mg-inner">
      <!-- ── Header ── -->
      <div class="mg-header">
        <div class="mg-badge">
          <img src="/premium-badge.svg" alt="VIP" class="mg-badge-icon">
          {{ tr('mm_badge_label', '会员专属权益') }}
        </div>
        <h1 class="mg-title">
          <span>{{ tr('mm_page_title_line1', '解锁你的语言学习') }}</span>
          <span class="mg-title-grad">{{ tr('mm_page_title_line2', '超级加速器') }}</span>
        </h1>
        <p class="mg-sub">{{ tr('mm_page_subtitle', '从视频到课堂，从字幕到随身听，AI 助教 24 小时在线陪你突破语言障碍') }}</p>

        <div v-if="status" class="mg-status-pill" :class="isMember ? 'pill-vip' : 'pill-free'">
          <span class="pill-dot"></span>
          <span v-if="isMember">{{ tr('mm_member', '会员') }} · {{ tr('mm_today_generated', '今日已生成') }} {{ status.usage?.videos_generated_today ?? 0 }} {{ tr('mm_videos', '个视频') }}</span>
          <span v-else>{{ tr('mm_free_user', '免费用户') }} · {{ tr('mm_today_generated', '今日已生成') }} {{ status.usage?.videos_generated_today ?? 0 }} / 3 {{ tr('mm_videos', '个视频') }}</span>
        </div>
      </div>

      <!-- ── Comparison Table ── -->
      <section class="cmp-section">
        <div class="section-eyebrow">{{ tr('mm_full_cmp_label', '权益全量对比') }}</div>
        <h2 class="section-heading">{{ tr('mm_full_cmp_title', '免费 vs 会员') }}</h2>

        <div class="cmp-wrap">
          <!-- Column headers -->
          <div class="cmp-header-row">
            <div class="cmp-feat-col"></div>
            <div class="cmp-free-col cmp-col-head-free">
              <div class="cmp-tier-label free-label">{{ tr('mm_free', '免费') }}</div>
              <div class="cmp-tier-price free-price">¥0</div>
              <div class="cmp-tier-sub">{{ tr('mm_forever_free', '永久免费') }}</div>
            </div>
            <div class="cmp-vip-col cmp-col-head-vip">
              <div class="vip-header-shine"></div>
              <div class="cmp-vip-crown">👑</div>
              <div class="cmp-tier-label vip-label">{{ tr('mm_member', '会员') }}</div>
              <div class="cmp-tier-price vip-price">
                <span class="best-tag">{{ tr('mm_best_value', '最超值') }}</span>
              </div>
              <div class="cmp-tier-sub vip-sub">{{ tr('mm_from', '低至') }} ¥3{{ tr('mm_per_day', '/天') }}</div>
            </div>
          </div>

          <!-- Rows -->
          <div v-for="row in compareRows" :key="row.key" class="cmp-row" :class="{ 'row-highlight': row.highlight }">
            <div class="cmp-feat-col">
              <span class="feat-icon">{{ row.icon }}</span>
              <span class="feat-name">{{ row.feature }}</span>
            </div>
            <div class="cmp-free-col">
              <span class="val-free">{{ row.free }}</span>
            </div>
            <div class="cmp-vip-col">
              <span class="val-vip" :class="{ 'val-vip-em': row.highlight }">{{ row.vip }}</span>
            </div>
          </div>
        </div>

        <div class="cmp-currency-note">
          🌐 {{ tr('mm_currency_converted', '价格已按学习目标语言换算') }} · {{ currentCurrencyCode }}
          <span v-if="currentCurrencyCode !== 'CNY'">（{{ tr('mm_base_cny', '基准人民币') }} ¥2.75 / ¥1.38 / 分钟）</span>
        </div>
      </section>

      <!-- ── Plans ── -->
      <section class="plans-section" ref="plansRef">
        <div class="section-eyebrow">{{ tr('mm_price_title', '会员定价') }}</div>
        <h2 class="section-heading">{{ tr('mm_plans_title', '选择适合你的计划') }}</h2>

        <div class="provider-tabs">
          <button :class="['pv-tab', { active: provider === 'alipay' }]" @click="provider = 'alipay'">
            {{ tr('mm_alipay', '支付宝') }}
          </button>
          <button :class="['pv-tab', { active: provider === 'stripe' }]" @click="provider = 'stripe'">
            {{ tr('mm_stripe', 'Stripe') }} · {{ tr('mm_global', '国际') }}
          </button>
        </div>

        <div class="plans-grid">
          <button
            v-for="p in displayPlans"
            :key="p.displayCode"
            class="plan-card"
            :class="{ recommended: p.period === 'month', unavailable: !p.available, 'is-loading': loadingCode === p.checkoutCode }"
            :disabled="!p.available || !!loadingCode"
            @click="checkout(p)"
          >
            <div v-if="p.period === 'month'" class="plan-rec-tag">{{ tr('mm_recommended', '推荐') }}</div>
            <div v-if="p.trial_once" class="plan-trial-tag">{{ tr('mm_trial_once', '仅限一次') }}</div>
            <div class="plan-name">{{ p.displayName }}</div>
            <div class="plan-price">
              <span class="plan-currency">{{ p.currencySymbol }}</span>
              <span class="plan-amount">{{ p.displayPrice }}</span>
            </div>
            <div class="plan-meta">{{ p.auto_renew ? tr('mm_auto_renew', '自动续费') : tr('mm_one_time', '一次性') }} · {{ p.periodLabel }}</div>
            <div class="plan-daily">{{ tr('mm_daily_avg', '平均每天') }} {{ p.currencySymbol }}{{ p.dailyAvg }}</div>
            <div v-if="!p.available" class="plan-footer used">{{ tr('mm_used', '已使用') }}</div>
            <div v-else-if="loadingCode === p.checkoutCode" class="plan-footer"><span class="spinner small"></span></div>
            <div v-else class="plan-footer cta">{{ tr('mm_buy_now', '立即开通') }} →</div>
          </button>
        </div>

        <div class="plans-note">
          <div>* {{ tr('mm_note_1', 'Stripe 以当前汇率估算展示，实际支付金额以收银台为准。') }}</div>
          <div>* {{ tr('mm_note_2', '套餐权益以会员协议和系统实时规则为准。') }}</div>
        </div>
      </section>

      <!-- ── Bottom CTA banner ── -->
      <div v-if="!isMember" class="cta-banner">
        <div class="cta-glow"></div>
        <div class="cta-content">
          <div class="cta-left">
            <div class="cta-title">{{ tr('mm_cta_title', '现在加入，立刻开启 AI 伴学之旅') }}</div>
            <div class="cta-sub">{{ tr('mm_cta_sub', '每月 2 次免费 AI 课堂 · 全功能解锁 · 随时可取消') }}</div>
          </div>
          <button class="cta-btn" @click="scrollToPlans">{{ tr('mm_cta_btn', '查看方案 ↓') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted } from 'vue'
import { apiFetch } from '../composables/useApi.js'
import { useI18n } from '../i18n.js'
import { useAuth } from '../composables/useAuth.js'
import { formatMembershipPeriod } from '../composables/membershipLabels.js'

const { t, uiLang } = useI18n()
const { user } = useAuth()
const languagePrefs = inject('languagePrefs', null)
const openAuth = inject('openAuth', null)

function tr(key, fallback = '') {
  return ((t.value?.[key]) ?? fallback) || key
}

const status = ref(null)
const plans = ref([])
const provider = ref('alipay')
const loadingCode = ref('')
const plansRef = ref(null)

const isMember = computed(() => user.value?.membership?.tier === 'member')

const BASE_PLAN_DEFS = [
  { period: 'day',   codeSuffix: 'day',   cnyPrice: 3,   days: 1,   auto_renew: false, trial_once: true  },
  { period: 'week',  codeSuffix: 'week',  cnyPrice: 21,  days: 7,   auto_renew: true,  trial_once: false },
  { period: 'month', codeSuffix: 'month', cnyPrice: 75,  days: 30,  auto_renew: true,  trial_once: false },
  { period: 'year',  codeSuffix: 'year',  cnyPrice: 730, days: 365, auto_renew: true,  trial_once: false },
]

const CURRENCY_BY_TGT_LANG = {
  'zh-Hans': 'CNY', 'zh-Hant': 'CNY',
  en: 'USD', ja: 'JPY', ko: 'KRW',
  de: 'EUR', fr: 'EUR', es: 'EUR', ru: 'RUB',
}

const CURRENCY_META = {
  CNY: { symbol: '¥',  rate: 1,     digits: 2 },
  USD: { symbol: '$',  rate: 0.14,  digits: 2 },
  EUR: { symbol: '€',  rate: 0.13,  digits: 2 },
  JPY: { symbol: '¥',  rate: 20.8,  digits: 2 },
  KRW: { symbol: '₩',  rate: 191,   digits: 2 },
  RUB: { symbol: '₽',  rate: 12.5,  digits: 2 },
}

const PERIOD_NAME = {
  day:   { zh: '一天体验价', en: '1-Day Trial'  },
  week:  { zh: '连续包周',   en: 'Weekly'       },
  month: { zh: '连续包月',   en: 'Monthly'      },
  year:  { zh: '连续包年',   en: 'Yearly'       },
}

const learningLangCode = computed(() => {
  const fromInject = languagePrefs?.learningLang?.value
  if (fromInject) return fromInject
  try { return localStorage.getItem('ll_learning_lang') || 'en' } catch { return 'en' }
})

const currentCurrencyCode = computed(() => {
  if (provider.value !== 'stripe') return 'CNY'
  return CURRENCY_BY_TGT_LANG[learningLangCode.value] || 'USD'
})

const currentMeta = computed(() => CURRENCY_META[currentCurrencyCode.value] || CURRENCY_META.USD)

function fmtPrice(cny) {
  return `${currentMeta.value.symbol}${(cny * currentMeta.value.rate).toFixed(2)}`
}

// Build compare rows — AI lesson uses real currency conversion
const compareRows = computed(() => [
  {
    key: 'daily_videos',
    icon: '🎬',
    feature: tr('mm_cmp_daily_videos', '每日视频生成'),
    free: tr('mm_cmp_free_daily_videos', '最多 3 个/天'),
    vip:  tr('mm_cmp_vip_daily_videos',  '最多 15 个/天'),
    highlight: false,
  },
  {
    key: 'video_minutes',
    icon: '⏱',
    feature: tr('mm_cmp_video_minutes', '单视频最长'),
    free: tr('mm_cmp_free_video_minutes', '5 分钟'),
    vip:  tr('mm_cmp_vip_video_minutes',  '20 分钟'),
    highlight: false,
  },
  {
    key: 'ai_lesson',
    icon: '🎙️',
    feature: tr('mm_cmp_ai_lesson', 'AI 互动课堂'),
    free: `${fmtPrice(2.75)} / ${tr('mm_per_minute', '分钟')}`,
    vip:  `${tr('mm_vip_free_2', '每月 2 次免费')} · ${tr('mm_beyond_free', '超出')} ${fmtPrice(1.38)} / ${tr('mm_per_minute', '分钟')}`,
    highlight: true,
  },
  {
    key: 'watermark',
    icon: '💧',
    feature: tr('mm_cmp_watermark', '视频水印'),
    free: tr('mm_cmp_free_watermark', '固定水印，不可删除'),
    vip:  tr('mm_cmp_vip_watermark',  '可自定义或删除'),
    highlight: false,
  },
  {
    key: 'storage',
    icon: '🗄️',
    feature: tr('mm_cmp_storage', '存储空间'),
    free: '10 GB',
    vip:  '128 GB',
    highlight: false,
  },
  {
    key: 'style',
    icon: '🎨',
    feature: tr('mm_cmp_style', '字幕 & 字体'),
    free: tr('mm_cmp_free_style', '基础样式'),
    vip:  tr('mm_cmp_vip_style',  '高级样式 + 更多字体'),
    highlight: false,
  },
  {
    key: 'export_pdf',
    icon: '📄',
    feature: tr('mm_cmp_pdf', 'PDF 导出'),
    free: '✗',
    vip:  '✓ ' + tr('mm_cmp_vip_pdf', '无限导出'),
    highlight: false,
  },
  {
    key: 'priority',
    icon: '⚡',
    feature: tr('mm_cmp_priority', '渲染优先级'),
    free: tr('mm_cmp_free_priority', '标准'),
    vip:  tr('mm_cmp_vip_priority', '高优先级'),
    highlight: false,
  },
])

function formatPrice(amount, digits) {
  return Number(amount).toFixed(digits)
}

function localizedPeriod(period) {
  return formatMembershipPeriod(period, uiLang.value, period)
}

const planAvailabilityMap = computed(() => {
  const map = new Map()
  for (const p of plans.value || []) map.set(p.code, p.available !== false)
  return map
})

const displayPlans = computed(() => {
  const isStripe = provider.value === 'stripe'
  const currencyCode = isStripe ? currentCurrencyCode.value : 'CNY'
  const meta = CURRENCY_META[currencyCode] || CURRENCY_META.USD
  const isZhUi = String(uiLang.value || '').startsWith('zh')
  const prefix = isStripe ? (currencyCode === 'CNY' ? 'cn_' : 'intl_') : 'cn_'

  return BASE_PLAN_DEFS.map(def => {
    const checkoutCode = `${prefix}${def.codeSuffix}`
    const rawPrice = def.cnyPrice * meta.rate
    const displayPrice = formatPrice(rawPrice, meta.digits)
    const dailyAvg = formatPrice(rawPrice / def.days, meta.digits)
    const labelSet = PERIOD_NAME[def.period] || PERIOD_NAME.month
    const displayName = isZhUi ? labelSet.zh : labelSet.en
    const availableByStatus = planAvailabilityMap.value.has(checkoutCode)
      ? Boolean(planAvailabilityMap.value.get(checkoutCode)) : true
    const trialLocked = def.trial_once && Boolean(status.value?.trial_used)
    const available = availableByStatus && !trialLocked
    return {
      ...def,
      displayCode: `${provider.value}_${def.codeSuffix}`,
      checkoutCode,
      displayName,
      displayPrice,
      currencyCode,
      currencySymbol: meta.symbol,
      dailyAvg,
      periodLabel: localizedPeriod(def.period),
      available,
    }
  })
})

onMounted(async () => {
  try {
    const s = await apiFetch('/api/membership/status')
    status.value = s
    plans.value = s.plans || []
  } catch {}
})

async function checkout(plan) {
  if (!plan?.available || loadingCode.value) return
  if (!user.value) { openAuth?.(); return }
  loadingCode.value = plan.checkoutCode
  try {
    const endpoint = provider.value === 'alipay'
      ? '/api/membership/checkout/alipay'
      : '/api/membership/checkout/stripe'
    const d = await apiFetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_code: plan.checkoutCode }),
    })
    if (!d.checkout_url) throw new Error(tr('mm_no_checkout_url', 'No checkout URL returned'))
    window.location.href = d.checkout_url
  } catch (e) {
    alert(e.message || tr('mm_checkout_failed', '支付创建失败'))
  } finally {
    loadingCode.value = ''
  }
}

function scrollToPlans() {
  plansRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<style scoped>
.membership-page {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  padding-bottom: 80px;
}

/* Glow orbs */
.mg-glow {
  position: fixed;
  border-radius: 50%;
  filter: blur(90px);
  pointer-events: none;
  z-index: 0;
}
.mg-glow-a { width: 500px; height: 500px; top: -100px; left: -150px; background: radial-gradient(circle, rgba(11,120,209,0.16), transparent 70%); animation: mgDrift 14s ease-in-out infinite; }
.mg-glow-b { width: 420px; height: 420px; top: 40vh; right: -100px; background: radial-gradient(circle, rgba(242,168,44,0.16), transparent 70%); animation: mgDrift 18s ease-in-out infinite reverse; }
.mg-glow-c { width: 360px; height: 360px; bottom: 100px; left: 30%; background: radial-gradient(circle, rgba(16,185,129,0.1), transparent 70%); animation: mgDrift 22s ease-in-out infinite; }
@keyframes mgDrift { 0%, 100% { transform: translateY(0) scale(1); } 50% { transform: translateY(40px) scale(1.07); } }

.mg-inner {
  position: relative;
  z-index: 1;
  max-width: 1060px;
  margin: 0 auto;
  padding: 52px 24px 0;
  display: flex;
  flex-direction: column;
  gap: 60px;
}

/* ── Header ── */
.mg-header { text-align: center; }
.mg-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 18px;
  border-radius: 999px;
  border: 1px solid rgba(242,168,44,0.38);
  background: linear-gradient(120deg, rgba(255,255,255,0.9), rgba(255,248,235,0.7));
  backdrop-filter: blur(8px);
  font-size: 12px;
  font-weight: 700;
  color: #92400e;
  margin-bottom: 20px;
  letter-spacing: 0.4px;
}
.mg-badge-icon { width: 17px; height: 17px; border-radius: 4px; }

.mg-title {
  font-size: clamp(34px, 6vw, 68px);
  font-weight: 900;
  line-height: 1.08;
  letter-spacing: -0.03em;
  color: #0d1a2e;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0 0 16px;
}
.mg-title-grad {
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 50%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  background-size: 200% 100%;
  animation: shimmer 9s linear infinite;
}
@keyframes shimmer { 0% { background-position: 100% 50%; } 100% { background-position: -100% 50%; } }

.mg-sub { max-width: 600px; margin: 0 auto 22px; font-size: clamp(14px, 2vw, 17px); line-height: 1.76; color: rgba(13,26,46,0.7); }

.mg-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}
.pill-vip { background: linear-gradient(120deg, rgba(16,185,129,0.14), rgba(6,182,212,0.1)); border: 1px solid rgba(16,185,129,0.3); color: #065f46; }
.pill-free { background: rgba(255,255,255,0.72); border: 1px solid rgba(148,163,184,0.3); color: #475569; }
.pill-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }

/* ── Comparison Table ── */
.cmp-section { text-align: center; }

.section-eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #0b78d1;
  margin-bottom: 8px;
}
.section-heading {
  font-size: clamp(22px, 4vw, 38px);
  font-weight: 900;
  letter-spacing: -0.02em;
  color: #0d1a2e;
  margin: 0 0 28px;
}

.cmp-wrap {
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(11,120,209,0.18);
  box-shadow: 0 20px 60px rgba(13,59,102,0.1);
  background: rgba(255,255,255,0.96);
  backdrop-filter: blur(8px);
  text-align: left;
}

/* Header row */
.cmp-header-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1.5fr;
  border-bottom: 2px solid rgba(11,120,209,0.15);
}
.cmp-feat-col { padding: 20px 20px 16px; }
.cmp-free-col, .cmp-vip-col { padding: 20px 20px 16px; }

.cmp-col-head-free { background: rgba(248,250,252,0.9); }
.cmp-col-head-vip {
  position: relative;
  background: linear-gradient(160deg, rgba(11,120,209,0.09), rgba(6,182,212,0.05));
  border-left: 1px solid rgba(11,120,209,0.15);
}
.vip-header-shine {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, #0b78d1, #06b6d4, #f2a82c);
}
.cmp-vip-crown { font-size: 22px; margin-bottom: 4px; }

.cmp-tier-label { font-size: 15px; font-weight: 800; color: #0f172a; margin-bottom: 4px; }
.free-label { color: #475569; }
.vip-label {
  background: linear-gradient(118deg, #0d2f5a, #0b78d1);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.cmp-tier-price { font-size: 26px; font-weight: 900; color: #0f172a; margin-bottom: 2px; }
.free-price { color: #94a3b8; }
.vip-price { margin-bottom: 4px; }
.cmp-tier-sub { font-size: 12px; color: #64748b; }
.vip-sub { color: #0b78d1; font-weight: 600; }

.best-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, #f59e0b, #f2a82c);
  padding: 3px 10px;
  border-radius: 999px;
  letter-spacing: 0.3px;
}

/* Data rows */
.cmp-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1.5fr;
  border-bottom: 1px solid rgba(148,163,184,0.12);
  transition: background 0.15s;
}
.cmp-row:last-child { border-bottom: none; }
.cmp-row:hover { background: rgba(11,120,209,0.025); }
.row-highlight { background: linear-gradient(90deg, rgba(11,120,209,0.04), rgba(242,168,44,0.04)) !important; }
.row-highlight:hover { background: linear-gradient(90deg, rgba(11,120,209,0.07), rgba(242,168,44,0.07)) !important; }

.cmp-feat-col {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 20px;
  font-size: 13px;
}
.feat-icon { font-size: 16px; flex-shrink: 0; }
.feat-name { font-weight: 600; color: #334155; }

.cmp-free-col, .cmp-vip-col { padding: 14px 20px; display: flex; align-items: center; }
.cmp-free-col { border-left: none; }
.cmp-vip-col { border-left: 1px solid rgba(11,120,209,0.1); background: rgba(11,120,209,0.018); }

.val-free { font-size: 13px; color: #94a3b8; }
.val-vip { font-size: 13px; color: #0f172a; font-weight: 600; }
.val-vip-em {
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  font-weight: 800;
  font-size: 13px;
}

.cmp-currency-note {
  margin-top: 14px;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
}

/* ── Plans ── */
.plans-section { text-align: center; }

.provider-tabs {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-bottom: 28px;
}
.pv-tab {
  padding: 9px 22px;
  border-radius: 10px;
  border: 1.5px solid rgba(148,163,184,0.3);
  background: rgba(255,255,255,0.7);
  backdrop-filter: blur(6px);
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  transition: all 0.18s;
}
.pv-tab.active { border-color: #0b78d1; color: #0b78d1; background: rgba(11,120,209,0.08); }

.plans-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}

.plan-card {
  position: relative;
  border-radius: 18px;
  padding: 20px 16px 16px;
  text-align: left;
  cursor: pointer;
  border: 1.5px solid rgba(148,163,184,0.25);
  background: linear-gradient(160deg, rgba(255,255,255,0.96), rgba(248,252,255,0.9));
  backdrop-filter: blur(6px);
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-height: 165px;
  transition: all 0.22s ease;
}
.plan-card:hover:not(:disabled) { border-color: rgba(11,120,209,0.45); transform: translateY(-5px); box-shadow: 0 18px 44px rgba(11,120,209,0.2); }
.plan-card.recommended { border-color: #0b78d1; background: linear-gradient(160deg, rgba(11,120,209,0.07), rgba(248,252,255,0.95)); box-shadow: 0 8px 28px rgba(11,120,209,0.15); }
.plan-card.unavailable { opacity: 0.55; cursor: not-allowed; }

.plan-rec-tag, .plan-trial-tag {
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 10px;
  font-weight: 800;
  padding: 3px 10px;
  border-radius: 999px;
  white-space: nowrap;
}
.plan-rec-tag { background: linear-gradient(135deg, #0b78d1, #06b6d4); color: #fff; }
.plan-trial-tag { background: rgba(239,68,68,0.1); color: #991b1b; border: 1px solid rgba(239,68,68,0.2); }

.plan-name { font-size: 13px; font-weight: 700; color: #0f172a; }
.plan-price { display: flex; align-items: baseline; gap: 2px; margin: 3px 0 1px; }
.plan-currency { font-size: 16px; font-weight: 800; color: #0f172a; }
.plan-amount { font-size: 34px; font-weight: 900; color: #0f172a; line-height: 1; letter-spacing: -0.03em; }
.plan-meta { font-size: 11px; color: #64748b; }
.plan-daily { font-size: 12px; color: #0d4d80; font-weight: 700; }
.plan-footer { font-size: 12px; margin-top: auto; }
.plan-footer.cta { color: #0b78d1; font-weight: 700; }
.plan-footer.used { color: #b45309; }

.plans-note {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.8;
  text-align: left;
  background: rgba(255,255,255,0.6);
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 12px;
  padding: 12px 16px;
}

/* ── CTA Banner ── */
.cta-banner {
  border-radius: 24px;
  background: linear-gradient(130deg, #0a2a5e 0%, #0b78d1 52%, #0ea5e9 100%);
  box-shadow: 0 24px 60px rgba(11,120,209,0.35);
  overflow: hidden;
  position: relative;
}
.cta-glow {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 55%);
  pointer-events: none;
}
.cta-content {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 32px 40px;
  flex-wrap: wrap;
}
.cta-title { font-size: 21px; font-weight: 900; color: #fff; margin-bottom: 5px; }
.cta-sub { font-size: 13px; color: rgba(255,255,255,0.75); }
.cta-btn {
  padding: 13px 30px;
  border-radius: 14px;
  background: rgba(255,255,255,0.16);
  border: 1.5px solid rgba(255,255,255,0.35);
  backdrop-filter: blur(6px);
  color: #fff;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.2s;
}
.cta-btn:hover { background: rgba(255,255,255,0.26); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.18); }

/* ── Responsive ── */
@media (max-width: 860px) { .plans-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 640px) {
  .mg-inner { padding: 28px 16px 0; gap: 40px; }
  .plans-grid { grid-template-columns: 1fr 1fr; }
  .cmp-header-row, .cmp-row { grid-template-columns: 1.4fr 1fr 1.4fr; }
  .cta-content { flex-direction: column; text-align: center; }
}
</style>
