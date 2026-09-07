<template>
  <div class="day-card card">
    <div class="day-head">
      <div class="day-no">{{ day.day }}</div>
      <div class="day-info">
        <div class="theme">{{ day.theme || `第${day.day}天` }}</div>
        <div class="meta">{{ day.date_label }} · 预算 ¥{{ day.budget }}</div>
      </div>
    </div>

    <div v-if="day.inspiration" class="inspiration">
      <span class="insp-quote">❝</span>{{ day.inspiration }}
    </div>

    <ul class="timeline" @dragover.prevent @drop.prevent="onDrop">
      <li
        v-for="(item, i) in day.items"
        :key="item.poi.id"
        class="item"
        :draggable="draggable"
        @dragstart="onDragStart(i)"
        @dragenter.prevent="dragEnter = i"
        @dragover.prevent
        @drop="onDrop(i)"
        @click="onItemClick(item)"
        :class="{ dragging: dragEnter === i }"
        :title="'在地图上查看：' + item.poi.name"
      >
        <div class="time-col">
          <span class="slot">{{ item.slot }}</span>
          <span class="time">{{ item.start_time }}</span>
        </div>
        <div class="body">
          <div class="row1">
            <span class="name">{{ item.poi.name }}</span>
            <span :class="['cat', item.poi.category]">{{ item.poi.category }}</span>
            <span v-if="item.poi.poi_level" class="level-badge">{{ item.poi.poi_level }}</span>
            <button v-if="isScenicSpot(item.poi)" class="ai-explain-btn" @click.stop="openAiExplain(item.poi)" title="AI完整讲解">
              ✨ AI讲解
            </button>
          </div>
          <div class="row2">
            <span class="dur">⏱ {{ item.duration_min }}分钟</span>
            <span v-if="item.poi.price > 0" class="price">¥{{ item.poi.price }}</span>
            <span v-if="item.poi.best_time" class="best-time">🕐 {{ item.poi.best_time }}</span>
          </div>
          <div v-if="item.transport" class="transit">
            <span class="transit-icon">{{ getTransportIcon(item.transport) }}</span>
            <span class="transit-text">{{ item.transport }}</span>
            <span class="transit-divider">·</span>
            <span class="transit-distance">{{ formatDistance(item.distance_m) }}</span>
            <span class="transit-divider">·</span>
            <span class="transit-time">约{{ item.transit_min }}分钟</span>
          </div>
          <div v-if="item.note" class="note">{{ item.note }}</div>

          <!-- 三层POI扩展：内部游览动线 + 周边联动 + RAG人文信息 -->
          <div v-if="item.poi.has_hierarchy && (item.poi.inner_route?.length || item.poi.nearby_attractions?.length)" class="hierarchy-section">
            <div class="hierarchy-toggle" @click.stop="toggleExpand(item.poi.id, item.poi)">
              <span class="toggle-icon">{{ expandedPoi === item.poi.id ? '▼' : '▶' }}</span>
              <span v-if="item.poi.inner_route?.length" class="toggle-text">内部动线{{ item.poi.inner_route.length }}站</span>
              <span v-if="item.poi.nearby_attractions?.length" class="toggle-text">· 周边{{ item.poi.nearby_attractions.length }}处</span>
              <span v-if="item.poi.avoid_tips?.length" class="toggle-text">· 避坑提示</span>
            </div>

            <div v-if="expandedPoi === item.poi.id" class="hierarchy-detail">
              <!-- 内部游览动线 -->
              <div v-if="item.poi.inner_route?.length" class="inner-route">
                <div class="section-title">🗺️ 内部游览动线</div>
                <div class="route-flow">
                  <template v-for="(stop, idx) in item.poi.inner_route" :key="idx">
                    <div class="route-stop">
                      <div class="stop-name">{{ stop.order }}. {{ stop.name }}</div>
                      <div v-if="stop.highlight" class="stop-highlight">{{ stop.highlight }}</div>
                      <div class="stop-duration">约{{ stop.duration_min }}分钟</div>
                    </div>
                    <div v-if="idx < item.poi.inner_route.length - 1" class="route-arrow">→</div>
                  </template>
                </div>
              </div>

              <!-- 周边联动 -->
              <div v-if="item.poi.nearby_attractions?.length" class="nearby-list">
                <div class="section-title">🍜 周边联动推荐</div>
                <div v-for="nearby in item.poi.nearby_attractions" :key="nearby.name" class="nearby-item">
                  <span :class="['nearby-cat', nearby.category]">{{ nearby.category }}</span>
                  <span class="nearby-name">{{ nearby.name }}</span>
                  <span class="nearby-dist">{{ (nearby.distance_m / 1000).toFixed(1) }}km</span>
                  <span class="nearby-slot">推荐{{ nearby.recommended_slot }}</span>
                  <span v-if="nearby.description" class="nearby-desc">{{ nearby.description }}</span>
                </div>
              </div>

              <!-- 避坑提示 -->
              <div v-if="item.poi.avoid_tips?.length" class="avoid-tips">
                <div class="section-title">⚠️ 避坑提示</div>
                <div v-for="(tip, idx) in item.poi.avoid_tips" :key="idx" class="tip-item">• {{ tip }}</div>
              </div>

              <!-- RAG人文信息（仅景点类型展示，展开时自动加载） -->
              <div v-if="isScenicSpot(item.poi)" class="rag-humanities">
                <div class="section-title">📚 人文知识（RAG知识库）</div>
                <div v-if="ragCardInfo[item.poi.id]?.loading" class="rag-loading">
                  <div class="loading-spinner"></div>
                  <span>正在加载人文知识...</span>
                </div>
                <div v-else-if="ragCardInfo[item.poi.id]?.error" class="rag-error">
                  ⚠️ 人文知识加载失败：{{ ragCardInfo[item.poi.id].error }}
                </div>
                <div v-else-if="ragCardInfo[item.poi.id]?.data" class="rag-content">
                  <div v-if="ragCardInfo[item.poi.id].data.summary" class="rag-item">
                    <span class="rag-label">📍 简介：</span>
                    <span class="rag-text">{{ ragCardInfo[item.poi.id].data.summary }}</span>
                  </div>
                  <div v-if="ragCardInfo[item.poi.id].data.historical_origin" class="rag-item">
                    <span class="rag-label">📜 历史渊源：</span>
                    <span class="rag-text">{{ ragCardInfo[item.poi.id].data.historical_origin }}</span>
                  </div>
                  <div v-if="ragCardInfo[item.poi.id].data.famous_legend" class="rag-item">
                    <span class="rag-label">📖 名人典故：</span>
                    <span class="rag-text">{{ ragCardInfo[item.poi.id].data.famous_legend }}</span>
                  </div>
                  <div v-if="ragCardInfo[item.poi.id].data.best_time" class="rag-item">
                    <span class="rag-label">🕐 最佳时节：</span>
                    <span class="rag-text">{{ ragCardInfo[item.poi.id].data.best_time }}</span>
                  </div>
                  <div v-if="ragCardInfo[item.poi.id].data.avoid_tips?.length" class="rag-item">
                    <span class="rag-label">💡 游玩建议：</span>
                    <span class="rag-text">{{ ragCardInfo[item.poi.id].data.avoid_tips.join('；') }}</span>
                  </div>
                  <div v-if="!ragCardInfo[item.poi.id].data.rag_available" class="rag-note">
                    💡 该景点暂无详细知识库，以上为通用信息
                  </div>
                </div>
                <div v-else class="rag-empty">
                  暂无人文知识信息
                </div>
              </div>
            </div>
          </div>
        </div>
        <span class="grip" v-if="draggable">⠿</span>
      </li>
    </ul>

    <div v-if="day.hotel_area" class="hotel">
      <span class="hotel-icon">🏨</span>
      <span class="hotel-area">建议住宿区域：{{ day.hotel_area.area_name }}</span>
      <span v-if="day.hotel_area.reason" class="hotel-reason">（{{ day.hotel_area.reason }}）</span>
    </div>

    <div v-if="day.tip" class="tip">💡 {{ day.tip }}</div>

    <!-- AI讲解弹窗 -->
    <div v-if="showAiExplain" class="ai-explain-modal" @click.self="closeAiExplain">
      <div class="ai-explain-content">
        <div class="ai-explain-header">
          <span class="ai-explain-title">✨ {{ aiExplainPoi?.name }} · AI完整讲解</span>
          <button class="ai-explain-close" @click="closeAiExplain">×</button>
        </div>
        <div v-if="aiExplainLoading" class="ai-explain-loading">
          <div class="loading-spinner"></div>
          <span>正在生成讲解，请稍候...</span>
        </div>
        <div v-else-if="aiExplainError" class="ai-explain-error">
          ⚠️ {{ aiExplainError }}
        </div>
        <div v-else class="ai-explain-body">
          <div v-if="aiExplainData?.introduction" class="explain-section">
            <div class="explain-label">📍 一句话定位</div>
            <div class="explain-text">{{ aiExplainData.introduction }}</div>
          </div>
          <div v-if="aiExplainData?.history" class="explain-section">
            <div class="explain-label">📜 历史沿革</div>
            <div class="explain-text">{{ aiExplainData.history }}</div>
          </div>
          <div v-if="aiExplainData?.architecture" class="explain-section">
            <div class="explain-label">🏛️ 建筑格局</div>
            <div class="explain-text">{{ aiExplainData.architecture }}</div>
          </div>
          <div v-if="aiExplainData?.culture" class="explain-section">
            <div class="explain-label">✨ 文化意义</div>
            <div class="explain-text">{{ aiExplainData.culture }}</div>
          </div>
          <div v-if="aiExplainData?.legends?.length" class="explain-section">
            <div class="explain-label">📖 名人典故</div>
            <div class="explain-text">
              <div v-for="(legend, i) in aiExplainData.legends" :key="i" class="legend-item">• {{ legend }}</div>
            </div>
          </div>
          <div v-if="aiExplainData?.visit_highlights" class="explain-section">
            <div class="explain-label">🎯 游玩重点</div>
            <div class="explain-text">{{ aiExplainData.visit_highlights }}</div>
          </div>
          <div v-if="aiExplainData?.photo_spots?.length" class="explain-section">
            <div class="explain-label">📸 拍照机位</div>
            <div class="explain-text">
              <div v-for="(spot, i) in aiExplainData.photo_spots" :key="i" class="spot-item">• {{ spot }}</div>
            </div>
          </div>
          <div v-if="aiExplainData?.avoid_tips?.length" class="explain-section">
            <div class="explain-label">⚠️ 避坑提示</div>
            <div class="explain-text">
              <div v-for="(tip, i) in aiExplainData.avoid_tips" :key="i" class="tip-item">• {{ tip }}</div>
            </div>
          </div>
          <div v-if="aiExplainData?.sources?.length" class="explain-sources">
            📚 信息来源：{{ aiExplainData.sources.join('、') }}
          </div>
          <div v-if="aiExplainData?.rag_retrieved === false" class="explain-note">
            💡 该景点暂无详细知识库，以上为AI通用介绍，建议查阅官方资料获取准确信息
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { generatePoiExplanation, getPoiCardInfo } from '../api'

