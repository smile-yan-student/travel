<template>
  <div class="rag-panel">
    <div class="panel-header">
      <h2>📚 RAG知识库管理</h2>
      <p class="subtitle">管理景点人文知识库，支持查看、检索、导入和删除</p>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid" v-if="stats">
      <div class="stat-card">
        <div class="stat-icon">📄</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.vector_store.document_count }}</div>
          <div class="stat-label">知识文档数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📍</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.knowledge_service.local_poi_count }}</div>
          <div class="stat-label">已覆盖景点</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">🧠</div>
        <div class="stat-info">
          <div class="stat-value model-name">{{ stats.vector_store.embedding_model }}</div>
          <div class="stat-label">嵌入模型</div>
        </div>
      </div>
      <div class="stat-card" :class="{ available: stats.rag_available }">
        <div class="stat-icon">{{ stats.rag_available ? '✅' : '❌' }}</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.rag_available ? '可用' : '不可用' }}</div>
          <div class="stat-label">RAG服务状态</div>
        </div>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="toolbar">
      <div class="search-box">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="🔍 语义搜索知识库（如：历史、文化、建筑）"
          @keyup.enter="searchKnowledge"
        />
        <button @click="searchKnowledge" :disabled="loading">搜索</button>
      </div>
      <div class="actions">
        <button class="btn-refresh" @click="loadStats" :disabled="loading">🔄 刷新</button>
        <button class="btn-import-all" @click="importAllPois" :disabled="loading">📥 批量导入所有景点</button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>加载中...</span>
    </div>

    <!-- 搜索结果 -->
    <div v-if="searchResults.length > 0" class="search-results">
      <h3>🔍 搜索结果（{{ searchResults.length }}条）</h3>
      <div class="result-list">
        <div v-for="(result, index) in searchResults" :key="index" class="result-item" @click="viewPoiKnowledge(result.metadata.poi_name)">
          <div class="result-header">
            <span class="poi-name">{{ result.metadata.poi_name }}</span>
            <span class="chunk-type">{{ result.metadata.chunk_type }}</span>
            <span class="distance">相似度: {{ (1 - result.distance).toFixed(2) }}</span>
          </div>
          <div class="result-content">{{ result.document }}</div>
        </div>
      </div>
    </div>

    <!-- 景点列表 -->
    <div class="poi-list-section" v-if="!loading">
      <h3>📍 已覆盖景点列表（{{ poiList.length }}个）</h3>
      <div class="poi-grid">
        <div
          v-for="poi in poiList"
          :key="poi.name"
          class="poi-card"
          @click="viewPoiKnowledge(poi.name)"
        >
          <div class="poi-icon">🏛️</div>
          <div class="poi-name">{{ poi.name }}</div>
          <div class="poi-chunks">{{ poi.count }}条知识</div>
          <div class="poi-actions">
            <button class="btn-view" @click.stop="viewPoiKnowledge(poi.name)">查看</button>
            <button class="btn-delete" @click.stop="deletePoi(poi.name)">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 景点知识详情弹窗 -->
    <div v-if="showDetail" class="detail-modal" @click.self="closeDetail">
      <div class="detail-content">
        <div class="detail-header">
          <h3>📖 {{ currentPoi }} - 知识详情</h3>
          <button class="close-btn" @click="closeDetail">×</button>
        </div>
        <div class="detail-body" v-if="poiKnowledge">
          <div v-for="(docs, type) in poiKnowledge" :key="type" class="knowledge-section">
            <h4>{{ getChunkTypeName(type) }}（{{ docs.length }}条）</h4>
            <div v-for="(doc, index) in docs" :key="index" class="knowledge-item">
              <div class="knowledge-meta">
                <span class="meta-title">{{ doc.metadata.title || '无标题' }}</span>
                <span class="meta-importance" v-if="doc.metadata.importance">重要度: {{ doc.metadata.importance }}</span>
              </div>
              <div class="knowledge-text">{{ doc.document }}</div>
            </div>
          </div>
          <div v-if="Object.keys(poiKnowledge).length === 0" class="empty-knowledge">
            该景点暂无知识内容
          </div>
        </div>
      </div>
    </div>

    <!-- 消息提示 -->
    <div v-if="message" class="message" :class="messageType">
      {{ message }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getRagStats as ragStats, ragSearch, getPoiKnowledge, importAllPois as importAllApi, deletePoiKnowledge as deletePoiApi } from '../../../api'

