<template>
  <div class="reservation-rules-panel">
    <div class="panel-header">
      <h2>📅 预约规则管理</h2>
      <div class="stats" v-if="stats">
        <span class="stat-item">总规则数: <b>{{ stats.total || 0 }}</b></span>
        <span class="stat-item">需预约景点: <b>{{ stats.need_reservation || 0 }}</b></span>
        <span class="stat-item">目的地数: <b>{{ stats.destinations || 0 }}</b></span>
      </div>
      <button class="btn-primary" @click="openModal()">+ 新增规则</button>
    </div>

    <!-- 搜索和筛选 -->
    <div class="toolbar">
      <input v-model="filter.destination" placeholder="目的地筛选（如：北京）" @keyup.enter="loadData" />
      <input v-model="filter.keyword" placeholder="景点名称搜索" @keyup.enter="loadData" />
      <button class="btn-secondary" @click="loadData">🔍 搜索</button>
      <button class="btn-secondary" @click="resetFilter">🔄 重置</button>
      <div class="toolbar-spacer"></div>
      <button class="btn-secondary" @click="exportData">📤 导出CSV</button>
      <button class="btn-secondary" @click="triggerImport">📥 导入CSV</button>
      <input ref="fileInput" type="file" accept=".csv" style="display:none" @change="handleImport" />
    </div>

    <!-- 数据表格 -->
    <table class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>景点名称</th>
          <th>目的地</th>
          <th>预约渠道</th>
          <th>放票时间</th>
          <th>开放时间</th>
          <th>闭馆日</th>
          <th>优先级</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in list" :key="item.id">
          <td>{{ item.id }}</td>
          <td class="name-cell">{{ item.attraction_name }}</td>
          <td>{{ item.destination || '-' }}</td>
          <td>{{ item.reservation_channel || '-' }}</td>
          <td class="highlight">{{ item.ticket_release_time || '-' }}</td>
          <td>{{ item.opening_hours || '-' }}</td>
          <td class="warning">{{ item.closing_days || '-' }}</td>
          <td>{{ item.priority }}</td>
          <td>
            <button class="btn-sm" @click="viewDetail(item)">查看</button>
            <button class="btn-sm" @click="openModal(item)">编辑</button>
            <button class="btn-sm btn-danger" @click="deleteItem(item.id)">删除</button>
          </td>
        </tr>
        <tr v-if="list.length === 0">
          <td colspan="9" class="empty-cell">暂无数据</td>
        </tr>
      </tbody>
    </table>

    <!-- 分页 -->
    <div class="pagination">
      <span>共 {{ total }} 条</span>
      <button @click="page--; loadData()" :disabled="page <= 1">上一页</button>
      <span>第 {{ page }} 页</span>
      <button @click="page++; loadData()" :disabled="page * pageSize >= total">下一页</button>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingId ? '编辑预约规则' : '新增预约规则' }}</h3>
          <button class="modal-close" @click="showModal = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>景点名称 <span class="required">*</span></label>
            <input v-model="form.attraction_name" placeholder="如：故宫博物院" />
          </div>
          <div class="form-row">
            <label>所属目的地</label>
            <input v-model="form.destination" placeholder="如：北京" />
          </div>
          <div class="form-row">
            <label>预约渠道</label>
            <input v-model="form.reservation_channel" placeholder="如：故宫博物院官方公众号" />
          </div>
          <div class="form-row">
            <label>放票时间</label>
            <input v-model="form.ticket_release_time" placeholder="如：提前7天20:00放票" />
          </div>
          <div class="form-row">
            <label>开放时间</label>
            <input v-model="form.opening_hours" placeholder="如：08:30-17:00（16:00停止入场）" />
          </div>
          <div class="form-row">
            <label>闭馆日</label>
            <input v-model="form.closing_days" placeholder="如：每周一闭馆（法定节假日除外）" />
          </div>
          <div class="form-row">
            <label>票价信息</label>
            <input v-model="form.ticket_price" placeholder="如：旺季60元，淡季40元，学生半价" />
          </div>
          <div class="form-row">
            <label>游览路线</label>
            <input v-model="form.visitor_route" placeholder="如：午门进，神武门出" />
          </div>
          <div class="form-row">
            <label>每日限流</label>
            <input v-model="form.daily_limit" placeholder="如：每日限流8万人" />
          </div>
          <div class="form-row">
            <label>温馨提示</label>
            <textarea v-model="form.tips" rows="2" placeholder="其他需要提醒的信息"></textarea>
          </div>
          <div class="form-row">
            <label>预约链接</label>
            <input v-model="form.reservation_url" placeholder="https://..." />
          </div>
          <div class="form-row form-row-inline">
            <div class="form-item">
              <label>优先级 (0-100)</label>
              <input type="number" v-model.number="form.priority" min="0" max="100" />
            </div>
            <div class="form-item">
              <label>数据来源</label>
              <select v-model="form.source">
                <option value="manual">手动录入</option>
                <option value="ai_generated">AI生成</option>
                <option value="imported">批量导入</option>
              </select>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showModal = false">取消</button>
          <button class="btn-primary" @click="saveItem" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <div v-if="showDetail" class="modal-overlay" @click.self="showDetail = false">
      <div class="modal detail-modal">
        <div class="modal-header">
          <h3>📋 {{ detailData.attraction_name }} - 预约规则详情</h3>
          <button class="modal-close" @click="showDetail = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="detail-grid">
            <div class="detail-item" v-if="detailData.destination">
              <span class="detail-label">所属目的地</span>
              <span class="detail-value">{{ detailData.destination }}</span>
            </div>
            <div class="detail-item" v-if="detailData.reservation_channel">
              <span class="detail-label">预约渠道</span>
              <span class="detail-value">{{ detailData.reservation_channel }}</span>
            </div>
            <div class="detail-item" v-if="detailData.ticket_release_time">
              <span class="detail-label">放票时间</span>
              <span class="detail-value highlight">{{ detailData.ticket_release_time }}</span>
            </div>
            <div class="detail-item" v-if="detailData.opening_hours">
              <span class="detail-label">开放时间</span>
              <span class="detail-value">{{ detailData.opening_hours }}</span>
            </div>
            <div class="detail-item" v-if="detailData.closing_days">
              <span class="detail-label">闭馆日</span>
              <span class="detail-value warning">{{ detailData.closing_days }}</span>
            </div>
            <div class="detail-item" v-if="detailData.ticket_price">
              <span class="detail-label">票价信息</span>
              <span class="detail-value">{{ detailData.ticket_price }}</span>
            </div>
            <div class="detail-item" v-if="detailData.visitor_route">
              <span class="detail-label">游览路线</span>
              <span class="detail-value">{{ detailData.visitor_route }}</span>
            </div>
            <div class="detail-item" v-if="detailData.daily_limit">
              <span class="detail-label">每日限流</span>
              <span class="detail-value">{{ detailData.daily_limit }}</span>
            </div>
            <div class="detail-item" v-if="detailData.tips">
              <span class="detail-label">温馨提示</span>
              <span class="detail-value">{{ detailData.tips }}</span>
            </div>
            <div class="detail-item" v-if="detailData.reservation_url">
              <span class="detail-label">预约链接</span>
              <a :href="detailData.reservation_url" target="_blank" class="detail-value link">
                点击预约 →
              </a>
            </div>
            <div class="detail-item">
              <span class="detail-label">优先级</span>
              <span class="detail-value">{{ detailData.priority }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">数据来源</span>
              <span class="detail-value">{{ detailData.source }}</span>
            </div>
            <div class="detail-item" v-if="detailData.created_at">
              <span class="detail-label">创建时间</span>
              <span class="detail-value">{{ detailData.created_at }}</span>
            </div>
            <div class="detail-item" v-if="detailData.updated_at">
              <span class="detail-label">更新时间</span>
              <span class="detail-value">{{ detailData.updated_at }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const stats = ref(null)
const loading = ref(false)
const saving = ref(false)

const filter = ref({
  destination: '',
  keyword: ''
})

const showModal = ref(false)
const showDetail = ref(false)
const editingId = ref(null)
const detailData = ref({})
const fileInput = ref(null)

const form = ref({
  attraction_name: '',
  destination: '',
  reservation_channel: '',
  ticket_release_time: '',
  opening_hours: '',
  closing_days: '',
  ticket_price: '',
  visitor_route: '',
  daily_limit: '',
  tips: '',
  reservation_url: '',
  priority: 50,
  source: 'manual'
})

function getToken() {
  return localStorage.getItem('admin_token') || ''
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${getToken()}`,
    ...(options.headers || {})
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `请求失败(${res.status})`)
  }
  return res.json()
}

async function loadStats() {
  try {
    const res = await request('/admin/online-data/reservation-rules/stats')
    stats.value = res.data
  } catch (e) {
    console.error('加载统计失败:', e)
  }
}

async function loadData() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: page.value,
      size: pageSize.value,
      destination: filter.value.destination,
      keyword: filter.value.keyword
    })
    const res = await request(`/admin/online-data/reservation-rules?${params.toString()}`)
    list.value = res.data.list
    total.value = res.data.total
  } catch (e) {
    console.error('加载数据失败:', e)
    alert('加载数据失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

function resetFilter() {
  filter.value = { destination: '', keyword: '' }
  page.value = 1
  loadData()
}

function openModal(item = null) {
  if (item) {
    editingId.value = item.id
    form.value = { ...item }
  } else {
    editingId.value = null
    form.value = {
      attraction_name: '',
      destination: '',
      reservation_channel: '',
      ticket_release_time: '',
      opening_hours: '',
      closing_days: '',
      ticket_price: '',
      visitor_route: '',
      daily_limit: '',
      tips: '',
      reservation_url: '',
      priority: 50,
      source: 'manual'
    }
  }
  showModal.value = true
}

function viewDetail(item) {
  detailData.value = item
  showDetail.value = true
}

async function saveItem() {
  if (!form.value.attraction_name) {
    alert('请输入景点名称')
    return
  }

  saving.value = true
  try {
    if (editingId.value) {
      await request(`/admin/online-data/reservation-rules/${editingId.value}`, {
        method: 'PUT',
        body: JSON.stringify(form.value)
      })
      alert('更新成功')
    } else {
      await request('/admin/online-data/reservation-rules', {
        method: 'POST',
        body: JSON.stringify(form.value)
      })
      alert('创建成功')
    }
    showModal.value = false
    loadData()
    loadStats()
  } catch (e) {
    alert('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

async function deleteItem(id) {
  if (!confirm('确定要删除这条预约规则吗？')) return
  try {
    await request(`/admin/online-data/reservation-rules/${id}`, {
      method: 'DELETE'
    })
    alert('删除成功')
    loadData()
    loadStats()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

function exportData() {
  const destination = filter.value.destination || ''
  const url = `${API_BASE}/admin/online-data/reservation-rules/export?destination=${encodeURIComponent(destination)}`
  const token = getToken()
  fetch(url, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
  .then(res => res.blob())
  .then(blob => {
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `reservation_rules_${destination || 'all'}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  })
  .catch(e => alert('导出失败: ' + e.message))
}

