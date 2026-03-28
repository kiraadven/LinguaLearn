<template>
  <div class="profile-page page-inner">
    <div class="page-header">
      <h1>个人中心</h1>
      <p>管理账号信息和安全设置</p>
    </div>

    <div v-if="!isLoggedIn" class="empty-state">
      <div class="empty-icon">🔒</div>
      <p class="empty-title">请先登录</p>
      <button class="btn-primary" @click="openAuth()">登录 / 注册</button>
    </div>

    <div v-else class="profile-grid">
      <!-- Avatar card -->
      <div class="profile-card card" style="padding:36px 24px;text-align:center">
        <div class="avatar-section">
          <img v-if="user.avatar_url" :src="user.avatar_url" class="avatar-img" alt="头像">
          <div v-else class="avatar">{{ (user.name||user.email||'?')[0].toUpperCase() }}</div>
          <input ref="avatarInput" type="file" accept="image/*" style="display:none" @change="onAvatarSelect">
          <button class="btn-small" @click="$refs.avatarInput.click()" style="margin-top:8px;font-size:12px;padding:6px 12px">
            {{ avatarLoading ? '上传中...' : '更换头像' }}
          </button>
        </div>
        <div style="font-size:19px;font-weight:700;margin-bottom:4px">{{ user.name||'—' }}</div>
        <div style="font-size:13px;color:var(--text3);margin-bottom:16px">{{ user.email }}</div>
        <div v-if="membership?.tier==='member'" class="vip-chip">
          <img src="/premium-badge.svg" alt="vip" class="vip-chip-logo">
          尊贵会员
        </div>
        <div class="verified-badge">✓ 已验证账号</div>
        <div class="stat-grid">
          <div class="stat">
            <div class="stat-val">{{ jobCount }}</div>
            <div class="stat-lbl">已生成视频</div>
          </div>
          <div class="stat">
            <div class="stat-val">{{ joinDate }}</div>
            <div class="stat-lbl">注册时间</div>
          </div>
        </div>
      </div>

      <!-- Settings -->
      <div>
        <div class="card" style="padding:28px;margin-bottom:16px">
          <div class="section-title" style="font-size:15px;margin-bottom:20px">👤 个人信息</div>
          <label class="label">昵称</label>
          <input class="input" :value="user.name||''" placeholder="输入昵称" style="margin-bottom:12px" disabled>
          <label class="label">邮箱</label>
          <input class="input" :value="user.email" disabled style="margin-bottom:16px;opacity:.6">
          <button class="btn-ghost" style="font-size:13px;padding:8px 18px" @click="toast('昵称修改功能规划中','info')">
            保存昵称
          </button>
        </div>

        <div class="card" style="padding:28px;margin-bottom:16px">
          <div class="section-title" style="font-size:15px;margin-bottom:20px">📧 邮箱绑定</div>
          <div v-if="emailBound" style="color:var(--ok);font-size:14px;margin-bottom:12px">✓ 邮箱已绑定</div>
          <div v-else>
            <label class="label">新邮箱</label>
            <input class="input" v-model="newEmail" type="email" placeholder="输入新邮箱地址" style="margin-bottom:8px">
            <div style="display:flex;gap:8px;margin-bottom:8px">
              <button class="btn-ghost" style="flex:1;font-size:13px;padding:8px" :disabled="emailCodeLoading || !newEmail" @click="doSendEmailCode">
                {{ emailCodeLoading ? '发送中...' : emailCodeSent ? `重新发送 (${emailCodeCountdown}s)` : '发送验证码' }}
              </button>
            </div>
            <label class="label">验证码</label>
            <input class="input" v-model="emailCode" type="text" placeholder="输入验证码" style="margin-bottom:8px" :disabled="!emailCodeSent">
            <div v-if="emailMsg" :style="{color:emailOk?'var(--ok)':'var(--err)',fontSize:'13px',marginBottom:'12px'}">
              {{ emailMsg }}
            </div>
            <button class="btn-ghost" style="font-size:13px;padding:8px 18px" :disabled="emailLoading || !emailCodeSent" @click="doBindEmail">
              {{ emailLoading ? '绑定中...' : '确认绑定' }}
            </button>
          </div>
        </div>

        <div class="card" style="padding:28px;margin-bottom:16px">
          <div class="section-title" style="font-size:15px;margin-bottom:20px">👑 会员权益</div>
          <div v-if="membership?.tier==='member'" class="member-box">
            <div class="member-row"><span>套餐</span><strong>{{ membership.plan_name || membership.plan_code || '会员' }}</strong></div>
            <div class="member-row"><span>到期时间</span><strong>{{ fmtDateTime(membership.expires_at) }}</strong></div>
            <div class="member-row"><span>自动续费</span><strong>{{ membership.auto_renew ? '开启' : '关闭' }}</strong></div>
            <div class="member-row">
              <span>文稿水印</span>
              <label style="display:flex;align-items:center;gap:6px;font-size:13px">
                <input type="checkbox" v-model="docWatermarkEnabled">
                开启
              </label>
            </div>
            <label class="label">文稿水印文本</label>
            <input class="input" v-model="docWatermarkText" placeholder="LinguaLearn" :disabled="!docWatermarkEnabled" style="margin-bottom:10px">
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn-ghost" style="font-size:13px;padding:8px 16px" @click="saveMembershipPrefs">保存会员偏好</button>
              <button class="btn-ghost" style="font-size:13px;padding:8px 16px;color:var(--warn);border-color:rgba(245,158,11,.3)" @click="cancelAutoRenew">取消自动续费</button>
            </div>
          </div>
          <div v-else class="member-box">
            <div class="member-row"><span>状态</span><strong>非会员</strong></div>
            <div class="member-row"><span>每日生成</span><strong>最多 5 个视频</strong></div>
            <div class="member-row"><span>单视频时长</span><strong>最多 5 分钟</strong></div>
            <div class="member-row"><span>默认水印</span><strong>不可删除</strong></div>
            <button class="btn-primary" style="font-size:13px;padding:9px 16px;margin-top:8px" @click="openMembership()">开通会员</button>
          </div>
        </div>

        <div class="card" style="padding:28px;margin-bottom:16px">
          <div class="section-title" style="font-size:15px;margin-bottom:20px">🔒 修改密码</div>
          <label class="label">当前密码</label>
          <input class="input" v-model="oldPw" type="password" placeholder="当前密码" style="margin-bottom:12px">
          <label class="label">新密码</label>
          <input class="input" v-model="newPw" type="password" placeholder="新密码（至少6位）" style="margin-bottom:12px">
          <label class="label">确认新密码</label>
          <input class="input" v-model="newPw2" type="password" placeholder="确认新密码" style="margin-bottom:8px">
          <div v-if="pwMsg" :style="{color:pwOk?'var(--ok)':'var(--err)',fontSize:'13px',marginBottom:'12px'}">
            {{ pwMsg }}
          </div>
          <button class="btn-ghost" style="font-size:13px;padding:8px 18px" :disabled="pwLoading" @click="doChangePw">
            {{ pwLoading ? '更新中...' : '更新密码' }}
          </button>
        </div>

        <div class="card" style="padding:28px">
          <button class="logout-btn" @click="doLogout">退出登录</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue'
