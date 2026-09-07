<template>
  <div class="me">
    <!-- 顶部 -->
    <header class="head">
      <div class="head-main">
        <h1>👤 我的</h1>
        <p>去看世界，把足迹画成自己的地图</p>
      </div>
    </header>

    <main class="content">
      <!-- 未登录：登录（注册入口在登录弹窗内） -->
      <template v-if="!loggedIn">
        <div class="brand-card">
          <div class="brand-logo">✈️</div>
          <div class="brand-title">去见山海</div>
          <p>登录后，你规划的每一次出行都会被记下——点亮一座座城市，累积属于你的探索里程。</p>
          <div class="brand-btns">
            <button class="btn-primary" @click="openAuth('login')">登录</button>
          </div>
        </div>
        <div class="tips">
          <div class="tip">🌍 点亮城市 · 记录你的每一次出发</div>
          <div class="tip">🚶 累积探索里程 · 见证行走天下的勇气</div>
          <div class="tip">🧳 行程即足迹 · 走多远都有迹可循</div>
        </div>
      </template>

      <!-- 已登录：用户 + 足迹 + 能力 -->
      <template v-else>
        <!-- 用户信息 -->
        <div class="user-card">
          <div class="avatar">{{ avatarChar }}</div>
          <div class="user-info">
            <div class="user-name">{{ username }}</div>
            <div class="user-sub">去见山海的旅行伙伴</div>
          </div>
          <button class="logout" @click="doLogout">退出</button>
        </div>

        <!-- 足迹统计 -->
        <div class="card">
          <div class="card-title">🌍 我的足迹</div>
          <div class="fp-stats">
            <div class="fp-stat">
              <div class="fp-num">{{ summary ? summary.city_count : 0 }}</div>
              <div class="fp-label">点亮城市</div>
            </div>
            <div class="fp-stat">
              <div class="fp-num">{{ summary ? summary.trip_count : 0 }}</div>
              <div class="fp-label">次出发</div>
            </div>
            <div class="fp-stat">
              <div class="fp-num">{{ summary ? kmText : 0 }}</div>
              <div class="fp-label">探索里程 km</div>
            </div>
          </div>
          <div v-if="summary && summary.trips.length" class="fp-cities">
            <span v-for="t in summary.trips.slice(0, 10)" :key="t.id" class="fp-city">{{ t.destination }}</span>
          </div>
          <p v-else class="empty">还没有足迹，去「对话」板块规划一次出发吧～</p>
        </div>

        <!-- 最近行程 -->
        <div v-if="summary && summary.trips.length" class="card">
          <div class="card-title">🗺️ 最近行程</div>
          <div v-for="t in summary.trips.slice(0, 5)" :key="t.id" class="trip-item">
            <div class="trip-name">{{ t.destination }} <span class="trip-days">{{ t.days }}天</span></div>
            <div class="trip-meta">{{ t.style || '综合' }} · {{ kmTextOf(t.distance_km) }}km · {{ t.created_at }}</div>
          </div>
        </div>

        <!-- 我的旅行偏好（用户画像） -->
        <div class="card">
          <div class="card-title">
            🎯 我的旅行偏好
            <span v-if="profileStats" class="profile-completeness">画像完整度 {{ profileStats.profile_completeness }}%</span>
          </div>
          <div v-if="userProfile && userProfile.preferences" class="profile-grid">
            <div class="profile-item">
              <span class="profile-label">出行节奏</span>
              <span class="profile-value">{{ userProfile.preferences.pace || '待学习' }}</span>
            </div>
            <div class="profile-item">
              <span class="profile-label">预算偏好</span>
              <span class="profile-value">{{ userProfile.preferences.budget || '待学习' }}</span>
            </div>
            <div class="profile-item">
              <span class="profile-label">出行人群</span>
              <span class="profile-value">{{ userProfile.preferences.group_type || '待学习' }}</span>
            </div>
            <div class="profile-item">
              <span class="profile-label">交通方式</span>
              <span class="profile-value">{{ userProfile.preferences.traffic || '待学习' }}</span>
            </div>
            <div class="profile-item profile-full">
              <span class="profile-label">旅行风格</span>
              <div class="profile-tags">
                <span v-for="style in userProfile.preferences.styles || []" :key="style" class="profile-tag">{{ style }}</span>
                <span v-if="!userProfile.preferences.styles?.length" class="profile-empty">规划几次行程后自动学习</span>
              </div>
            </div>
            <div class="profile-item">
              <span class="profile-label">美食爱好者</span>
              <span class="profile-value">{{ userProfile.preferences.food_lover ? '是' : '待学习' }}</span>
            </div>
            <div class="profile-item">
              <span class="profile-label">人文历史</span>
              <span class="profile-value">{{ userProfile.preferences.humanities_interest ? '感兴趣' : '待学习' }}</span>
            </div>
            <div class="profile-item">
              <span class="profile-label">拍照打卡</span>
              <span class="profile-value">{{ userProfile.preferences.photography_interest ? '喜欢' : '待学习' }}</span>
            </div>
          </div>
          <div v-if="profileStats" class="profile-stats">
            <div class="stat-item">
              <span class="stat-num">{{ profileStats.total_plans || 0 }}</span>
              <span class="stat-label">次规划</span>
            </div>
            <div class="stat-item">
              <span class="stat-num">{{ profileStats.total_modifications || 0 }}</span>
              <span class="stat-label">次调整</span>
            </div>
            <div class="stat-item">
              <span class="stat-num">{{ profileStats.learned_preferences_count || 0 }}</span>
              <span class="stat-label">项偏好</span>
            </div>
          </div>
          <p class="profile-tip">💡 你的每次规划和调整都会被学习，下次规划自动带入你的偏好</p>
        </div>

        <!-- 其他能力 -->
        <div class="card">
          <div class="card-title">🧰 更多</div>
          <div class="ability-item">
            <span class="ab-icon">🧭</span>
            <span class="ab-txt">周边探索</span>
            <router-link to="/explore" class="ab-link">去探索 →</router-link>
          </div>
          <div class="ability-item">
            <span class="ab-icon">💬</span>
            <span class="ab-txt">对话规划</span>
            <router-link to="/" class="ab-link">去规划 →</router-link>
          </div>
          <div class="ability-item">
            <span class="ab-icon">🛰️</span>
            <span class="ab-txt">数据来源</span>
            <span class="ab-meta">高德地图 · 本地AI模型</span>
          </div>
        </div>
      </template>
    </main>

    <!-- 登录 / 注册弹窗 -->
    <div v-if="showAuth" class="auth-mask" @click.self="showAuth = false">
      <div class="auth-box">
        <div class="auth-head">
          <div class="auth-tabs">
            <button :class="['auth-tab', { active: authMode === 'login' }]" @click="authMode = 'login'">登录</button>
            <button :class="['auth-tab', { active: authMode === 'register' }]" @click="authMode = 'register'">注册</button>
          </div>
          <button class="auth-close" @click="showAuth = false">✕</button>
        </div>
        <p class="auth-sub">去见山海 · 记录你的每一次出发</p>

        <!-- 邮箱密码登录 -->
        <template v-if="authMode === 'login'">
          <input v-model="authForm.email" class="auth-input" type="email" placeholder="请输入邮箱地址" @keyup.enter="doAuth" />
          <input v-model="authForm.password" type="password" class="auth-input" placeholder="请输入密码" @keyup.enter="doAuth" />
          <button class="auth-btn" :disabled="authLoading" @click="doAuth">
            <span v-if="authLoading" class="spinner"></span>
            <span v-else>登录</span>
          </button>
        </template>

        <!-- 注册：邮箱验证码 + 密码 -->
        <template v-else-if="authMode === 'register'">
          <input v-model="authForm.email" class="auth-input" type="email" placeholder="请输入邮箱地址" @input="emailStatus = ''; emailText = ''" @blur="checkEmail" />
          <p v-if="emailStatus" :class="['uname-status', emailStatus === 'taken' || emailStatus === 'error' ? 'err' : 'ok']">{{ emailText }}</p>
          <div class="email-code-row">
            <input v-model="authForm.code" class="auth-input email-code-input" type="text" maxlength="6" placeholder="请输入验证码" @keyup.enter="doAuth" />
            <button class="send-code-btn" :disabled="registerCountdown > 0 || registerSending" @click="sendRegisterCode">
              <span v-if="registerSending" class="spinner"></span>
              <span v-else-if="registerCountdown > 0">{{ registerCountdown }}s后重发</span>
              <span v-else>获取验证码</span>
            </button>
          </div>
          <input v-model="authForm.password" type="password" class="auth-input" placeholder="设置密码（8-64位，大小写/数字/特殊字符至少3种）" @keyup.enter="doAuth" />
          <button class="auth-btn" :disabled="authLoading" @click="doAuth">
            <span v-if="authLoading" class="spinner"></span>
            <span v-else>注册</span>
          </button>
          <p class="auth-hint">注册即表示同意用户协议和隐私政策，用户名将自动生成。</p>
        </template>

        <p v-if="authError" class="auth-error">{{ authError }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'Me' })