const props = defineProps({
  day: { type: Object, required: true },
  draggable: { type: Boolean, default: true },
})
const emit = defineEmits(['reorder', 'focus-poi'])

const dragIndex = ref(-1)
const dragEnter = ref(-1)
const expandedPoi = ref(null)

// AI讲解相关状态
const showAiExplain = ref(false)
const aiExplainPoi = ref(null)
const aiExplainLoading = ref(false)
const aiExplainError = ref('')
const aiExplainData = ref(null)

// RAG卡片人文信息（展开时自动加载）
const ragCardInfo = ref({})  // { poiId: { loading, data, error } }

async function loadRagCardInfo(poi) {
  if (!poi || !poi.id) return
  if (ragCardInfo.value[poi.id]) return  // 已加载或加载中

  ragCardInfo.value[poi.id] = { loading: true, data: null, error: '' }
  try {
    const res = await getPoiCardInfo(poi.name)
    if (res.code === 0 && res.data) {
      ragCardInfo.value[poi.id] = { loading: false, data: res.data, error: '' }
    } else {
      ragCardInfo.value[poi.id] = { loading: false, data: null, error: res.message || '加载失败' }
    }
  } catch (e) {
    ragCardInfo.value[poi.id] = { loading: false, data: null, error: e.message || '加载失败' }
  }
}

