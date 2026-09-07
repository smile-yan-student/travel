<template>
  <span class="base-tag" :class="[`base-tag--${type}`, `base-tag--${size}`, { 'base-tag--effect': effect }]">
    <span v-if="icon" class="base-tag__icon">{{ icon }}</span>
    <slot></slot>
    <span v-if="closable" class="base-tag__close" @click="handleClose">×</span>
  </span>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

const props = defineProps({
  type: {
    type: String,
    default: 'default',
    validator: (v) => ['primary', 'success', 'warning', 'danger', 'info', 'default'].includes(v)
  },
  size: {
    type: String,
    default: 'medium',
    validator: (v) => ['large', 'medium', 'small'].includes(v)
  },
  effect: {
    type: String,
    default: 'light',
    validator: (v) => ['dark', 'light', 'plain'].includes(v)
  },
  closable: {
    type: Boolean,
    default: false
  },
  icon: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['close'])

const handleClose = (e) => {
  e.stopPropagation()
  emit('close')
}
</script>

<style scoped>
.base-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 8px;
  height: 24px;
  font-size: 12px;
  line-height: 22px;
  border-radius: 4px;
  border: 1px solid transparent;
  white-space: nowrap;
}

.base-tag--large {
  height: 32px;
  padding: 0 12px;
  font-size: 14px;
}

.base-tag--small {
  height: 20px;
  padding: 0 6px;
  font-size: 11px;
}

/* 类型 - light效果 */
.base-tag--primary.base-tag--light {
  background: #ecf5ff;
  color: #409eff;
  border-color: #d9ecff;
}

.base-tag--success.base-tag--light {
  background: #f0f9eb;
  color: #67c23a;
  border-color: #e1f3d8;
}

.base-tag--warning.base-tag--light {
  background: #fdf6ec;
  color: #e6a23c;
  border-color: #faecd8;
}

.base-tag--danger.base-tag--light {
  background: #fef0f0;
  color: #f56c6c;
  border-color: #fde2e2;
}

.base-tag--info.base-tag--light {
  background: #f4f4f5;
  color: #909399;
  border-color: #e9e9eb;
}

.base-tag--default.base-tag--light {
  background: #f4f4f5;
  color: #606266;
  border-color: #dcdfe6;
}

/* 类型 - dark效果 */
.base-tag--primary.base-tag--dark {
  background: #409eff;
  color: #fff;
}

.base-tag--success.base-tag--dark {
  background: #67c23a;
  color: #fff;
}

.base-tag--warning.base-tag--dark {
  background: #e6a23c;
  color: #fff;
}

.base-tag--danger.base-tag--dark {
  background: #f56c6c;
  color: #fff;
}

.base-tag--info.base-tag--dark {
  background: #909399;
  color: #fff;
}

.base-tag--default.base-tag--dark {
  background: #606266;
  color: #fff;
}

/* 类型 - plain效果 */
.base-tag--primary.base-tag--plain {
  background: transparent;
  color: #409eff;
  border-color: #409eff;
}

.base-tag--success.base-tag--plain {
  background: transparent;
  color: #67c23a;
  border-color: #67c23a;
}

.base-tag--warning.base-tag--plain {
  background: transparent;
  color: #e6a23c;
  border-color: #e6a23c;
}

.base-tag--danger.base-tag--plain {
  background: transparent;
  color: #f56c6c;
  border-color: #f56c6c;
}

.base-tag--info.base-tag--plain {
  background: transparent;
  color: #909399;
  border-color: #909399;
}

.base-tag--default.base-tag--plain {
  background: transparent;
  color: #606266;
  border-color: #dcdfe6;
}

.base-tag__close {
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.base-tag__close:hover {
  opacity: 1;
}

.base-tag__icon {
  font-size: 12px;
}
</style>