import { useAuth } from '../composables/useAuth.js'
import { apiFetch } from '../composables/useApi.js'

const { user, isLoggedIn, changePassword, logout, sendEmailCode, bindEmail, uploadAvatar, refreshMembership } = useAuth()
const openAuth = inject('openAuth')
const openMembership = inject('openMembership', () => {})
const toast    = inject('toast')

const jobCount = ref(0)
const joinDate = ref('—')
const oldPw = ref(''); const newPw = ref(''); const newPw2 = ref('')
const pwMsg = ref(''); const pwOk = ref(false); const pwLoading = ref(false)
const newEmail = ref('')
const emailCode = ref('')
const emailMsg = ref('')
const emailOk = ref(false)
const emailLoading = ref(false)
const emailCodeLoading = ref(false)
const emailCodeSent = ref(false)
const emailCodeCountdown = ref(0)
const emailBound = ref(false)
const avatarLoading = ref(false)
const avatarInput = ref(null)
const membership = ref(null)
const docWatermarkEnabled = ref(true)
const docWatermarkText = ref('LinguaLearn')

onMounted(async () => {
  if (!isLoggedIn.value) return
  try {
    membership.value = await refreshMembership()
  } catch {}
  try {
    const d = await apiFetch('/api/jobs')
    jobCount.value = (d.jobs||[]).length
  } catch {}
  if (user.value?.created_at) {
    const dt = new Date(user.value.created_at)
    joinDate.value = `${dt.getFullYear()}/${dt.getMonth()+1}`
  }
  emailBound.value = !!user.value?.email_bound
  if (membership.value) {
    docWatermarkEnabled.value = !!membership.value.doc_watermark_enabled
    docWatermarkText.value = membership.value.doc_watermark_text || 'LinguaLearn'
  }
})

