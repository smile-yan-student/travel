<template>
  <div class="panel">
    <h2>💬 对话运营</h2>
    <p class="tip">会话查看与意图统计（M5）</p>

    <div class="toolbar">
      <input v-model="keyword" placeholder="按标题/用户名搜索" @keyup.enter="load(1)" />
      <button @click="load(1)">搜索</button>
      <button class="ghost" @click="loadStats">刷新统计</button>
    </div>

    <div class="stats-row" v-if="stats">
      <div class="stat-box">
        <b>{{ stats.total }}</b><span>会话总数</span>
      </div>
      <div class="stat-box">
        <b>{{ stats.with_plan }}</b><span>含行程会话</span>
      </div>
      <div class="stat-box">
        <b>{{ stats.plain_chat }}</b><span>纯聊天会话</span>
      </div>
      <div class="stat-box wide">
        <span class="note">{{ stats.note }}</span>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>标题</th>
          <th>用户</th>
          <th>消息数</th>
          <th>最近更新</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in list" :key="c.id">
          <td>{{ c.id }}</td>
          <td class="title">{{ c.title }}</td>
          <td>{{ c.username }}</td>
          <td>{{ c.msg_cnt }}</td>
          <td>{{ c.updated_at }}</td>
          <td><button class="mini" @click="openDetail(c.id)">查看</button></td>
        </tr>
        <tr v-if="!list.length">
          <td colspan="6" class="empty">暂无数据</td>
        </tr>
      </tbody>
    </table>

    <div class="pager">
      <button :disabled="page <= 1" @click="load(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页</span>
      <button :disabled="page >= totalPages" @click="load(page + 1)">下一页</button>
    </div>

    <!-- 会话详情弹层 -->
    <div v-if="detail" class="mask" @click.self="detail = null">
      <div class="drawer">
        <h3>{{ detail.title }}</h3>
        <p class="tip">
          {{ detail.username }} · {{ detail.created_at }}
          <span :class="['tag', detail.has_plan ? 'ok' : '']">
            {{ detail.has_plan ? '含行程' : '纯聊天' }}
          </span>
        </p>
        <div class="msgs">
          <div v-for="(m, i) in detail.messages" :key="i" :class="['msg', m.role]">
            <div class="who">{{ m.role === 'user' ? '用户' : 'AI' }}</div>
            <div class="body">{{ m.content }}</div>
          </div>
          <p v-if="!detail.messages.length" class="muted">该会话暂无消息内容</p>
        </div>
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
const size = 12
const keyword = ref('')
const stats = ref(null)
const detail = ref(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size)))

async function load(p = 1) {
  page.value = p
  const qs = `?page=${p}&size=${size}&keyword=${encodeURIComponent(keyword.value)}`
  const res = await adminRequest(`/conversations${qs}`, {}, props.token)
  list.value = res.items
  total.value = res.total
}

async function loadStats() {
  stats.value = await adminRequest('/conversations/stats', {}, props.token)
}

async function openDetail(id) {
  detail.value = await adminRequest(`/conversations/${id}`, {}, props.token)
}
onMounted(() => {
  load(1)
  loadStats()
})
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
.toolbar .ghost {
  background: #fff;
  color: #1a2a3a;
  border: 1px solid #ccd2dc;
}
.stats-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.stat-box {
  background: #fff;
  border: 1px solid #e6e9ef;
  border-radius: 10px;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 90px;
}
.stat-box b {
  font-size: 22px;
  color: #1a2a3a;
}
.stat-box span {
  font-size: 12px;
  color: #7a8494;
}
.stat-box.wide {
  flex: 1;
}
.note {
  color: #a0a8b4;
  font-size: 12px;
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
.title {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  background: #eef2f7;
}
.tag.ok {
  background: #e6f7ee;
  color: #1a9e5c;
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
  width: 480px;
  max-width: 92vw;
  background: #fff;
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  box-sizing: border-box;
}
.msgs {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 12px 0 16px;
}
.msg {
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
}
.msg .who {
  font-size: 11px;
  color: #a0a8b4;
  margin-bottom: 4px;
}
.msg .body {
  white-space: pre-wrap;
}
.msg.user {
  background: #eef2f7;
}
.msg.assistant {
  background: #f0f7ff;
}
.muted {
  color: #a0a8b4;
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
