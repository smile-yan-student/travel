<template>
  <div class="poi-hierarchy-panel">
    <div class="panel-header">
      <h2>🏛️ POI层级管理</h2>
      <p class="subtitle">管理主景点、内部子景点、周边附属景点的层级数据</p>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid" v-if="stats">
      <div class="stat-card">
        <div class="stat-icon">🏛️</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total_main }}</div>
          <div class="stat-label">主景点</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📍</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total_inner }}</div>
          <div class="stat-label">内部子景点</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">🍜</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total_nearby }}</div>
          <div class="stat-label">周边附属景点</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">⭐</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.large_scenic_count }}</div>
          <div class="stat-label">大型景区</div>
        </div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <select v-model="filter.city" @change="loadMainPois">
        <option value="">全部城市</option>
        <option v-for="city in cities" :key="city" :value="city">{{ city }}</option>
      </select>
      <select v-model="filter.level" @change="loadMainPois">
        <option value="">全部级别</option>
        <option value="5A">5A</option>
        <option value="4A">4A</option>
      </select>
      <input v-model="filter.keyword" type="text" placeholder="🔍 搜索景点名称" @keyup.enter="loadMainPois" />
      <button class="btn-primary" @click="showMainForm = true; editingMain = null">➕ 新建主景点</button>
      <button class="btn-secondary" @click="loadStats">🔄 刷新</button>
    </div>

    <!-- 主景点列表 -->
    <div class="poi-list" v-if="mainPois.length > 0">
      <div v-for="poi in mainPois" :key="poi.id" class="poi-card">
        <div class="poi-header">
          <span class="poi-name">{{ poi.name }}</span>
          <span v-if="poi.level" class="level-badge">{{ poi.level }}</span>
          <span v-if="poi.is_large_scenic" class="large-badge">大型景区</span>
          <span class="poi-city">{{ poi.city }}</span>
        </div>
        <div class="poi-meta">
          <span v-if="poi.district">📍 {{ poi.district }}</span>
          <span v-if="poi.recommended_duration">⏱️ {{ poi.recommended_duration }}分钟</span>
          <span v-if="poi.lng && poi.lat">🌐 {{ poi.lng }}, {{ poi.lat }}</span>
        </div>
        <div class="poi-desc" v-if="poi.description">{{ poi.description.substring(0, 100) }}...</div>
        <div class="poi-actions">
          <button @click="viewDetail(poi)">👁️ 详情</button>
          <button @click="editMain(poi)">✏️ 编辑</button>
          <button @click="toggleLargeScenic(poi)">
            {{ poi.is_large_scenic ? '取消大型景区' : '标记大型景区' }}
          </button>
          <button class="btn-danger" @click="deleteMain(poi)">🗑️ 删除</button>
        </div>
      </div>
    </div>
    <div v-else class="empty">暂无主景点数据</div>

    <!-- 分页 -->
    <div class="pagination" v-if="total > pageSize">
      <button @click="prevPage" :disabled="page <= 1">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条</span>
      <button @click="nextPage" :disabled="page >= totalPages">下一页</button>
    </div>

    <!-- 主景点详情弹窗 -->
    <div v-if="showDetail && currentPoi" class="modal-overlay" @click.self="showDetail = false">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3>{{ currentPoi.name }} - 详细信息</h3>
          <button class="modal-close" @click="showDetail = false">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-section">
            <h4>基本信息</h4>
            <div class="detail-grid">
              <div><strong>城市：</strong>{{ currentPoi.city }}</div>
              <div><strong>区县：</strong>{{ currentPoi.district }}</div>
              <div><strong>级别：</strong>{{ currentPoi.level || '无' }}</div>
              <div><strong>建议时长：</strong>{{ currentPoi.recommended_duration }}分钟</div>
              <div><strong>经纬度：</strong>{{ currentPoi.lng }}, {{ currentPoi.lat }}</div>
              <div><strong>大型景区：</strong>{{ currentPoi.is_large_scenic ? '是' : '否' }}</div>
            </div>
            <div v-if="currentPoi.description" class="detail-desc">
              <strong>描述：</strong>{{ currentPoi.description }}
            </div>
            <div v-if="currentPoi.best_time" class="detail-desc">
              <strong>最佳时间：</strong>{{ currentPoi.best_time }}
            </div>
          </div>

          <div class="detail-section">
            <h4>内部子景点（{{ innerPois.length }}个）</h4>
            <div class="inner-list">
              <div v-for="(inner, idx) in innerPois" :key="inner.id" class="inner-item">
                <span class="inner-order">{{ idx + 1 }}</span>
                <span class="inner-name">{{ inner.name }}</span>
                <span class="inner-duration">{{ inner.duration_min }}分钟</span>
                <span v-if="inner.must_see" class="must-see">必看</span>
              </div>
            </div>
          </div>

          <div class="detail-section">
            <h4>周边附属景点（{{ nearbyPois.length }}个）</h4>
            <div class="nearby-list">
              <div v-for="nearby in nearbyPois" :key="nearby.id" class="nearby-item">
                <span class="nearby-name">{{ nearby.name }}</span>
                <span class="nearby-cat">{{ nearby.category }}</span>
                <span class="nearby-dist">{{ (nearby.distance_m / 1000).toFixed(1) }}km</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 主景点编辑弹窗 -->
    <div v-if="showMainForm" class="modal-overlay" @click.self="showMainForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingMain ? '编辑主景点' : '新建主景点' }}</h3>
          <button class="modal-close" @click="showMainForm = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>名称：</label>
            <input v-model="mainForm.name" type="text" placeholder="景点名称" />
          </div>
          <div class="form-row">
            <label>城市：</label>
            <input v-model="mainForm.city" type="text" placeholder="所在城市" />
          </div>
          <div class="form-row">
            <label>区县：</label>
            <input v-model="mainForm.district" type="text" placeholder="所在区县" />
          </div>
          <div class="form-row">
            <label>级别：</label>
            <select v-model="mainForm.level">
              <option value="">无</option>
              <option value="5A">5A</option>
              <option value="4A">4A</option>
            </select>
          </div>
          <div class="form-row">
            <label>建议时长：</label>
            <input v-model.number="mainForm.recommended_duration" type="number" placeholder="分钟" />
          </div>
          <div class="form-row">
            <label>经度：</label>
            <input v-model.number="mainForm.lng" type="number" step="0.000001" placeholder="经度" />
          </div>
          <div class="form-row">
            <label>纬度：</label>
            <input v-model.number="mainForm.lat" type="number" step="0.000001" placeholder="纬度" />
          </div>
          <div class="form-row">
            <label>描述：</label>
            <textarea v-model="mainForm.description" rows="3" placeholder="景点描述"></textarea>
          </div>
          <div class="form-row">
            <label>最佳时间：</label>
            <input v-model="mainForm.best_time" type="text" placeholder="最佳游玩时间" />
          </div>
          <div class="form-row">
            <label>大型景区：</label>
            <input v-model="mainForm.is_large_scenic" type="checkbox" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showMainForm = false">取消</button>
          <button class="btn-primary" @click="saveMain" :disabled="saving">💾 保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'

