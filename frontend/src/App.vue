<template>
  <!-- Aurora background -->
  <div class="aurora-bg">
    <div class="aurora-orb aurora-orb-1"></div>
    <div class="aurora-orb aurora-orb-2"></div>
    <div class="aurora-orb aurora-orb-3"></div>
  </div>

  <!-- Nav -->
  <nav class="nav">
    <span class="nav-logo" @click="$router.push('/')">🎓 LinguaLearn</span>
    <button class="nav-btn" :class="{active:$route.path==='/'}" @click="$router.push('/')">{{ t.nav_home }}</button>
    <button class="nav-btn" :class="{active:$route.path==='/create'}" @click="goCreate">{{ t.nav_create }}</button>
    <button class="nav-btn" :class="{active:$route.path==='/results'}" @click="$router.push('/results')">{{ t.nav_results }}</button>
    <button class="nav-btn" :class="{active:$route.path==='/quiz'}" @click="goQuiz">{{ t.nav_quiz }}</button>
    <div class="nav-spacer"></div>
    <div style="display:flex;align-items:center;gap:10px">
      <button class="nav-btn" @click="openLanguagePicker">{{ t.nav_language_settings }}</button>
      <button class="nav-vip-btn" @click="openMembership">
        <img src="/premium-badge.svg" alt="VIP" class="vip-mini">
        {{ isMember ? t.nav_manage_membership : t.nav_upgrade_membership }}
      </button>
      <template v-if="user">
        <div class="nav-avatar" @click="$router.push('/profile')" :title="user.name||user.email">
          <img v-if="user.avatar_url" :src="user.avatar_url" :alt="user.name||user.email" style="width:100%;height:100%;border-radius:50%;object-fit:cover">
          <span v-else>{{ (user.name||user.email||'?')[0].toUpperCase() }}</span>
          <img v-if="isMember" src="/premium-badge.svg" alt="VIP" class="avatar-vip-mark">
        </div>
      </template>
      <template v-else>
        <button class="nav-login-btn" @click="showAuth=true">{{ t.nav_login_register }}</button>
      </template>
    </div>
  </nav>

  <!-- Router view -->
  <div style="position:relative;z-index:1;padding-top:60px;min-height:100vh">
    <RouterView v-slot="{Component}">
      <Transition name="page" mode="out-in">
        <component :is="Component" @need-auth="showAuth=true" />
      </Transition>
    </RouterView>
  </div>

  <!-- Auth modal -->
  <Teleport to="body">
    <div v-if="showAuth" class="modal-overlay" @click.self="showAuth=false">
      <div class="modal-box">
        <button class="modal-close" @click="showAuth=false">✕</button>
        <div style="font-size:22px;font-weight:800;margin-bottom:4px;color:var(--text)">{{ t.auth_welcome }}</div>
        <div style="font-size:13px;color:var(--text3);margin-bottom:24px">{{ t.auth_login_or_register_desc }}</div>
        <div class="auth-tabs">
          <button :class="['auth-tab',{active:authTab==='login'}]" @click="authTab='login'">{{ t.auth_login }}</button>
          <button :class="['auth-tab',{active:authTab==='reg'}]" @click="authTab='reg'">{{ t.auth_register }}</button>
        </div>
        <!-- Login -->
        <div v-if="authTab==='login'">
          <label class="label">{{ t.auth_email }}</label>
          <input class="input" v-model="loginEmail" placeholder="you@example.com" type="email" style="margin-bottom:12px">
          <label class="label">{{ t.auth_password }}</label>
          <input class="input" v-model="loginPw" :placeholder="t.auth_password" type="password" style="margin-bottom:16px" @keyup.enter="doLogin">
          <div v-if="loginErr" style="font-size:13px;color:var(--err);margin-bottom:12px">{{ loginErr }}</div>
          <button class="btn-primary" style="width:100%" :disabled="loginLoading" @click="doLogin">
            {{ loginLoading ? t.auth_logging_in : t.auth_login_btn }}
          </button>
        </div>
        <!-- Register -->
        <div v-else>
          <label class="label">{{ t.auth_email }}</label>
          <input class="input" v-model="regEmail" placeholder="you@example.com" type="email" style="margin-bottom:12px">
          <label class="label">{{ t.auth_nickname }}</label>
          <input class="input" v-model="regName" :placeholder="t.auth_nickname" style="margin-bottom:12px">
          <label class="label">{{ t.auth_password }}</label>
          <input class="input" v-model="regPw" :placeholder="t.auth_password_hint" type="password" style="margin-bottom:12px">
          <label class="label">{{ t.auth_code }}</label>
          <div style="display:flex;gap:8px;margin-bottom:16px">
            <input class="input" v-model="regCode" :placeholder="t.auth_code_hint" style="flex:1;margin-bottom:0">
            <button class="btn-ghost" style="padding:10px 14px;white-space:nowrap" :disabled="codeSent" @click="doSendCode">
              {{ codeSent ? `${codeCountdown}s` : t.auth_get_code }}
            </button>
          </div>
          <div v-if="regErr" style="font-size:13px;color:var(--err);margin-bottom:12px">{{ regErr }}</div>
          <button class="btn-primary" style="width:100%" :disabled="regLoading" @click="doRegister">
            {{ regLoading ? t.auth_registering : t.auth_create_account }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Initial language setup -->
  <Teleport to="body">
    <div v-if="showLanguagePicker" class="modal-overlay">
      <div class="modal-box">
        <button v-if="hasSavedLanguagePrefs" class="modal-close" @click="showLanguagePicker=false">✕</button>
        <div style="font-size:22px;font-weight:800;margin-bottom:6px;color:var(--text)">{{ t.lang_pref_title }}</div>
        <div style="font-size:13px;color:var(--text3);margin-bottom:20px">{{ t.lang_pref_desc }}</div>

        <label class="label">{{ t.lang_pref_native }}</label>
        <select class="input" v-model="familiarLang" style="margin-bottom:14px">
          <option v-for="lang in familiarLanguageOptions" :key="`familiar-${lang.code}`" :value="lang.code">
            {{ lang.flag }} {{ lang.native_name }}
          </option>
        </select>

        <label class="label">{{ t.lang_pref_learning }}</label>
        <select class="input" v-model="learningLang" style="margin-bottom:16px">
          <option v-for="lang in learningLanguageOptions" :key="`learning-${lang.code}`" :value="lang.code">
            {{ lang.flag }} {{ lang.native_name }}
          </option>
        </select>

        <div v-if="languagePrefError" style="font-size:13px;color:var(--err);margin-bottom:12px">{{ languagePrefError }}</div>
        <button class="btn-primary" style="width:100%" @click="saveLanguagePreferences">
          {{ t.lang_pref_confirm }}
        </button>
      </div>
    </div>
  </Teleport>

  <!-- Membership modal -->
  <MembershipModal
    :visible="showMembership"
    @close="showMembership=false"
    @refreshed="refreshMembershipSafe"
  />

  <!-- Toasts -->
  <Teleport to="body">
    <div class="toasts">
      <div v-for="t in toasts" :key="t.id" :class="['toast', t.type]">{{ t.msg }}</div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, provide, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from './composables/useAuth.js'
import { apiFetch } from './composables/useApi.js'
import { useI18n } from './i18n.js'
import { useToast } from './composables/useToast.js'
import MembershipModal from './components/MembershipModal.vue'

const router = useRouter()
const { user, isLoggedIn, checkAuth, login, register, sendCode, refreshMembership } = useAuth()
const { toasts, toast } = useToast()
const { uiLang, t, setLang, SUPPORTED_LANGS } = useI18n()

const FALLBACK_LANGS = [
  { code: 'en', native_name: 'English', flag: '🇺🇸' },
  { code: 'zh-Hans', native_name: '中文（简体）', flag: '🇨🇳' },
  { code: 'zh-Hant', native_name: '中文（繁體）', flag: '🇭🇰' },
  { code: 'ja', native_name: '日本語', flag: '🇯🇵' },
  { code: 'ko', native_name: '한국어', flag: '🇰🇷' },
  { code: 'de', native_name: 'Deutsch', flag: '🇩🇪' },
  { code: 'fr', native_name: 'Français', flag: '🇫🇷' },
  { code: 'es', native_name: 'Español', flag: '🇪🇸' },
  { code: 'ru', native_name: 'Русский', flag: '🇷🇺' },
]

const showAuth = ref(false)
const showMembership = ref(false)
const authTab  = ref('login')
const isMember = ref(false)
const languageOptions = ref(FALLBACK_LANGS)
const showLanguagePicker = ref(false)
const hasSavedLanguagePrefs = ref(false)
const familiarLang = ref('zh-Hans')
const learningLang = ref('en')
const languagePrefError = ref('')

const familiarLanguageOptions = computed(() =>
  languageOptions.value.filter(lang => SUPPORTED_LANGS.includes(lang.code))
)

const learningLanguageOptions = computed(() => languageOptions.value)

function tr(key, fallback = '') {
  return ((t.value?.[key]) ?? fallback) || key
}

function detectPreferredLanguage() {
  if (typeof navigator === 'undefined') return 'zh-Hans'
  const candidates = [navigator.language, ...(navigator.languages || [])]
  for (const candidate of candidates) {
    const raw = String(candidate || '').toLowerCase()
    if (raw.startsWith('zh')) {
      if (raw.includes('tw') || raw.includes('hk') || raw.includes('mo') || raw.includes('hant')) {
        return 'zh-Hant'
      }
      return 'zh-Hans'
    }
    const code = raw.split('-')[0]
    if (SUPPORTED_LANGS.includes(code)) return code
  }
  return 'zh-Hans'
}

function defaultLearningLanguage(familiar) {
  return familiar === 'en' ? 'zh-Hans' : 'en'
}

function getLearningLanguageSet() {
  const byApi = languageOptions.value.map(item => item.code).filter(Boolean)
  const byFallback = FALLBACK_LANGS.map(item => item.code)
  return new Set([...byFallback, ...byApi])
}

async function loadLanguageOptions() {
  try {
    const data = await apiFetch('/api/languages')
    if (Array.isArray(data.languages) && data.languages.length) {
      languageOptions.value = data.languages
    }
  } catch {}
}

function initLanguagePreferences() {
  const storedFamiliar = localStorage.getItem('ll_familiar_lang')
  const storedLearning = localStorage.getItem('ll_learning_lang')
  const familiarValid = storedFamiliar && SUPPORTED_LANGS.includes(storedFamiliar)
  const learningValid = storedLearning && getLearningLanguageSet().has(storedLearning)

  familiarLang.value = familiarValid ? storedFamiliar : detectPreferredLanguage()
  learningLang.value = learningValid ? storedLearning : defaultLearningLanguage(familiarLang.value)
  if (learningLang.value === familiarLang.value) {
    learningLang.value = defaultLearningLanguage(familiarLang.value)
  }

  setLang(familiarLang.value)
  hasSavedLanguagePrefs.value = Boolean(familiarValid && learningValid && storedFamiliar !== storedLearning)
  showLanguagePicker.value = !hasSavedLanguagePrefs.value
}

function saveLanguagePreferences() {
  languagePrefError.value = ''
  if (familiarLang.value === learningLang.value) {
    languagePrefError.value = tr('lang_pref_error_same', 'These two languages must be different.')
    return
  }
  localStorage.setItem('ll_familiar_lang', familiarLang.value)
  localStorage.setItem('ll_learning_lang', learningLang.value)
  setLang(familiarLang.value)
  hasSavedLanguagePrefs.value = true
  showLanguagePicker.value = false
}

function openLanguagePicker() {
  showLanguagePicker.value = true
}

provide('auth',  { user, isLoggedIn, checkAuth })
provide('toast', toast)
provide('languagePrefs', { familiarLang, learningLang })
provide('openAuth', () => { showAuth.value = true })
provide('openMembership', () => {
  if (!isLoggedIn.value) { showAuth.value = true; return }
  showMembership.value = true
})

onMounted(async () => {
  await loadLanguageOptions()
  initLanguagePreferences()
  await checkAuth()
  isMember.value = user.value?.membership?.tier === 'member'
  if (location.hash.includes('membership=success')) {
    try {
      await refreshMembership()
      toast(tr('payment_success_refreshed', 'Payment successful, membership refreshed'), 'ok')
    } catch {}
  }
})
watch(user, () => {
  isMember.value = user.value?.membership?.tier === 'member'
}, { deep: true })
watch(uiLang, (lang) => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('lang', lang)
  }
}, { immediate: true })
watch(familiarLang, () => {
  languagePrefError.value = ''
})
watch(learningLang, () => {
  languagePrefError.value = ''
})