import { computed, reactive, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login as apiLogin, register as apiRegister, checkUsername, checkEmail as apiCheckEmail, getMyProfile, getProfileStats, sendEmailCode as apiSendEmailCode, emailLogin as apiEmailLogin } from '../api'
import {
  getToken, refreshMe, fetchMyTrips, saveSession, clearSession, notifyUserChanged,
} from '../utils/user'

const route = useRoute()
const router = useRouter()

const loggedIn = ref(false)
const username = ref('')
const summary = ref(null)
const userProfile = ref(null)
const profileStats = ref(null)
const showAuth = ref(false)
const authMode = ref('login')
const authLoading = ref(false)
const authError = ref('')
const authForm = reactive({ username: '', email: '', code: '', password: '' })
const unameStatus = ref('') // '' | checking | ok | taken | error
const unameText = ref('')
const emailStatus = ref('') // '' | checking | ok | taken | error
const emailText = ref('')
const registerCountdown = ref(0)
const registerSending = ref(false)
let registerCountdownTimer = null

// 邮箱验证码登录
const emailForm = reactive({ email: '', code: '' })
const emailSending = ref(false)
const emailLoading = ref(false)
const emailCountdown = ref(0)
let emailCountdownTimer = null

function startEmailCountdown() {
  emailCountdown.value = 60
  if (emailCountdownTimer) clearInterval(emailCountdownTimer)
  emailCountdownTimer = setInterval(() => {
    emailCountdown.value--
    if (emailCountdown.value <= 0) {
      clearInterval(emailCountdownTimer)
      emailCountdownTimer = null
    }
  }, 1000)
}

