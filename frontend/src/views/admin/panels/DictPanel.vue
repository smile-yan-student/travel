<template>
  <div class="dict-panel">
    <div class="panel-header">
      <h2>📚 字典数据管理</h2>
      <div class="stats">
        <span class="stat-item" v-for="(v, k) in stats" :key="k">
          {{ labelMap[k] }}: <b>{{ v }}</b>
        </span>
      </div>
      <button class="btn-clear" @click="clearCache">🔄 清除缓存</button>
    </div>

    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab', { active: currentTab === tab.key }]"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 必去景点 -->
    <div v-if="currentTab === 'must_visit'" class="tab-content">
      <div class="toolbar">
        <input v-model="mvFilter.city" placeholder="城市筛选" @keyup.enter="loadMustVisit" />
        <button class="btn-primary" @click="openMvModal()">+ 新增必去景点</button>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th><th>城市</th><th>名称</th><th>类别</th><th>评分</th><th>优先级</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in mvList" :key="item.id">
            <td>{{ item.id }}</td>
            <td>{{ item.city }}</td>
            <td>{{ item.name }}</td>
            <td>{{ item.category }}</td>
            <td>{{ item.rating }}</td>
            <td>{{ item.priority }}</td>
            <td>
              <button class="btn-sm" @click="openMvModal(item)">编辑</button>
              <button class="btn-sm btn-danger" @click="deleteMustVisit(item.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="pagination">
        <span>共 {{ mvTotal }} 条</span>
        <button @click="mvPage--" :disabled="mvPage <= 1">上一页</button>
        <span>第 {{ mvPage }} 页</span>
        <button @click="mvPage++" :disabled="mvPage * mvPageSize >= mvTotal">下一页</button>
      </div>
    </div>

    <!-- 景点层级关系 -->
    <div v-if="currentTab === 'poi_hierarchy'" class="tab-content">
      <div class="toolbar">
        <input v-model="phFilter.keyword" placeholder="名称搜索" @keyup.enter="loadPoiHierarchy" />
        <input v-model="phFilter.city" placeholder="城市" @keyup.enter="loadPoiHierarchy" />
        <label><input type="checkbox" v-model="phFilter.is_large_scenic" @change="loadPoiHierarchy" /> 仅大型景区</label>
        <button class="btn-primary" @click="openPhModal()">+ 新增景点层级</button>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th><th>名称</th><th>城市</th><th>等级</th><th>大型景区</th><th>内部动线</th><th>周边景点</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in phList" :key="item.id">
            <td>{{ item.id }}</td>
            <td>{{ item.name }}</td>
            <td>{{ item.city }}</td>
            <td>{{ item.level || '-' }}</td>
            <td>{{ item.is_large_scenic ? '✅' : '❌' }}</td>
            <td>{{ item.inner_count || 0 }}</td>
            <td>{{ item.nearby_count || 0 }}</td>
            <td>
              <button class="btn-sm" @click="viewPoiHierarchy(item.id)">查看</button>
              <button class="btn-sm" @click="openPhModal(item)">编辑</button>
              <button class="btn-sm btn-danger" @click="deletePoiHierarchy(item.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="pagination">
        <span>共 {{ phTotal }} 条</span>
        <button @click="phPage--" :disabled="phPage <= 1">上一页</button>
        <span>第 {{ phPage }} 页</span>
        <button @click="phPage++" :disabled="phPage * phPageSize >= phTotal">下一页</button>
      </div>
    </div>

    <!-- 配置常量 -->
    <div v-if="currentTab === 'config'" class="tab-content">
      <div class="toolbar">
        <button class="btn-primary" @click="openConfigModal()">+ 新增配置</button>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>配置键</th><th>配置值</th><th>说明</th><th>更新时间</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in configList" :key="item.k">
            <td><code>{{ item.k }}</code></td>
            <td class="config-value">{{ String(item.v).substring(0, 80) }}{{ String(item.v).length > 80 ? '...' : '' }}</td>
            <td>{{ item.description }}</td>
            <td>{{ item.updated_at }}</td>
            <td>
              <button class="btn-sm" @click="openConfigModal(item)">编辑</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 品牌文案 -->
    <div v-if="currentTab === 'brand_copy'" class="tab-content">
      <div class="toolbar">
        <select v-model="bcFilter.kind" @change="loadBrandCopy">
          <option value="">全部类型</option>
          <option value="departure_message">出发宣言</option>
          <option value="daily_inspiration">每日寄语</option>
        </select>
        <button class="btn-primary" @click="openBcModal()">+ 新增文案</button>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th><th>类型</th><th>关键词</th><th>内容</th><th>优先级</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in bcList" :key="item.id">
            <td>{{ item.id }}</td>
            <td>{{ item.kind === 'departure_message' ? '出发宣言' : '每日寄语' }}</td>
            <td>{{ item.keyword || '通用' }}</td>
            <td class="config-value">{{ item.content.substring(0, 60) }}...</td>
            <td>{{ item.priority }}</td>
            <td>
              <button class="btn-sm" @click="openBcModal(item)">编辑</button>
              <button class="btn-sm btn-danger" @click="deleteBrandCopy(item.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="pagination">
        <span>共 {{ bcTotal }} 条</span>
        <button @click="bcPage--" :disabled="bcPage <= 1">上一页</button>
        <span>第 {{ bcPage }} 页</span>
        <button @click="bcPage++" :disabled="bcPage * bcPageSize >= bcTotal">下一页</button>
      </div>
    </div>

    <!-- 通用编辑弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <h3>{{ modalTitle }}</h3>
        <div class="modal-body">
          <template v-if="modalType === 'must_visit'">
            <label>城市 <input v-model="mvForm.city" /></label>
            <label>名称 <input v-model="mvForm.name" /></label>
            <label>搜索关键词 <input v-model="mvForm.kw" /></label>
            <label>类别
              <select v-model="mvForm.category">
                <option>景点</option><option>美食</option><option>购物</option><option>夜生活</option>
              </select>
            </label>
            <label>评分 <input type="number" v-model.number="mvForm.rating" step="0.1" min="0" max="5" /></label>
            <label>优先级 <input type="number" v-model.number="mvForm.priority" min="0" max="100" /></label>
          </template>
          <template v-else-if="modalType === 'poi_hierarchy'">
            <label>名称 <input v-model="phForm.name" /></label>
            <label>城市 <input v-model="phForm.city" /></label>
            <label>区县 <input v-model="phForm.district" /></label>
            <label>等级 <input v-model="phForm.level" placeholder="5A/4A等" /></label>
            <label>经度 <input type="number" v-model.number="phForm.lng" step="0.000001" /></label>
            <label>纬度 <input type="number" v-model.number="phForm.lat" step="0.000001" /></label>
            <label>是否大型景区 <input type="checkbox" v-model="phForm.is_large_scenic" /></label>
            <label>描述 <textarea v-model="phForm.description" rows="2"></textarea></label>
            <label>最佳时间 <input v-model="phForm.best_time" /></label>
          </template>
          <template v-else-if="modalType === 'config'">
            <label>配置键 <input v-model="configForm.k" :disabled="!!configForm._id" /></label>
            <label>配置值（JSON或字符串） <textarea v-model="configForm.v" rows="4"></textarea></label>
            <label>说明 <input v-model="configForm.description" /></label>
          </template>
          <template v-else-if="modalType === 'brand_copy'">
            <label>类型
              <select v-model="bcForm.kind">
                <option value="departure_message">出发宣言</option>
                <option value="daily_inspiration">每日寄语</option>
              </select>
            </label>
            <label>关键词（目的地/主题，留空为通用） <input v-model="bcForm.keyword" /></label>
            <label>文案内容 <textarea v-model="bcForm.content" rows="3"></textarea></label>
            <label>优先级 <input type="number" v-model.number="bcForm.priority" min="0" max="100" /></label>
          </template>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="showModal = false">取消</button>
          <button class="btn-primary" @click="saveModal">保存</button>
        </div>
      </div>
    </div>

    <!-- 查看详情弹窗 -->
    <div v-if="showDetail" class="modal-overlay" @click.self="showDetail = false">
      <div class="modal modal-wide">
        <h3>景点层级详情 - {{ detailData.name }}</h3>
        <div class="modal-body detail-body" v-if="detailData">
          <div class="detail-section">
            <h4>基本信息</h4>
            <p>城市：{{ detailData.city }} / {{ detailData.district }}</p>
            <p>等级：{{ detailData.level || '未填写' }}</p>
            <p>经纬度：{{ detailData.lng }}, {{ detailData.lat }}</p>
            <p>大型景区：{{ detailData.is_large_scenic ? '是' : '否' }}</p>
          </div>
          <div class="detail-section">
            <h4>描述</h4>
            <p>{{ detailData.description || '无' }}</p>
          </div>
          <div class="detail-section">
            <h4>内部游览动线（{{ (detailData.inner_route || []).length }}个）</h4>
            <ul>
              <li v-for="(p, i) in detailData.inner_route" :key="i">
                {{ p.name }} - {{ p.description }}（{{ p.duration_min }}分钟）
              </li>
            </ul>
          </div>
          <div class="detail-section">
            <h4>周边附属景点（{{ (detailData.nearby_attractions || []).length }}个）</h4>
            <ul>
              <li v-for="(p, i) in detailData.nearby_attractions" :key="i">
                {{ p.name }}（{{ p.category }}）- 距离{{ p.distance_m }}米
              </li>
            </ul>
          </div>
          <div class="detail-section">
            <h4>避坑提示（{{ (detailData.avoid_tips || []).length }}条）</h4>
            <ul>
              <li v-for="(t, i) in detailData.avoid_tips" :key="i">{{ t }}</li>
            </ul>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="showDetail = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'

