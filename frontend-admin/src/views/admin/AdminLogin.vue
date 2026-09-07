<template>
  <div class="admin-login">
    <div class="login-card">
      <div class="logo">🗺️</div>
      <h1>去见山海 · 管理后台</h1>
      <p class="sub">请使用管理员账号登录</p>
      <form @submit.prevent="doLogin">
        <label>
          <span>用户名</span>
          <input v-model="username" placeholder="管理员用户名" autocomplete="username" />
        </label>
        <label>
          <span>密码</span>
          <input
            v-model="password"
            type="password"
            placeholder="密码"
            autocomplete="current-password"
          />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '登 录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { adminLogin } from '../../api'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function doLogin() {
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await adminLogin({ username: username.value, password: password.value })
    localStorage.setItem('admin_token', res.token)
    localStorage.setItem('admin_role', res.admin.role)
    localStorage.setItem('admin_name', res.admin.username)
    router.push('/app')
  } catch (e) {
    let msg = '登录失败'
    try {
      msg = JSON.parse(e.message).detail || msg
    } catch (_) {
      /* 非 JSON 错误信息 */
    }
    error.value = msg
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.admin-login {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(160deg, #1a2a3a 0%, #24425c 100%);
}
.login-card {
  width: 100%;
  max-width: 380px;
  background: #fff;
  border-radius: 16px;
  padding: 32px 28px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
}
.logo {
  font-size: 34px;
  text-align: center;
}
h1 {
  font-size: 19px;
  text-align: center;
  margin: 10px 0 4px;
}
.sub {
  text-align: center;
  color: #8a94a6;
  font-size: 13px;
  margin-bottom: 20px;
}
label {
  display: block;
  margin-bottom: 14px;
}
label span {
  display: block;
  font-size: 12px;
  color: #5a6472;
  margin-bottom: 6px;
}
input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #dfe3ea;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}
.error {
  color: #d33;
  font-size: 13px;
  margin: 6px 0 10px;
}
button {
  width: 100%;
  padding: 11px;
  background: #1a2a3a;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  cursor: pointer;
}
button:disabled {
  opacity: 0.6;
}
.back {
  display: block;
  text-align: center;
  margin-top: 16px;
  color: #8a94a6;
  font-size: 13px;
  text-decoration: none;
}
</style>
