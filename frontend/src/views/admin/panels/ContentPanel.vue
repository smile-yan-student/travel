<template>
  <div class="panel">
    <h2>📍 内容与景点管理</h2>
    <p class="tip">必去地标库 / 城市库管理（M6）—— 修改后对新生成的行程即时生效</p>

    <div class="toolbar">
      <button class="ghost" :class="{ on: tab === 'must' }" @click="tab = 'must'; loadMust()">
        必去地标库
      </button>
      <button class="ghost" :class="{ on: tab === 'city' }" @click="tab = 'city'; loadCities()">
        城市库
      </button>
    </div>

    <!-- 必去地标库 -->
    <template v-if="tab === 'must'">
      <div class="add-form">
        <input v-model="form.city" placeholder="城市，如 北京" />
        <input v-model="form.name" placeholder="地标名，如 故宫博物院" />
        <input v-model="form.kw" placeholder="检索词(可空)" />
        <select v-model="form.category">
          <option value="景点">景点</option>
          <option value="美食">美食</option>
          <option value="购物">购物</option>
          <option value="夜生活">夜生活</option>
        </select>
        <input v-model.number="form.rating" type="number" step="0.1" placeholder="热度" />
        <input v-model.number="form.priority" type="number" placeholder="优先级" />
        <button @click="addItem">新增</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>城市</th>
            <th>地标</th>
            <th>类别</th>
            <th>热度</th>
            <th>优先级</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in mustList" :key="it.id">
            <td>{{ it.id }}</td>
            <td>{{ it.city }}</td>
            <td>{{ it.name }}</td>
            <td>{{ it.category }}</td>
            <td>{{ it.rating }}</td>
            <td>{{ it.priority }}</td>
            <td><button class="mini danger" @click="delItem(it.id)">删除</button></td>
          </tr>
          <tr v-if="!mustList.length">
            <td colspan="7" class="empty">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </template>

    <!-- 城市库 -->
    <template v-else>
      <table>
        <thead>
          <tr>
            <th>城市</th>
            <th>经度</th>
            <th>纬度</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in cityList" :key="c.city">
            <td>{{ c.city }}</td>
            <td>{{ c.lng }}</td>
            <td>{{ c.lat }}</td>
          </tr>
          <tr v-if="!cityList.length">
            <td colspan="3" class="empty">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminRequest } from '../../../api'

const props = defineProps({ token: String })
const tab = ref('must')
const mustList = ref([])
const cityList = ref([])
const form = ref({ city: '', name: '', kw: '', category: '景点', rating: 4.5, priority: 50 })

async function loadMust(city = '') {
  const qs = city ? `?city=${encodeURIComponent(city)}` : ''
  const res = await adminRequest(`/must-visit${qs}`, {}, props.token)
  mustList.value = res.items
}
async function loadCities() {
  const res = await adminRequest('/cities', {}, props.token)
  cityList.value = res.items
}
async function addItem() {
  if (!form.value.city || !form.value.name) {
    alert('请填写城市与地标名')
    return
  }
  try {
    await adminRequest('/must-visit', {
      method: 'POST',
      body: JSON.stringify(form.value),
    }, props.token)
    alert('新增成功')
    form.value = { city: '', name: '', kw: '', category: '景点', rating: 4.5, priority: 50 }
    loadMust()
  } catch (e) {
    alert('新增失败：' + e.message)
  }
}
async function delItem(id) {
  if (!confirm('确认删除该地标？')) return
  await adminRequest(`/must-visit/${id}`, { method: 'DELETE' }, props.token)
  loadMust()
}
onMounted(loadMust)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.toolbar .ghost {
  padding: 8px 16px;
  background: #fff;
  color: #1a2a3a;
  border: 1px solid #ccd2dc;
  border-radius: 8px;
  cursor: pointer;
}
.toolbar .ghost.on {
  background: #1a2a3a;
  color: #fff;
  border-color: #1a2a3a;
}
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
.mini.danger {
  padding: 4px 10px;
  border: 1px solid #e6c4c4;
  background: #fff;
  color: #d33;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}
.empty {
  text-align: center;
  color: #a0a8b4;
  padding: 24px;
}
</style>
