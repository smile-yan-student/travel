<template>
  <div class="poster-wrapper">
    <!-- 海报内容（用于生成图片） -->
    <div ref="posterRef" class="poster" :style="{ background: gradientStyle }">
      <!-- 顶部装饰 -->
      <div class="poster-header">
        <div class="header-pattern"></div>
        <div class="header-content">
          <div class="brand">
            <span class="brand-icon">✈️</span>
            <span class="brand-name">{{ brandName }}</span>
          </div>
          <div class="destination">{{ plan.destination }}</div>
          <div class="trip-meta">
            <span class="meta-item">{{ plan.days }}天行程</span>
            <span class="meta-dot">·</span>
            <span class="meta-item">{{ plan.all_pois.length }}个点位</span>
            <span class="meta-dot">·</span>
            <span class="meta-item">{{ plan.style || '经典打卡' }}</span>
          </div>
          <div class="trip-quote" v-if="plan.departure_message">
            "{{ plan.departure_message }}"
          </div>
        </div>
      </div>

      <!-- 行程内容 -->
      <div class="poster-body">
        <div v-for="(day, di) in plan.day_plans" :key="day.day" class="day-section">
          <div class="day-header">
            <div class="day-badge" :style="{ background: dayColors[di % dayColors.length] }">
              Day {{ day.day }}
            </div>
            <div class="day-title">{{ day.theme || `第${day.day}天行程` }}</div>
          </div>
          <div class="day-items">
            <div v-for="(item, ii) in day.items.slice(0, 5)" :key="ii" class="day-item">
              <div class="item-time">{{ item.start_time || '--:--' }}</div>
              <div class="item-dot" :style="{ background: catColor(item.poi?.category) }"></div>
              <div class="item-info">
                <div class="item-name">{{ item.poi?.name || '未命名' }}</div>
                <div class="item-cat" v-if="item.poi?.category">
                  {{ item.poi?.category }}
                  <span v-if="item.poi?.rating" class="item-rating">⭐ {{ item.poi.rating }}</span>
                </div>
              </div>
            </div>
            <div v-if="day.items.length > 5" class="more-hint">
              还有 {{ day.items.length - 5 }} 个点位...
            </div>
          </div>
        </div>
      </div>

      <!-- 底部 -->
      <div class="poster-footer">
        <div class="footer-line"></div>
        <div class="footer-content">
          <div class="footer-slogan">世界在等你，出发吧！</div>
          <div class="footer-info">
            <span>由 AI 智能规划生成</span>
            <span class="footer-dot">·</span>
            <span>{{ generateDate }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="poster-actions">
      <button class="action-btn primary" @click="generatePoster" :disabled="generating">
        {{ generating ? '生成中...' : '📸 生成海报' }}
      </button>
      <button v-if="posterUrl" class="action-btn success" @click="downloadPoster">
        ⬇️ 下载图片
      </button>
      <button v-if="posterUrl" class="action-btn" @click="closePoster">
        关闭
      </button>
    </div>

    <!-- 生成的海报预览 -->
    <div v-if="posterUrl" class="poster-preview">
      <div class="preview-title">海报预览（长按保存）</div>
      <img :src="posterUrl" alt="行程海报" class="preview-img" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import html2canvas from 'html2canvas'

const props = defineProps({
  plan: { type: Object, required: true },
  brandName: { type: String, default: 'AI智能行程规划' },
})

const emit = defineEmits(['close'])

const posterRef = ref(null)
const generating = ref(false)
const posterUrl = ref('')

const dayColors = ['#00b8a9', '#f8b500', '#3b82f6', '#ef4444', '#8b5cf6', '#10b981']

const CAT_COLOR = {
  '景点': '#f59e0b',
  '美食': '#ef4444',
  '购物': '#3b82f6',
  '夜生活': '#8b5cf6',
  '酒店': '#6b7280',
  '其他': '#6b7280',
}

function catColor(c) {
  return CAT_COLOR[c] || CAT_COLOR['其他']
}

const gradientStyle = computed(() => {
  return 'linear-gradient(180deg, #1a1a2e 0%, #16213e 30%, #0f3460 100%)'
})

const generateDate = computed(() => {
  const now = new Date()
  return `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, '0')}.${String(now.getDate()).padStart(2, '0')}`
})

async function generatePoster() {
  if (!posterRef.value || generating.value) return

  generating.value = true
  try {
    // 等待DOM更新
    await new Promise(resolve => setTimeout(resolve, 100))

    const canvas = await html2canvas(posterRef.value, {
      scale: 2,
      useCORS: true,
      allowTaint: true,
      backgroundColor: null,
      logging: false,
    })

    posterUrl.value = canvas.toDataURL('image/png')
  } catch (error) {
    console.error('生成海报失败:', error)
    alert('生成海报失败，请重试')
  } finally {
    generating.value = false
  }
}

function downloadPoster() {
  if (!posterUrl.value) return

  const link = document.createElement('a')
  link.download = `${props.plan.destination}_行程海报_${generateDate.value}.png`
  link.href = posterUrl.value
  link.click()
}

function closePoster() {
  emit('close')
}
</script>

<style scoped>
.poster-wrapper {
  padding: 16px;
}

/* 海报主体 */
.poster {
  width: 100%;
  max-width: 420px;
  margin: 0 auto;
  border-radius: 20px;
  overflow: hidden;
  color: #fff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* 顶部 */
.poster-header {
  position: relative;
  padding: 30px 24px 24px;
}

.header-pattern {
  position: absolute;
  top: -50px;
  right: -50px;
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(0, 184, 169, 0.3) 0%, transparent 70%);
  border-radius: 50%;
}

.header-content {
  position: relative;
  z-index: 1;
}

.brand {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
}

.brand-icon {
  font-size: 18px;
}

.brand-name {
  font-size: 14px;
  font-weight: 600;
  opacity: 0.9;
  letter-spacing: 1px;
}

.destination {
  font-size: 36px;
  font-weight: 800;
  margin-bottom: 8px;
  background: linear-gradient(135deg, #fff 0%, #a8d8ea 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.trip-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  opacity: 0.85;
  margin-bottom: 12px;
}

.meta-dot {
  opacity: 0.5;
}

.trip-quote {
  font-size: 13px;
  font-style: italic;
  opacity: 0.75;
  line-height: 1.6;
  padding-left: 12px;
  border-left: 2px solid rgba(0, 184, 169, 0.6);
}

/* 行程内容 */
.poster-body {
  padding: 0 24px 20px;
}

.day-section {
  margin-bottom: 20px;
}

.day-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.day-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 700;
}

.day-title {
  font-size: 15px;
  font-weight: 600;
}

.day-items {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 12px;
}

.day-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.day-item:last-child {
  border-bottom: none;
}

.item-time {
  width: 45px;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  opacity: 0.8;
  padding-top: 2px;
}

.item-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 6px;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-name {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 2px;
}

.item-cat {
  font-size: 11px;
  opacity: 0.65;
}

.item-rating {
  margin-left: 6px;
}

.more-hint {
  text-align: center;
  font-size: 12px;
  opacity: 0.5;
  padding-top: 8px;
}

/* 底部 */
.poster-footer {
  padding: 16px 24px 24px;
}

.footer-line {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  margin-bottom: 16px;
}

.footer-content {
  text-align: center;
}

.footer-slogan {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 6px;
  background: linear-gradient(135deg, #00b8a9, #f8b500);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.footer-info {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  opacity: 0.5;
}

.footer-dot {
  opacity: 0.3;
}

/* 操作按钮 */
.poster-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  justify-content: center;
  flex-wrap: wrap;
}

.action-btn {
  padding: 10px 20px;
  border-radius: 24px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn.primary {
  background: linear-gradient(135deg, #00b8a9, #00a89a);
  color: #fff;
}

.action-btn.success {
  background: linear-gradient(135deg, #10b981, #059669);
  color: #fff;
}

.action-btn:not(.primary):not(.success) {
  background: #e5e7eb;
  color: #374151;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 海报预览 */
.poster-preview {
  margin-top: 20px;
  text-align: center;
}

.preview-title {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 10px;
}

.preview-img {
  max-width: 100%;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}
</style>