async function onAvatarSelect(e) {
  const file = e.target.files?.[0]
  if (!file) return

  // 验证文件大小 (5MB)
  if (file.size > 5 * 1024 * 1024) {
    toast('文件大小不能超过 5MB', 'err')
    return
  }

  avatarLoading.value = true
  try {
    await uploadAvatar(file)
    toast('头像已更新', 'ok')
  } catch(e) {
    toast(e.message || '头像上传失败', 'err')
  } finally {
    avatarLoading.value = false
    if (avatarInput.value) avatarInput.value.value = ''
  }
}

async function doSendEmailCode() {
  if (!newEmail.value) {
    emailMsg.value = '请输入邮箱地址'
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newEmail.value)) {
    emailMsg.value = '邮箱格式错误'
    return
  }

  emailCodeLoading.value = true
  emailMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('email', newEmail.value)
    const res = await apiFetch('/api/auth/send-email-code', { method: 'POST', body: fd })

    // Auto-fill verification code in dev mode
    if (res.code) {
      emailCode.value = res.code
    }

    emailCodeSent.value = true
    emailCodeCountdown.value = 60
    const timer = setInterval(() => {
      emailCodeCountdown.value--
      if (emailCodeCountdown.value <= 0) {
        clearInterval(timer)
        emailCodeSent.value = false
      }
    }, 1000)
    emailMsg.value = '验证码已发送'
  } catch(e) {
    emailMsg.value = e.message || '验证码发送失败'
  } finally {
    emailCodeLoading.value = false
  }
}

async function doBindEmail() {
  emailMsg.value = ''
  emailOk.value = false
  if (!emailCode.value) {
    emailMsg.value = '请输入验证码'
    return
  }

  emailLoading.value = true
  try {
    await bindEmail(newEmail.value, emailCode.value)
    emailMsg.value = '邮箱已绑定'
    emailOk.value = true
    emailBound.value = true
    newEmail.value = ''
    emailCode.value = ''
    emailCodeSent.value = false
  } catch(e) {
    emailMsg.value = e.message || '邮箱绑定失败'
  } finally {
    emailLoading.value = false
  }
}

async function doChangePw() {
  pwMsg.value = ''; pwOk.value = false
  if (!oldPw.value || !newPw.value) { pwMsg.value = '请填写完整'; return }
  if (newPw.value !== newPw2.value) { pwMsg.value = '两次密码不一致'; return }
  if (newPw.value.length < 6) { pwMsg.value = '新密码至少6位'; return }
  pwLoading.value = true
  try {
    await changePassword(oldPw.value, newPw.value)
    pwMsg.value = '密码修改成功'; pwOk.value = true
    oldPw.value = ''; newPw.value = ''; newPw2.value = ''
  } catch(e) { pwMsg.value = e.message }
  finally { pwLoading.value = false }
}