async function sendEmailCode() {
  const email = emailForm.email.trim()
  if (!email) {
    authError.value = '请输入邮箱地址'
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    authError.value = '邮箱格式不正确'
    return
  }
  authError.value = ''
  emailSending.value = true
  try {
    const res = await apiSendEmailCode({ email, scene: 'login' })
    if (res.ok) {
      startEmailCountdown()
      authError.value = ''
    } else {
      authError.value = res.message || '验证码发送失败'
    }
  } catch (e) {
    authError.value = e.message || '验证码发送失败，请稍后重试'
  } finally {
    emailSending.value = false
  }
}

async function doEmailLogin() {
  const email = emailForm.email.trim()
  const code = emailForm.code.trim()
  if (!email) {
    authError.value = '请输入邮箱地址'
    return
  }
  if (!code || code.length !== 6) {
    authError.value = '请输入6位验证码'
    return
  }
  authError.value = ''
  emailLoading.value = true
  try {
    const res = await apiEmailLogin({ email, code })
    if (res.ok && res.token) {
      saveSession(res.token, res.user)
      notifyUserChanged()
      showAuth.value = false
      authError.value = ''
      emailForm.email = ''
      emailForm.code = ''
      if (emailCountdownTimer) {
        clearInterval(emailCountdownTimer)
        emailCountdownTimer = null
      }
      emailCountdown.value = 0
      await refreshMe()
      await loadSummary()
    } else {
      authError.value = res.message || '登录失败'
    }
  } catch (e) {
    authError.value = e.message || '登录失败，请稍后重试'
  } finally {
    emailLoading.value = false
  }
}

async function checkUserName() {
  if (authMode.value !== 'register') return
  const u = authForm.username.trim()
  if (u.length < 6 || u.length > 20) {
    unameStatus.value = ''
    unameText.value = ''
    return
  }
  unameStatus.value = 'checking'
  try {
    const res = await checkUsername(u)
    unameStatus.value = res.available ? 'ok' : 'taken'
    unameText.value = res.message || ''
  } catch (e) {
    unameStatus.value = 'error'
    unameText.value = '检查失败，提交时再校验'
  }
}

async function checkEmail() {
  if (authMode.value !== 'register') return
  const e = authForm.email.trim().toLowerCase()
  if (!e) {
    emailStatus.value = ''
    emailText.value = ''
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) {
    emailStatus.value = 'error'
    emailText.value = '邮箱格式不正确'
    return
  }
  emailStatus.value = 'checking'
  try {
    const res = await apiCheckEmail(e)
    emailStatus.value = res.available ? 'ok' : 'taken'
    emailText.value = res.message || ''
  } catch (err) {
    emailStatus.value = 'error'
    emailText.value = '检查失败，提交时再校验'
  }
}

