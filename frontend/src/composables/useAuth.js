import { ref, computed } from 'vue'
import { apiFetch, apiPost, buildForm } from './useApi.js'

const token  = ref(localStorage.getItem('ll_token') || '')
const user   = ref(null)

export function useAuth() {
  const isLoggedIn = computed(() => !!user.value)

  async function checkAuth() {
    if (!token.value) return
    try {
      const d = await apiFetch('/api/auth/me')
      user.value = { email: d.email, name: d.name, avatar_url: d.avatar_url, created_at: d.created_at }
    } catch {
      token.value = ''
      user.value = null
      localStorage.removeItem('ll_token')
    }
  }

  async function login(email, password) {
    const fd = buildForm({ login_type: 'email_password', email, password })
    const d = await apiPost('/api/auth/login', fd)
    token.value = d.token
    localStorage.setItem('ll_token', d.token)
    user.value = { email: d.email, name: d.name, avatar_url: d.avatar_url }
    return d
  }

  async function sendCode(email) {
    const fd = buildForm({ email })
    return apiPost('/api/auth/send-code', fd)
  }

  async function register(email, name, password, code) {
    const fd = buildForm({ email, name, password, code })
    const d = await apiPost('/api/auth/register', fd)
    token.value = d.token
    localStorage.setItem('ll_token', d.token)
    user.value = { email: d.email, name: d.name, avatar_url: d.avatar_url }
    return d
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('ll_token')
  }

  async function changePassword(old_password, new_password) {
    const fd = buildForm({ old_password, new_password })
    return apiPost('/api/auth/change-password', fd)
  }

  async function sendEmailCode(email) {
    const fd = buildForm({ email })
    return apiPost('/api/auth/send-email-code', fd)
  }

  async function bindEmail(email, code) {
    const fd = buildForm({ email, code })
    const d = await apiPost('/api/auth/bind-email', fd)
    if (user.value) {
      user.value.email = d.email
    }
    return d
  }

  async function uploadAvatar(file) {
    const fd = new FormData()
    fd.append('file', file)
    const d = await apiPost('/api/users/avatar', fd)
    if (user.value) {
      user.value.avatar_url = d.avatar_url
    }
    return d
  }

  return { token, user, isLoggedIn, checkAuth, login, register, sendCode, logout, changePassword, sendEmailCode, bindEmail, uploadAvatar }
}
