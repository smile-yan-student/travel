<template>
  <div class="major-attractions-panel">
    <div class="panel-header">
      <h2>🏛️ 主要景点库管理</h2>
      <div class="header-actions">
        <button class="btn btn-primary" @click="showAddModal = true">+ 添加景点</button>
        <button class="btn" @click="loadStats">刷新统计</button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-cards" v-if="stats">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total || 0 }}</div>
        <div class="stat-label">总景点数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.must_visit_count || 0 }}</div>
        <div class="stat-label">必去景点</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.hot_count || 0 }}</div>
        <div class="stat-label">热门景点</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.city_count || 0 }}</div>
        <div class="stat-label">覆盖城市</div>
      </div>
    </div>

    <!-- 搜索和筛选 -->
    <div class="filter-bar">
      <input
        v-model="filters.keyword"
        type="text"
        placeholder="搜索景点名称或描述..."
        class="filter-input"
        @keyup.enter="loadAttractions"
      />
      <input
        v-model="filters.city"
        type="text"
        placeholder="城市"
        class="filter-input"
      />
      <select v-model="filters.category" class="filter-select">
        <option value="">全部分类</option>
        <option value="景点">景点</option>
        <option value="美食">美食</option>
        <option value="购物">购物</option>
        <option value="夜生活">夜生活</option>
      </select>
      <select v-model="filters.level" class="filter-select">
        <option value="">全部等级</option>
        <option value="5A">5A</option>
        <option value="4A">4A</option>
        <option value="3A">3A</option>
      </select>
      <button class="btn btn-primary" @click="loadAttractions">搜索</button>
      <button class="btn" @click="resetFilters">重置</button>
    </div>

    <!-- 景点列表 -->
    <div class="attractions-table">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>名称</th>
            <th>城市</th>
            <th>分类</th>
            <th>等级</th>
            <th>必去</th>
            <th>热门</th>
            <th>推荐时长</th>
            <th>优先级</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="attr in attractions" :key="attr.id">
            <td>{{ attr.id }}</td>
            <td class="name-cell">{{ attr.name }}</td>
            <td>{{ attr.city }}</td>
            <td>{{ attr.category }}</td>
            <td>{{ attr.level || '-' }}</td>
            <td>
              <span :class="['badge', attr.must_visit ? 'badge-success' : 'badge-default']">
                {{ attr.must_visit ? '是' : '否' }}
              </span>
            </td>
            <td>
              <span :class="['badge', attr.hot ? 'badge-warning' : 'badge-default']">
                {{ attr.hot ? '是' : '否' }}
              </span>
            </td>
            <td>{{ attr.recommended_duration }}分钟</td>
            <td>{{ attr.priority }}</td>
            <td class="actions-cell">
              <button class="btn btn-small" @click="editAttraction(attr)">编辑</button>
              <button class="btn btn-small btn-danger" @click="deleteAttraction(attr)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="attractions.length === 0" class="empty-state">
        暂无数据
      </div>
    </div>

    <!-- 分页 -->
    <div class="pagination" v-if="total > 0">
      <span>共 {{ total }} 条</span>
      <button class="btn btn-small" :disabled="page === 1" @click="page--; loadAttractions()">上一页</button>
      <span>第 {{ page }} 页</span>
      <button class="btn btn-small" :disabled="page * size >= total" @click="page++; loadAttractions()">下一页</button>
    </div>

    <!-- 添加/编辑弹窗 -->
    <div v-if="showAddModal || showEditModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ showEditModal ? '编辑景点' : '添加景点' }}</h3>
          <button class="close-btn" @click="closeModal">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <div class="form-group">
              <label>景点名称 *</label>
              <input v-model="form.name" type="text" class="form-input" />
            </div>
            <div class="form-group">
              <label>城市 *</label>
              <input v-model="form.city" type="text" class="form-input" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>区县</label>
              <input v-model="form.district" type="text" class="form-input" />
            </div>
            <div class="form-group">
              <label>省份</label>
              <input v-model="form.province" type="text" class="form-input" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>分类</label>
              <select v-model="form.category" class="form-input">
                <option value="景点">景点</option>
                <option value="美食">美食</option>
                <option value="购物">购物</option>
                <option value="夜生活">夜生活</option>
              </select>
            </div>
            <div class="form-group">
              <label>等级</label>
              <select v-model="form.level" class="form-input">
                <option value="">无</option>
                <option value="5A">5A</option>
                <option value="4A">4A</option>
                <option value="3A">3A</option>
              </select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>推荐时长（分钟）</label>
              <input v-model.number="form.recommended_duration" type="number" class="form-input" />
            </div>
            <div class="form-group">
              <label>优先级（0-100）</label>
              <input v-model.number="form.priority" type="number" class="form-input" min="0" max="100" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>经度</label>
              <input v-model.number="form.lng" type="number" step="0.000001" class="form-input" />
            </div>
            <div class="form-group">
              <label>纬度</label>
              <input v-model.number="form.lat" type="number" step="0.000001" class="form-input" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group checkbox-group">
              <label>
                <input v-model="form.must_visit" type="checkbox" />
                必去景点
              </label>
            </div>
            <div class="form-group checkbox-group">
              <label>
                <input v-model="form.hot" type="checkbox" />
                热门景点
              </label>
            </div>
          </div>
          <div class="form-group">
            <label>描述</label>
            <textarea v-model="form.description" class="form-textarea" rows="3"></textarea>
          </div>
          <div class="form-group">
            <label>最佳游览时间</label>
            <input v-model="form.best_time" type="text" class="form-input" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="closeModal">取消</button>
          <button class="btn btn-primary" @click="saveAttraction">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  token: String,
  userRole: String,
})

