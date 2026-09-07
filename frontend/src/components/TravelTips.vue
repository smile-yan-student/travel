<template>
  <div class="travel-tips" v-if="tips && tips.length > 0">
    <div class="card-header" @click="expanded = !expanded">
      <div class="header-left">
        <span class="icon">💡</span>
        <span class="title">避坑指南</span>
        <span class="count-badge">{{ tips.length }}条实用提示</span>
      </div>
      <span class="expand-icon">{{ expanded ? '▼' : '▶' }}</span>
    </div>

    <div class="tips-content" v-show="expanded">
      <!-- 分类筛选 -->
      <div class="category-filter" v-if="categories.length > 1">
        <button
          v-for="cat in categories"
          :key="cat.key"
          :class="['filter-btn', { active: activeCategory === cat.key }]"
          @click="activeCategory = cat.key"
        >
          {{ cat.icon }} {{ cat.label }}
          <span class="filter-count">{{ cat.count }}</span>
        </button>
      </div>

      <!-- 提示列表 -->
      <div class="tips-list">
        <div
          v-for="(tip, index) in filteredTips"
          :key="index"
          :class="['tip-item', tip.severity || 'info']"
        >
          <div class="tip-icon">
            {{ getSeverityIcon(tip.severity) }}
          </div>
          <div class="tip-content">
            <div class="tip-text">{{ tip.tip }}</div>
            <div class="tip-meta" v-if="tip.category || tip.source">
              <span class="tip-category" v-if="tip.category">
                {{ getCategoryLabel(tip.category) }}
              </span>
              <span class="tip-source" v-if="tip.source">
                来源: {{ tip.source }}
              </span>
              <span class="tip-frequency" v-if="tip.frequency">
                {{ tip.frequency }}人验证
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div class="empty-state" v-if="filteredTips.length === 0">
        该分类暂无提示
      </div>
    </div>

    <div class="footer-tip" v-if="!expanded">
      点击展开查看详细避坑指南
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  tips: {
    type: Array,
    default: () => []
  },
  defaultExpanded: {
    type: Boolean,
    default: false
  }
})

const expanded = ref(props.defaultExpanded)
const activeCategory = ref('all')

// 类别配置
const categoryConfig = {
  all: { label: '全部', icon: '📋' },
  anti_fraud: { label: '防骗', icon: '🚫' },
  reservation: { label: '预约', icon: '📅' },
  traffic: { label: '交通', icon: '🚇' },
  food: { label: '美食', icon: '🍜' },
  accommodation: { label: '住宿', icon: '🏨' },
  weather: { label: '天气', icon: '🌤' },
  safety: { label: '安全', icon: '⚠️' },
  general: { label: '通用', icon: '📌' }
}

// 严重程度配置
const severityConfig = {
  info: { icon: 'ℹ️', label: '信息' },
  warning: { icon: '⚠️', label: '警告' },
  danger: { icon: '🚨', label: '危险' }
}

// 计算所有类别
const categories = computed(() => {
  const catMap = {}
  props.tips.forEach(tip => {
    const cat = tip.category || 'general'
    if (!catMap[cat]) {
      catMap[cat] = 0
    }
    catMap[cat]++
  })

  const result = [{ key: 'all', label: '全部', icon: '📋', count: props.tips.length }]
  Object.keys(catMap).forEach(cat => {
    const config = categoryConfig[cat] || categoryConfig.general
    result.push({
      key: cat,
      label: config.label,
      icon: config.icon,
      count: catMap[cat]
    })
  })
  return result
})

// 过滤后的提示
const filteredTips = computed(() => {
  if (activeCategory.value === 'all') {
    return props.tips
  }
  return props.tips.filter(tip => (tip.category || 'general') === activeCategory.value)
})

watch(() => props.tips, () => {
  activeCategory.value = 'all'
}, { deep: true })

function getCategoryLabel(category) {
  const config = categoryConfig[category] || categoryConfig.general
  return config.label
}

function getSeverityIcon(severity) {
  const config = severityConfig[severity] || severityConfig.info
  return config.icon
}
</script>

<style scoped>
.travel-tips {
  background: linear-gradient(135deg, #e3f2fd 0%, #e8f5e9 100%);
  border-radius: 12px;
  border: 1px solid #90caf9;
  overflow: hidden;
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  cursor: pointer;
  user-select: none;
  background: rgba(33, 150, 243, 0.1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon {
  font-size: 18px;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: #1565c0;
}

.count-badge {
  background: #2196f3;
  color: white;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.expand-icon {
  font-size: 12px;
  color: #1565c0;
  transition: transform 0.2s;
}

.tips-content {
  padding: 0 16px 16px;
}

.category-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 12px 0;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border: 1px solid #bbdefb;
  border-radius: 16px;
  background: white;
  font-size: 12px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-btn:hover {
  border-color: #2196f3;
  color: #2196f3;
}

.filter-btn.active {
  background: #2196f3;
  color: white;
  border-color: #2196f3;
}

.filter-count {
  background: rgba(0, 0, 0, 0.1);
  padding: 1px 5px;
  border-radius: 8px;
  font-size: 10px;
}

.filter-btn.active .filter-count {
  background: rgba(255, 255, 255, 0.2);
}

.tips-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tip-item {
  display: flex;
  gap: 10px;
  padding: 12px;
  background: white;
  border-radius: 8px;
  border-left: 3px solid #90caf9;
}

.tip-item.info {
  border-left-color: #2196f3;
  background: #f5f9ff;
}

.tip-item.warning {
  border-left-color: #ff9800;
  background: #fff8e1;
}

.tip-item.danger {
  border-left-color: #f44336;
  background: #ffebee;
}

.tip-icon {
  font-size: 16px;
  flex-shrink: 0;
  margin-top: 1px;
}

.tip-content {
  flex: 1;
  min-width: 0;
}

.tip-text {
  font-size: 13px;
  color: #333;
  line-height: 1.6;
}

.tip-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
  font-size: 11px;
}

.tip-category {
  background: #e3f2fd;
  color: #1565c0;
  padding: 2px 6px;
  border-radius: 4px;
}

.tip-source {
  color: #999;
}

.tip-frequency {
  color: #4caf50;
  font-weight: 500;
}

.empty-state {
  text-align: center;
  padding: 20px;
  color: #999;
  font-size: 13px;
}

.footer-tip {
  text-align: center;
  font-size: 11px;
  color: #999;
  padding: 8px;
  background: rgba(33, 150, 243, 0.05);
}
</style>
