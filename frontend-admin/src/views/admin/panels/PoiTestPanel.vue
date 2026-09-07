<template>
  <div class="panel">
    <h2>🔍 高德POI数据测试</h2>
    <p class="tip">测试高德地图POI检索能力，查看数据覆盖情况（M8）</p>

    <!-- 测试表单 -->
    <div class="test-form">
      <div class="form-row">
        <div class="form-item">
          <label>城市名称</label>
          <input
            v-model="city"
            type="text"
            placeholder="例如：休宁、杭州、北京"
            @keyup.enter="runTest"
          />
        </div>
        <div class="form-item">
          <label>POI类型</label>
          <select v-model="poiType">
            <option value="110200">风景名胜</option>
            <option value="050000">餐饮服务</option>
            <option value="060000">购物服务</option>
            <option value="100000">住宿服务</option>
            <option value="110000">风景名胜相关</option>
            <option value="120000">商务住宅</option>
            <option value="140000">交通设施服务</option>
            <option value="150000">公共设施</option>
            <option value="160000">科教文化服务</option>
            <option value="170000">体育休闲服务</option>
            <option value="180000">医疗保健服务</option>
          </select>
        </div>
        <div class="form-item">
          <label>检索页数</label>
          <input
            v-model.number="pages"
            type="number"
            min="1"
            max="10"
            placeholder="每页20条"
          />
        </div>
        <div class="form-item form-actions">
          <button class="primary" @click="runTest" :disabled="loading">
            {{ loading ? '测试中...' : '开始测试' }}
          </button>
          <button class="ghost" @click="clearResult" :disabled="loading">
            清空结果
          </button>
        </div>
      </div>
    </div>

    <!-- 统计信息 -->
    <div v-if="stats" class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">高德API返回总数</div>
        <div class="stat-value">{{ stats.totalCount }}</div>
        <div class="stat-desc">条POI数据</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">实际获取数量</div>
        <div class="stat-value">{{ stats.fetchedCount }}</div>
        <div class="stat-desc">条（{{ stats.pagesFetched }}页）</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">数据覆盖率</div>
        <div class="stat-value" :class="stats.coverage >= 80 ? 'ok' : stats.coverage >= 50 ? 'warn' : 'bad'">
          {{ stats.coverage }}%
        </div>
        <div class="stat-desc">{{ stats.coverage >= 80 ? '覆盖良好' : stats.coverage >= 50 ? '覆盖一般' : '覆盖不足' }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">去重后数量</div>
        <div class="stat-value">{{ stats.uniqueCount }}</div>
        <div class="stat-desc">条（重复{{ stats.fetchedCount - stats.uniqueCount }}条）</div>
      </div>
    </div>

    <!-- 错误信息 -->
    <div v-if="error" class="error-box">
      <span class="error-icon">❌</span>
      <span>{{ error }}</span>
    </div>

    <!-- POI数据列表 -->
    <div v-if="pois.length > 0" class="poi-list">
      <div class="list-header">
        <h3>POI数据列表（共{{ pois.length }}条）</h3>
        <div class="list-actions">
          <button class="ghost" @click="exportData">📥 导出JSON</button>
        </div>
      </div>
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>序号</th>
              <th>POI名称</th>
              <th>类型</th>
              <th>省份</th>
              <th>城市</th>
              <th>区县</th>
              <th>adcode</th>
              <th>评分</th>
              <th>坐标</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(poi, index) in displayedPois" :key="poi.id || index">
              <td>{{ index + 1 }}</td>
              <td class="poi-name">{{ poi.name }}</td>
              <td class="poi-type">{{ (poi.type || '').substring(0, 20) }}{{ (poi.type || '').length > 20 ? '...' : '' }}</td>
              <td>{{ poi.pname || poi.province || '-' }}</td>
              <td>{{ poi.cityname || '-' }}</td>
              <td>{{ poi.adname || poi.district || '-' }}</td>
              <td>{{ poi.adcode || '-' }}</td>
              <td>{{ poi.rating || '-' }}</td>
              <td class="coord">{{ poi.location || (poi.lng + ',' + poi.lat) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- 分页 -->
      <div v-if="pois.length > pageSize" class="pagination">
        <button class="ghost" @click="currentPage = Math.max(1, currentPage - 1)" :disabled="currentPage === 1">
          上一页
        </button>
        <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页</span>
        <button class="ghost" @click="currentPage = Math.min(totalPages, currentPage + 1)" :disabled="currentPage === totalPages">
          下一页
        </button>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && !error && pois.length === 0" class="empty-state">
      <div class="empty-icon">🔍</div>
      <p>输入城市名称，点击"开始测试"查看高德POI数据</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  token: { type: String, default: '' },
  userRole: { type: String, default: 'ops' },
})

const city = ref('')
const poiType = ref('110200')
const pages = ref(3)
const loading = ref(false)
const error = ref('')
const pois = ref([])
const stats = ref(null)
const currentPage = ref(1)
const pageSize = 20

const totalPages = computed(() => Math.ceil(pois.value.length / pageSize))
const displayedPois = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return pois.value.slice(start, start + pageSize)
})

