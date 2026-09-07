<template>
  <div class="travel-tips-panel">
    <div class="panel-header">
      <h2>💡 避坑提示管理</h2>
      <div class="stats" v-if="stats">
        <span class="stat-item">总提示数: <b>{{ stats.total || 0 }}</b></span>
        <span class="stat-item">目的地数: <b>{{ stats.destinations || 0 }}</b></span>
        <span class="stat-item">高危提示: <b>{{ stats.danger_count || 0 }}</b></span>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" @click="showBatchModal = true">📥 批量添加</button>
        <button class="btn-primary" @click="openModal()">+ 新增提示</button>
      </div>
    </div>

    <!-- 搜索和筛选 -->
    <div class="toolbar">
      <input v-model="filter.destination" placeholder="目的地筛选（如：北京）" @keyup.enter="loadData" />
      <select v-model="filter.category" @change="loadData">
        <option value="">全部类别</option>
        <option value="general">通用</option>
        <option value="anti_fraud">防骗</option>
        <option value="reservation">预约</option>
        <option value="traffic">交通</option>
        <option value="food">美食</option>
        <option value="accommodation">住宿</option>
        <option value="weather">天气</option>
        <option value="safety">安全</option>
      </select>
      <select v-model="filter.severity" @change="loadData">
        <option value="">全部严重程度</option>
        <option value="info">信息</option>
        <option value="warning">警告</option>
        <option value="danger">危险</option>
      </select>
      <input v-model="filter.keyword" placeholder="关键词搜索" @keyup.enter="loadData" />
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
          <th>目的地</th>
          <th>提示内容</th>
          <th>类别</th>
          <th>严重程度</th>
          <th>排序权重</th>
          <th>验证人数</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in list" :key="item.id">
          <td>{{ item.id }}</td>
          <td>{{ item.destination }}</td>
          <td class="tip-cell">{{ item.tip }}</td>
          <td>
            <span :class="['category-tag', item.category]">
              {{ categoryMap[item.category] || item.category }}
            </span>
          </td>
          <td>
            <span :class="['severity-tag', item.severity]">
              {{ severityMap[item.severity] || item.severity }}
            </span>
          </td>
          <td>{{ item.sort_weight }}</td>
          <td>{{ item.frequency || 0 }}</td>
          <td>
            <button class="btn-sm" @click="openModal(item)">编辑</button>
            <button class="btn-sm btn-danger" @click="deleteItem(item.id)">删除</button>
          </td>
        </tr>
        <tr v-if="list.length === 0">
          <td colspan="8" class="empty-cell">暂无数据</td>
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
          <h3>{{ editingId ? '编辑避坑提示' : '新增避坑提示' }}</h3>
          <button class="modal-close" @click="showModal = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>所属目的地 <span class="required">*</span></label>
            <input v-model="form.destination" placeholder="如：北京" />
          </div>
          <div class="form-row">
            <label>提示内容 <span class="required">*</span></label>
            <textarea v-model="form.tip" rows="3" placeholder="请输入避坑提示内容"></textarea>
          </div>
          <div class="form-row form-row-inline">
            <div class="form-item">
              <label>类别</label>
              <select v-model="form.category">
                <option value="general">通用</option>
                <option value="anti_fraud">防骗</option>
                <option value="reservation">预约</option>
                <option value="traffic">交通</option>
                <option value="food">美食</option>
                <option value="accommodation">住宿</option>
                <option value="weather">天气</option>
                <option value="safety">安全</option>
              </select>
            </div>
            <div class="form-item">
              <label>严重程度</label>
              <select v-model="form.severity">
                <option value="info">信息（蓝色）</option>
                <option value="warning">警告（黄色）</option>
                <option value="danger">危险（红色）</option>
              </select>
            </div>
          </div>
          <div class="form-row form-row-inline">
            <div class="form-item">
              <label>排序权重 (0-100)</label>
              <input type="number" v-model.number="form.sort_weight" min="0" max="100" />
            </div>
            <div class="form-item">
              <label>验证人数</label>
              <input type="number" v-model.number="form.frequency" min="0" />
            </div>
          </div>
          <div class="form-row">
            <label>数据来源</label>
            <select v-model="form.source">
              <option value="manual">手动录入</option>
              <option value="ai_generated">AI生成</option>
              <option value="imported">批量导入</option>
              <option value="online_search">在线搜索</option>
            </select>
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

    <!-- 批量添加弹窗 -->
    <div v-if="showBatchModal" class="modal-overlay" @click.self="showBatchModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>📥 批量添加避坑提示</h3>
          <button class="modal-close" @click="showBatchModal = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>所属目的地 <span class="required">*</span></label>
            <input v-model="batchForm.destination" placeholder="如：北京" />
          </div>
          <div class="form-row">
            <label>提示内容（每行一条） <span class="required">*</span></label>
            <textarea v-model="batchForm.tipsText" rows="8" placeholder="每行输入一条避坑提示，例如：