const API_BASE = 'http://127.0.0.1:8000/api/admin/poi-hierarchy'

// 状态
const loading = ref(false)
const saving = ref(false)

// 统计
const stats = ref(null)

// 主景点列表
const mainPois = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

// 筛选
const filter = reactive({
  city: '',
  level: '',
  keyword: '',
})

// 城市列表
const cities = ref([])

// 详情
const showDetail = ref(false)
const currentPoi = ref(null)
const innerPois = ref([])
const nearbyPois = ref([])

// 编辑
const showMainForm = ref(false)
const editingMain = ref(null)
const mainForm = reactive({
  name: '',
  city: '',
  district: '',
  level: '',
  recommended_duration: 180,
  lng: null,
  lat: null,
  description: '',
  best_time: '',
  is_large_scenic: false,
})

// 方法
async function request(url, options = {}) {
  const token = localStorage.getItem('admin_token') || ''
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...options.headers,
  }
  const res = await fetch(`${API_BASE}${url}`, { ...options, headers })
  return res.json()
}

async function loadStats() {
  const res = await request('/stats')
  if (res.code === 0) {
    stats.value = res.data
    // 提取城市列表
    cities.value = [...new Set(mainPois.value.map(p => p.city))].sort()
  }
}

async function loadMainPois() {
  loading.value = true
  const params = new URLSearchParams()
  if (filter.city) params.append('city', filter.city)
  if (filter.level) params.append('level', filter.level)
  if (filter.keyword) params.append('keyword', filter.keyword)
  params.append('page', page.value)
  params.append('page_size', pageSize.value)
  const res = await request(`/main?${params}`)
  if (res.code === 0) {
    mainPois.value = res.data.list
    total.value = res.data.total
    // 更新城市列表
    const newCities = [...new Set([...cities.value, ...mainPois.value.map(p => p.city)])].sort()
    cities.value = newCities.filter(c => c)
  }
  loading.value = false
}

async function viewDetail(poi) {
  const res = await request(`/main/${poi.id}`)
  if (res.code === 0) {
    currentPoi.value = res.data
    innerPois.value = res.data.inner_route || []
    nearbyPois.value = res.data.nearby_attractions || []
    showDetail.value = true
  }
}

