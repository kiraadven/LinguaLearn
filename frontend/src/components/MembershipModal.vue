<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
      <div class="mm-box">
        <button class="modal-close" @click="$emit('close')">✕</button>
        <div class="mm-head">
          <img src="/premium-badge.svg" alt="Premium" class="mm-logo">
          <div>
            <div class="mm-title">{{ tr('mm_title', 'LinguaLearn Membership') }}</div>
            <div class="mm-sub">{{ tr('mm_sub', 'Unlock no default watermark, longer videos, unlimited generation, and premium badge') }}</div>
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
          <button :class="['pv-btn', {active: provider==='stripe'}]" @click="provider='stripe'">{{ tr('mm_stripe', 'Stripe') }}</button>
        </div>

        <div class="mm-plan-grid">
          <button
            v-for="p in plans"
            :key="p.code"
            class="mm-plan"
            :disabled="!p.available || loadingCode === p.code"
            @click="checkout(p)"
          >
            <div class="mm-plan-name">
              {{ localizedPlanLabel(p) }}
              <span v-if="p.trial_once" class="trial-tag">{{ tr('mm_trial_once', '1-time only') }}</span>
            </div>
            <div class="mm-plan-price">{{ p.currency === 'CNY' ? '¥' : '$' }}{{ p.price }}</div>
            <div class="mm-plan-meta">
              {{ p.auto_renew ? tr('mm_auto_renew', 'Auto renew') : tr('mm_one_time', 'One-time') }} · {{ localizedPeriod(p.period) }}
            </div>
            <div v-if="!p.available" class="mm-plan-unavail">{{ tr('mm_used', 'Used') }}</div>
          </button>
        </div>

        <div class="mm-features">
          <div>{{ tr('mm_feature_free', 'Free: up to 5 videos/day, max 5 minutes each, default LinguaLearn watermark cannot be removed.') }}</div>
          <div>{{ tr('mm_feature_member', 'Member: unlimited daily generation, max 30 minutes each, customizable/removable video and document watermark.') }}</div>
          <div>{{ tr('mm_feature_badge', 'Member exclusive: premium identity badge.') }}</div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { apiFetch } from '../composables/useApi.js'
import { useI18n } from '../i18n.js'
import { formatMembershipPeriod, formatMembershipPlanLabel } from '../composables/membershipLabels.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'refreshed'])

const status = ref(null)
const plans = ref([])
const provider = ref('alipay')
const loadingCode = ref('')
const { t, uiLang } = useI18n()

function tr(key, fallback = '') {
  return ((t.value?.[key]) ?? fallback) || key
}

function localizedPlanLabel(plan) {
  return formatMembershipPlanLabel(plan?.code, plan?.label, uiLang.value)
}

function localizedPeriod(period) {
  return formatMembershipPeriod(period, uiLang.value, period)
}

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
  loadingCode.value = plan.code
  try {
    const endpoint = provider.value === 'alipay'
      ? '/api/membership/checkout/alipay'
      : '/api/membership/checkout/stripe'
    const d = await apiFetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_code: plan.code }),
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
  width: min(860px, calc(100vw - 24px));
  max-height: calc(100vh - 40px);
  overflow: auto;
  border-radius: 20px;
  background: linear-gradient(165deg, #ffffff 0%, #f8fbff 46%, #f4fff8 100%);
  border: 1px solid rgba(99,102,241,.2);
  box-shadow: 0 24px 90px rgba(15,23,42,.28);
  padding: 22px;
  position: relative;
}
.mm-head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.mm-logo { width: 42px; height: 42px; border-radius: 12px; box-shadow: 0 6px 22px rgba(16,185,129,.35); }
.mm-title { font-size: 20px; font-weight: 800; color: #0f172a; }
.mm-sub { font-size: 12px; color: #475569; }
.mm-status { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
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
.mm-plan-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; margin-bottom: 12px; }
.mm-plan {
  text-align: left;
  border: 1px solid rgba(148,163,184,.28);
  background: #fff;
  border-radius: 14px;
  padding: 12px;
  min-height: 120px;
  transition: .18s ease;
}
.mm-plan:hover:not(:disabled) { border-color: #6366f1; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(99,102,241,.15); }
.mm-plan:disabled { opacity: .6; cursor: not-allowed; }
.mm-plan-name { font-size: 13px; font-weight: 700; color: #0f172a; display: flex; align-items: center; gap: 6px; }
.trial-tag { font-size: 10px; color: #991b1b; background: rgba(239,68,68,.12); padding: 2px 5px; border-radius: 999px; }
.mm-plan-price { font-size: 24px; font-weight: 800; margin: 8px 0 3px; color: #111827; }
.mm-plan-meta { font-size: 11px; color: #64748b; }
.mm-plan-unavail { margin-top: 8px; font-size: 11px; color: #b45309; }
.mm-features {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: #334155;
  background: #fff;
  border: 1px solid rgba(148,163,184,.24);
  border-radius: 12px;
  padding: 10px;
}
</style>