不要参加路边的长城一日游，多为黑导游
北京地铁发达，景点间优先选择地铁出行
故宫需要提前7天预约，周一闭馆"></textarea>
          </div>
          <div class="form-row form-row-inline">
            <div class="form-item">
              <label>默认类别</label>
              <select v-model="batchForm.category">
                <option value="general">通用</option>
                <option value="anti_fraud">防骗</option>
                <option value="reservation">预约</option>
                <option value="traffic">交通</option>
                <option value="food">美食</option>
                <option value="accommodation">住宿</option>
                <option value="weather">天气</option>
                <option value="safety">安全</option>
              </select>
            </div>
            <div class="form-item">
              <label>默认严重程度</label>
              <select v-model="batchForm.severity">
                <option value="info">信息</option>
                <option value="warning">警告</option>
                <option value="danger">危险</option>
              </select>
            </div>
          </div>
          <div class="batch-preview" v-if="parsedBatchTips.length > 0">
            <div class="preview-title">预览（共 {{ parsedBatchTips.length }} 条）：</div>
            <div class="preview-list">
              <div v-for="(tip, idx) in parsedBatchTips" :key="idx" class="preview-item">
                {{ idx + 1 }}. {{ tip }}
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showBatchModal = false">取消</button>
          <button class="btn-primary" @click="batchSave" :disabled="batchSaving || parsedBatchTips.length === 0">
            {{ batchSaving ? '保存中...' : `批量添加 (${parsedBatchTips.length}条)` }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const categoryMap = {
  general: '通用',
  anti_fraud: '防骗',
  reservation: '预约',
  traffic: '交通',
  food: '美食',
  accommodation: '住宿',
  weather: '天气',
  safety: '安全'
}

const severityMap = {
  info: '信息',
  warning: '警告',
  danger: '危险'
}

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const stats = ref(null)
const loading = ref(false)
const saving = ref(false)
const batchSaving = ref(false)

const filter = ref({
  destination: '',
  category: '',
  severity: '',
  keyword: ''
})

const showModal = ref(false)
const showBatchModal = ref(false)
const editingId = ref(null)
const fileInput = ref(null)

const form = ref({
  destination: '',
  tip: '',
  category: 'general',
  severity: 'info',
  sort_weight: 50,
  source: 'manual',
  frequency: 0
})

const batchForm = ref({
  destination: '',
  tipsText: '',
  category: 'general',
  severity: 'info'
})

const parsedBatchTips = computed(() => {
  if (!batchForm.value.tipsText) return []
  return batchForm.value.tipsText
    .split('\n')
    .map(t => t.trim())
    .filter(t => t.length > 0)
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
    const res = await request('/admin/online-data/travel-tips/stats')
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
      category: filter.value.category,
      severity: filter.value.severity,
      keyword: filter.value.keyword
    })
    const res = await request(`/admin/online-data/travel-tips?${params.toString()}`)
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
  filter.value = { destination: '', category: '', severity: '', keyword: '' }
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
      destination: '',
      tip: '',
      category: 'general',
      severity: 'info',
      sort_weight: 50,
      source: 'manual',
      frequency: 0
    }
  }
  showModal.value = true
}