function triggerImport() {
  fileInput.value.click()
}

async function handleImport(event) {
  const file = event.target.files[0]
  if (!file) return

  if (!confirm(`确定要导入文件「${file.name}」吗？已存在的数据将被跳过。`)) {
    event.target.value = ''
    return
  }

  const formData = new FormData()
  formData.append('file', file)

  try {
    const token = getToken()
    const res = await fetch(`${API_BASE}/admin/online-data/reservation-rules/import`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    })
    const data = await res.json()
    if (data.success) {
      alert(data.message)
      loadData()
      loadStats()
    } else {
      alert('导入失败: ' + (data.detail || '未知错误'))
    }
  } catch (e) {
    alert('导入失败: ' + e.message)
  } finally {
    event.target.value = ''
  }
}

onMounted(() => {
  loadStats()
  loadData()
})
</script>

<style scoped>
.reservation-rules-panel {
  padding: 20px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 10px;
}

.panel-header h2 {
  margin: 0;
  font-size: 20px;
}

.stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  font-size: 13px;
  color: #666;
}

.stat-item b {
  color: #1976d2;
}

.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: center;
}

.toolbar-spacer {
  flex: 1;
}

.toolbar input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
  min-width: 180px;
}

.btn-primary, .btn-secondary {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}

.btn-primary {
  background: #1976d2;
  color: white;
}