const API_BASE = 'http://127.0.0.1:8000/api/admin/major-attractions'

// 状态
const attractions = ref([])
const stats = ref(null)
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)

// 筛选条件
const filters = ref({
  keyword: '',
  city: '',
  category: '',
  level: '',
})

// 弹窗状态
const showAddModal = ref(false)
const showEditModal = ref(false)
const editingId = ref(null)

// 表单数据
const form = ref({
  name: '',
  city: '',
  district: '',
  province: '',
  category: '景点',
  level: '',
  description: '',
  recommended_duration: 120,
  lng: null,
  lat: null,
  must_visit: true,
  hot: false,
  best_time: '',
  priority: 50,
})

// 加载统计
async function loadStats() {
  try {
    const res = await fetch(`${API_BASE}/stats/overview`, {
      headers: { Authorization: `Bearer ${props.token}` },
    })
    const data = await res.json()
    stats.value = data.data
  } catch (e) {
    console.error('加载统计失败', e)
  }
}

// 加载景点列表
async function loadAttractions() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: page.value,
      size: size.value,
    })
    if (filters.value.keyword) params.append('keyword', filters.value.keyword)
    if (filters.value.city) params.append('city', filters.value.city)
    if (filters.value.category) params.append('category', filters.value.category)
    if (filters.value.level) params.append('level', filters.value.level)

    const res = await fetch(`${API_BASE}?${params}`, {
      headers: { Authorization: `Bearer ${props.token}` },
    })
    const data = await res.json()
    attractions.value = data.data.list
    total.value = data.data.total
  } catch (e) {
    console.error('加载景点列表失败', e)
  } finally {
    loading.value = false
  }
}

// 重置筛选
function resetFilters() {
  filters.value = { keyword: '', city: '', category: '', level: '' }
  page.value = 1
  loadAttractions()
}

// 编辑景点
function editAttraction(attr) {
  editingId.value = attr.id
  form.value = { ...attr }
  showEditModal.value = true
}

// 删除景点
async function deleteAttraction(attr) {
  if (!confirm(`确定要删除「${attr.name}」吗？`)) return
  try {
    const res = await fetch(`${API_BASE}/${attr.id}?soft_delete=true`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${props.token}` },
    })
    if (res.ok) {
      alert('删除成功')
      loadAttractions()
      loadStats()
    }
  } catch (e) {
    console.error('删除失败', e)
    alert('删除失败')
  }
}

// 保存景点
async function saveAttraction() {
  if (!form.value.name || !form.value.city) {
    alert('请填写景点名称和城市')
    return
  }

  try {
    const url = showEditModal.value ? `${API_BASE}/${editingId.value}` : API_BASE
    const method = showEditModal.value ? 'PUT' : 'POST'

    const res = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${props.token}`,
      },
      body: JSON.stringify(form.value),
    })

    if (res.ok) {
      alert(showEditModal.value ? '更新成功' : '添加成功')
      closeModal()
      loadAttractions()
      loadStats()
    } else {
      const data = await res.json()
      alert(data.detail || '保存失败')
    }
  } catch (e) {
    console.error('保存失败', e)
    alert('保存失败')
  }
}

// 关闭弹窗
function closeModal() {
  showAddModal.value = false
  showEditModal.value = false
  editingId.value = null
  form.value = {
    name: '',
    city: '',
    district: '',
    province: '',
    category: '景点',
    level: '',
    description: '',
    recommended_duration: 120,
    lng: null,
    lat: null,
    must_visit: true,
    hot: false,
    best_time: '',
    priority: 50,
  }
}

onMounted(() => {
  loadStats()
  loadAttractions()
})
</script>

<style scoped>
.major-attractions-panel {
  padding: 20px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.panel-header h2 {
  margin: 0;
  font-size: 20px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #1a73e8;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 5px;
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.filter-input,
.filter-select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.filter-input {
  flex: 1;
  min-width: 200px;
}

.btn {
  padding: 8px 16px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 14px;
}

.btn:hover {
  background: #f5f5f5;
}

.btn-primary {
  background: #1a73e8;
  color: white;
  border-color: #1a73e8;
}

.btn-primary:hover {
  background: #1557b0;
}

.btn-danger {
  color: #dc3545;
  border-color: #dc3545;
}

.btn-small {
  padding: 4px 8px;
  font-size: 12px;
}

.attractions-table {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

th {
  background: #f8f9fa;
  font-weight: 600;
  font-size: 13px;
  color: #555;
}

.name-cell {
  font-weight: 500;
}

.badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}

.badge-success {
  background: #d4edda;
  color: #155724;
}

.badge-warning {
  background: #fff3cd;
  color: #856404;
}

.badge-default {
  background: #e2e3e5;
  color: #383d41;
}

.actions-cell {
  display: flex;
  gap: 5px;
}

.empty-state {
  padding: 40px;
  text-align: center;
  color: #999;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 15px;
  margin-top: 20px;
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
  border-radius: 8px;
  width: 90%;
  max-width: 700px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
}

.modal-body {
  padding: 20px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  margin-bottom: 15px;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-size: 14px;
  font-weight: 500;
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-textarea {
  resize: vertical;
}

.checkbox-group label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 20px;
  border-top: 1px solid #eee;
}
</style>