function editMain(poi) {
  editingMain.value = poi
  Object.assign(mainForm, {
    name: poi.name,
    city: poi.city,
    district: poi.district,
    level: poi.level,
    recommended_duration: poi.recommended_duration,
    lng: poi.lng,
    lat: poi.lat,
    description: poi.description,
    best_time: poi.best_time,
    is_large_scenic: poi.is_large_scenic,
  })
  showMainForm.value = true
}

async function saveMain() {
  saving.value = true
  if (editingMain.value) {
    await request(`/main/${editingMain.value.id}`, {
      method: 'PUT',
      body: JSON.stringify(mainForm),
    })
  } else {
    await request('/main', {
      method: 'POST',
      body: JSON.stringify(mainForm),
    })
  }
  saving.value = false
  showMainForm.value = false
  loadMainPois()
  loadStats()
}

async function toggleLargeScenic(poi) {
  await request(`/main/${poi.id}`, {
    method: 'PUT',
    body: JSON.stringify({ is_large_scenic: !poi.is_large_scenic }),
  })
  poi.is_large_scenic = !poi.is_large_scenic
  loadStats()
}

async function deleteMain(poi) {
  if (!confirm(`确定要删除「${poi.name}」吗？这将同时删除其内部子景点和周边附属景点。`)) return
  await request(`/main/${poi.id}`, { method: 'DELETE' })
  loadMainPois()
  loadStats()
}

function prevPage() {
  if (page.value > 1) {
    page.value--
    loadMainPois()
  }
}

function nextPage() {
  if (page.value < totalPages.value) {
    page.value++
    loadMainPois()
  }
}

onMounted(() => {
  loadStats()
  loadMainPois()
})
</script>

<style scoped>
.poi-hierarchy-panel {
  padding: 20px;
}
.panel-header {
  margin-bottom: 20px;
}
.panel-header h2 {
  margin: 0 0 8px 0;
  font-size: 22px;
}
.subtitle {
  color: #666;
  font-size: 14px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.stat-icon {
  font-size: 32px;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
}
.stat-label {
  color: #666;
  font-size: 13px;
}
.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.filter-bar select,
.filter-bar input {
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
}
.btn-primary {
  background: #1677ff;
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.btn-primary:hover {
  background: #4096ff;
}
.btn-secondary {
  background: #f5f5f5;
  color: #333;
  border: 1px solid #d9d9d9;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.btn-danger {
  background: #fff2f0;
  color: #ff4d4f;
  border: 1px solid #ffccc7;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.poi-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.poi-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.poi-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.poi-name {
  font-size: 16px;
  font-weight: 600;
  flex: 1;
}
.level-badge {
  background: #f6ffed;
  color: #52c41a;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.large-badge {
  background: #fffbe6;
  color: #faad14;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.poi-city {
  color: #666;
  font-size: 13px;
}
.poi-meta {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}
.poi-desc {
  color: #888;
  font-size: 13px;
  margin-bottom: 12px;
  line-height: 1.5;
}
.poi-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.poi-actions button {
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.poi-actions button:hover {
  background: #e6f4ff;
  color: #1677ff;
}
.empty {
  text-align: center;
  padding: 40px;
  color: #999;
}
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 20px;
}
.pagination button {
  padding: 6px 12px;
  border: 1px solid #d9d9d9;
  background: #fff;
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
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal {
  background: #fff;
  border-radius: 12px;
  width: 600px;
  max-height: 80vh;
  overflow-y: auto;
}
.modal-large {
  width: 800px;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
}
.modal-header h3 {
  margin: 0;
}
.modal-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
}
.modal-body {
  padding: 20px;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid #f0f0f0;
}
.form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.form-row label {
  width: 100px;
  text-align: right;
  color: #666;
}
.form-row input,
.form-row select,
.form-row textarea {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
}
.detail-section {
  margin-bottom: 20px;
}
.detail-section h4 {
  margin: 0 0 12px 0;
  color: #333;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 8px;
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  font-size: 14px;
}
.detail-desc {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #555;
}
.inner-list,
.nearby-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.inner-item,
.nearby-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #f9f9f9;
  border-radius: 6px;
  font-size: 14px;
}
.inner-order {
  width: 24px;
  height: 24px;
  background: #1677ff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}
.inner-name,
.nearby-name {
  flex: 1;
  font-weight: 500;
}
.inner-duration,
.nearby-dist {
  color: #666;
  font-size: 13px;
}
.nearby-cat {
  background: #e6f4ff;
  color: #1677ff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.must-see {
  background: #fffbe6;
  color: #faad14;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}
</style>
