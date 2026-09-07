<template>
  <div class="panel">
    <h2>🧳 行程与足迹运营</h2>
    <p class="tip">行程数据与足迹分布分析（M4）</p>

    <div class="toolbar">
      <input v-model="destination" placeholder="按目的地筛选" @keyup.enter="load(1)" />
      <button @click="load(1)">筛选</button>
      <button class="ghost" @click="loadStats">刷新统计</button>
    </div>

    <div class="stats-row" v-if="stats">
      <div class="stat-box">
        <b>{{ stats.total }}</b><span>行程总数</span>
      </div>
      <div class="stat-box">
        <b>{{ stats.avg_days }}</b><span>平均天数</span>
      </div>
      <div class="stat-box wide">
        <span class="lbl">足迹 Top 城市</span>
        <div class="chips">
          <span v-for="c in stats.top_cities.slice(0, 8)" :key="c.destination" class="chip">
            {{ c.destination }} · {{ c.count }}
          </span>
        </div>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>用户</th>
          <th>目的地</th>
          <th>天数</th>
          <th>风格</th>
          <th>创建时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in list" :key="t.id">
          <td>{{ t.id }}</td>
          <td>{{ t.username }}</td>
          <td>{{ t.destination }}</td>
          <td>{{ t.days }}</td>
          <td>{{ t.style || '-' }}</td>
          <td>{{ t.created_at }}</td>
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
const destination = ref('')
const stats = ref(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size)))

async function load(p = 1) {
  page.value = p
  const qs = `?page=${p}&size=${size}&destination=${encodeURIComponent(destination.value)}`
  const res = await adminRequest(`/trips${qs}`, {}, props.token)
  list.value = res.items
  total.value = res.total
}

async function loadStats() {
  stats.value = await adminRequest('/trips/stats', {}, props.token)
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
  min-width: 200px;
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
.lbl {
  font-size: 12px;
  color: #7a8494;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}
.chip {
  background: #eef2f7;
  border-radius: 12px;
  padding: 3px 10px;
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
</style>