async function runTest() {
  if (!city.value.trim()) {
    error.value = '请输入城市名称'
    return
  }

  loading.value = true
  error.value = ''
  pois.value = []
  stats.value = null
  currentPage.value = 1

  try {
    // 调用后端API进行测试
    const response = await fetch(`/api/admin/poi-test?city=${encodeURIComponent(city.value)}&types=${poiType.value}&pages=${pages.value}`, {
      headers: {
        'Authorization': `Bearer ${props.token}`,
      },
    })

    if (!response.ok) {
      throw new Error(`API请求失败: ${response.status}`)
    }

    const data = await response.json()

    if (data.success && data.data) {
      pois.value = data.data.pois || []
      stats.value = {
        totalCount: data.data.totalCount || 0,
        fetchedCount: data.data.fetchedCount || pois.value.length,
        pagesFetched: data.data.pagesFetched || pages.value,
        uniqueCount: data.data.uniqueCount || pois.value.length,
        coverage: data.data.coverage || (pois.value.length > 0 && data.data.totalCount > 0 ? Math.round((pois.value.length / data.data.totalCount) * 100) : 0),
      }
    } else {
      throw new Error(data.message || '测试失败')
    }
  } catch (e) {
    console.error('POI测试失败:', e)
    error.value = `测试失败: ${e.message}`
  } finally {
    loading.value = false
  }
}

function clearResult() {
  pois.value = []
  stats.value = null
  error.value = ''
  currentPage.value = 1
}

function exportData() {
  const data = {
    city: city.value,
    poiType: poiType.value,
    stats: stats.value,
    pois: pois.value,
    exportTime: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `poi-test-${city.value}-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.panel {
  padding: 20px;
}

.tip {
  color: #666;
  font-size: 14px;
  margin-bottom: 20px;
}

.test-form {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.form-row {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.form-item {
  flex: 1;
  min-width: 150px;
}

.form-item label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: #333;
}

.form-item input,
.form-item select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.form-actions {
  flex: 0 0 auto;
  display: flex;
  gap: 8px;
}

button {
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  border: none;
}

button.primary {
  background: #4f46e5;
  color: white;
}

button.primary:disabled {
  background: #a5b4fc;
  cursor: not-allowed;
}

button.ghost {
  background: white;
  color: #4f46e5;
  border: 1px solid #4f46e5;
}

button.ghost:disabled {
  color: #a5b4fc;
  border-color: #a5b4fc;
  cursor: not-allowed;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  text-align: center;
}

.stat-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #1f2937;
}

.stat-value.ok {
  color: #10b981;
}

.stat-value.warn {
  color: #f59e0b;
}

.stat-value.bad {
  color: #ef4444;
}

.stat-desc {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.error-box {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 12px 16px;
  border-radius: 6px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.poi-list {
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  overflow: hidden;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.list-header h3 {
  margin: 0;
  font-size: 16px;
}

.table-container {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th {
  background: #f8f9fa;
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: #374151;
  border-bottom: 2px solid #e5e7eb;
  white-space: nowrap;
}

.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #f3f4f6;
  color: #4b5563;
}

.data-table tr:hover {
  background: #f9fafb;
}

.poi-name {
  font-weight: 500;
  color: #1f2937;
}

.poi-type {
  color: #6b7280;
  font-size: 12px;
}

.coord {
  font-family: monospace;
  font-size: 12px;
  color: #6b7280;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-top: 1px solid #eee;
}

.page-info {
  color: #666;
  font-size: 14px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}
</style>
