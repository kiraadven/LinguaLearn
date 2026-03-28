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
    <button class="nav-btn" :class="{active:$route.path==='/'}" @click="$router.push('/')">首页</button>
    <button class="nav-btn" :class="{active:$route.path==='/create'}" @click="goCreate">生成视频</button>
    <button class="nav-btn" :class="{active:$route.path==='/results'}" @click="$router.push('/results')">学习结果</button>
    <button class="nav-btn" :class="{active:$route.path==='/quiz'}" @click="goQuiz">成果自测</button>
    <div class="nav-spacer"></div>
    <div style="display:flex;align-items:center;gap:10px">
      <button class="nav-vip-btn" @click="openMembership">
        <img src="/premium-badge.svg" alt="VIP" class="vip-mini">
        会员
      </button>
      <template v-if="user">
        <div class="nav-avatar" @click="$router.push('/profile')" :title="user.name||user.email">
          <img v-if="user.avatar_url" :src="user.avatar_url" :alt="user.name||user.email" style="width:100%;height:100%;border-radius:50%;object-fit:cover">
          <span v-else>{{ (user.name||user.email||'?')[0].toUpperCase() }}</span>
          <img v-if="isMember" src="/premium-badge.svg" alt="VIP" class="avatar-vip-mark">
        </div>
      </template>
      <template v-else>
        <button class="nav-login-btn" @click="showAuth=true">登录 / 注册</button>
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
        <div style="font-size:22px;font-weight:800;margin-bottom:4px;color:var(--text)">欢迎回来</div>
        <div style="font-size:13px;color:var(--text3);margin-bottom:24px">登录或注册你的账号</div>
        <div class="auth-tabs">
          <button :class="['auth-tab',{active:authTab==='login'}]" @click="authTab='login'">登录</button>
          <button :class="['auth-tab',{active:authTab==='reg'}]" @click="authTab='reg'">注册</button>
        </div>
        <!-- Login -->
        <div v-if="authTab==='login'">
          <label class="label">邮箱</label>
          <input class="input" v-model="loginEmail" placeholder="you@example.com" type="email" style="margin-bottom:12px">
          <label class="label">密码</label>
          <input class="input" v-model="loginPw" placeholder="密码" type="password" style="margin-bottom:16px" @keyup.enter="doLogin">
          <div v-if="loginErr" style="font-size:13px;color:var(--err);margin-bottom:12px">{{ loginErr }}</div>
          <button class="btn-primary" style="width:100%" :disabled="loginLoading" @click="doLogin">
            {{ loginLoading ? '登录中...' : '登录' }}
          </button>
        </div>
        <!-- Register -->
        <div v-else>
          <label class="label">邮箱</label>
          <input class="input" v-model="regEmail" placeholder="you@example.com" type="email" style="margin-bottom:12px">
          <label class="label">昵称</label>
          <input class="input" v-model="regName" placeholder="你的昵称" style="margin-bottom:12px">
          <label class="label">密码</label>
          <input class="input" v-model="regPw" placeholder="至少6位" type="password" style="margin-bottom:12px">
          <label class="label">验证码</label>
          <div style="display:flex;gap:8px;margin-bottom:16px">
            <input class="input" v-model="regCode" placeholder="6位验证码" style="flex:1;margin-bottom:0">
            <button class="btn-ghost" style="padding:10px 14px;white-space:nowrap" :disabled="codeSent" @click="doSendCode">
              {{ codeSent ? `${codeCountdown}s` : '获取验证码' }}
            </button>
          </div>
          <div v-if="regErr" style="font-size:13px;color:var(--err);margin-bottom:12px">{{ regErr }}</div>
          <button class="btn-primary" style="width:100%" :disabled="regLoading" @click="doRegister">
            {{ regLoading ? '注册中...' : '创建账号' }}
          </button>
        </div>
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
import { ref, provide, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from './composables/useAuth.js'
import { useToast } from './composables/useToast.js'
import MembershipModal from './components/MembershipModal.vue'

const router = useRouter()
const { user, isLoggedIn, checkAuth, login, register, sendCode, refreshMembership } = useAuth()
const { toasts, toast } = useToast()

const showAuth = ref(false)
const showMembership = ref(false)
const authTab  = ref('login')
const isMember = ref(false)

provide('auth',  { user, isLoggedIn, checkAuth })
provide('toast', toast)
provide('openAuth', () => { showAuth.value = true })
provide('openMembership', () => {
  if (!isLoggedIn.value) { showAuth.value = true; return }
  showMembership.value = true
})

onMounted(async () => {
  await checkAuth()
  isMember.value = user.value?.membership?.tier === 'member'
  if (location.hash.includes('membership=success')) {
    try {
      await refreshMembership()
      toast('支付成功，会员状态已刷新', 'ok')
    } catch {}
  }
})
watch(user, () => {
  isMember.value = user.value?.membership?.tier === 'member'
}, { deep: true })

// Login state
const loginEmail = ref(''); const loginPw = ref('')
const loginErr   = ref(''); const loginLoading = ref(false)

async function doLogin() {
  loginErr.value = ''
  if (!loginEmail.value || !loginPw.value) { loginErr.value = '请填写邮箱和密码'; return }
  loginLoading.value = true
  try {
    await login(loginEmail.value, loginPw.value)
    isMember.value = user.value?.membership?.tier === 'member'
    showAuth.value = false
    toast('登录成功 🎉', 'ok')
  } catch(e) { loginErr.value = e.message }
  finally { loginLoading.value = false }
}

// Register state
const regEmail = ref(''); const regName = ref(''); const regPw = ref(''); const regCode = ref('')
const regErr = ref(''); const regLoading = ref(false)
const codeSent = ref(false); const codeCountdown = ref(60)

async function doSendCode() {
  if (!regEmail.value) { regErr.value = '请先输入邮箱'; return }
  try {
    await sendCode(regEmail.value)
    codeSent.value = true
    codeCountdown.value = 60
    const iv = setInterval(() => {
      codeCountdown.value--
      if (codeCountdown.value <= 0) { clearInterval(iv); codeSent.value = false }
    }, 1000)
    toast('验证码已发送', 'ok')
  } catch(e) { regErr.value = e.message }
}

async function doRegister() {
  regErr.value = ''
  if (!regEmail.value || !regName.value || !regPw.value || !regCode.value) {
    regErr.value = '请填写所有字段'; return
  }
  regLoading.value = true
  try {
    await register(regEmail.value, regName.value, regPw.value, regCode.value)
    isMember.value = user.value?.membership?.tier === 'member'
    showAuth.value = false
    toast('注册成功！欢迎 🎉', 'ok')
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