function startRegisterCountdown() {
  registerCountdown.value = 60
  if (registerCountdownTimer) clearInterval(registerCountdownTimer)
  registerCountdownTimer = setInterval(() => {
    registerCountdown.value--
    if (registerCountdown.value <= 0) {
      clearInterval(registerCountdownTimer)
      registerCountdownTimer = null
    }
  }, 1000)
}

async function sendRegisterCode() {
  const email = authForm.email.trim().toLowerCase()
  if (!email) {
    authError.value = '请输入邮箱地址'
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    authError.value = '邮箱格式不正确'
    return
  }
  authError.value = ''
  registerSending.value = true
  try {
    const res = await apiSendEmailCode({ email, scene: 'register' })
    if (res.ok) {
      startRegisterCountdown()
      authError.value = ''
    } else {
      authError.value = res.message || '验证码发送失败'
    }
  } catch (e) {
    authError.value = e.message || '验证码发送失败，请稍后重试'
  } finally {
    registerSending.value = false
  }
}

const avatarChar = computed(() => (username.value ? username.value.slice(0, 1).toUpperCase() : '?'))
const kmText = computed(() => {
  if (!summary.value) return 0
  const km = summary.value.total_km
  return km >= 10000 ? (km / 10000).toFixed(1) + '万' : Math.round(km)
})
function kmTextOf(km) {
  return km >= 10000 ? (km / 10000).toFixed(1) + '万' : Math.round(km || 0)
}

function openAuth(mode) {
  authMode.value = mode
  authError.value = ''
  showAuth.value = true
}
const SPECIAL_CHARS = '~!@#$%^&*()_+-=[]{}|;:,.<>?/'
function validateCredentials(username, password) {
  if (username.length < 6 || username.length > 20) return '用户名长度需为 6~20 个字符'
  if (password.length < 8 || password.length > 64) return '密码长度需为 8~64 个字符'
  if (password === username) return '密码不能与用户名相同'
  if (password === username.split('').reverse().join('')) return '密码不能是用户名的倒序'
  const lp = password.toLowerCase()
  const lu = username.toLowerCase()
  for (let i = 0; i <= lu.length - 3; i++) {
    if (lp.includes(lu.slice(i, i + 3))) return '密码不能包含超过两个连续的用户名字符'
  }
  let classes = 0
  if (/[A-Z]/.test(password)) classes++
  if (/[a-z]/.test(password)) classes++
  if (/\d/.test(password)) classes++
  if (SPECIAL_CHARS.split('').some((ch) => password.includes(ch))) classes++
  if (classes < 3) return '密码需包含大写字母、小写字母、数字、特殊字符中的至少三种'
  return ''
}
async function doAuth() {
  if (authMode.value === 'login') {
    if (!authForm.email.trim() || !authForm.password) {
      authError.value = '请填写邮箱和密码'
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(authForm.email.trim())) {
      authError.value = '邮箱格式不正确'
      return
    }
  } else {
    if (!authForm.email.trim() || !authForm.code || !authForm.password) {
      authError.value = '请填写邮箱、验证码和密码'
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(authForm.email.trim())) {
      authError.value = '邮箱格式不正确'
      return
    }
    if (!authForm.code || authForm.code.length !== 6 || !/^\d{6}$/.test(authForm.code)) {
      authError.value = '请输入6位数字验证码'
      return
    }
    // 密码强度校验（注册时自动生成用户名，用邮箱前缀代替用户名做关联性校验）
    const tempUsername = authForm.email.split('@')[0].slice(0, 20)
    const verr = validateCredentials(tempUsername, authForm.password)
    if (verr) {
      authError.value = verr
      return
    }
  }
  authLoading.value = true
  authError.value = ''
  try {
    if (authMode.value === 'login') {
      const res = await apiLogin({ email: authForm.email.trim().toLowerCase(), password: authForm.password })
      if (!res.ok) {
        authError.value = res.message || '登录失败'
        return
      }
      saveSession(res.token, res.user.username)
      loggedIn.value = true
      username.value = res.user.username
      showAuth.value = false
      summary.value = await fetchMyTrips()
      // 广播登录态变化：对话板块据此同步未登录本地会话到后端
      notifyUserChanged()
      // 登录后跳回原页面（如果有 redirect 参数）
      const redirect = route.query.redirect
      if (redirect && typeof redirect === 'string') {
        router.replace(redirect)
      }
    } else {
      const res = await apiRegister({
        email: authForm.email.trim().toLowerCase(),
        code: authForm.code,
        password: authForm.password
      })
      if (!res.ok) {
        authError.value = res.message || '注册失败'
        return
      }
      authError.value = '注册成功，请登录'
      authMode.value = 'login'
      // 注册成功后，把邮箱填到登录表单
      authForm.email = authForm.email.trim().toLowerCase()
      authForm.code = ''
      authForm.password = ''
      // 清除注册验证码倒计时
      if (registerCountdownTimer) {
        clearInterval(registerCountdownTimer)
        registerCountdownTimer = null
      }
      registerCountdown.value = 0
    }
  } catch (e) {
    authError.value = '请求失败：' + (e.message || '')
  } finally {
    authLoading.value = false
  }
}
function doLogout() {
  clearSession()
  loggedIn.value = false
  username.value = ''
  summary.value = null
  // 广播登出：对话板块切换为本地会话模式
  notifyUserChanged()
}