function toggleExpand(poiId, poi) {
  if (expandedPoi.value === poiId) {
    expandedPoi.value = null
  } else {
    expandedPoi.value = poiId
    // 展开时自动加载RAG人文信息
    if (poi) {
      loadRagCardInfo(poi)
    }
  }
}

async function openAiExplain(poi) {
  aiExplainPoi.value = poi
  showAiExplain.value = true
  aiExplainLoading.value = true
  aiExplainError.value = ''
  aiExplainData.value = null

  try {
    const res = await generatePoiExplanation(poi.name, 'default')
    if (res.code === 0) {
      aiExplainData.value = res.data
    } else {
      aiExplainError.value = res.message || '生成失败，请稍后重试'
    }
  } catch (e) {
    aiExplainError.value = e.message || '生成失败，请稍后重试'
  } finally {
    aiExplainLoading.value = false
  }
}

function closeAiExplain() {
  showAiExplain.value = false
  aiExplainPoi.value = null
  aiExplainData.value = null
  aiExplainError.value = ''
}

function onDragStart(i) {
  dragIndex.value = i
}
function onDrop(i) {
  const from = dragIndex.value
  if (from >= 0 && from !== i) {
    emit('reorder', from, i)
  }
  dragIndex.value = -1
  dragEnter.value = -1
}
function onItemClick(item) {
  // 拖拽刚结束时（dragIndex 尚未重置）不触发聚焦
  if (dragIndex.value >= 0) return
  emit('focus-poi', item.poi)
}