// Login state
const loginEmail = ref(''); const loginPw = ref('')
const loginErr   = ref(''); const loginLoading = ref(false)

async function doLogin() {
  loginErr.value = ''
  if (!loginEmail.value || !loginPw.value) { loginErr.value = tr('auth_fill_email_password', 'Please enter email and password'); return }
  loginLoading.value = true
  try {
    await login(loginEmail.value, loginPw.value)
    isMember.value = user.value?.membership?.tier === 'member'
    showAuth.value = false
    toast(tr('auth_login_success', 'Logged in successfully 🎉'), 'ok')
  } catch(e) { loginErr.value = e.message }
  finally { loginLoading.value = false }
}

// Register state
const regEmail = ref(''); const regName = ref(''); const regPw = ref(''); const regCode = ref('')
const regErr = ref(''); const regLoading = ref(false)
const codeSent = ref(false); const codeCountdown = ref(60)

async function doSendCode() {
  if (!regEmail.value) { regErr.value = tr('auth_fill_email_first', 'Please enter email first'); return }
  try {
    await sendCode(regEmail.value)
    codeSent.value = true
    codeCountdown.value = 60
    const iv = setInterval(() => {
      codeCountdown.value--
      if (codeCountdown.value <= 0) { clearInterval(iv); codeSent.value = false }
    }, 1000)
    toast(tr('auth_code_sent_ok', 'Verification code sent'), 'ok')
  } catch(e) { regErr.value = e.message }
}

