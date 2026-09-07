<template>
  <div class="panel">
    <h2>📋 日志监控</h2>
    <p class="tip">结构化运行日志（请求 / 规划 / AI / 地图 API / 错误），JSON 文件按天轮转保留 7 天（M10）</p>

    <div class="info-grid" v-if="stats">
      <div class="info-item"><span>日志总数</span><b>{{ stats.total }}</b></div>
      <div class="info-item"><span>INFO</span><b class="ok">{{ stats.level_counts.INFO || 0 }}</b></div>
      <div class="info-item"><span>WARNING</span><b class="warn">{{ stats.level_counts.WARNING || 0 }}</b></div>
      <div class="info-item"><span>ERROR</span><b class="bad">{{ stats.level_counts.ERROR || 0 }}</b></div>
    </div>

    <div class="filter-bar">
      <select v-model="level" @change="load">
        <option value="">全部级别</option>
        <option value="INFO">INFO</option>
        <option value="WARNING">WARNING</option>
        <option value="ERROR">ERROR</option>
        <option value="DEBUG">DEBUG</option>
      </select>
      <input v-model="keyword" placeholder="搜索关键词（消息/字段）" @keyup.enter="load" />
      <button @click="load">刷新</button>
    </div>

    <div class="log-list">
      <div v-for="(log, idx) in logs" :key="idx" :class="['log-item', `level-${log.level}`]">
        <div class="log-head">
          <span class="log-ts">{{ log.ts }}</span>
          <span :class="['log-level', `level-${log.level}`]">{{ log.level }}</span>
          <span class="log-logger">{{ log.logger }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
        <div class="log-fields" v-if="hasFields(log)">
          <span v-for="(v, k) in extraFields(log)" :key="k" class="log-field">
            <b>{{ k }}:</b> {{ formatVal(v) }}
          </span>
        </div>
        <pre v-if="log.exc" class="log-exc">{{ log.exc }}</pre>
      </div>
      <div v-if="!logs.length" class="empty">暂无日志（调整过滤条件或刷新）</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminRequest } from '../../../api'

const props = defineProps({ token: String })

const logs = ref([])
const stats = ref(null)
const level = ref('')
const keyword = ref('')

const SKIP_FIELDS = new Set(['ts', 'level', 'logger', 'msg', 'exc'])

function hasFields(log) {
  return Object.keys(log).some(k => !SKIP_FIELDS.has(k))
}
function extraFields(log) {
  const out = {}
  for (const [k, v] of Object.entries(log)) {
    if (!SKIP_FIELDS.has(k)) out[k] = v
  }
  return out
}
function formatVal(v) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

async function load() {
  try {
    const params = new URLSearchParams()
    if (level.value) params.set('level', level.value)
    if (keyword.value) params.set('keyword', keyword.value)
    params.set('limit', '300')
    const res = await adminRequest(`/logs?${params.toString()}`, {}, props.token)
    logs.value = res.logs || []
    stats.value = { total: res.total, level_counts: res.level_counts || {} }
  } catch (e) {
    console.error('load logs failed', e)
  }
}

onMounted(load)
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 8px;
  margin: 12px 0;
  align-items: center;
}
.filter-bar select, .filter-bar input {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
}
.filter-bar input { flex: 1; }
.filter-bar button {
  padding: 6px 16px;
  background: #4f6ef7;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.log-list { margin-top: 8px; }
.log-item {
  padding: 8px 12px;
  border-left: 3px solid #ccc;
  margin-bottom: 4px;
  background: #fafafa;
  border-radius: 0 4px 4px 0;
  font-size: 12px;
}
.log-item.level-INFO { border-left-color: #4f6ef7; }
.log-item.level-WARNING { border-left-color: #f5a623; background: #fffbf0; }
.log-item.level-ERROR { border-left-color: #e74c3c; background: #fff5f5; }
.log-head { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.log-ts { color: #888; font-family: monospace; font-size: 11px; }
.log-level { font-weight: bold; font-size: 11px; padding: 1px 6px; border-radius: 3px; }
.log-level.level-INFO { background: #e8edff; color: #4f6ef7; }
.log-level.level-WARNING { background: #fef3e0; color: #b87a00; }
.log-level.level-ERROR { background: #fde8e8; color: #c0392b; }
.log-logger { color: #666; font-family: monospace; }
.log-msg { font-weight: 500; color: #333; }
.log-fields { margin-top: 4px; display: flex; flex-wrap: wrap; gap: 6px; }
.log-field { background: #fff; padding: 2px 8px; border-radius: 3px; font-size: 11px; color: #555; border: 1px solid #eee; }
.log-field b { color: #888; font-weight: normal; }
.log-exc { margin-top: 6px; padding: 8px; background: #2d2d2d; color: #f88; font-size: 11px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; }
.empty { text-align: center; color: #999; padding: 40px; }
.ok { color: #27ae60; }
.warn { color: #f5a623; }
.bad { color: #e74c3c; }
</style>
