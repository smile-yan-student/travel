/**
 * 全局状态存储（轻量级，替代 sessionStorage）
 *
 * 使用 Vue 的 reactive 实现响应式全局状态，配合 keep-alive 保存组件状态。
 * 行程数据在内存中传递，不写入本地存储，避免新旧数据混淆。
 */
import { reactive } from 'vue'

// 全局状态
export const appState = reactive({
  // 当前行程数据（ChatPlanner 生成后存入，Plan 页面读取）
  currentPlan: null,
  // 行程生成时间戳（用于判断是否为新行程）
  currentPlanTime: 0,
})

/**
 * 设置当前行程
 * @param {Object} plan - 行程数据
 */
export function setCurrentPlan(plan) {
  appState.currentPlan = plan
  appState.currentPlanTime = Date.now()
}

/**
 * 获取当前行程
 * @returns {Object|null} 行程数据
 */
export function getCurrentPlan() {
  return appState.currentPlan
}

/**
 * 清除当前行程
 */
export function clearCurrentPlan() {
  appState.currentPlan = null
  appState.currentPlanTime = 0
}