async function refreshSummary() {
  if (loggedIn.value) summary.value = await fetchMyTrips()
}

async function loadUserProfile() {
  if (!loggedIn.value) return
  try {
    const res = await getMyProfile()
    if (res.code === 0) {
      userProfile.value = res.data
    }
    const statsRes = await getProfileStats()
    if (statsRes.code === 0) {
      profileStats.value = statsRes.data
    }
  } catch (e) {
    console.warn('加载用户画像失败:', e.message)
  }
}

onMounted(async () => {
  if (getToken()) {
    const u = await refreshMe()
    if (u) {
      loggedIn.value = true
      username.value = u.username
      summary.value = await fetchMyTrips()
      await loadUserProfile()
      // 已登录但带 redirect 参数 → 直接跳回
      const redirect = route.query.redirect
      if (redirect && typeof redirect === 'string') {
        router.replace(redirect)
        return
      }
    }
  }
  // 未登录且带 redirect 或 auth=login 参数 → 自动打开登录弹窗
  if (!loggedIn.value && (route.query.redirect || route.query.auth === 'login')) {
    authMode.value = 'login'
    showAuth.value = true
  }
  window.addEventListener('travel:trips-updated', refreshSummary)
})
onBeforeUnmount(() => {
  window.removeEventListener('travel:trips-updated', refreshSummary)
})
</script>