const props = defineProps({
  token: { type: String, default: '' },
  userRole: { type: String, default: '' },
})

const stats = ref(null)
const poiList = ref([])
const searchQuery = ref('')
const searchResults = ref([])
const loading = ref(false)
const showDetail = ref(false)
const currentPoi = ref('')
const poiKnowledge = ref(null)
const message = ref('')
const messageType = ref('info')

const chunkTypeNames = {
  overview: '景点概述',
  history: '历史沿革',
  architecture: '建筑格局',
  culture: '文化意义',
  legends: '名人典故',
  visit_highlights: '游玩重点',
  photo_spots: '拍照机位',
  avoid_tips: '避坑提示',
  best_time: '最佳时节',
  food: '美食推荐',
  transport: '交通指南',
  tickets: '门票信息',
  general: '通用知识',
}

function getChunkTypeName(type) {
  return chunkTypeNames[type] || type
}

function showMessage(msg, type = 'info') {
  message.value = msg
  messageType.value = type
  setTimeout(() => {
    message.value = ''
  }, 3000)
}

async function loadStats() {
  loading.value = true
  try {
    const res = await ragStats()
    if (res.code === 0) {
      stats.value = res.data
      await loadPoiList()
    }
  } catch (e) {
    showMessage('加载统计信息失败: ' + e.message, 'error')
  } finally {
    loading.value = false
  }
}

async function loadPoiList() {
  try {
    const res = await ragSearch('景点', null, 100)
    if (res.code === 0) {
      const results = res.data.results || []
      const poiMap = {}
      results.forEach(r => {
        const name = r.metadata?.poi_name || 'unknown'
        if (!poiMap[name]) {
          poiMap[name] = { name, count: 0 }
        }
        poiMap[name].count++
      })
      poiList.value = Object.values(poiMap).sort((a, b) => b.count - a.count)
    }
  } catch (e) {
    console.error('加载景点列表失败:', e)
  }
}

async function searchKnowledge() {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }
  loading.value = true
  try {
    const res = await ragSearch(searchQuery.value, null, 20)
    if (res.code === 0) {
      searchResults.value = res.data.results || []
      showMessage(`找到 ${searchResults.value.length} 条相关知识`, 'success')
    }
  } catch (e) {
    showMessage('搜索失败: ' + e.message, 'error')
  } finally {
    loading.value = false
  }
}

async function viewPoiKnowledge(poiName) {
  currentPoi.value = poiName
  showDetail.value = true
  poiKnowledge.value = null
  try {
    const res = await getPoiKnowledge(poiName)
    if (res.code === 0) {
      poiKnowledge.value = res.data.knowledge || {}
    }
  } catch (e) {
    showMessage('加载知识详情失败: ' + e.message, 'error')
  }
}

function closeDetail() {
  showDetail.value = false
  currentPoi.value = ''
  poiKnowledge.value = null
}

async function importAllPois() {
  if (!confirm('确定要批量导入所有景点知识吗？这可能需要一些时间。')) {
    return
  }
  loading.value = true
  try {
    const res = await importAllApi()
    if (res.code === 0) {
      showMessage('批量导入成功: ' + JSON.stringify(res.data), 'success')
      await loadStats()
    } else {
      showMessage('导入失败: ' + res.message, 'error')
    }
  } catch (e) {
    showMessage('导入失败: ' + e.message, 'error')
  } finally {
    loading.value = false
  }
}

