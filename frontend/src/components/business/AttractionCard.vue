<template>
  <div class="attraction-card" :class="{ 'attraction-card--clickable': clickable }" @click="handleClick">
    <div class="attraction-card__header">
      <div class="attraction-card__title">
        <h3 class="attraction-card__name">{{ attraction.name }}</h3>
        <div class="attraction-card__tags">
          <BaseTag v-if="attraction.level" type="primary" size="small">{{ attraction.level }}</BaseTag>
          <BaseTag v-if="attraction.must_visit" type="danger" size="small">必去</BaseTag>
          <BaseTag v-if="attraction.hot" type="warning" size="small">热门</BaseTag>
          <BaseTag v-if="attraction.category" type="info" size="small">{{ attraction.category }}</BaseTag>
        </div>
      </div>
      <div v-if="attraction.rating" class="attraction-card__rating">
        <span class="attraction-card__rating-value">{{ attraction.rating }}</span>
        <span class="attraction-card__rating-star">★</span>
      </div>
    </div>

    <div v-if="attraction.description" class="attraction-card__description">
      {{ attraction.description }}
    </div>

    <div class="attraction-card__info">
      <div v-if="attraction.recommended_duration" class="attraction-card__info-item">
        <span class="attraction-card__info-icon">⏱</span>
        <span>建议游玩 {{ formatDuration(attraction.recommended_duration) }}</span>
      </div>
      <div v-if="attraction.open_hours" class="attraction-card__info-item">
        <span class="attraction-card__info-icon">🕐</span>
        <span>{{ attraction.open_hours }}</span>
      </div>
      <div v-if="attraction.ticket_price" class="attraction-card__info-item">
        <span class="attraction-card__info-icon">🎫</span>
        <span>{{ attraction.ticket_price }}</span>
      </div>
      <div v-if="attraction.best_time" class="attraction-card__info-item">
        <span class="attraction-card__info-icon">📅</span>
        <span>{{ attraction.best_time }}</span>
      </div>
    </div>

    <div v-if="attraction.tags && attraction.tags.length" class="attraction-card__tags-list">
      <BaseTag v-for="tag in attraction.tags.slice(0, 5)" :key="tag" type="default" size="small" effect="plain">
        {{ tag }}
      </BaseTag>
    </div>

    <div v-if="$slots.footer" class="attraction-card__footer">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'
import BaseTag from '../base/BaseTag.vue'

const props = defineProps({
  attraction: {
    type: Object,
    required: true,
    default: () => ({})
  },
  clickable: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['click'])

const handleClick = () => {
  if (props.clickable) {
    emit('click', props.attraction)
  }
}

const formatDuration = (minutes) => {
  if (!minutes) return ''
  if (minutes < 60) return `${minutes}分钟`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (mins === 0) return `${hours}小时`
  return `${hours}小时${mins}分钟`
}
</script>

<style scoped>
.attraction-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.2s ease;
}

.attraction-card--clickable {
  cursor: pointer;
}

.attraction-card--clickable:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.attraction-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.attraction-card__title {
  flex: 1;
}

.attraction-card__name {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.attraction-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.attraction-card__rating {
  display: flex;
  align-items: center;
  gap: 2px;
  background: linear-gradient(135deg, #ff6b6b, #ffa502);
  color: #fff;
  padding: 4px 8px;
  border-radius: 6px;
  font-weight: 600;
}

.attraction-card__rating-value {
  font-size: 14px;
}

.attraction-card__rating-star {
  font-size: 12px;
}

.attraction-card__description {
  margin-bottom: 12px;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.attraction-card__info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.attraction-card__info-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
}

.attraction-card__info-icon {
  font-size: 14px;
}

.attraction-card__tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.attraction-card__footer {
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}
</style>
