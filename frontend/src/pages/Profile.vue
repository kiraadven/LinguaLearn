<template>
  <div class="profile-page page-inner">
    <div class="page-header">
      <h1>{{ tr('profile_center_title', t.profile_title) }}</h1>
      <p>{{ tr('profile_center_subtitle', 'Manage account info and security settings') }}</p>
    </div>

    <div v-if="!isLoggedIn" class="empty-state">
      <div class="empty-icon">🔒</div>
      <p class="empty-title">{{ tr('create_login_required', 'Please log in first') }}</p>
      <button class="btn-primary" @click="openAuth()">{{ tr('nav_login_register', 'Login / Register') }}</button>
    </div>

    <div v-else class="profile-grid">
      <!-- Avatar card -->
      <div class="profile-card card" style="padding:36px 24px;text-align:center">
        <div class="avatar-section">
          <img v-if="user.avatar_url" :src="user.avatar_url" class="avatar-img" :alt="tr('profile_avatar', 'Avatar')">
          <div v-else class="avatar">{{ (user.name||user.email||'?')[0].toUpperCase() }}</div>
          <input ref="avatarInput" type="file" accept="image/*" style="display:none" @change="onAvatarSelect">
          <button class="btn-small" @click="$refs.avatarInput.click()" style="margin-top:8px;font-size:12px;padding:6px 12px">
            {{ avatarLoading ? tr('profile_uploading', 'Uploading...') : tr('profile_change_avatar', 'Change Avatar') }}
          </button>
        </div>
        <div style="font-size:19px;font-weight:700;margin-bottom:4px">{{ user.name||'—' }}</div>
        <div style="font-size:13px;color:var(--text3);margin-bottom:16px">{{ user.email }}</div>
        <div v-if="membership?.tier==='member'" class="vip-chip">
          <img src="/premium-badge.svg" alt="vip" class="vip-chip-logo">
          {{ tr('profile_premium_member', 'Premium Member') }}
        </div>
        <div class="verified-badge">✓ {{ tr('profile_verified_account', 'Verified Account') }}</div>
        <div class="stat-grid">
          <div class="stat">
            <div class="stat-val">{{ jobCount }}</div>
            <div class="stat-lbl">{{ tr('profile_generated_videos', 'Generated Videos') }}</div>
          </div>
          <div class="stat">
            <div class="stat-val">{{ joinDate }}</div>
            <div class="stat-lbl">{{ tr('profile_join_time', 'Join Date') }}</div>
          </div>
        </div>
      </div>

      <!-- Settings -->
      <div>
        <div class="card" style="padding:28px;margin-bottom:16px">
          <div class="section-title" style="font-size:15px;margin-bottom:20px">👤 {{ t.profile_personal_info }}</div>
          <label class="label">{{ t.auth_nickname }}</label>
          <input class="input" :value="user.name||''" :placeholder="t.auth_nickname" style="margin-bottom:12px" disabled>
          <label class="label">{{ t.auth_email }}</label>
          <input class="input" :value="user.email" disabled style="margin-bottom:16px;opacity:.6">
          <button class="btn-ghost" style="font-size:13px;padding:8px 18px" @click="toast(tr('profile_nickname_todo', 'Nickname editing is coming soon'),'info')">
            {{ tr('profile_save_nickname', 'Save Nickname') }}
          </button>
        </div>

        <div class="card" style="padding:28px;margin-bottom:16px">
          <div class="section-title" style="font-size:15px;margin-bottom:20px">📧 {{ t.profile_bind_email }}</div>
          <div v-if="emailBound" style="color:var(--ok);font-size:14px;margin-bottom:12px">✓ {{ t.profile_email_bound }}</div>
          <div v-else>
            <label class="label">{{ t.profile_bind_new_email }}</label>
            <input class="input" v-model="newEmail" type="email" :placeholder="t.profile_email_input" style="margin-bottom:8px">
            <div style="display:flex;gap:8px;margin-bottom:8px">
              <button class="btn-ghost" style="flex:1;font-size:13px;padding:8px" :disabled="emailCodeLoading || !newEmail" @click="doSendEmailCode">
                {{ emailCodeLoading ? tr('profile_sending', 'Sending...') : emailCodeSent ? `${tr('profile_resend', 'Resend')} (${emailCodeCountdown}s)` : t.profile_send_code }}
              </button>
            </div>
            <label class="label">{{ t.profile_enter_code }}</label>
            <input class="input" v-model="emailCode" type="text" :placeholder="t.profile_enter_code" style="margin-bottom:8px" :disabled="!emailCodeSent">
            <div v-if="emailMsg" :style="{color:emailOk?'var(--ok)':'var(--err)',fontSize:'13px',marginBottom:'12px'}">
              {{ emailMsg }}
            </div>
            <button class="btn-ghost" style="font-size:13px;padding:8px 18px" :disabled="emailLoading || !emailCodeSent" @click="doBindEmail">
              {{ emailLoading ? tr('profile_binding', 'Binding...') : t.profile_confirm_bind }}
            </button>
          </div>
        </div>

        <div class="card" style="padding:28px;margin-bottom:16px">
          <div class="section-title" style="font-size:15px;margin-bottom:20px">👑 {{ tr('profile_membership', 'Membership') }}</div>
          <div v-if="membership?.tier==='member'" class="member-box">
            <div class="member-row"><span>{{ tr('profile_plan', 'Plan') }}</span><strong>{{ membership.plan_name || membership.plan_code || tr('profile_member', 'Member') }}</strong></div>
            <div class="member-row"><span>{{ tr('profile_expires_at', 'Expires At') }}</span><strong>{{ fmtDateTime(membership.expires_at) }}</strong></div>
            <div class="member-row"><span>{{ tr('profile_auto_renew', 'Auto Renew') }}</span><strong>{{ membership.auto_renew ? tr('profile_on', 'On') : tr('profile_off', 'Off') }}</strong></div>
            <div class="member-row">
              <span>{{ tr('profile_doc_watermark', 'Document Watermark') }}</span>
              <label style="display:flex;align-items:center;gap:6px;font-size:13px">
                <input type="checkbox" v-model="docWatermarkEnabled">
                {{ tr('profile_on', 'On') }}
              </label>
            </div>
            <label class="label">{{ tr('profile_doc_watermark_text', 'Document Watermark Text') }}</label>
            <input class="input" v-model="docWatermarkText" placeholder="LinguaLearn" :disabled="!docWatermarkEnabled" style="margin-bottom:10px">
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn-ghost" style="font-size:13px;padding:8px 16px" @click="saveMembershipPrefs">{{ tr('profile_save_membership_prefs', 'Save Membership Preferences') }}</button>
              <button class="btn-ghost" style="font-size:13px;padding:8px 16px;color:var(--warn);border-color:rgba(245,158,11,.3)" @click="cancelAutoRenew">{{ tr('profile_cancel_auto_renew', 'Cancel Auto Renew') }}</button>
            </div>
          </div>
          <div v-else class="member-box">
            <div class="member-row"><span>{{ tr('profile_status', 'Status') }}</span><strong>{{ tr('profile_non_member', 'Free') }}</strong></div>
            <div class="member-row"><span>{{ tr('profile_daily_generation', 'Daily Limit') }}</span><strong>{{ tr('profile_daily_limit_text', 'Up to 5 videos') }}</strong></div>
            <div class="member-row"><span>{{ tr('profile_video_duration', 'Single Video Duration') }}</span><strong>{{ tr('profile_video_duration_text', 'Up to 5 minutes') }}</strong></div>
            <div class="member-row"><span>{{ tr('profile_default_watermark', 'Default Watermark') }}</span><strong>{{ tr('profile_watermark_not_removable', 'Not removable') }}</strong></div>
            <button class="btn-primary" style="font-size:13px;padding:9px 16px;margin-top:8px" @click="openMembership()">{{ tr('nav_upgrade_membership', 'Upgrade Membership') }}</button>
          </div>
        </div>

        <div class="card" style="padding:28px;margin-bottom:16px">
          <div class="section-title" style="font-size:15px;margin-bottom:20px">🔒 {{ t.profile_change_password }}</div>
          <label class="label">{{ tr('profile_current_password', 'Current Password') }}</label>
          <input class="input" v-model="oldPw" type="password" :placeholder="tr('profile_current_password', 'Current Password')" style="margin-bottom:12px">
          <label class="label">{{ tr('profile_new_password', 'New Password') }}</label>
          <input class="input" v-model="newPw" type="password" :placeholder="tr('profile_new_password_hint', 'New password (min 6 chars)')" style="margin-bottom:12px">
          <label class="label">{{ tr('profile_confirm_new_password', 'Confirm New Password') }}</label>
          <input class="input" v-model="newPw2" type="password" :placeholder="tr('profile_confirm_new_password', 'Confirm New Password')" style="margin-bottom:8px">
          <div v-if="pwMsg" :style="{color:pwOk?'var(--ok)':'var(--err)',fontSize:'13px',marginBottom:'12px'}">
            {{ pwMsg }}
          </div>
          <button class="btn-ghost" style="font-size:13px;padding:8px 18px" :disabled="pwLoading" @click="doChangePw">
            {{ pwLoading ? tr('profile_updating', 'Updating...') : tr('profile_update_password', 'Update Password') }}
          </button>
        </div>

        <div class="card" style="padding:28px">
          <button class="logout-btn" @click="doLogout">{{ t.profile_logout }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue'
import { useAuth } from '../composables/useAuth.js'
import { apiFetch } from '../composables/useApi.js'
import { useI18n } from '../i18n.js'

const { user, isLoggedIn, changePassword, logout, sendEmailCode, bindEmail, uploadAvatar, refreshMembership } = useAuth()
const openAuth = inject('openAuth')
const openMembership = inject('openMembership', () => {})
const toast    = inject('toast')
const { t } = useI18n()

function tr(key, fallback = '') {
  return t.value?.[key] || fallback || key
}

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
    toast(tr('profile_file_size_limit', 'File size cannot exceed 5MB'), 'err')
    return
  }

  avatarLoading.value = true
  try {
    await uploadAvatar(file)
    toast(tr('profile_avatar_updated', 'Avatar updated'), 'ok')
  } catch(e) {
    toast(e.message || t.value.profile_upload_failed, 'err')
  } finally {
    avatarLoading.value = false
    if (avatarInput.value) avatarInput.value.value = ''
  }
}

