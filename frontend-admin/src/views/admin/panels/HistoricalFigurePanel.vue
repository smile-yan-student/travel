<template>
  <div class="historical-figure-panel">
    <div class="panel-header">
      <h2>📖 历史名人管理</h2>
      <p class="subtitle">管理历史名人、革命先辈、文人墨客及其相关旅行地</p>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid" v-if="stats">
      <div class="stat-card">
        <div class="stat-icon">👤</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total_figures }}</div>
          <div class="stat-label">历史名人</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📍</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total_places }}</div>
          <div class="stat-label">相关地点</div>
        </div>
      </div>
      <div class="stat-card" v-for="cat in stats.category_distribution" :key="cat.category">
        <div class="stat-icon">{{ getCategoryIcon(cat.category) }}</div>
        <div class="stat-info">
          <div class="stat-value">{{ cat.count }}</div>
          <div class="stat-label">{{ cat.category }}</div>
        </div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <select v-model="filter.category" @change="loadFigures">
        <option value="">全部分类</option>
        <option value="革命先辈">革命先辈</option>
        <option value="历史名人">历史名人</option>
        <option value="文人墨客">文人墨客</option>
      </select>
      <input v-model="filter.keyword" type="text" placeholder="🔍 搜索人物名称或简介" @keyup.enter="loadFigures" />
      <button class="btn-primary" @click="showForm = true; editing = null">➕ 新建人物</button>
      <button class="btn-secondary" @click="loadStats">🔄 刷新</button>
    </div>

    <!-- 人物列表 -->
    <div class="figure-list" v-if="figures.length > 0">
      <div v-for="figure in figures" :key="figure.id" class="figure-card">
        <div class="figure-header">
          <span class="figure-name">{{ figure.name }}</span>
          <span class="category-badge" :class="getCategoryClass(figure.category)">
            {{ figure.category }}
          </span>
        </div>
        <div class="figure-aliases" v-if="figure.aliases && figure.aliases.length > 0">
          别名：{{ figure.aliases.join('、') }}
        </div>
        <div class="figure-intro">{{ figure.brief_intro.substring(0, 80) }}...</div>
        <div class="figure-theme" v-if="figure.travel_theme">
          🎯 {{ figure.travel_theme }}
        </div>
        <div class="figure-actions">
          <button @click="viewDetail(figure)">👁️ 详情</button>
          <button @click="editFigure(figure)">✏️ 编辑</button>
          <button class="btn-danger" @click="deleteFigure(figure)">🗑️ 删除</button>
        </div>
      </div>
    </div>
    <div v-else class="empty">暂无历史名人数据</div>

    <!-- 分页 -->
    <div class="pagination" v-if="total > pageSize">
      <button @click="prevPage" :disabled="page <= 1">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条</span>
      <button @click="nextPage" :disabled="page >= totalPages">下一页</button>
    </div>

    <!-- 详情弹窗 -->
    <div v-if="showDetail && currentFigure" class="modal-overlay" @click.self="showDetail = false">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3>{{ currentFigure.name }} - 详细信息</h3>
          <button class="modal-close" @click="showDetail = false">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-section">
            <h4>基本信息</h4>
            <div class="detail-grid">
              <div><strong>分类：</strong>{{ currentFigure.category }}</div>
              <div><strong>旅行主题：</strong>{{ currentFigure.travel_theme }}</div>
            </div>
            <div v-if="currentFigure.aliases && currentFigure.aliases.length > 0" class="detail-desc">
              <strong>别名：</strong>{{ currentFigure.aliases.join('、') }}
            </div>
            <div class="detail-desc">
              <strong>简介：</strong>{{ currentFigure.brief_intro }}
            </div>
          </div>

          <div class="detail-section">
            <h4>相关旅行地（{{ currentFigure.related_places.length }}个）</h4>
            <div class="place-list">
              <div v-for="place in currentFigure.related_places" :key="place.id" class="place-card">
                <div class="place-header">
                  <span class="place-name">📍 {{ place.place_name }}</span>
                  <span class="place-relation">{{ place.relation }}</span>
                </div>
                <div class="place-recommendation">{{ place.travel_recommendation }}</div>
                <div class="place-attractions" v-if="place.attractions && place.attractions.length > 0">
                  🏛️ 必去景点：{{ place.attractions.join('、') }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3>{{ editing ? '编辑历史名人' : '新建历史名人' }}</h3>
          <button class="modal-close" @click="showForm = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>名称：</label>
            <input v-model="form.name" type="text" placeholder="人物名称" />
          </div>
          <div class="form-row">
            <label>分类：</label>
            <select v-model="form.category">
              <option value="历史名人">历史名人</option>
              <option value="革命先辈">革命先辈</option>
              <option value="文人墨客">文人墨客</option>
            </select>
          </div>
          <div class="form-row">
            <label>别名：</label>
            <input v-model="aliasesInput" type="text" placeholder="多个别名用逗号分隔" />
          </div>
          <div class="form-row">
            <label>旅行主题：</label>
            <input v-model="form.travel_theme" type="text" placeholder="相关的旅行主题" />
          </div>
          <div class="form-row">
            <label>简介：</label>
            <textarea v-model="form.brief_intro" rows="3" placeholder="人物简介"></textarea>
          </div>

          <div class="places-section">
            <div class="places-header">
              <h4>相关旅行地</h4>
              <button class="btn-primary btn-small" @click="addPlace">➕ 添加地点</button>
            </div>
            <div v-for="(place, idx) in form.related_places" :key="idx" class="place-form">
              <div class="place-form-row">
                <input v-model="place.place_name" type="text" placeholder="地名" style="flex: 1" />
                <input v-model="place.relation" type="text" placeholder="关系（出生地/主要活动地/纪念地）" style="flex: 1" />
                <button class="btn-danger btn-small" @click="removePlace(idx)">×</button>
              </div>
              <div class="place-form-row">
                <input v-model="place.attractionsInput" type="text" placeholder="必去景点（多个用逗号分隔）" style="flex: 1" />
              </div>
              <div class="place-form-row">
                <textarea v-model="place.travel_recommendation" rows="2" placeholder="出行推荐介绍" style="flex: 1"></textarea>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showForm = false">取消</button>
          <button class="btn-primary" @click="saveFigure" :disabled="saving">💾 保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'

const API_BASE = 'http://127.0.0.1:8000/api/admin/historical-figures'

// 状态
const loading = ref(false)
const saving = ref(false)

// 统计
const stats = ref(null)

// 列表
const figures = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

// 筛选
const filter = reactive({
  category: '',
  keyword: '',
})

// 详情
const showDetail = ref(false)
const currentFigure = ref(null)

// 编辑
const showForm = ref(false)
const editing = ref(null)
const aliasesInput = ref('')
const form = reactive({
  name: '',
  category: '历史名人',
  brief_intro: '',
  travel_theme: '',
  related_places: [],
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

function getCategoryIcon(category) {
  const icons = {
    '革命先辈': '🚩',
    '历史名人': '👤',
    '文人墨客': '📝',
  }
  return icons[category] || '👤'
}

function getCategoryClass(category) {
  const classes = {
    '革命先辈': 'cat-revolution',
    '历史名人': 'cat-historical',
    '文人墨客': 'cat-literary',
  }
  return classes[category] || 'cat-historical'
}

async function loadStats() {
  const res = await request('/stats')
  if (res.code === 0) {
    stats.value = res.data
  }
}

async function loadFigures() {
  loading.value = true
  const params = new URLSearchParams()
  if (filter.category) params.append('category', filter.category)
  if (filter.keyword) params.append('keyword', filter.keyword)
  params.append('page', page.value)
  params.append('page_size', pageSize.value)
  const res = await request(`?${params}`)
  if (res.code === 0) {
    figures.value = res.data.list
    total.value = res.data.total
  }
  loading.value = false
}

async function viewDetail(figure) {
  const res = await request(`/${figure.id}`)
  if (res.code === 0) {
    currentFigure.value = res.data
    showDetail.value = true
  }
}

function editFigure(figure) {
  editing.value = figure
  form.name = figure.name
  form.category = figure.category
  form.brief_intro = figure.brief_intro
  form.travel_theme = figure.travel_theme
  aliasesInput.value = (figure.aliases || []).join(',')
  form.related_places = (figure.related_places || []).map(p => ({
    place_name: p.place_name,
    relation: p.relation,
    attractionsInput: (p.attractions || []).join(','),
    travel_recommendation: p.travel_recommendation,
  }))
  showForm.value = true
}

function addPlace() {
  form.related_places.push({
    place_name: '',
    relation: '',
    attractionsInput: '',
    travel_recommendation: '',
  })
}

function removePlace(idx) {
  form.related_places.splice(idx, 1)
}

async function saveFigure() {
  saving.value = true
  const payload = {
    name: form.name,
    category: form.category,
    aliases: aliasesInput.value.split(',').map(s => s.trim()).filter(s => s),
    brief_intro: form.brief_intro,
    travel_theme: form.travel_theme,
    related_places: form.related_places.map(p => ({
      place_name: p.place_name,
      relation: p.relation,
      attractions: p.attractionsInput.split(',').map(s => s.trim()).filter(s => s),
      travel_recommendation: p.travel_recommendation,
    })),
  }
  if (editing.value) {
    await request(`/${editing.value.id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  } else {
    await request('', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }
  saving.value = false
  showForm.value = false
  loadFigures()
  loadStats()
}

async function deleteFigure(figure) {
  if (!confirm(`确定要删除「${figure.name}」吗？`)) return
  await request(`/${figure.id}`, { method: 'DELETE' })
  loadFigures()
  loadStats()
}

function prevPage() {
  if (page.value > 1) {
    page.value--
    loadFigures()
  }
}

function nextPage() {
  if (page.value < totalPages.value) {
    page.value++
    loadFigures()
  }
}

onMounted(() => {
  loadStats()
  loadFigures()
})
</script>

<style scoped>
.historical-figure-panel {
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
.btn-small {
  padding: 4px 8px;
  font-size: 12px;
}
.figure-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.figure-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.figure-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.figure-name {
  font-size: 16px;
  font-weight: 600;
  flex: 1;
}
.category-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.cat-revolution {
  background: #fff1f0;
  color: #f5222d;
}
.cat-historical {
  background: #f6ffed;
  color: #52c41a;
}
.cat-literary {
  background: #e6f4ff;
  color: #1677ff;
}
.figure-aliases {
  color: #888;
  font-size: 13px;
  margin-bottom: 8px;
}
.figure-intro {
  color: #666;
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 8px;
}
.figure-theme {
  color: #faad14;
  font-size: 13px;
  margin-bottom: 12px;
}
.figure-actions {
  display: flex;
  gap: 8px;
}
.figure-actions button {
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.figure-actions button:hover {
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
.places-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}
.places-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.places-header h4 {
  margin: 0;
}
.place-form {
  background: #f9f9f9;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 12px;
}
.place-form-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
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
.place-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.place-card {
  background: #f9f9f9;
  padding: 12px;
  border-radius: 8px;
}
.place-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.place-name {
  font-weight: 600;
  font-size: 15px;
}
.place-relation {
  color: #1677ff;
  font-size: 13px;
  background: #e6f4ff;
  padding: 2px 8px;
  border-radius: 4px;
}
.place-recommendation {
  color: #666;
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 8px;
}
.place-attractions {
  color: #faad14;
  font-size: 13px;
}
</style>