const props = defineProps({ token: String, userRole: String })

const API_BASE = '/api/admin/dict'
const labelMap = { must_visit: '必去景点', poi_hierarchy: '景点层级', site_config: '配置常量', dict_brand_copy: '品牌文案' }

const tabs = [
  { key: 'must_visit', label: '必去景点' },
  { key: 'poi_hierarchy', label: '景点层级关系' },
  { key: 'config', label: '配置常量' },
  { key: 'brand_copy', label: '品牌文案' },
]
const currentTab = ref('must_visit')

const stats = reactive({ must_visit: 0, poi_hierarchy: 0, site_config: 0, dict_brand_copy: 0 })

// 必去景点
const mvList = ref([])
const mvTotal = ref(0)
const mvPage = ref(1)
const mvPageSize = 20
const mvFilter = reactive({ city: '' })

// 景点层级
const phList = ref([])
const phTotal = ref(0)
const phPage = ref(1)
const phPageSize = 20
const phFilter = reactive({ keyword: '', city: '', is_large_scenic: false })

// 配置常量
const configList = ref([])

// 品牌文案
const bcList = ref([])
const bcTotal = ref(0)
const bcPage = ref(1)
const bcPageSize = 20
const bcFilter = reactive({ kind: '' })

// 弹窗
const showModal = ref(false)
const showDetail = ref(false)
const modalType = ref('')
const modalTitle = ref('')
const detailData = ref(null)

