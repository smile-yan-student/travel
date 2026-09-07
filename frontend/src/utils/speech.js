/**
 * 语音播放工具（基于 Web Speech API）
 *
 * 功能：
 * - 语音播放/暂停/停止
 * - 语速/音调/音量调节
 * - 播放进度回调
 * - 中文语音优先选择
 */

// 语音合成实例
let synth = null
// 当前播放的语音
let currentUtterance = null
// 播放状态
let isPlaying = false
let isPaused = false
// 播放回调
let onEndCallback = null
let onStartCallback = null
let onBoundaryCallback = null

/**
 * 初始化语音合成
 */
function initSynth() {
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    synth = window.speechSynthesis
    return true
  }
  return false
}

/**
 * 获取可用的语音列表
 */
function getVoices() {
  if (!synth) initSynth()
  if (!synth) return []
  return synth.getVoices()
}

/**
 * 选择中文语音
 */
function getChineseVoice() {
  const voices = getVoices()
  // 优先选择中文语音
  const chineseVoices = voices.filter(v =>
    v.lang.startsWith('zh') || v.lang.includes('CN') || v.name.includes('中文') || v.name.includes('Chinese')
  )

  if (chineseVoices.length > 0) {
    // 优先选择普通话
    const mandarin = chineseVoices.find(v =>
      v.lang.includes('zh-CN') || v.name.includes('普通话') || v.name.includes('Mandarin')
    )
    return mandarin || chineseVoices[0]
  }

  return null
}

/**
 * 播放语音
 * @param {string} text - 要播放的文本
 * @param {Object} options - 播放选项
 * @param {number} options.rate - 语速（0.1-10，默认1）
 * @param {number} options.pitch - 音调（0-2，默认1）
 * @param {number} options.volume - 音量（0-1，默认1）
 * @param {Function} options.onStart - 开始播放回调
 * @param {Function} options.onEnd - 结束播放回调
 * @param {Function} options.onBoundary - 播放边界回调（用于进度显示）
 * @param {Function} options.onError - 错误回调
 */
function speak(text, options = {}) {
  if (!initSynth()) {
    console.warn('当前浏览器不支持语音合成')
    options.onError && options.onError(new Error('浏览器不支持语音合成'))
    return false
  }

  // 停止当前播放
  stop()

  if (!text || !text.trim()) {
    options.onError && options.onError(new Error('播放文本为空'))
    return false
  }

  // 创建语音实例
  const utterance = new SpeechSynthesisUtterance(text)

  // 设置语音参数
  utterance.rate = options.rate || 1.0
  utterance.pitch = options.pitch || 1.0
  utterance.volume = options.volume || 1.0
  utterance.lang = 'zh-CN'

  // 选择中文语音
  const chineseVoice = getChineseVoice()
  if (chineseVoice) {
    utterance.voice = chineseVoice
  }

  // 设置回调
  utterance.onstart = (event) => {
    isPlaying = true
    isPaused = false
    options.onStart && options.onStart(event)
  }

  utterance.onend = (event) => {
    isPlaying = false
    isPaused = false
    currentUtterance = null
    options.onEnd && options.onEnd(event)
  }

  utterance.onerror = (event) => {
    isPlaying = false
    isPaused = false
    currentUtterance = null
    console.error('语音播放错误:', event)
    options.onError && options.onError(event)
  }

  utterance.onboundary = (event) => {
    options.onBoundary && options.onBoundary(event)
  }

  currentUtterance = utterance
  synth.speak(utterance)

  return true
}

/**
 * 暂停播放
 */
function pause() {
  if (synth && isPlaying && !isPaused) {
    synth.pause()
    isPaused = true
    return true
  }
  return false
}

/**
 * 恢复播放
 */
function resume() {
  if (synth && isPaused) {
    synth.resume()
    isPaused = false
    return true
  }
  return false
}

/**
 * 停止播放
 */
function stop() {
  if (synth) {
    synth.cancel()
    isPlaying = false
    isPaused = false
    currentUtterance = null
    return true
  }
  return false
}

/**
 * 切换播放/暂停
 */
function toggle(text, options = {}) {
  if (isPlaying && !isPaused) {
    return pause()
  } else if (isPaused) {
    return resume()
  } else {
    return speak(text, options)
  }
}

/**
 * 获取播放状态
 */
function getStatus() {
  return {
    isPlaying,
    isPaused,
    supported: !!synth || (typeof window !== 'undefined' && 'speechSynthesis' in window),
  }
}

/**
 * 生成景点介绍文本
 * @param {Object} poi - 景点信息
 * @returns {string} 介绍文本
 */
function generatePoiIntro(poi) {
  if (!poi) return ''

  const parts = []

  // 景点名称
  parts.push(`${poi.name}。`)

  // 景点级别
  if (poi.poi_level) {
    parts.push(`这是${poi.poi_level}级景区。`)
  }

  // 景点描述
  if (poi.description && poi.description.trim()) {
    parts.push(poi.description)
  }

  // 评分
  if (poi.rating && poi.rating > 0) {
    parts.push(`游客评分${poi.rating}分。`)
  }

  // 建议游玩时长
  if (poi.recommended_duration && poi.recommended_duration > 0) {
    const hours = Math.floor(poi.recommended_duration / 60)
    const minutes = poi.recommended_duration % 60
    if (hours > 0) {
      parts.push(`建议游玩${hours}小时${minutes > 0 ? minutes + '分钟' : ''}。`)
    } else {
      parts.push(`建议游玩${minutes}分钟。`)
    }
  }

  // 最佳游玩时间
  if (poi.best_time && poi.best_time.trim()) {
    parts.push(`最佳游玩时间是${poi.best_time}。`)
  }

  // 避坑提示
  if (poi.avoid_tips && poi.avoid_tips.length > 0) {
    parts.push(`温馨提示：${poi.avoid_tips.join('，')}。`)
  }

  return parts.join('')
}

export default {
  initSynth,
  getVoices,
  getChineseVoice,
  speak,
  pause,
  resume,
  stop,
  toggle,
  getStatus,
  generatePoiIntro,
}
