<template>
  <button
    class="base-button"
    :class="[
      `base-button--${type}`,
      `base-button--${size}`,
      {
        'base-button--plain': plain,
        'base-button--round': round,
        'base-button--circle': circle,
        'base-button--disabled': disabled,
        'base-button--loading': loading
      }
    ]"
    :disabled="disabled || loading"
    @click="handleClick"
  >
    <span v-if="loading" class="base-button__loading"></span>
    <span v-if="icon && !loading" class="base-button__icon">{{ icon }}</span>
    <span v-if="$slots.default" class="base-button__text">
      <slot></slot>
    </span>
  </button>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

const props = defineProps({
  type: {
    type: String,
    default: 'default',
    validator: (v) => ['primary', 'success', 'warning', 'danger', 'info', 'default', 'text'].includes(v)
  },
  size: {
    type: String,
    default: 'medium',
    validator: (v) => ['large', 'medium', 'small', 'mini'].includes(v)
  },
  plain: {
    type: Boolean,
    default: false
  },
  round: {
    type: Boolean,
    default: false
  },
  circle: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  },
  icon: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['click'])

const handleClick = (e) => {
  if (!props.disabled && !props.loading) {
    emit('click', e)
  }
}
</script>

<style scoped>
.base-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.4;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  user-select: none;
}

.base-button:focus {
  outline: none;
}

/* 尺寸 */
.base-button--large {
  padding: 12px 24px;
  font-size: 16px;
}

.base-button--small {
  padding: 6px 12px;
  font-size: 12px;
}

.base-button--mini {
  padding: 4px 8px;
  font-size: 12px;
}

/* 类型 */
.base-button--primary {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}

.base-button--primary:hover:not(:disabled) {
  background: #66b1ff;
  border-color: #66b1ff;
}

.base-button--success {
  background: #67c23a;
  color: #fff;
  border-color: #67c23a;
}

.base-button--success:hover:not(:disabled) {
  background: #85ce61;
  border-color: #85ce61;
}

.base-button--warning {
  background: #e6a23c;
  color: #fff;
  border-color: #e6a23c;
}

.base-button--warning:hover:not(:disabled) {
  background: #ebb563;
  border-color: #ebb563;
}

.base-button--danger {
  background: #f56c6c;
  color: #fff;
  border-color: #f56c6c;
}

.base-button--danger:hover:not(:disabled) {
  background: #f78989;
  border-color: #f78989;
}

.base-button--info {
  background: #909399;
  color: #fff;
  border-color: #909399;
}

.base-button--info:hover:not(:disabled) {
  background: #a6a9ad;
  border-color: #a6a9ad;
}

.base-button--default {
  background: #fff;
  color: #606266;
  border-color: #dcdfe6;
}

.base-button--default:hover:not(:disabled) {
  background: #ecf5ff;
  color: #409eff;
  border-color: #c6e2ff;
}

.base-button--text {
  background: transparent;
  color: #409eff;
  border-color: transparent;
}

.base-button--text:hover:not(:disabled) {
  background: transparent;
  color: #66b1ff;
}

/* 朴素 */
.base-button--plain.base-button--primary {
  background: #ecf5ff;
  color: #409eff;
  border-color: #b3d8ff;
}

/* 圆角 */
.base-button--round {
  border-radius: 20px;
}

.base-button--circle {
  border-radius: 50%;
  padding: 8px;
}

/* 禁用 */
.base-button--disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 加载 */
.base-button__loading {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.base-button__icon {
  font-size: 16px;
}
</style>