async function doRegister() {
  regErr.value = ''
  if (!regEmail.value || !regName.value || !regPw.value || !regCode.value) {
    regErr.value = tr('auth_fill_email_password', 'Please fill all required fields'); return
  }
  regLoading.value = true
  try {
    await register(regEmail.value, regName.value, regPw.value, regCode.value)
    isMember.value = user.value?.membership?.tier === 'member'
    showAuth.value = false
    toast(tr('auth_register_success', 'Registration successful 🎉'), 'ok')
  } catch(e) { regErr.value = e.message }
  finally { regLoading.value = false }
}

function goCreate() {
  if (!isLoggedIn.value) { showAuth.value = true; return }
  router.push('/create')
}

function goQuiz() {
  if (!isLoggedIn.value) { showAuth.value = true; return }
  router.push('/quiz')
}

function openMembership() {
  if (!isLoggedIn.value) { showAuth.value = true; return }
  showMembership.value = true
}

async function refreshMembershipSafe() {
  try {
    await refreshMembership()
    isMember.value = user.value?.membership?.tier === 'member'
  } catch {}
}
</script>

<style scoped>
.nav-avatar {
  width:34px;height:34px;border-radius:50%;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:700;cursor:pointer;color:#fff;
  box-shadow:0 2px 12px rgba(167,139,250,0.35);transition:all .2s;
  position: relative;
}
.nav-avatar:hover{transform:scale(1.08);}
.nav-login-btn {
  padding:8px 18px;border-radius:20px;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  color:#fff;font-size:13px;font-weight:600;
  transition:all .2s;box-shadow:0 2px 12px rgba(167,139,250,0.25);
}
.nav-login-btn:hover{transform:translateY(-1px);box-shadow:0 4px 20px rgba(167,139,250,0.45);}
.nav-vip-btn{
  display:flex;align-items:center;gap:6px;
  padding:7px 12px;border-radius:999px;
  border:1px solid rgba(16,185,129,.35);
  background:linear-gradient(135deg, rgba(16,185,129,.13), rgba(14,165,233,.1));
  color:#065f46;font-size:12px;font-weight:700;
}
.vip-mini{width:16px;height:16px;border-radius:4px;}
.avatar-vip-mark{
  position:absolute;right:-6px;bottom:-6px;
  width:15px;height:15px;border-radius:50%;
  box-shadow:0 2px 8px rgba(15,23,42,.22);
  background:#fff;
}

.auth-tabs{display:flex;gap:4px;border-bottom:1px solid var(--border);margin-bottom:20px;}
.auth-tab{flex:1;padding:9px;text-align:center;font-size:13px;font-weight:600;color:var(--text3);
  border-bottom:2px solid transparent;margin-bottom:-1px;cursor:pointer;transition:all .2s;background:transparent;}
.auth-tab.active{color:var(--accent);border-bottom-color:var(--accent);}

.page-enter-active,.page-leave-active{transition:all .25s ease;}
.page-enter-from{opacity:0;transform:translateY(10px);}
.page-leave-to{opacity:0;transform:translateY(-10px);}
</style>