async function doSendEmailCode() {
  if (!newEmail.value) {
    emailMsg.value = tr('profile_email_required', 'Please enter email address')
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newEmail.value)) {
    emailMsg.value = tr('profile_email_invalid', 'Invalid email format')
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
    emailMsg.value = t.value.profile_email_sent
  } catch(e) {
    emailMsg.value = e.message || tr('profile_code_send_failed', 'Failed to send verification code')
  } finally {
    emailCodeLoading.value = false
  }
}

async function doBindEmail() {
  emailMsg.value = ''
  emailOk.value = false
  if (!emailCode.value) {
    emailMsg.value = tr('profile_code_required', 'Please enter verification code')
    return
  }

  emailLoading.value = true
  try {
    await bindEmail(newEmail.value, emailCode.value)
    emailMsg.value = t.value.profile_bind_success
    emailOk.value = true
    emailBound.value = true
    newEmail.value = ''
    emailCode.value = ''
    emailCodeSent.value = false
  } catch(e) {
    emailMsg.value = e.message || t.value.profile_bind_failed
  } finally {
    emailLoading.value = false
  }
}

async function doChangePw() {
  pwMsg.value = ''; pwOk.value = false
  if (!oldPw.value || !newPw.value) { pwMsg.value = tr('profile_fill_all_fields', 'Please fill all fields'); return }
  if (newPw.value !== newPw2.value) { pwMsg.value = tr('profile_password_mismatch', 'Passwords do not match'); return }
  if (newPw.value.length < 6) { pwMsg.value = tr('profile_password_min_length', 'New password must be at least 6 characters'); return }
  pwLoading.value = true
  try {
    await changePassword(oldPw.value, newPw.value)
    pwMsg.value = tr('profile_password_updated', 'Password updated successfully'); pwOk.value = true
    oldPw.value = ''; newPw.value = ''; newPw2.value = ''
  } catch(e) { pwMsg.value = e.message }
  finally { pwLoading.value = false }
}

function doLogout() {
  logout()
  toast(tr('profile_logged_out', 'Logged out'), 'info')
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
    toast(tr('profile_membership_prefs_saved', 'Membership preferences saved'), 'ok')
  } catch (e) {
    toast(e.message || tr('profile_save_failed', 'Save failed'), 'err')
  }
}

async function cancelAutoRenew() {
  try {
    await apiFetch('/api/membership/cancel-auto-renew', { method: 'POST' })
    membership.value = await refreshMembership()
    toast(tr('profile_auto_renew_cancelled', 'Auto-renew cancelled'), 'ok')
  } catch (e) {
    toast(e.message || tr('profile_cancel_failed', 'Cancel failed'), 'err')
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
