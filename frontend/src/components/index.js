/**
 * 组件统一导出索引
 * 
 * 使用方式：
 * import { BaseCard, BaseButton, BaseTag, BaseEmpty, AttractionCard } from '@/components'
 */

// 基础组件
export { default as BaseCard } from './base/BaseCard.vue'
export { default as BaseButton } from './base/BaseButton.vue'
export { default as BaseTag } from './base/BaseTag.vue'
export { default as BaseEmpty } from './base/BaseEmpty.vue'

// 业务组件
export { default as AttractionCard } from './business/AttractionCard.vue'

// 原有组件（保持向后兼容）
export { default as ChatPlanner } from './ChatPlanner.vue'
export { default as DayCard } from './DayCard.vue'
export { default as MapView } from './MapView.vue'