// 交通方式图标
function getTransportIcon(transport) {
  const icons = {
    '步行': '🚶',
    '驾车': '🚗',
    '公交地铁': '🚇',
    '骑行': '🚴',
    '混合': '🚗',
  }
  return icons[transport] || '🚶'
}

// 距离格式化：小于1000米显示米，大于等于1000米显示公里
function formatDistance(distanceM) {
  if (!distanceM || distanceM <= 0) return ''
  if (distanceM < 1000) return `${distanceM}米`
  return `${(distanceM / 1000).toFixed(1)}公里`
}

// 判断是否为景点类型（只有景点才显示AI讲解和RAG人文信息）
function isScenicSpot(poi) {
  if (!poi) return false
  const category = poi.category || poi.type || ''
  // 景点类型包括：景点、风景名胜、公园、博物馆、纪念馆、遗址等
  const scenicCategories = ['景点', '风景名胜', '公园', '森林公园', '地质公园', '湿地公园',
                             '博物馆', '博物院', '纪念馆', '遗址', '古镇', '古城', '古村',
                             '主题公园', '游乐园', '度假区', '风景区', '风景名胜区']
  return scenicCategories.some(cat => category.includes(cat))
}
</script>

<style scoped>
.day-card {
  margin-bottom: 14px;
  overflow: hidden;
}
.day-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--border);
}
.day-no {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--gradient);
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.theme {
  font-size: 16px;
  font-weight: 600;
}
.meta {
  font-size: 12.5px;
  color: var(--text-2);
}
.timeline {
  list-style: none;
  padding: 4px 0;
}
.inspiration {
  margin: 10px 0 6px;
  padding: 9px 13px;
  background: linear-gradient(135deg, #eef9f6, #f5fbf9);
  border-left: 3px solid var(--primary);
  border-radius: 8px;
  font-size: 13px;
  color: var(--primary-dark);
  line-height: 1.6;
}
.insp-quote {
  color: var(--primary);
  font-size: 15px;
  font-weight: 700;
  margin-right: 4px;
}
.item {
  display: flex;
  gap: 10px;
  padding: 12px 4px;
  position: relative;
  border-radius: 10px;
  cursor: grab;
}
.item.dragging {
  background: #f0faf8;
  outline: 1.5px dashed var(--primary);
}
.time-col {
  width: 44px;
  text-align: center;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.slot {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-dark);
  background: #e0f5f1;
  padding: 2px 8px;
  border-radius: 999px;
}
.time {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 3px;
}
.body {
  flex: 1;
  min-width: 0;
}
.row1 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.name {
  font-size: 15px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cat {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 999px;
  flex-shrink: 0;
}
.cat.景点 { background: #fdf0d8; color: #b26b00; }
.cat.美食 { background: #fee2e2; color: #b91c1c; }
.cat.购物 { background: #dbeafe; color: #1d4ed8; }
.cat.夜生活 { background: #ede9fe; color: #6d28d9; }
.cat.酒店 { background: #e5e7eb; color: #374151; }
.row2 {
  display: flex;
  gap: 12px;
  margin-top: 3px;
  font-size: 12.5px;
  color: var(--text-2);
}
.transit {
  margin-top: 8px;
  font-size: 12px;
  color: #1677ff;
  background: linear-gradient(135deg, #e6f4ff 0%, #f0f7ff 100%);
  border-radius: 8px;
  padding: 6px 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  border-left: 3px solid #1677ff;
}
.transit-icon {
  font-size: 14px;
}
.transit-text {
  font-weight: 600;
}
.transit-divider {
  color: #91caff;
}
.transit-distance,
.transit-time {
  color: #4096ff;
}
.note {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-3);
}
.hotel {
  margin-top: 10px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #eef7ff 0%, #f0f9ff 100%);
  border-radius: 10px;
  font-size: 12.5px;
  color: #1d4ed8;
  border-left: 3px solid #3b82f6;
}
.hotel-area {
  font-weight: 600;
  margin-left: 4px;
}
.hotel-reason {
  margin-left: 6px;
  color: #60a5fa;
  font-size: 11.5px;
}
.hotel-price {
  margin-left: 6px;
  color: var(--text-2);
}
.tip {
  margin-top: 10px;
  padding: 10px 12px;
  background: #fffbea;
  border-radius: 10px;
  font-size: 12.5px;
  color: #8a5b00;
}
.grip {
  color: var(--text-3);
  font-size: 18px;
  align-self: center;
  padding: 0 4px;
}

/* 三层POI扩展样式 */
.level-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #92400e;
  font-weight: 600;
  flex-shrink: 0;
}
.best-time {
  color: #059669;
  font-size: 11.5px;
}
.hierarchy-section {
  margin-top: 8px;
  border-top: 1px dashed var(--border);
  padding-top: 8px;
}
.hierarchy-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--primary);
  cursor: pointer;
  padding: 4px 0;
  user-select: none;
}
.toggle-icon {
  font-size: 10px;
  transition: transform 0.2s;
}
.toggle-text {
  color: var(--text-2);
}
.hierarchy-detail {
  margin-top: 8px;
  padding: 10px;
  background: #fafcfb;
  border-radius: 8px;
  border: 1px solid #e8f5f0;
}
.section-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--primary-dark);
  margin-bottom: 8px;
}
.inner-route {
  margin-bottom: 12px;
}
.route-flow {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 4px;
}
.route-stop {
  background: #fff;
  border: 1px solid #d1fae5;
  border-radius: 6px;
  padding: 6px 8px;
  flex: 1;
  min-width: 100px;
}
.stop-name {
  font-size: 12px;
  font-weight: 600;
  color: #065f46;
}
.stop-highlight {
  font-size: 11px;
  color: var(--text-2);
  margin-top: 2px;
  line-height: 1.4;
}
.stop-duration {
  font-size: 10.5px;
  color: #059669;
  margin-top: 3px;
}
.route-arrow {
  color: #10b981;
  font-size: 14px;
  align-self: center;
  padding: 0 2px;
}
.nearby-list {
  margin-bottom: 12px;
}
.nearby-item {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding: 5px 0;
  border-bottom: 1px dashed #e5e7eb;
  font-size: 12px;
}
.nearby-item:last-child {
  border-bottom: none;
}
.nearby-cat {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 600;
}
.nearby-cat.美食街 { background: #fee2e2; color: #b91c1c; }
.nearby-cat.老街 { background: #fef3c7; color: #92400e; }
.nearby-cat.市井 { background: #d1fae5; color: #065f46; }
.nearby-cat.夜市 { background: #ede9fe; color: #6d28d9; }
.nearby-cat.购物街 { background: #dbeafe; color: #1d4ed8; }
.nearby-cat.景点 { background: #fdf0d8; color: #b26b00; }
.nearby-cat.文艺 { background: #fce7f3; color: #be185d; }
.nearby-name {
  font-weight: 600;
  color: var(--text-1);
}
.nearby-dist {
  color: #059669;
  font-size: 11px;
}
.nearby-slot {
  color: #8b5cf6;
  font-size: 11px;
  background: #f5f3ff;
  padding: 1px 5px;
  border-radius: 4px;
}
.nearby-desc {
  width: 100%;
  color: var(--text-3);
  font-size: 11px;
  padding-left: 4px;
}
.avoid-tips .tip-item {
  font-size: 12px;
  color: #92400e;
  line-height: 1.6;
  padding: 2px 0;
}

/* AI讲解按钮 */
.ai-explain-btn {
  margin-left: auto;
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 999px;
  border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
  flex-shrink: 0;
}
.ai-explain-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

/* AI讲解弹窗 */
.ai-explain-modal {
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
.ai-explain-content {
  background: #fff;
  border-radius: 16px;
  width: 100%;
  max-width: 560px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}
.ai-explain-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
}
.ai-explain-title {
  font-size: 16px;
  font-weight: 600;
}
.ai-explain-close {
  background: none;
  border: none;
  color: #fff;
  font-size: 24px;
  cursor: pointer;
  line-height: 1;
  padding: 0 4px;
}
.ai-explain-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}
.ai-explain-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 16px;
  color: #6b7280;
}
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e5e7eb;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.ai-explain-error {
  padding: 40px 20px;
  text-align: center;
  color: #dc2626;
}
.explain-section {
  margin-bottom: 18px;
}
.explain-label {
  font-size: 13px;
  font-weight: 600;
  color: #6366f1;
  margin-bottom: 6px;
}
.explain-text {
  font-size: 13.5px;
  color: #374151;
  line-height: 1.7;
}
.legend-item, .spot-item, .tip-item {
  padding: 3px 0;
}
.explain-sources {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px dashed #e5e7eb;
  font-size: 11.5px;
  color: #9ca3af;
}
.explain-note {
  margin-top: 12px;
  padding: 10px 12px;
  background: #fef3c7;
  border-radius: 8px;
  font-size: 12px;
  color: #92400e;
}

/* RAG人文信息样式 */
.rag-humanities {
  margin-top: 12px;
  padding: 12px;
  background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
  border-radius: 10px;
  border-left: 3px solid #0ea5e9;
}
.rag-loading, .rag-error, .rag-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
  padding: 8px 0;
}
.rag-error {
  color: #dc2626;
}
.rag-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rag-item {
  font-size: 12px;
  line-height: 1.6;
}
.rag-label {
  font-weight: 600;
  color: #0369a1;
}
.rag-text {
  color: #334155;
}
.rag-note {
  margin-top: 8px;
  padding: 6px 10px;
  background: #fef3c7;
  border-radius: 6px;
  font-size: 11px;
  color: #92400e;
}
.loading-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #e2e8f0;
  border-top-color: #0ea5e9;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