async function deletePoi(poiName) {
  if (!confirm(`确定要删除「${poiName}」的所有知识吗？此操作不可恢复。`)) {
    return
  }
  loading.value = true
  try {
    const res = await deletePoiApi(poiName)
    if (res.code === 0) {
      showMessage(`已删除「${poiName}」的知识`, 'success')
      await loadStats()
    } else {
      showMessage('删除失败: ' + res.message, 'error')
    }
  } catch (e) {
    showMessage('删除失败: ' + e.message, 'error')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.rag-panel {
  padding: 0;
}
.panel-header {
  margin-bottom: 20px;
}
.panel-header h2 {
  margin: 0 0 8px;
  font-size: 22px;
  color: #1a2a3a;
}
.subtitle {
  margin: 0;
  color: #6b7c8d;
  font-size: 13px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #e8edf2;
}
.stat-card.available {
  border-color: #10b981;
  background: linear-gradient(135deg, #ecfdf5, #fff);
}
.stat-icon {
  font-size: 32px;
}
.stat-info {
  flex: 1;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #1a2a3a;
}
.stat-value.model-name {
  font-size: 13px;
  word-break: break-all;
}
.stat-label {
  font-size: 12px;
  color: #6b7c8d;
  margin-top: 2px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  gap: 16px;
}
.search-box {
  flex: 1;
  display: flex;
  gap: 8px;
}
.search-box input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #d1d9e0;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}
.search-box input:focus {
  border-color: #3b82f6;
}
.search-box button,
.actions button {
  padding: 10px 18px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.search-box button {
  background: #3b82f6;
  color: #fff;
}
.search-box button:hover {
  background: #2563eb;
}
.search-box button:disabled,
.actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.actions {
  display: flex;
  gap: 8px;
}
.btn-refresh {
  background: #f1f5f9;
  color: #475569;
}
.btn-refresh:hover {
  background: #e2e8f0;
}
.btn-import-all {
  background: #10b981;
  color: #fff;
}
.btn-import-all:hover {
  background: #059669;
}
.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px;
  color: #6b7c8d;
}
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.search-results {
  margin-bottom: 24px;
}
.search-results h3,
.poi-list-section h3 {
  font-size: 16px;
  color: #1a2a3a;
  margin: 0 0 14px;
}
.result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.result-item {
  background: #fff;
  border: 1px solid #e8edf2;
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
}
.result-item:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1);
}
.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.poi-name {
  font-weight: 600;
  color: #1a2a3a;
}
.chunk-type {
  background: #eff6ff;
  color: #2563eb;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}
.distance {
  margin-left: auto;
  font-size: 12px;
  color: #6b7c8d;
}
.result-content {
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.poi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 14px;
}
.poi-card {
  background: #fff;
  border: 1px solid #e8edf2;
  border-radius: 12px;
  padding: 18px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}
.poi-card:hover {
  border-color: #3b82f6;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}
.poi-icon {
  font-size: 36px;
  margin-bottom: 10px;
}
.poi-card .poi-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a2a3a;
  margin-bottom: 6px;
  word-break: break-all;
}
.poi-chunks {
  font-size: 12px;
  color: #6b7c8d;
  margin-bottom: 12px;
}
.poi-actions {
  display: flex;
  gap: 6px;
  justify-content: center;
}
.poi-actions button {
  padding: 5px 12px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-view {
  background: #eff6ff;
  color: #2563eb;
}
.btn-view:hover {
  background: #dbeafe;
}
.btn-delete {
  background: #fef2f2;
  color: #dc2626;
}
.btn-delete:hover {
  background: #fee2e2;
}
.detail-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}
.detail-content {
  background: #fff;
  border-radius: 16px;
  width: 100%;
  max-width: 800px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  color: #fff;
}
.detail-header h3 {
  margin: 0;
  font-size: 18px;
}
.close-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 28px;
  cursor: pointer;
  line-height: 1;
  padding: 0 4px;
}
.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
.knowledge-section {
  margin-bottom: 24px;
}
.knowledge-section h4 {
  font-size: 15px;
  color: #1a2a3a;
  margin: 0 0 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e8edf2;
}
.knowledge-item {
  background: #f8fafc;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 10px;
}
.knowledge-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.meta-title {
  font-weight: 600;
  color: #1a2a3a;
  font-size: 13px;
}
.meta-importance {
  background: #fef3c7;
  color: #92400e;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}
.knowledge-text {
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
}
.empty-knowledge {
  text-align: center;
  padding: 40px;
  color: #94a3b8;
}
.message {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 12px 20px;
  border-radius: 8px;
  font-size: 14px;
  z-index: 2000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  animation: slideIn 0.3s ease;
}
.message.success {
  background: #10b981;
  color: #fff;
}
.message.error {
  background: #ef4444;
  color: #fff;
}
.message.info {
  background: #3b82f6;
  color: #fff;
}
@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
</style>