const mvForm = reactive({ id: null, city: '', name: '', kw: '', category: '景点', rating: 4.5, priority: 50 })
const phForm = reactive({ id: null, name: '', city: '', district: '', level: '', lng: null, lat: null, is_large_scenic: false, description: '', best_time: '' })
const configForm = reactive({ _id: null, k: '', v: '', description: '' })
const bcForm = reactive({ id: null, kind: 'departure_message', keyword: '', content: '', priority: 50 })

function authHeaders() {
  return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${props.token}` }
}

async function apiRequest(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, { ...options, headers: authHeaders() })
  return res.json()
}

async function loadStats() {
  const d = await apiRequest('/stats')
  if (d.code === 0) Object.assign(stats, d.data)
}

function switchTab(key) {
  currentTab.value = key
  if (key === 'must_visit') loadMustVisit()
  else if (key === 'poi_hierarchy') loadPoiHierarchy()
  else if (key === 'config') loadConfig()
  else if (key === 'brand_copy') loadBrandCopy()
}

// 必去景点
async function loadMustVisit() {
  const params = new URLSearchParams({ page: mvPage.value, page_size: mvPageSize })
  if (mvFilter.city) params.set('city', mvFilter.city)
  const d = await apiRequest(`/must_visit?${params}`)
  if (d.code === 0) { mvList.value = d.data.items; mvTotal.value = d.data.total }
}

function openMvModal(item = null) {
  modalType.value = 'must_visit'
  modalTitle.value = item ? '编辑必去景点' : '新增必去景点'
  Object.assign(mvForm, item || { id: null, city: '', name: '', kw: '', category: '景点', rating: 4.5, priority: 50 })
  showModal.value = true
}

async function deleteMustVisit(id) {
  if (!confirm('确认删除？')) return
  await apiRequest(`/must_visit/${id}`, { method: 'DELETE' })
  loadMustVisit(); loadStats()
}

// 景点层级
async function loadPoiHierarchy() {
  const params = new URLSearchParams({ page: phPage.value, page_size: phPageSize })
  if (phFilter.keyword) params.set('keyword', phFilter.keyword)
  if (phFilter.city) params.set('city', phFilter.city)
  if (phFilter.is_large_scenic) params.set('is_large_scenic', 'true')
  const d = await apiRequest(`/poi_hierarchy?${params}`)
  if (d.code === 0) { phList.value = d.data.items; phTotal.value = d.data.total }
}

function openPhModal(item = null) {
  modalType.value = 'poi_hierarchy'
  modalTitle.value = item ? '编辑景点层级' : '新增景点层级'
  Object.assign(phForm, item || { id: null, name: '', city: '', district: '', level: '', lng: null, lat: null, is_large_scenic: false, description: '', best_time: '' })
  showModal.value = true
}

async function viewPoiHierarchy(id) {
  const d = await apiRequest(`/poi_hierarchy/${id}`)
  if (d.code === 0) { detailData.value = d.data; showDetail.value = true }
}

async function deletePoiHierarchy(id) {
  if (!confirm('确认删除？')) return
  await apiRequest(`/poi_hierarchy/${id}`, { method: 'DELETE' })
  loadPoiHierarchy(); loadStats()
}

// 配置常量
async function loadConfig() {
  const d = await apiRequest('/config')
  if (d.code === 0) configList.value = d.data.items
}

function openConfigModal(item = null) {
  modalType.value = 'config'
  modalTitle.value = item ? '编辑配置' : '新增配置'
  Object.assign(configForm, item ? { ...item, _id: item.k } : { _id: null, k: '', v: '', description: '' })
  showModal.value = true
}

// 品牌文案
async function loadBrandCopy() {
  const params = new URLSearchParams({ page: bcPage.value, page_size: bcPageSize })
  if (bcFilter.kind) params.set('kind', bcFilter.kind)
  const d = await apiRequest(`/brand_copy?${params}`)
  if (d.code === 0) { bcList.value = d.data.items; bcTotal.value = d.data.total }
}

function openBcModal(item = null) {
  modalType.value = 'brand_copy'
  modalTitle.value = item ? '编辑品牌文案' : '新增品牌文案'
  Object.assign(bcForm, item || { id: null, kind: 'departure_message', keyword: '', content: '', priority: 50 })
  showModal.value = true
}

async function deleteBrandCopy(id) {
  if (!confirm('确认删除？')) return
  await apiRequest(`/brand_copy/${id}`, { method: 'DELETE' })
  loadBrandCopy(); loadStats()
}

// 保存
async function saveModal() {
  let url, method, body
  if (modalType.value === 'must_visit') {
    url = mvForm.id ? `/must_visit/${mvForm.id}` : '/must_visit'
    method = mvForm.id ? 'PUT' : 'POST'
    body = mvForm
  } else if (modalType.value === 'poi_hierarchy') {
    url = phForm.id ? `/poi_hierarchy/${phForm.id}` : '/poi_hierarchy'
    method = phForm.id ? 'PUT' : 'POST'
    body = { ...phForm, alias: [], inner_route: [], nearby_attractions: [], avoid_tips: [] }
  } else if (modalType.value === 'config') {
    url = '/config'; method = 'PUT'; body = configForm
  } else if (modalType.value === 'brand_copy') {
    url = bcForm.id ? `/brand_copy/${bcForm.id}` : '/brand_copy'
    method = bcForm.id ? 'PUT' : 'POST'
    body = bcForm
  }
  await apiRequest(url, { method, body: JSON.stringify(body) })
  showModal.value = false
  switchTab(currentTab.value)
  loadStats()
}

async function clearCache() {
  await apiRequest('/cache/clear', { method: 'POST' })
  alert('缓存已清除')
}

onMounted(() => {
  loadStats()
  loadMustVisit()
})
</script>

<style scoped>
.dict-panel { padding: 20px; }
.panel-header { display: flex; align-items: center; gap: 20px; margin-bottom: 16px; }
.panel-header h2 { margin: 0; }
.stats { display: flex; gap: 16px; }
.stat-item { font-size: 13px; color: #666; }
.stat-item b { color: #333; }
.btn-clear { padding: 6px 14px; background: #f0f0f0; border: none; border-radius: 6px; cursor: pointer; }
.tabs { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #eee; }
.tab { padding: 10px 20px; border: none; background: none; cursor: pointer; font-size: 14px; color: #666; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab.active { color: #10b981; border-bottom-color: #10b981; font-weight: 600; }
.toolbar { display: flex; gap: 10px; margin-bottom: 12px; align-items: center; }
.toolbar input, .toolbar select { padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; }
.btn-primary { padding: 6px 14px; background: #10b981; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-sm { padding: 4px 10px; background: #f0f0f0; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; margin-right: 4px; }
.btn-danger { background: #fee2e2; color: #dc2626; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th, .data-table td { padding: 8px 10px; border-bottom: 1px solid #eee; text-align: left; }
.data-table th { background: #f9fafb; font-weight: 600; }
.config-value { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pagination { display: flex; gap: 10px; align-items: center; margin-top: 12px; justify-content: flex-end; }
.pagination button { padding: 4px 10px; border: 1px solid #ddd; background: #fff; border-radius: 4px; cursor: pointer; }
.pagination button:disabled { opacity: 0.5; cursor: not-allowed; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; padding: 24px; width: 500px; max-height: 80vh; overflow-y: auto; }
.modal-wide { width: 700px; }
.modal h3 { margin: 0 0 16px; }
.modal-body label { display: block; margin-bottom: 12px; font-size: 13px; }
.modal-body input, .modal-body textarea, .modal-body select { width: 100%; padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; margin-top: 4px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
.btn-cancel { padding: 6px 14px; background: #f0f0f0; border: none; border-radius: 6px; cursor: pointer; }
.detail-body .detail-section { margin-bottom: 16px; }
.detail-body h4 { margin: 0 0 8px; color: #10b981; }
.detail-body ul { margin: 0; padding-left: 20px; }
.detail-body li { margin-bottom: 4px; font-size: 13px; }
</style>
