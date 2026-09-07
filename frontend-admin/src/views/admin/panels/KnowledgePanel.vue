<template>
  <div class="knowledge-panel">
    <div class="panel-header">
      <h2>📚 知识库管理（B端）</h2>
      <p class="subtitle">管理景点人文、历史名人、美食文化、旅行贴士等知识内容，支持人工干预（置顶、屏蔽、权重调整）</p>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid" v-if="stats">
      <div class="stat-card">
        <div class="stat-icon">📄</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total_docs }}</div>
          <div class="stat-label">知识文档总数</div>
        </div>
      </div>
      <div class="stat-card success">
        <div class="stat-icon">✅</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.published_docs }}</div>
          <div class="stat-label">已发布</div>
        </div>
      </div>
      <div class="stat-card warning">
        <div class="stat-icon">📝</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.draft_docs }}</div>
          <div class="stat-label">草稿</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📂</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.active_categories }}</div>
          <div class="stat-label">活跃分类</div>
        </div>
      </div>
    </div>

    <!-- Tab切换 -->
    <div class="tabs">
      <div :class="['tab', { active: activeTab === 'docs' }]" @click="activeTab = 'docs'">📄 文档管理</div>
      <div :class="['tab', { active: activeTab === 'categories' }]" @click="activeTab = 'categories'">📂 分类管理</div>
      <div :class="['tab', { active: activeTab === 'search' }]" @click="activeTab = 'search'">🔍 检索测试</div>
      <div :class="['tab', { active: activeTab === 'config' }]" @click="activeTab = 'config'">⚙️ 配置管理</div>
    </div>

    <!-- 文档管理 -->
    <div v-if="activeTab === 'docs'" class="tab-content">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <select v-model="filter.category_id" @change="loadDocs">
          <option value="">全部分类</option>
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
        <select v-model="filter.status" @change="loadDocs">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="published">已发布</option>
          <option value="offline">已下架</option>
        </select>
        <input v-model="filter.keyword" type="text" placeholder="🔍 搜索标题/内容/标签" @keyup.enter="loadDocs" />
        <button class="btn-primary" @click="showDocForm = true; editingDoc = null">➕ 新建文档</button>
        <button class="btn-secondary" @click="loadDocs">🔄 刷新</button>
      </div>

      <!-- 文档列表 -->
      <div class="doc-list" v-if="docs.length > 0">
        <div v-for="doc in docs" :key="doc.id" class="doc-card">
          <div class="doc-header">
            <span class="doc-title">{{ doc.title }}</span>
            <span :class="['status-badge', doc.status]">{{ statusText(doc.status) }}</span>
            <span v-if="doc.is_pinned" class="pin-badge">📌 置顶</span>
            <span v-if="doc.is_blocked" class="block-badge">🚫 屏蔽</span>
          </div>
          <div class="doc-meta">
            <span class="meta-item">📂 {{ doc.category_name }}</span>
            <span v-if="doc.related_poi" class="meta-item">📍 {{ doc.related_poi }}</span>
            <span v-if="doc.related_city" class="meta-item">🏙️ {{ doc.related_city }}</span>
            <span v-if="doc.tags" class="meta-item">🏷️ {{ doc.tags }}</span>
            <span class="meta-item">👁️ {{ doc.view_count }}</span>
            <span class="meta-item">🕐 {{ formatTime(doc.updated_at) }}</span>
          </div>
          <div class="doc-summary" v-if="doc.summary">{{ doc.summary }}</div>
          <div class="doc-actions">
            <button @click="editDoc(doc)">✏️ 编辑</button>
            <button @click="toggleStatus(doc)" v-if="doc.status === 'draft'">✅ 发布</button>
            <button @click="toggleStatus(doc)" v-else-if="doc.status === 'published'">📤 下架</button>
            <button @click="togglePin(doc)" v-if="!doc.is_pinned">📌 置顶</button>
            <button @click="togglePin(doc)" v-else>📌 取消置顶</button>
            <button @click="toggleBlock(doc)" v-if="!doc.is_blocked">🚫 屏蔽</button>
            <button @click="toggleBlock(doc)" v-else>✅ 取消屏蔽</button>
            <button class="btn-danger" @click="deleteDoc(doc)">🗑️ 删除</button>
          </div>
        </div>
      </div>
      <div v-else class="empty">暂无文档，点击"新建文档"开始创建</div>

      <!-- 分页 -->
      <div class="pagination" v-if="total > pageSize">
        <button @click="prevPage" :disabled="page <= 1">上一页</button>
        <span>第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条</span>
        <button @click="nextPage" :disabled="page >= totalPages">下一页</button>
      </div>
    </div>

    <!-- 分类管理 -->
    <div v-if="activeTab === 'categories'" class="tab-content">
      <div class="filter-bar">
        <button class="btn-primary" @click="showCategoryForm = true; editingCategory = null">➕ 新建分类</button>
        <button class="btn-secondary" @click="loadCategories">🔄 刷新</button>
      </div>
      <div class="category-list" v-if="categories.length > 0">
        <div v-for="cat in categories" :key="cat.id" class="category-card">
          <div class="category-info">
            <span class="category-name">{{ cat.name }}</span>
            <span class="category-code">{{ cat.code }}</span>
            <span class="category-desc">{{ cat.description }}</span>
          </div>
          <div class="category-actions">
            <button @click="editCategory(cat)">✏️ 编辑</button>
            <button @click="toggleCategoryActive(cat)" v-if="cat.is_active">❌ 禁用</button>
            <button @click="toggleCategoryActive(cat)" v-else>✅ 启用</button>
          </div>
        </div>
      </div>
      <div v-else class="empty">暂无分类</div>
    </div>

    <!-- 检索测试 -->
    <div v-if="activeTab === 'search'" class="tab-content">
      <div class="search-test-form">
        <div class="form-row">
          <label>关联POI：</label>
          <input v-model="searchTest.poi_name" type="text" placeholder="如：故宫、西湖" />
        </div>
        <div class="form-row">
          <label>关联城市：</label>
          <input v-model="searchTest.city" type="text" placeholder="如：北京、杭州" />
        </div>
        <div class="form-row">
          <label>关键词：</label>
          <input v-model="searchTest.keyword" type="text" placeholder="如：历史、文化" />
        </div>
        <div class="form-row">
          <label>分类：</label>
          <select v-model="searchTest.category_code">
            <option value="">全部分类</option>
            <option v-for="cat in categories" :key="cat.id" :value="cat.code">{{ cat.name }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>结果数：</label>
          <input v-model.number="searchTest.limit" type="number" min="1" max="20" />
        </div>
        <button class="btn-primary" @click="runSearchTest" :disabled="searchLoading">🔍 执行检索</button>
      </div>
      <div class="search-results" v-if="searchResults.length > 0">
        <h3>检索结果（{{ searchResults.length }}条）</h3>
        <div v-for="(doc, idx) in searchResults" :key="doc.id" class="search-result-item">
          <div class="result-rank">{{ idx + 1 }}</div>
          <div class="result-content">
            <div class="result-title">{{ doc.title }}</div>
            <div class="result-meta">
              <span>{{ doc.category_name }}</span>
              <span v-if="doc.is_pinned">📌 置顶</span>
              <span>权重：{{ doc.weight }}</span>
            </div>
            <div class="result-summary">{{ doc.summary }}</div>
          </div>
        </div>
      </div>
      <div v-else-if="searchPerformed" class="empty">未检索到相关知识</div>
    </div>

    <!-- 配置管理 -->
    <div v-if="activeTab === 'config'" class="tab-content">
      <div class="config-list" v-if="configs.length > 0">
        <div v-for="config in configs" :key="config.config_key" class="config-card">
          <div class="config-info">
            <span class="config-key">{{ config.config_key }}</span>
            <span class="config-desc">{{ config.description }}</span>
          </div>
          <div class="config-value">
            <input v-model="config.config_value" type="text" />
            <button class="btn-primary" @click="saveConfig(config)">💾 保存</button>
          </div>
        </div>
      </div>
      <div v-else class="empty">暂无配置</div>
    </div>

    <!-- 文档编辑弹窗 -->
    <div v-if="showDocForm" class="modal-overlay" @click.self="showDocForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingDoc ? '编辑文档' : '新建文档' }}</h3>
          <button class="modal-close" @click="showDocForm = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>分类：</label>
            <select v-model="docForm.category_id">
              <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>标题：</label>
            <input v-model="docForm.title" type="text" placeholder="文档标题" />
          </div>
          <div class="form-row">
            <label>摘要：</label>
            <textarea v-model="docForm.summary" rows="2" placeholder="内容摘要"></textarea>
          </div>
          <div class="form-row">
            <label>内容：</label>
            <textarea v-model="docForm.content" rows="8" placeholder="文档内容（支持Markdown）"></textarea>
          </div>
          <div class="form-row">
            <label>标签：</label>
            <input v-model="docForm.tags" type="text" placeholder="标签，逗号分隔" />
          </div>
          <div class="form-row">
            <label>关联POI：</label>
            <input v-model="docForm.related_poi" type="text" placeholder="关联景点名称，逗号分隔" />
          </div>
          <div class="form-row">
            <label>关联城市：</label>
            <input v-model="docForm.related_city" type="text" placeholder="关联城市" />
          </div>
          <div class="form-row">
            <label>状态：</label>
            <select v-model="docForm.status">
              <option value="draft">草稿</option>
              <option value="published">已发布</option>
              <option value="offline">已下架</option>
            </select>
          </div>
          <div class="form-row">
            <label>权重：</label>
            <input v-model.number="docForm.weight" type="number" min="0" max="100" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showDocForm = false">取消</button>
          <button class="btn-primary" @click="saveDoc" :disabled="saving">💾 保存</button>
        </div>
      </div>
    </div>

    <!-- 分类编辑弹窗 -->
    <div v-if="showCategoryForm" class="modal-overlay" @click.self="showCategoryForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingCategory ? '编辑分类' : '新建分类' }}</h3>
          <button class="modal-close" @click="showCategoryForm = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>名称：</label>
            <input v-model="categoryForm.name" type="text" placeholder="分类名称" />
          </div>
          <div class="form-row">
            <label>编码：</label>
            <input v-model="categoryForm.code" type="text" placeholder="分类编码（英文）" :disabled="editingCategory" />
          </div>
          <div class="form-row">
            <label>描述：</label>
            <textarea v-model="categoryForm.description" rows="2" placeholder="分类描述"></textarea>
          </div>
          <div class="form-row">
            <label>排序：</label>
            <input v-model.number="categoryForm.sort_order" type="number" min="0" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showCategoryForm = false">取消</button>
          <button class="btn-primary" @click="saveCategory" :disabled="saving">💾 保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'

const API_BASE = 'http://127.0.0.1:8000/api/admin/knowledge'

// 状态
const activeTab = ref('docs')
const loading = ref(false)
const saving = ref(false)
const searchLoading = ref(false)
const searchPerformed = ref(false)

// 统计
const stats = ref(null)

// 文档列表
const docs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

// 筛选
const filter = reactive({
  category_id: '',
  status: '',
  keyword: '',
})

// 分类
const categories = ref([])

// 配置
const configs = ref([])

// 检索测试
const searchTest = reactive({
  poi_name: '',
  city: '',
  keyword: '',
  category_code: '',
  limit: 5,
})
const searchResults = ref([])

// 文档编辑
const showDocForm = ref(false)
const editingDoc = ref(null)
const docForm = reactive({
  category_id: 1,
  title: '',
  summary: '',
  content: '',
  tags: '',
  related_poi: '',
  related_city: '',
  status: 'draft',
  weight: 0,
})

// 分类编辑
const showCategoryForm = ref(false)
const editingCategory = ref(null)
const categoryForm = reactive({
  name: '',
  code: '',
  description: '',
  sort_order: 0,
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
  if (res.code === 0) stats.value = res.data
}

async function loadDocs() {
  loading.value = true
  const params = new URLSearchParams()
  if (filter.category_id) params.append('category_id', filter.category_id)
  if (filter.status) params.append('status', filter.status)
  if (filter.keyword) params.append('keyword', filter.keyword)
  params.append('page', page.value)
  params.append('page_size', pageSize.value)
  const res = await request(`/docs?${params}`)
  if (res.code === 0) {
    docs.value = res.data.list
    total.value = res.data.total
  }
  loading.value = false
}

async function loadCategories() {
  const res = await request('/categories')
  if (res.code === 0) categories.value = res.data
}

async function loadConfigs() {
  const res = await request('/configs')
  if (res.code === 0) configs.value = res.data
}

function editDoc(doc) {
  editingDoc.value = doc
  Object.assign(docForm, {
    category_id: doc.category_id,
    title: doc.title,
    summary: doc.summary,
    content: doc.content,
    tags: doc.tags,
    related_poi: doc.related_poi,
    related_city: doc.related_city,
    status: doc.status,
    weight: doc.weight,
  })
  showDocForm.value = true
}

async function saveDoc() {
  saving.value = true
  if (editingDoc.value) {
    await request(`/docs/${editingDoc.value.id}`, {
      method: 'PUT',
      body: JSON.stringify(docForm),
    })
  } else {
    await request('/docs', {
      method: 'POST',
      body: JSON.stringify(docForm),
    })
  }
  saving.value = false
  showDocForm.value = false
  loadDocs()
  loadStats()
}

async function toggleStatus(doc) {
  const newStatus = doc.status === 'draft' ? 'published' : (doc.status === 'published' ? 'offline' : 'draft')
  await request(`/docs/${doc.id}`, {
    method: 'PUT',
    body: JSON.stringify({ status: newStatus }),
  })
  loadDocs()
  loadStats()
}

async function togglePin(doc) {
  await request(`/docs/${doc.id}`, {
    method: 'PUT',
    body: JSON.stringify({ is_pinned: !doc.is_pinned }),
  })
  loadDocs()
}

async function toggleBlock(doc) {
  await request(`/docs/${doc.id}`, {
    method: 'PUT',
    body: JSON.stringify({ is_blocked: !doc.is_blocked }),
  })
  loadDocs()
}

async function deleteDoc(doc) {
  if (!confirm(`确定要删除文档「${doc.title}」吗？`)) return
  await request(`/docs/${doc.id}`, { method: 'DELETE' })
  loadDocs()
  loadStats()
}

function editCategory(cat) {
  editingCategory.value = cat
  Object.assign(categoryForm, {
    name: cat.name,
    code: cat.code,
    description: cat.description,
    sort_order: cat.sort_order,
  })
  showCategoryForm.value = true
}

async function saveCategory() {
  saving.value = true
  if (editingCategory.value) {
    await request(`/categories/${editingCategory.value.id}`, {
      method: 'PUT',
      body: JSON.stringify(categoryForm),
    })
  } else {
    await request('/categories', {
      method: 'POST',
      body: JSON.stringify(categoryForm),
    })
  }
  saving.value = false
  showCategoryForm.value = false
  loadCategories()
}

async function toggleCategoryActive(cat) {
  await request(`/categories/${cat.id}`, {
    method: 'PUT',
    body: JSON.stringify({ is_active: !cat.is_active }),
  })
  loadCategories()
}

async function runSearchTest() {
  searchLoading.value = true
  searchPerformed.value = true
  const res = await request('/search-test', {
    method: 'POST',
    body: JSON.stringify(searchTest),
  })
  if (res.code === 0) searchResults.value = res.data.results
  searchLoading.value = false
}

async function saveConfig(config) {
  await request('/configs', {
    method: 'POST',
    body: JSON.stringify({
      config_key: config.config_key,
      config_value: config.config_value,
      description: config.description,
    }),
  })
  alert('配置保存成功')
}

function statusText(status) {
  return { draft: '草稿', published: '已发布', offline: '已下架' }[status] || status
}

function formatTime(time) {
  if (!time) return ''
  return new Date(time).toLocaleString('zh-CN')
}

function prevPage() {
  if (page.value > 1) {
    page.value--
    loadDocs()
  }
}

function nextPage() {
  if (page.value < totalPages.value) {
    page.value++
    loadDocs()
  }
}

onMounted(() => {
  loadStats()
  loadCategories()
  loadDocs()
  loadConfigs()
})
</script>

<style scoped>
.knowledge-panel {
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
.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  border-bottom: 2px solid #f0f0f0;
}
.tab {
  padding: 10px 20px;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  font-size: 14px;
  color: #666;
}
.tab.active {
  background: #e6f4ff;
  color: #1677ff;
  font-weight: 600;
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
.doc-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.doc-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.doc-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.doc-title {
  font-size: 16px;
  font-weight: 600;
  flex: 1;
}
.status-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.status-badge.draft {
  background: #f5f5f5;
  color: #666;
}
.status-badge.published {
  background: #f6ffed;
  color: #52c41a;
}
.status-badge.offline {
  background: #fff2f0;
  color: #ff4d4f;
}
.pin-badge {
  background: #fffbe6;
  color: #faad14;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.block-badge {
  background: #fff2f0;
  color: #ff4d4f;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.doc-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
  font-size: 13px;
  color: #666;
}
.doc-summary {
  color: #888;
  font-size: 13px;
  margin-bottom: 12px;
}
.doc-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.doc-actions button {
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.doc-actions button:hover {
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
.category-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.category-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.category-name {
  font-size: 16px;
  font-weight: 600;
  margin-right: 8px;
}
.category-code {
  background: #f5f5f5;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #666;
}
.category-desc {
  display: block;
  color: #888;
  font-size: 13px;
  margin-top: 4px;
}
.category-actions {
  display: flex;
  gap: 8px;
}
.category-actions button {
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.search-test-form {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
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
.search-results h3 {
  margin-bottom: 12px;
}
.search-result-item {
  display: flex;
  gap: 12px;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.result-rank {
  width: 28px;
  height: 28px;
  background: #1677ff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
}
.result-title {
  font-weight: 600;
  margin-bottom: 4px;
}
.result-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}
.result-summary {
  color: #888;
  font-size: 13px;
}
.config-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.config-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.config-key {
  font-family: monospace;
  font-weight: 600;
  margin-right: 12px;
}
.config-desc {
  color: #888;
  font-size: 13px;
}
.config-value {
  display: flex;
  gap: 8px;
}
.config-value input {
  padding: 6px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  width: 200px;
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
</style>
