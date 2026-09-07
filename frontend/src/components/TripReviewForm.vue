<template>
  <div class="review-form">
    <div class="form-header">
      <h3 class="form-title">📝 评价本次行程</h3>
      <p class="form-subtitle">您的评价将帮助更多旅行者做出更好的选择</p>
    </div>

    <!-- 整体评分 -->
    <div class="form-section">
      <label class="section-label">整体评分</label>
      <div class="rating-row">
        <StarRating v-model="form.overall_rating" :show-text="true" size="large" />
      </div>
    </div>

    <!-- 多维度评分 -->
    <div class="form-section">
      <label class="section-label">分项评分</label>
      <div class="dimension-ratings">
        <div class="dimension-item">
          <span class="dimension-name">🗺️ 路线合理性</span>
          <StarRating v-model="form.route_rating" size="small" />
        </div>
        <div class="dimension-item">
          <span class="dimension-name">🏛️ 景点质量</span>
          <StarRating v-model="form.attraction_rating" size="small" />
        </div>
        <div class="dimension-item">
          <span class="dimension-name">💰 预算合理性</span>
          <StarRating v-model="form.budget_rating" size="small" />
        </div>
      </div>
    </div>

    <!-- 推荐指数 -->
    <div class="form-section">
      <label class="section-label">推荐指数</label>
      <div class="recommend-row">
        <StarRating v-model="form.recommend_index" size="medium" />
        <label class="recommend-check">
          <input type="checkbox" v-model="form.would_recommend" />
          <span>我会推荐给朋友</span>
        </label>
      </div>
    </div>

    <!-- 评价标签 -->
    <div class="form-section">
      <label class="section-label">评价标签（可多选）</label>
      <div class="tags-group">
        <button
          v-for="tag in availableTags"
          :key="tag"
          :class="['tag-btn', { active: form.tags.includes(tag) }]"
          @click="toggleTag(tag)"
        >
          {{ tag }}
        </button>
      </div>
    </div>

    <!-- 评价内容 -->
    <div class="form-section">
      <label class="section-label">评价内容</label>
      <textarea
        v-model="form.content"
        class="review-textarea"
        placeholder="分享您的旅行体验，比如哪些景点超出预期，哪些地方可以改进..."
        rows="4"
        maxlength="500"
      ></textarea>
      <div class="char-count">{{ form.content.length }}/500</div>
    </div>

    <!-- 提交按钮 -->
    <div class="form-actions">
      <button class="submit-btn" @click="submitReview" :disabled="submitting || form.overall_rating === 0">
        {{ submitting ? '提交中...' : '提交评价' }}
      </button>
      <button v-if="showCancel" class="cancel-btn" @click="$emit('cancel')">
        取消
      </button>
    </div>

    <!-- 提交成功提示 -->
    <div v-if="submitSuccess" class="success-message">
      ✅ 评价提交成功，感谢您的反馈！
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import StarRating from './StarRating.vue'
import { createTripReview } from '../api'

const props = defineProps({
  tripId: { type: String, required: true },
  destination: { type: String, default: '' },
  showCancel: { type: Boolean, default: false },
})

const emit = defineEmits(['success', 'cancel'])

const submitting = ref(false)
const submitSuccess = ref(false)

const form = reactive({
  overall_rating: 0,
  route_rating: 5,
  attraction_rating: 5,
  budget_rating: 5,
  recommend_index: 3,
  would_recommend: 1,
  content: '',
  tags: [],
})

const availableTags = [
  '景点丰富', '路线合理', '预算准确', '超出预期',
  '人太多', '门票贵', '交通不便', '值得再去',
  '适合亲子', '适合情侣', '适合拍照', '美食很多'
]

function toggleTag(tag) {
  const idx = form.tags.indexOf(tag)
  if (idx > -1) {
    form.tags.splice(idx, 1)
  } else {
    if (form.tags.length < 5) {
      form.tags.push(tag)
    }
  }
}

async function submitReview() {
  if (form.overall_rating === 0) {
    alert('请先给出整体评分')
    return
  }

  submitting.value = true
  try {
    const res = await createTripReview({
      trip_id: props.tripId,
      destination: props.destination,
      overall_rating: form.overall_rating,
      route_rating: form.route_rating,
      attraction_rating: form.attraction_rating,
      budget_rating: form.budget_rating,
      recommend_index: form.recommend_index,
      would_recommend: form.would_recommend,
      content: form.content,
      tags: form.tags,
    })

    if (res.code === 0) {
      submitSuccess.value = true
      emit('success', res.data)
      setTimeout(() => {
        submitSuccess.value = false
      }, 3000)
    } else {
      alert(res.message || '提交失败，请重试')
    }
  } catch (e) {
    alert('提交失败：' + (e.message || '网络错误'))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.review-form {
  background: #fff;
  border-radius: 16px;
  padding: 20px;
}

.form-header {
  text-align: center;
  margin-bottom: 20px;
}

.form-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 6px;
}

.form-subtitle {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
}

.form-section {
  margin-bottom: 18px;
}

.section-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 10px;
}

.rating-row {
  display: flex;
  justify-content: center;
  padding: 10px 0;
}

.dimension-ratings {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dimension-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 10px;
}

.dimension-name {
  font-size: 13px;
  color: #4b5563;
}

.recommend-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.recommend-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #4b5563;
  cursor: pointer;
}

.recommend-check input {
  width: 16px;
  height: 16px;
  accent-color: #00b8a9;
}

.tags-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-btn {
  padding: 6px 14px;
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 20px;
  font-size: 12px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-btn:hover {
  border-color: #00b8a9;
  color: #00b8a9;
}

.tag-btn.active {
  background: #00b8a9;
  border-color: #00b8a9;
  color: #fff;
}

.review-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  font-size: 14px;
  color: #1f2937;
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.review-textarea:focus {
  outline: none;
  border-color: #00b8a9;
}

.char-count {
  text-align: right;
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.submit-btn {
  flex: 1;
  padding: 12px 24px;
  background: linear-gradient(135deg, #00b8a9, #00a89a);
  color: #fff;
  border: none;
  border-radius: 24px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 184, 169, 0.4);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cancel-btn {
  padding: 12px 24px;
  background: #f3f4f6;
  color: #6b7280;
  border: none;
  border-radius: 24px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.cancel-btn:hover {
  background: #e5e7eb;
}

.success-message {
  text-align: center;
  padding: 12px;
  background: #ecfdf5;
  color: #059669;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  margin-top: 16px;
}
</style>
