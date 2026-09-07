<template>
  <div class="panel">
    <h2>🔐 管理员账号</h2>
    <p class="tip">超级管理员可创建/停用运营账号、重置密码（M1）</p>

    <div v-if="role === 'super'" class="add-form">
      <input v-model="form.username" placeholder="管理员用户名" />
      <input v-model="form.password" type="password" placeholder="密码（至少8位）" />
      <select v-model="form.role">
        <option value="ops">运营</option>
        <option value="super">超级管理员</option>
      </select>
      <button @click="create">创建账号</button>
    </div>
    <p v-else class="muted">当前为运营账号，无账号管理权限。</p>

    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>用户名</th>
          <th>角色</th>
          <th>状态</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in list" :key="a.id">
          <td>{{ a.id }}</td>
          <td>{{ a.username }}</td>
          <td>{{ a.role === 'super' ? '超级管理员' : '运营' }}</td>
          <td>
            <span :class="['tag', a.enabled ? 'ok' : 'off']">
              {{ a.enabled ? '正常' : '已停用' }}
            </span>
          </td>
          <td>{{ a.created_at }}</td>
          <td class="ops" v-if="role === 'super'">
            <button class="mini" @click="toggle(a)">
              {{ a.enabled ? '停用' : '启用' }}
            </button>
            <button class="mini" @click="resetPw(a)">重置密码</button>
          </td>
          <td v-else>-</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminRequest } from '../../../api'

const props = defineProps({ token: String, role: String })
const list = ref([])
const form = ref({ username: '', password: '', role: 'ops' })

async function load() {
  const res = await adminRequest('/admins', {}, props.token)
  list.value = res.items
}

async function create() {
  if (!form.value.username || !form.value.password) {
    alert('请填写用户名与密码')
    return
  }
  try {
    await adminRequest('/admins', {
      method: 'POST',
      body: JSON.stringify(form.value),
    }, props.token)
    alert('创建成功')
    form.value = { username: '', password: '', role: 'ops' }
    load()
  } catch (e) {
    alert('创建失败：' + e.message)
  }
}

async function toggle(a) {
  if (!confirm(`确认${a.enabled ? '停用' : '启用'}「${a.username}」？`)) return
  await adminRequest(`/admins/${a.id}/status`, {
    method: 'PUT',
    body: JSON.stringify({ enabled: !a.enabled }),
  }, props.token)
  load()
}

async function resetPw(a) {
  const pw = prompt(`为「${a.username}」设置新密码（至少8位）：`)
  if (!pw) return
  await adminRequest(`/admins/${a.id}/reset-password`, {
    method: 'POST',
    body: JSON.stringify({ password: pw }),
  }, props.token)
  alert('密码已重置')
}
onMounted(load)
</script>

<style scoped>
.add-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
  padding: 12px;
  background: #fff;
  border: 1px solid #e6e9ef;
  border-radius: 10px;
}
.add-form input,
.add-form select {
  padding: 7px 10px;
  border: 1px solid #dfe3ea;
  border-radius: 6px;
  font-size: 13px;
}
.add-form button {
  padding: 7px 16px;
  background: #1a9e5c;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.muted {
  color: #a0a8b4;
}
table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  font-size: 13px;
}
th,
td {
  padding: 9px 12px;
  border: 1px solid #e6e9ef;
  text-align: left;
}
th {
  background: #f4f6f9;
  font-weight: 600;
}
.tag {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}
.tag.ok {
  background: #e6f7ee;
  color: #1a9e5c;
}
.tag.off {
  background: #fdeaea;
  color: #d33;
}
.mini {
  padding: 4px 10px;
  border: 1px solid #ccd2dc;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  margin-right: 6px;
}
</style>