.btn-primary:hover {
  background: #1565c0;
}

.btn-secondary {
  background: #f5f5f5;
  color: #333;
  border: 1px solid #ddd;
}

.btn-secondary:hover {
  background: #eee;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  margin-right: 4px;
}

.btn-sm:hover {
  background: #f5f5f5;
}

.btn-danger {
  color: #d32f2f;
  border-color: #ffcdd2;
}

.btn-danger:hover {
  background: #ffebee;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.data-table th {
  background: #f5f5f5;
  padding: 12px;
  text-align: left;
  font-size: 13px;
  font-weight: 600;
  color: #333;
  border-bottom: 2px solid #e0e0e0;
}

.data-table td {
  padding: 10px 12px;
  font-size: 13px;
  border-bottom: 1px solid #f0f0f0;
}

.data-table tr:hover {
  background: #fafafa;
}

.name-cell {
  font-weight: 600;
  color: #1976d2;
}

.highlight {
  color: #e65100;
  font-weight: 500;
}

.warning {
  color: #d32f2f;
}

.empty-cell {
  text-align: center;
  color: #999;
  padding: 40px !important;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
  font-size: 13px;
}

.pagination button {
  padding: 6px 12px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 600px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.detail-modal {
  max-width: 700px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
}

.modal-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #999;
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid #eee;
}

.form-row {
  margin-bottom: 14px;
}

.form-row label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin-bottom: 6px;
}

.form-row .required {
  color: #d32f2f;
}

.form-row input,
.form-row textarea,
.form-row select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
  box-sizing: border-box;
}

.form-row input:focus,
.form-row textarea:focus {
  outline: none;
  border-color: #1976d2;
}

.form-row-inline {
  display: flex;
  gap: 16px;
}

.form-row-inline .form-item {
  flex: 1;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 12px;
  color: #999;
  font-weight: 500;
}

.detail-value {
  font-size: 14px;
  color: #333;
}

.detail-value.highlight {
  color: #e65100;
  font-weight: 600;
}

.detail-value.warning {
  color: #d32f2f;
}

.detail-value.link {
  color: #1976d2;
  text-decoration: none;
}

.detail-value.link:hover {
  text-decoration: underline;
}
</style>