function doLogout() {
  logout()
  toast('已退出登录', 'info')
  window.location.hash = '/'
}

async function saveMembershipPrefs() {
  if (membership.value?.tier !== 'member') return
  try {
    const d = await apiFetch('/api/membership/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        doc_watermark_enabled: docWatermarkEnabled.value,
        doc_watermark_text: docWatermarkText.value,
      }),
    })
    membership.value = d
    if (user.value) user.value.membership = d
    toast('会员偏好已保存', 'ok')
  } catch (e) {
    toast(e.message || '保存失败', 'err')
  }
}

async function cancelAutoRenew() {
  try {
    await apiFetch('/api/membership/cancel-auto-renew', { method: 'POST' })
    membership.value = await refreshMembership()
    toast('已取消自动续费', 'ok')
  } catch (e) {
    toast(e.message || '取消失败', 'err')
  }
}

function fmtDateTime(v) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}
</script>

<style scoped>
.profile-page { padding: 32px 24px 80px; max-width: 900px; margin: 0 auto; }
.page-header { margin-bottom: 32px; }
.page-header h1 { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 6px; }
.page-header p  { color: var(--text2); font-size: 14px; }
.empty-state { text-align:center;padding:80px 24px;display:flex;flex-direction:column;align-items:center;gap:12px; }
.empty-icon { font-size:64px; }
.empty-title { font-size:18px;font-weight:700; }

.profile-grid { display: grid; grid-template-columns: 240px 1fr; gap: 20px; align-items: start; }
@media (max-width: 640px) { .profile-grid { grid-template-columns: 1fr; } }

.avatar-section { margin-bottom: 16px; }
.avatar-img {
  width:76px;height:76px;border-radius:50%;
  object-fit:cover;
  margin:0 auto 8px;
  border:2px solid var(--border);
  display:block;
}
.vip-chip{
  display:inline-flex;align-items:center;gap:6px;
  border:1px solid rgba(16,185,129,.35);
  background:rgba(16,185,129,.09);
  color:#065f46;font-size:12px;font-weight:700;
  border-radius:999px;padding:4px 10px;margin-bottom:10px;
}
.vip-chip-logo{width:14px;height:14px;border-radius:4px;}
.member-box{
  border:1px solid rgba(148,163,184,.2);
  border-radius:12px;padding:12px;background:#fff;
}
.member-row{
  display:flex;justify-content:space-between;gap:10px;
  font-size:13px;color:var(--text2);margin-bottom:8px;
}
.member-row strong{color:var(--text);}
.avatar {
  width:76px;height:76px;border-radius:50%;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  display:flex;align-items:center;justify-content:center;
  font-size:30px;font-weight:800;margin:0 auto 8px;color:#fff;
  box-shadow:0 4px 20px rgba(167,139,250,0.3);
}
.verified-badge {
  display:inline-flex;align-items:center;gap:4px;padding:4px 13px;
  border-radius:12px;background:rgba(167,139,250,0.1);
  border:1px solid rgba(167,139,250,0.25);font-size:12px;color:var(--accent);font-weight:600;
}
.stat-grid { display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:20px; }
.stat { background:rgba(255,255,255,0.04);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center; }
.stat-val { font-size:22px;font-weight:800;color:var(--accent); }
.stat-lbl { font-size:11px;color:var(--text3);margin-top:2px; }

.btn-small {
  background:var(--accent);color:#fff;border:none;border-radius:6px;
  font-weight:600;cursor:pointer;transition:all .2s;
}
.btn-small:hover:not(:disabled) { background:var(--accent2); }
.btn-small:disabled { opacity:0.5;cursor:not-allowed; }

.logout-btn {
  width:100%;padding:12px;border-radius:8px;
  border:1.5px solid rgba(248,113,113,0.4);background:transparent;
  color:var(--err);font-size:14px;font-weight:600;transition:all .2s;
}
.logout-btn:hover { background:rgba(248,113,113,0.1); }
</style>
