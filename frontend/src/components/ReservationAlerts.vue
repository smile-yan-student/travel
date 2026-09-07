<template>
  <div class="reservation-alerts" v-if="alerts && alerts.length > 0">
    <div class="card-header" @click="expanded = !expanded">
      <div class="header-left">
        <span class="icon">📅</span>
        <span class="title">预约提醒</span>
        <span class="count-badge">{{ alerts.length }}个景点需预约</span>
      </div>
      <span class="expand-icon">{{ expanded ? '▼' : '▶' }}</span>
    </div>

    <div class="alerts-content" v-show="expanded">
      <div class="alert-item" v-for="(alert, index) in alerts" :key="index">
        <div class="alert-header" @click="toggleItem(index)">
          <div class="attraction-name">
            <span class="name">{{ alert.attraction }}</span>
            <span v-if="alert.ticket_release_time" class="urgent-tag">需提前预约</span>
          </div>
          <span class="item-expand">{{ expandedItems[index] ? '−' : '+' }}</span>
        </div>

        <div class="alert-detail" v-show="expandedItems[index]">
          <div class="detail-row" v-if="alert.channel">
            <span class="detail-label">预约渠道</span>
            <span class="detail-value">{{ alert.channel }}</span>
          </div>
          <div class="detail-row" v-if="alert.ticket_release_time">
            <span class="detail-label">放票时间</span>
            <span class="detail-value highlight">{{ alert.ticket_release_time }}</span>
          </div>
          <div class="detail-row" v-if="alert.opening_hours">
            <span class="detail-label">开放时间</span>
            <span class="detail-value">{{ alert.opening_hours }}</span>
          </div>
          <div class="detail-row" v-if="alert.closing_days">
            <span class="detail-label">闭馆日</span>
            <span class="detail-value warning">{{ alert.closing_days }}</span>
          </div>
          <div class="detail-row" v-if="alert.ticket_price">
            <span class="detail-label">票价</span>
            <span class="detail-value">{{ alert.ticket_price }}</span>
          </div>
          <div class="detail-row" v-if="alert.visitor_route">
            <span class="detail-label">游览路线</span>
            <span class="detail-value">{{ alert.visitor_route }}</span>
          </div>
          <div class="detail-row" v-if="alert.daily_limit">
            <span class="detail-label">每日限流</span>
            <span class="detail-value">{{ alert.daily_limit }}</span>
          </div>
          <div class="detail-row" v-if="alert.tips">
            <span class="detail-label">温馨提示</span>
            <span class="detail-value tip">{{ alert.tips }}</span>
          </div>
          <div class="detail-row" v-if="alert.reservation_url">
            <span class="detail-label">预约链接</span>
            <a :href="alert.reservation_url" target="_blank" class="detail-value link">
              点击预约 →
            </a>
          </div>
        </div>
      </div>
    </div>

    <div class="footer-tip" v-if="!expanded">
      点击展开查看详细预约信息
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  alerts: {
    type: Array,
    default: () => []
  },
  defaultExpanded: {
    type: Boolean,
    default: false
  }
})

const expanded = ref(props.defaultExpanded)
const expandedItems = ref({})

watch(() => props.alerts, (newAlerts) => {
  // 重置展开状态
  expandedItems.value = {}
}, { deep: true })

function toggleItem(index) {
  expandedItems.value[index] = !expandedItems.value[index]
}
</script>

<style scoped>
.reservation-alerts {
  background: linear-gradient(135deg, #fff8e1 0%, #fffde7 100%);
  border-radius: 12px;
  border: 1px solid #ffe082;
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
  background: rgba(255, 193, 7, 0.1);
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
  color: #e65100;
}

.count-badge {
  background: #ff9800;
  color: white;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.expand-icon {
  font-size: 12px;
  color: #e65100;
  transition: transform 0.2s;
}

.alerts-content {
  padding: 0 16px 16px;
}

.alert-item {
  background: white;
  border-radius: 8px;
  margin-top: 10px;
  border: 1px solid #ffe082;
  overflow: hidden;
}

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
  user-select: none;
  background: #fffde7;
}

.attraction-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.urgent-tag {
  background: #f44336;
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.item-expand {
  font-size: 18px;
  color: #999;
  font-weight: 300;
}

.alert-detail {
  padding: 12px 14px;
  border-top: 1px solid #fff3e0;
}

.detail-row {
  display: flex;
  margin-bottom: 8px;
  font-size: 13px;
  line-height: 1.5;
}

.detail-row:last-child {
  margin-bottom: 0;
}

.detail-label {
  width: 70px;
  flex-shrink: 0;
  color: #999;
  font-weight: 500;
}

.detail-value {
  flex: 1;
  color: #333;
}

.detail-value.highlight {
  color: #e65100;
  font-weight: 600;
}

.detail-value.warning {
  color: #f44336;
  font-weight: 500;
}

.detail-value.tip {
  color: #ff9800;
  font-style: italic;
}

.detail-value.link {
  color: #2196f3;
  text-decoration: none;
}

.detail-value.link:hover {
  text-decoration: underline;
}

.footer-tip {
  text-align: center;
  font-size: 11px;
  color: #999;
  padding: 8px;
  background: rgba(255, 193, 7, 0.05);
}
</style>
