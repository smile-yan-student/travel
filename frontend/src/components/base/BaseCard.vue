<template>
  <div class="base-card" :class="[`base-card--${variant}`, { 'base-card--clickable': clickable }]" @click="handleClick">
    <div v-if="title || $slots.header" class="base-card__header">
      <slot name="header">
        <h3 class="base-card__title">{{ title }}</h3>
        <span v-if="subtitle" class="base-card__subtitle">{{ subtitle }}</span>
      </slot>
    </div>
    <div class="base-card__body">
      <slot></slot>
    </div>
    <div v-if="$slots.footer" class="base-card__footer">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  subtitle: {
    type: String,
    default: ''
  },
  variant: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'primary', 'success', 'warning', 'danger'].includes(v)
  },
  clickable: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['click'])

const handleClick = () => {
  if (props.clickable) {
    emit('click')
  }
}
</script>

<style scoped>
.base-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.2s ease;
}

.base-card--clickable {
  cursor: pointer;
}

.base-card--clickable:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.base-card--primary {
  border-left: 4px solid #409eff;
}

.base-card--success {
  border-left: 4px solid #67c23a;
}

.base-card--warning {
  border-left: 4px solid #e6a23c;
}

.base-card--danger {
  border-left: 4px solid #f56c6c;
}

.base-card__header {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.base-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.base-card__subtitle {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  color: #909399;
}

.base-card__body {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.base-card__footer {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}
</style>
