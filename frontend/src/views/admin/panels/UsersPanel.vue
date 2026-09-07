<template>
  <div class="panel">
    <h2>👥 用户管理</h2>
    <p class="tip">用户列表、详情与启停用治理（M3）</p>

    <div class="toolbar">
      <input v-model="keyword" placeholder="按用户名搜索" @keyup.enter="load(1)" />
      <button @click="load(1)">搜索</button>
    </div>

    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>用户名</th>
          <th>足迹城市</th>
          <th>行程数</th>
          <th>对话数</th>
          <th>注册时间</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in list" :key="u.id">
          <td>{{ u.id }}</td>
          <td>{{ u.username }}</td>
          <td>{{ u.city_cnt }}</td>
          <td>{{ u.trip_cnt }}</td>
          <td>{{ u.convo_cnt }}</td>
          <td>{{ u.created_at }}</td>
          <td>
            <span :class="['tag', u.enabled ? 'ok' : 'off']">
              {{ u.enabled ? '正常' : '已停用' }}
            </span>
          </td>
          <td class="ops">
            <button class="mini" @click="openDetail(u.id)">详情</button>
            <button class="mini" @click="toggle(u)">
              {{ u.enabled ? '停用' : '启用' }}
            </button>
          </td>
        </tr>
        <tr v-if="!list.length">
          <td colspan="8" class="empty">暂无数据</td>
        </tr>
      </tbody>
    </table>

    <div class="pager">
      <button :disabled="page <= 1" @click="load(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页</span>
      <button :disabled="page >= totalPages" @click="load(page + 1)">下一页</button>
    </div>

    <!-- 用户详情弹层 -->
    <div v-if="detail" class="mask" @click.self="detail = null">
      <div class="drawer">
        <h3>用户详情：{{ detail.username }}</h3>
        <p class="tip">注册于 {{ detail.created_at }} · {{ detail.enabled ? '正常' : '已停用' }}</p>
        <h4>行程足迹（{{ detail.trips.length }}）</h4>
        <ul class="mini-list">
          <li v-for="t in detail.trips" :key="t.id">
            {{ t.destination }} · {{ t.days }}天 · {{ t.style }} · {{ t.created_at }}
          </li>
          <li v-if="!detail.trips.length" class="muted">暂无行程</li>
        </ul>
        <h4>对话会话（{{ detail.conversations.length }}）</h4>
        <ul class="mini-list">
          <li v-for="c in detail.conversations" :key="c.id">
            {{ c.title }} · {{ c.updated_at }}
          </li>
          <li v-if="!detail.conversations.length" class="muted">暂无会话</li>
        </ul>
        <button class="close" @click="detail = null">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { adminRequest } from '../../../api'

const props = defineProps({ token: String })
const list = ref([])
const total = ref(0)
const page = ref(1)
const size = 10
const keyword = ref('')
const detail = ref(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size)))

async function load(p = 1) {
  page.value = p
  const qs = `?page=${p}&size=${size}&keyword=${encodeURIComponent(keyword.value)}`
  const res = await adminRequest(`/users${qs}`, {}, props.token)
  list.value = res.items
  total.value = res.total
}

async function toggle(u) {
  if (!confirm(`确认${u.enabled ? '停用' : '启用'}用户「${u.username}」？`)) return
  await adminRequest(`/users/${u.id}/status`, {
    method: 'PUT',
    body: JSON.stringify({ enabled: !u.enabled }),
  }, props.token)
  load(page.value)
}

async function openDetail(id) {
  detail.value = await adminRequest(`/users/${id}`, {}, props.token)
}
onMounted(() => load(1))
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.toolbar input {
  padding: 8px 12px;
  border: 1px solid #dfe3ea;
  border-radius: 8px;
  min-width: 220px;
}
.toolbar button {
  padding: 8px 16px;
  background: #1a2a3a;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  font-size: 13px;
}
th,
td {
  padding: 10px 12px;
  border: 1px solid #e6e9ef;
  text-align: left;
}
th {
  background: #f4f6f9;
  font-weight: 600;
}
.ops {
  display: flex;
  gap: 6px;
}
.mini {
  padding: 4px 10px;
  border: 1px solid #ccd2dc;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
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
.empty {
  text-align: center;
  color: #a0a8b4;
  padding: 24px;
}
.pager {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 12px;
  font-size: 13px;
}
.pager button {
  padding: 6px 12px;
  border: 1px solid #ccd2dc;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
}
.pager button:disabled {
  opacity: 0.5;
}
.mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 80;
  display: flex;
  justify-content: flex-end;
}
.drawer {
  width: 420px;
  max-width: 90vw;
  background: #fff;
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  box-sizing: border-box;
}
.mini-list {
  margin: 6px 0 14px;
  padding-left: 18px;
  font-size: 13px;
  color: #333;
}
.muted {
  color: #a0a8b4;
  list-style: none;
  margin-left: -18px;
}
.close {
  padding: 8px 16px;
  background: #1a2a3a;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
</style>