<style scoped>
.head {
  background: var(--gradient);
  color: #fff;
  padding: 40px 20px 30px;
  border-radius: 0 0 26px 26px;
}
.head-main h1 {
  font-size: 24px;
  font-weight: 800;
}
.head-main p {
  font-size: 12.5px;
  opacity: 0.9;
  margin-top: 4px;
}
.content {
  padding: 16px 16px 30px;
}
.brand-card {
  background: #fff;
  border: 1.5px solid var(--border);
  border-radius: 16px;
  padding: 26px 20px;
  text-align: center;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
}
.brand-logo {
  font-size: 44px;
}
.brand-title {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 3px;
  margin-top: 6px;
  color: var(--primary-dark);
}
.brand-card p {
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.7;
  margin: 12px 0 18px;
}
.brand-btns {
  display: flex;
  gap: 12px;
}
.btn-ghost {
  flex: 1;
  padding: 12px 0;
  border-radius: 12px;
  background: #fff;
  border: 1.5px solid var(--border);
  color: var(--primary-dark);
  font-size: 15px;
  font-weight: 700;
}
.tips {
  margin-top: 18px;
}
.tip {
  background: #fff;
  border: 1.5px solid var(--border);
  border-radius: 12px;
  padding: 12px 14px;
  font-size: 13.5px;
  color: var(--text);
  margin-bottom: 8px;
}
.user-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border: 1.5px solid var(--border);
  border-radius: 16px;
  padding: 18px;
}
.avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--gradient);
  color: #fff;
  font-size: 24px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.user-info {
  flex: 1;
  min-width: 0;
}
.user-name {
  font-size: 18px;
  font-weight: 700;
}
.user-sub {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 3px;
}
.logout {
  color: var(--danger);
  font-size: 13px;
  background: #fdf2f2;
  padding: 7px 13px;
  border-radius: 999px;
  font-weight: 600;
  flex-shrink: 0;
}
.card {
  background: #fff;
  border: 1.5px solid var(--border);
  border-radius: 14px;
  padding: 15px;
  margin-top: 14px;
}
.card-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 12px;
}
.fp-stats {
  display: flex;
  gap: 12px;
}
.fp-stat {
  flex: 1;
  text-align: center;
  background: #f7faf9;
  border-radius: 12px;
  padding: 10px 4px;
}
.fp-num {
  font-size: 20px;
  font-weight: 800;
  color: var(--primary-dark);
}
.fp-label {
  font-size: 12px;
  color: var(--text-2);
  margin-top: 2px;
}
.fp-cities {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.fp-city {
  background: #eef9f6;
  color: var(--primary-dark);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12.5px;
  font-weight: 600;
}
.empty {
  font-size: 13px;
  color: var(--text-3);
  text-align: center;
  padding: 14px 0 6px;
}
.trip-item {
  padding: 9px 2px;
  border-bottom: 1px solid #f1f5f4;
}
.trip-item:last-child {
  border-bottom: none;
}
.trip-name {
  font-size: 14px;
  font-weight: 600;
}
.trip-days {
  font-size: 12px;
  color: var(--primary);
  background: #eef9f6;
  padding: 1px 8px;
  border-radius: 999px;
  margin-left: 6px;
}
.trip-meta {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 3px;
}
.ability-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 2px;
  border-bottom: 1px solid #f1f5f4;
}
.ability-item:last-child {
  border-bottom: none;
}
.ab-icon {
  font-size: 20px;
}
.ab-txt {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
}
.ab-link {
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}
.ab-meta {
  color: var(--text-3);
  font-size: 12px;
}
.auth-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 30, 26, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99;
  padding: 24px;
}
.auth-box {
  width: 100%;
  max-width: 340px;
  background: #fff;
  border-radius: 18px;
  padding: 20px;
}
.auth-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.auth-tabs {
  display: flex;
  gap: 6px;
}
.auth-tab {
  padding: 6px 16px;
  border-radius: 999px;
  background: #eef2f1;
  color: var(--text-2);
  font-size: 14px;
  font-weight: 600;
}
.auth-tab.active {
  background: var(--gradient);
  color: #fff;
}
.auth-close {
  color: var(--text-3);
  font-size: 16px;
  padding: 4px;
}
.auth-sub {
  font-size: 12.5px;
  color: var(--text-3);
  margin-bottom: 14px;
}
.auth-input {
  width: 100%;
  padding: 12px 13px;
  border: 1.5px solid var(--border);
  border-radius: 12px;
  font-size: 14px;
  margin-bottom: 10px;
  background: #fbfdfc;
  box-sizing: border-box;
}
.auth-btn {
  width: 100%;
  padding: 12px 0;
  border-radius: 12px;
  background: var(--gradient);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.auth-error {
  color: var(--danger);
  font-size: 12.5px;
  text-align: center;
  margin-top: 10px;
}
.auth-hint {
  color: var(--text-3);
  font-size: 12px;
  line-height: 1.6;
  margin-top: 10px;
}
.email-code-row {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}
.email-code-input {
  flex: 1;
  margin-bottom: 0;
}
.send-code-btn {
  flex-shrink: 0;
  padding: 0 14px;
  border: 1.5px solid var(--primary);
  border-radius: 12px;
  background: #fff;
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 110px;
}
.send-code-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.uname-status {
  font-size: 12px;
  margin: -4px 0 8px;
}
.uname-status.ok {
  color: var(--primary);
}
.uname-status.err {
  color: var(--danger);
}
.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: rot 0.8s linear infinite;
}
@keyframes rot {
  to { transform: rotate(360deg); }
}

/* 用户画像 */
.profile-completeness {
  font-size: 11px;
  color: #6366f1;
  font-weight: 600;
  margin-left: auto;
}
.profile-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 14px;
}
.profile-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  background: #f9fafb;
  border-radius: 8px;
}
.profile-full {
  grid-column: 1 / -1;
}
.profile-label {
  font-size: 11px;
  color: #9ca3af;
}
.profile-value {
  font-size: 13px;
  color: #374151;
  font-weight: 500;
}
.profile-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.profile-tag {
  font-size: 11px;
  padding: 3px 8px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border-radius: 999px;
}
.profile-empty {
  font-size: 11px;
  color: #9ca3af;
}
.profile-stats {
  display: flex;
  justify-content: space-around;
  padding: 12px 0;
  border-top: 1px solid #f3f4f6;
}
.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.stat-num {
  font-size: 18px;
  font-weight: 700;
  color: #6366f1;
}
.stat-label {
  font-size: 11px;
  color: #9ca3af;
}
.profile-tip {
  margin-top: 10px;
  font-size: 11px;
  color: #9ca3af;
  text-align: center;
}
</style>
