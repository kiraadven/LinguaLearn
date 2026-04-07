<template>
  <div class="tutor-page page-inner">
    <div class="tp-glow tp-glow-a"></div>
    <div class="tp-glow tp-glow-b"></div>

    <section v-if="!isLoggedIn" class="panel empty">
      <div class="empty-icon">🔒</div>
      <p>{{ tr('create_login_required', 'Please log in first') }}</p>
      <button class="btn primary" @click="openAuth?.()">{{ tr('nav_login_register', 'Login / Register') }}</button>
    </section>

    <section v-else class="panel redirect-panel">
      <div class="empty-icon">🎬</div>
      <p>{{ tr('tutor_redirected_hint', '请从「我的视频」中选择一个视频，进入 AI 讲课。') }}</p>
      <button class="btn-primary" @click="$router.push('/results')">
        {{ tr('tutor_go_my_videos', '前往我的视频') }}
      </button>
    </section>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import { useAuth } from '../composables/useAuth.js'
import { useI18n } from '../i18n.js'

const { t } = useI18n()
const { isLoggedIn } = useAuth()
const openAuth = inject('openAuth', null)

function tr(key, fallback = '') {
  return t.value?.[key] ?? fallback
}
</script>

<style scoped>
.tp-glow {
  position: fixed;
  border-radius: 50%;
  filter: blur(90px);
  pointer-events: none;
  z-index: 0;
}
.tp-glow-a {
  width: 500px; height: 500px;
  top: -100px; left: -150px;
  background: radial-gradient(circle, rgba(11,120,209,0.15), transparent 70%);
  animation: tpDrift 15s ease-in-out infinite;
}
.tp-glow-b {
  width: 400px; height: 400px;
  bottom: 60px; right: -80px;
  background: radial-gradient(circle, rgba(242,168,44,0.13), transparent 70%);
  animation: tpDrift 19s ease-in-out infinite reverse;
}
@keyframes tpDrift {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(36px) scale(1.06); }
}

.tutor-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 60px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  position: relative;
}

.panel {
  border-radius: 20px;
  border: 1px solid rgba(11,120,209,.16);
  background: linear-gradient(165deg, rgba(255,255,255,.97), rgba(248,252,255,.92));
  box-shadow: 0 20px 48px rgba(13,59,102,.1);
  backdrop-filter: blur(8px);
  position: relative;
  z-index: 1;
}

.redirect-panel {
  padding: 48px 32px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.empty-icon { font-size: 52px; }

.redirect-panel p {
  color: var(--text2);
  font-size: 15px;
  line-height: 1.6;
  max-width: 340px;
}

.empty {
  padding: 40px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
</style>
