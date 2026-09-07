<template>
  <div class="speech-player" :class="{ playing: isPlaying, paused: isPaused }">
    <!-- 播放/暂停按钮 -->
    <button class="play-btn" @click="togglePlay" :disabled="!text">
      <span v-if="!isPlaying" class="icon">🔊</span>
      <span v-else-if="isPaused" class="icon">▶️</span>
      <span v-else class="icon playing-icon">⏸</span>
    </button>

    <!-- 播放状态和进度 -->
    <div class="play-info" v-if="isPlaying || isPaused">
      <div class="status-text">
        {{ isPaused ? '已暂停' : '正在讲解...' }}
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
    </div>

    <!-- 语速调节 -->
    <div class="rate-control" v-if="showRateControl">
      <button class="rate-btn" @click="changeRate(-0.1)" :disabled="rate <= 0.5">−</button>
      <span class="rate-value">{{ rate.toFixed(1) }}x</span>
      <button class="rate-btn" @click="changeRate(0.1)" :disabled="rate >= 2">+</button>
    </div>

    <!-- 停止按钮 -->
    <button v-if="isPlaying || isPaused" class="stop-btn" @click="stopPlay">
      ✕
    </button>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import speech from '../utils/speech.js'

const props = defineProps({
  text: { type: String, default: '' },
  showRateControl: { type: Boolean, default: true },
  autoPlay: { type: Boolean, default: false },
})

const emit = defineEmits(['start', 'end', 'error'])

const isPlaying = ref(false)
const isPaused = ref(false)
const rate = ref(1.0)
const progressPercent = ref(0)

// 监听文本变化，停止当前播放
watch(() => props.text, () => {
  stopPlay()
})

// 自动播放
watch(() => props.autoPlay, (val) => {
  if (val && props.text) {
    play()
  }
})

function play() {
  if (!props.text) return

  const success = speech.speak(props.text, {
    rate: rate.value,
    onStart: () => {
      isPlaying.value = true
      isPaused.value = false
      progressPercent.value = 0
      emit('start')
    },
    onEnd: () => {
      isPlaying.value = false
      isPaused.value = false
      progressPercent.value = 100
      emit('end')
      // 重置进度
      setTimeout(() => { progressPercent.value = 0 }, 500)
    },
    onError: (e) => {
      isPlaying.value = false
      isPaused.value = false
      emit('error', e)
    },
    onBoundary: (e) => {
      // 估算进度（基于字符位置）
      if (props.text && props.text.length > 0) {
        progressPercent.value = Math.min(100, (e.charIndex / props.text.length) * 100)
      }
    },
  })

  if (!success) {
    emit('error', new Error('语音播放失败'))
  }
}

function pause() {
  if (speech.pause()) {
    isPaused.value = true
  }
}

function resume() {
  if (speech.resume()) {
    isPaused.value = false
  }
}

function stopPlay() {
  speech.stop()
  isPlaying.value = false
  isPaused.value = false
  progressPercent.value = 0
}

function togglePlay() {
  if (isPlaying.value && !isPaused.value) {
    pause()
  } else if (isPaused.value) {
    resume()
  } else {
    play()
  }
}

function changeRate(delta) {
  const newRate = Math.max(0.5, Math.min(2, rate.value + delta))
  rate.value = newRate
  // 如果正在播放，重新播放以应用新语速
  if (isPlaying.value) {
    play()
  }
}

// 组件卸载时停止播放
onBeforeUnmount(() => {
  stopPlay()
})

// 暴露方法给父组件
defineExpose({
  play,
  pause,
  resume,
  stop: stopPlay,
  toggle: togglePlay,
})
</script>

<style scoped>
.speech-player {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #f7faf9;
  border-radius: 20px;
  transition: all 0.2s;
}

.speech-player.playing {
  background: #e8f5f3;
}

.play-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #00b8a9, #00a89a);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}

.play-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(0, 184, 169, 0.4);
}

.play-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.playing-icon {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.play-info {
  flex: 1;
  min-width: 0;
}

.status-text {
  font-size: 11px;
  color: #00b8a9;
  font-weight: 500;
  margin-bottom: 3px;
}

.progress-bar {
  height: 3px;
  background: #e5e7eb;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #00b8a9, #f8b500);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.rate-control {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.rate-btn {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid #d1d5db;
  background: #fff;
  color: #374151;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.rate-btn:hover:not(:disabled) {
  background: #f3f4f6;
  border-color: #00b8a9;
}

.rate-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.rate-value {
  font-size: 11px;
  color: #6b7280;
  min-width: 30px;
  text-align: center;
}

.stop-btn {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: #fee2e2;
  color: #ef4444;
  font-size: 11px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}

.stop-btn:hover {
  background: #fecaca;
}
</style>