async function saveItem() {
  if (!form.value.destination || !form.value.tip) {
    alert('请填写目的地和提示内容')
    return
  }

  saving.value = true
  try {
    if (editingId.value) {
      await request(`/admin/online-data/travel-tips/${editingId.value}`, {
        method: 'PUT',
        body: JSON.stringify(form.value)
      })
      alert('更新成功')
    } else {
      await request('/admin/online-data/travel-tips', {
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

async function batchSave() {
  if (!batchForm.value.destination || parsedBatchTips.value.length === 0) {
    alert('请填写目的地和提示内容')
    return
  }

  batchSaving.value = true
  try {
    const tips = parsedBatchTips.value.map(tip => ({
      destination: batchForm.value.destination,
      tip: tip,
      category: batchForm.value.category,
      severity: batchForm.value.severity,
      sort_weight: 50,
      source: 'manual',
      frequency: 0
    }))

    await request('/admin/online-data/travel-tips/batch', {
      method: 'POST',
      body: JSON.stringify({ tips })
    })

    alert(`成功添加 ${parsedBatchTips.value.length} 条提示`)
    showBatchModal.value = false
    batchForm.value = { destination: '', tipsText: '', category: 'general', severity: 'info' }
    loadData()
    loadStats()
  } catch (e) {
    alert('批量添加失败: ' + e.message)
  } finally {
    batchSaving.value = false
  }
}

async function deleteItem(id) {
  if (!confirm('确定要删除这条避坑提示吗？')) return
  try {
    await request(`/admin/online-data/travel-tips/${id}`, {
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
  const category = filter.value.category || ''
  const url = `${API_BASE}/admin/online-data/travel-tips/export?destination=${encodeURIComponent(destination)}&category=${encodeURIComponent(category)}`
  const token = getToken()
  fetch(url, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
  .then(res => res.blob())
  .then(blob => {
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `travel_tips_${destination || 'all'}.csv`
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
    const res = await fetch(`${API_BASE}/admin/online-data/travel-tips/import`, {
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
.travel-tips-panel {
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
  color: #388e3c;
}

.header-actions {
  display: flex;
  gap: 10px;
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

.toolbar input,
.toolbar select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
  min-width: 140px;
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
  background: #388e3c;
  color: white;
}

.btn-primary:hover {
  background: #2e7d32;
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

.tip-cell {
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.category-tag.general { background: #e0e0e0; color: #424242; }
.category-tag.anti_fraud { background: #ffebee; color: #c62828; }
.category-tag.reservation { background: #fff3e0; color: #ef6c00; }
.category-tag.traffic { background: #e3f2fd; color: #1565c0; }
.category-tag.food { background: #fce4ec; color: #ad1457; }
.category-tag.accommodation { background: #f3e5f5; color: #6a1b9a; }
.category-tag.weather { background: #e1f5fe; color: #0277bd; }
.category-tag.safety { background: #ffebee; color: #b71c1c; }

.severity-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.severity-tag.info { background: #e3f2fd; color: #1565c0; }
.severity-tag.warning { background: #fff8e1; color: #f57f17; }
.severity-tag.danger { background: #ffebee; color: #c62828; }

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
  border-color: #388e3c;
}

.form-row-inline {
  display: flex;
  gap: 16px;
}

.form-row-inline .form-item {
  flex: 1;
}

.batch-preview {
  margin-top: 16px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 8px;
}

.preview-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.preview-list {
  max-height: 150px;
  overflow-y: auto;
}

.preview-item {
  font-size: 12px;
  color: #666;
  padding: 4px 0;
  border-bottom: 1px solid #eee;
}

.preview-item:last-child {
  border-bottom: none;
}
</style>
