<template>
  <div class="base-empty">
    <div class="base-empty__icon">
      <slot name="icon">
        <span class="base-empty__icon-default">📭</span>
      </slot>
    </div>
    <p class="base-empty__description">
      <slot>{{ description }}</slot>
    </p>
    <div v-if="$slots.default" class="base-empty__action">
      <slot name="action"></slot>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue'

defineProps({
  description: {
    type: String,
    default: '暂无数据'
  }
})
</script>

<style scoped>
.base-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.base-empty__icon {
  margin-bottom: 16px;
}

.base-empty__icon-default {
  font-size: 48px;
  opacity: 0.5;
}

.base-empty__description {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: #909399;
  line-height: 1.6;
}

.base-empty__action {
  margin-top: 8px;
}
</style>
