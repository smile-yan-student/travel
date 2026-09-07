<template>
  <div class="star-rating" :class="{ readonly: readonly }">
    <div class="stars">
      <span
        v-for="star in 5"
        :key="star"
        class="star"
        :class="{
          active: star <= modelValue,
          hover: star <= hoverStar && !readonly,
          half: star - 0.5 <= modelValue && star > modelValue
        }"
        @click="!readonly && setRating(star)"
        @mouseenter="!readonly && (hoverStar = star)"
        @mouseleave="!readonly && (hoverStar = 0)"
      >
        <span class="star-icon">{{ star <= modelValue ? '★' : '☆' }}</span>
      </span>
    </div>
    <span v-if="showText" class="rating-text">{{ ratingText }}</span>
    <span v-if="showValue" class="rating-value">{{ modelValue.toFixed(1) }}</span>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: { type: Number, default: 0 },
  readonly: { type: Boolean, default: false },
  showText: { type: Boolean, default: false },
  showValue: { type: Boolean, default: false },
  size: { type: String, default: 'medium' }, // small, medium, large
})

const emit = defineEmits(['update:modelValue', 'change'])

const hoverStar = ref(0)

const ratingText = computed(() => {
  const r = props.modelValue
  if (r >= 4.5) return '非常满意'
  if (r >= 3.5) return '满意'
  if (r >= 2.5) return '一般'
  if (r >= 1.5) return '不满意'
  if (r > 0) return '非常不满意'
  return '未评分'
})

function setRating(star) {
  emit('update:modelValue', star)
  emit('change', star)
}
</script>

<style scoped>
.star-rating {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.stars {
  display: flex;
  gap: 2px;
}

.star {
  cursor: pointer;
  transition: transform 0.15s ease;
  font-size: 20px;
  line-height: 1;
}

.star:hover:not(.readonly) {
  transform: scale(1.15);
}

.star-icon {
  color: #d1d5db;
  transition: color 0.15s ease;
}

.star.active .star-icon,
.star.hover .star-icon {
  color: #f59e0b;
}

.star.half .star-icon {
  background: linear-gradient(90deg, #f59e0b 50%, #d1d5db 50%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.readonly .star {
  cursor: default;
}

.readonly .star:hover {
  transform: none;
}

.rating-text {
  font-size: 13px;
  color: #6b7280;
  font-weight: 500;
}

.rating-value {
  font-size: 14px;
  color: #f59e0b;
  font-weight: 700;
}

/* 尺寸变体 */
.star-rating.size-small .star {
  font-size: 14px;
}

.star-rating.size-medium .star {
  font-size: 20px;
}

.star-rating.size-large .star {
  font-size: 28px;
}
</style>
