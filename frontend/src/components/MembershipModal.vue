<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
      <div class="mm-box">
        <button class="modal-close" @click="$emit('close')">✕</button>
        <div class="mm-head">
          <img src="/premium-badge.svg" alt="Premium" class="mm-logo">
          <div>
            <div class="mm-title">{{ tr('mm_title', 'LinguaLearn Membership') }}</div>
            <div class="mm-sub">{{ tr('mm_sub', 'Choose the plan that fits your learning intensity and unlock premium creation power.') }}</div>
          </div>
        </div>

        <div class="mm-status" v-if="status">
          <span :class="['tag', status.tier === 'member' ? 'tag-ok' : 'tag-free']">
            {{ status.tier === 'member' ? tr('mm_member', 'Member') : tr('mm_free', 'Free') }}
          </span>
          <span class="mm-status-text">
            {{ tr('mm_today_generated', 'Today generated') }} {{ status.usage?.videos_generated_today ?? 0 }} {{ tr('mm_videos', 'videos') }}
          </span>
        </div>

        <div class="mm-provider">
          <button :class="['pv-btn', {active: provider==='alipay'}]" @click="provider='alipay'">{{ tr('mm_alipay', 'Alipay') }}</button>
          <button :class="['pv-btn', {active: provider==='stripe'}]" @click="provider='stripe'">
            {{ tr('mm_stripe', 'Stripe') }}
          </button>
        </div>

        <div class="mm-compare card-like">
          <div class="mm-sec-head">{{ tr('mm_compare_title', '非会员 vs 会员') }}</div>
          <table class="cmp-table">
            <thead>
              <tr>
                <th>{{ tr('mm_compare_item', '能力项') }}</th>
                <th>{{ tr('mm_free', 'Free') }}</th>
                <th>{{ tr('mm_member', 'VIP') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in compareRows" :key="row.key">
                <td>{{ row.feature }}</td>
                <td>{{ row.free }}</td>
                <td>{{ row.vip }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="mm-pricing-head">
          <div class="mm-sec-head">{{ tr('mm_price_title', '会员定价') }}</div>
          <div class="mm-currency-hint">
            <template v-if="provider === 'stripe'">
              {{ tr('mm_currency_hint_stripe', 'Stripe价格按你的学习目标语言自动换算展示') }} · {{ currentCurrencyCode }}
            </template>
            <template v-else>
              {{ tr('mm_currency_hint_alipay', '支付宝使用人民币结算') }}
            </template>
          </div>
        </div>

        <div class="mm-plan-grid">
          <button
            v-for="p in displayPlans"
            :key="p.displayCode"
            class="mm-plan"
            :disabled="!p.available || loadingCode === p.checkoutCode"
            @click="checkout(p)"
          >
            <div class="mm-plan-name">
              {{ p.displayName }}
              <span v-if="p.trial_once" class="trial-tag">{{ tr('mm_trial_once', '1-time only') }}</span>
            </div>
            <div class="mm-plan-price">{{ p.currencySymbol }}{{ p.displayPrice }}</div>
            <div class="mm-plan-meta">
              {{ p.auto_renew ? tr('mm_auto_renew', 'Auto renew') : tr('mm_one_time', 'One-time') }} · {{ p.periodLabel }}
            </div>
            <div class="mm-plan-daily">
              {{ tr('mm_daily_avg', '平均每天') }} {{ p.currencySymbol }}{{ p.dailyAvg }}
            </div>
            <div v-if="!p.available" class="mm-plan-unavail">{{ tr('mm_used', 'Used') }}</div>
          </button>
        </div>

        <div class="mm-foot-note">
          <div>{{ tr('mm_note_1', '* Stripe以当前汇率估算展示，实际支付金额以收银台为准。') }}</div>
          <div>{{ tr('mm_note_2', '* 套餐权益以会员协议和系统实时规则为准。') }}</div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, inject, ref, watch } from 'vue'
import { apiFetch } from '../composables/useApi.js'
import { useI18n } from '../i18n.js'
import { formatMembershipPeriod } from '../composables/membershipLabels.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'refreshed'])

const status = ref(null)
const plans = ref([])
const provider = ref('alipay')
const loadingCode = ref('')
const { t, uiLang } = useI18n()
const languagePrefs = inject('languagePrefs', null)

function tr(key, fallback = '') {
  return ((t.value?.[key]) ?? fallback) || key
}

function localizedPeriod(period) {
  return formatMembershipPeriod(period, uiLang.value, period)
}

const BASE_PLAN_DEFS = [
  { period: 'day', codeSuffix: 'day', cnyPrice: 3, days: 1, auto_renew: false, trial_once: true },
  { period: 'week', codeSuffix: 'week', cnyPrice: 21, days: 7, auto_renew: true, trial_once: false },
  { period: 'month', codeSuffix: 'month', cnyPrice: 75, days: 30, auto_renew: true, trial_once: false },
  { period: 'year', codeSuffix: 'year', cnyPrice: 730, days: 365, auto_renew: true, trial_once: false },
]

const CURRENCY_BY_TGT_LANG = {
  'zh-Hans': 'CNY',
  'zh-Hant': 'CNY',
  en: 'USD',
  ja: 'JPY',
  ko: 'KRW',
  de: 'EUR',
  fr: 'EUR',
  es: 'EUR',
  ru: 'RUB',
}

const CURRENCY_META = {
  CNY: { symbol: '¥', rate: 1, digits: 0 },
  USD: { symbol: '$', rate: 0.14, digits: 2 },
  EUR: { symbol: '€', rate: 0.13, digits: 2 },
  JPY: { symbol: '¥', rate: 20.8, digits: 0 },
  KRW: { symbol: '₩', rate: 191, digits: 0 },
  RUB: { symbol: '₽', rate: 12.5, digits: 0 },
}

const PERIOD_NAME = {
  day: { zh: '一天体验价', en: '1-day Trial' },
  week: { zh: '连续包周', en: 'Weekly' },
  month: { zh: '连续包月', en: 'Monthly' },
  year: { zh: '连续包年', en: 'Yearly' },
}

const compareRows = computed(() => [
  {
    key: 'daily_videos',
    feature: tr('mm_cmp_daily_videos', '每日视频生成上限'),
    free: tr('mm_cmp_free_daily_videos', '每天最多生成3个视频'),
    vip: tr('mm_cmp_vip_daily_videos', '每天最多生成15个视频'),
  },
  {
    key: 'video_minutes',
    feature: tr('mm_cmp_video_minutes', '单个视频长度'),
    free: tr('mm_cmp_free_video_minutes', '每个视频初始长度不超过5分钟'),
    vip: tr('mm_cmp_vip_video_minutes', '每个视频长度不超过20分钟'),
  },
  {
    key: 'watermark',
    feature: tr('mm_cmp_watermark', '视频水印'),
    free: tr('mm_cmp_free_watermark', '视频默认携带水印'),
    vip: tr('mm_cmp_vip_watermark', '可自定义水印或删除水印'),
  },
  {
    key: 'storage',
    feature: tr('mm_cmp_storage', '个人视频总空间'),
    free: tr('mm_cmp_free_storage', '10G'),
    vip: tr('mm_cmp_vip_storage', '128G'),
  },
  {
    key: 'style',
    feature: tr('mm_cmp_style', '字幕与字体'),
    free: tr('mm_cmp_free_style', '基础字幕样式 / 基础字体'),
    vip: tr('mm_cmp_vip_style', '高级字幕样式 / 更多字体'),
  },
  {
    key: 'ai',
    feature: tr('mm_cmp_ai', 'AI辅助功能'),
    free: tr('mm_cmp_free_ai', '无AI辅助功能'),
    vip: tr('mm_cmp_vip_ai', 'AI辅助伴学'),
  },
])

const learningLangCode = computed(() => {
  const fromInject = languagePrefs?.learningLang?.value
  if (fromInject) return fromInject
  try {
    return localStorage.getItem('ll_learning_lang') || 'en'
  } catch {
    return 'en'
  }
})

const currentCurrencyCode = computed(() => {
  if (provider.value !== 'stripe') return 'CNY'
  return CURRENCY_BY_TGT_LANG[learningLangCode.value] || 'USD'
})

function formatPrice(amount, digits) {
  return Number(amount).toFixed(digits)
}

const planAvailabilityMap = computed(() => {
  const map = new Map()
  for (const p of plans.value || []) {
    map.set(p.code, p.available !== false)
  }
  return map
})

const displayPlans = computed(() => {
  const isStripe = provider.value === 'stripe'
  const currencyCode = isStripe ? currentCurrencyCode.value : 'CNY'
  const meta = CURRENCY_META[currencyCode] || CURRENCY_META.USD
  const isZhUi = String(uiLang.value || '').startsWith('zh')
  const prefix = isStripe
    ? (currencyCode === 'CNY' ? 'cn_' : 'intl_')
    : 'cn_'

  return BASE_PLAN_DEFS.map(def => {
    const checkoutCode = `${prefix}${def.codeSuffix}`
    const rawPrice = def.cnyPrice * meta.rate
    const displayPrice = formatPrice(rawPrice, meta.digits)
    const dailyAvg = formatPrice(rawPrice / def.days, meta.digits)
    const labelSet = PERIOD_NAME[def.period] || PERIOD_NAME.month
    const displayName = isZhUi ? labelSet.zh : labelSet.en
    const availableByStatus = planAvailabilityMap.value.has(checkoutCode)
      ? Boolean(planAvailabilityMap.value.get(checkoutCode))
      : true
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

watch(() => props.visible, async (v) => {
  if (!v) return
  try {
    const s = await apiFetch('/api/membership/status')
    status.value = s
    plans.value = s.plans || []
  } catch (e) {
    console.error(e)
  }
}, { immediate: true })

async function checkout(plan) {
  if (!plan?.available || loadingCode.value) return
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
    emit('refreshed')
    window.location.href = d.checkout_url
  } catch (e) {
    alert(e.message || tr('mm_checkout_failed', 'Failed to create payment'))
  } finally {
    loadingCode.value = ''
  }
}
</script>

<style scoped>
.mm-box {
  width: min(980px, calc(100vw - 24px));
  max-height: calc(100vh - 40px);
  overflow: auto;
  border-radius: 24px;
  background:
    radial-gradient(120% 120% at 0% 0%, rgba(11, 120, 209, 0.1), transparent 45%),
    radial-gradient(120% 120% at 100% 0%, rgba(242, 168, 44, 0.11), transparent 40%),
    linear-gradient(165deg, #ffffff 0%, #f8fbff 46%, #f4fff8 100%);
  border: 1px solid rgba(11,120,209,.2);
  box-shadow: 0 24px 90px rgba(15,23,42,.28);
  padding: 24px;
  position: relative;
}
.mm-head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.mm-logo { width: 46px; height: 46px; border-radius: 12px; box-shadow: 0 6px 22px rgba(16,185,129,.35); }
.mm-title {
  font-size: 22px;
  font-weight: 900;
  background: linear-gradient(118deg, #0d2f5a 0%, #0b78d1 56%, #f2a82c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.mm-sub { font-size: 12px; color: #475569; line-height: 1.6; }
.mm-status { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.tag { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }
.tag-ok { color: #065f46; background: rgba(16,185,129,.16); }
.tag-free { color: #92400e; background: rgba(245,158,11,.16); }
.mm-status-text { font-size: 12px; color: #475569; }
.mm-provider { display: flex; gap: 8px; margin-bottom: 12px; }
.pv-btn {
  border: 1px solid #dbeafe;
  background: #fff;
  color: #334155;
  border-radius: 10px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
}
.pv-btn.active { border-color: #6366f1; color: #4338ca; background: rgba(99,102,241,.08); }

.card-like {
  border: 1px solid rgba(11,120,209,.16);
  background: rgba(255,255,255,.7);
  border-radius: 14px;
  padding: 12px;
  margin-bottom: 14px;
}

.mm-sec-head {
  font-size: 14px;
  font-weight: 800;
  color: #0d4d80;
  margin-bottom: 8px;
}

.cmp-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.cmp-table th,
.cmp-table td {
  border: 1px solid rgba(148,163,184,.24);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}

.cmp-table th {
  background: rgba(11,120,209,.08);
  color: #0f172a;
  font-weight: 800;
}

.cmp-table td:nth-child(2) {
  background: rgba(245,158,11,.06);
}

.cmp-table td:nth-child(3) {
  background: rgba(16,185,129,.06);
}

.mm-pricing-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.mm-currency-hint {
  font-size: 12px;
  color: #475569;
}

.mm-plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.mm-plan {
  text-align: left;
  border: 1px solid rgba(11,120,209,.18);
  background: linear-gradient(150deg, #ffffff, #f8fbff);
  border-radius: 14px;
  padding: 12px;
  min-height: 138px;
  transition: .18s ease;
}
.mm-plan:hover:not(:disabled) { border-color: #6366f1; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(99,102,241,.15); }
.mm-plan:disabled { opacity: .6; cursor: not-allowed; }
.mm-plan-name { font-size: 13px; font-weight: 700; color: #0f172a; display: flex; align-items: center; gap: 6px; }
.trial-tag { font-size: 10px; color: #991b1b; background: rgba(239,68,68,.12); padding: 2px 5px; border-radius: 999px; }
.mm-plan-price { font-size: 24px; font-weight: 800; margin: 8px 0 3px; color: #111827; }
.mm-plan-meta { font-size: 11px; color: #64748b; }
.mm-plan-daily { margin-top: 8px; font-size: 12px; color: #0d4d80; font-weight: 700; }
.mm-plan-unavail { margin-top: 8px; font-size: 11px; color: #b45309; }

.mm-foot-note {
  display: grid;
  gap: 5px;
  font-size: 12px;
  color: #475569;
  background: rgba(255,255,255,.78);
  border: 1px solid rgba(11,120,209,.14);
  border-radius: 12px;
  padding: 10px;
}

@media (max-width: 760px) {
  .mm-pricing-head { flex-direction: column; align-items: flex-start; }
  .cmp-table th,
  .cmp-table td { padding: 8px; font-size: 11px; }
}
</style>
