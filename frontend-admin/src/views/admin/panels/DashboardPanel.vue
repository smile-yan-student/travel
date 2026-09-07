<template>
  <div class="panel">
    <h2>📊 仪表盘</h2>
    <p class="tip">核心经营指标总览（M2）</p>

    <div class="cards" v-if="dash.stats">
      <div class="stat-card">
        <span class="num">{{ dash.stats.users_total }}</span>
        <span class="lbl">用户总数</span>
      </div>
      <div class="stat-card">
        <span class="num">{{ dash.stats.users_new_7d }}</span>
        <span class="lbl">近7日新增用户</span>
      </div>
      <div class="stat-card">
        <span class="num">{{ dash.stats.trips_total }}</span>
        <span class="lbl">行程总数</span>
      </div>
      <div class="stat-card">
        <span class="num">{{ dash.stats.cities_total }}</span>
        <span class="lbl">足迹城市数</span>
      </div>
      <div class="stat-card">
        <span class="num">{{ dash.stats.conv_total }}</span>
        <span class="lbl">对话会话数</span>
      </div>
      <div class="stat-card">
        <span class="num">{{ dash.stats.conv_msgs_total }}</span>
        <span class="lbl">对话消息数</span>
      </div>
    </div>

    <h3>系统运行状态</h3>
    <table class="grid">
      <tbody>
        <tr>
          <td>高德数据源</td>
          <td>
            <span :class="['tag', dash.amap_ready ? 'ok' : 'warn']">
              {{ dash.amap_mode === 'real' ? '真实数据' : '演示数据' }}
            </span>
          </td>
        </tr>
        <tr>
          <td>AI 模型</td>
          <td>
            <span :class="['tag', dash.ai_available ? 'ok' : 'warn']">
              {{ dash.ai_available ? dash.ai_model : '不可用' }}
            </span>
          </td>
        </tr>
        <tr>
          <td>高德缓存占用</td>
          <td>{{ dash.cache ? dash.cache.total : 0 }} 条（{{ cacheDetail }}）</td>
        </tr>
      </tbody>
    </table>

    <button class="refresh" @click="load" :disabled="loading">刷新数据</button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { adminRequest } from '../../../api'

const props = defineProps({ token: String })
const dash = ref({})
const loading = ref(false)

const cacheDetail = computed(() => {
  const by = dash.value.cache?.by_type || {}
  return Object.entries(by)
    .map(([k, v]) => `${k}:${v}`)
    .join(' / ') || '空'
})

async function load() {
  loading.value = true
  try {
    dash.value = await adminRequest('/dashboard', {}, props.token)
  } catch (e) {
    alert('加载失败：' + e.message)
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 22px;
}
.stat-card {
  background: #fff;
  border: 1px solid #e6e9ef;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.num {
  font-size: 24px;
  font-weight: 700;
  color: #1a2a3a;
}
.lbl {
  font-size: 12px;
  color: #7a8494;
}
.grid td {
  padding: 10px 12px;
  border: 1px solid #e6e9ef;
  background: #fff;
  font-size: 13px;
}
.tag {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}
.tag.ok {
  background: #e6f7ee;
  color: #1a9e5c;
}
.tag.warn {
  background: #fff3e0;
  color: #e8833a;
}
.refresh {
  margin-top: 16px;
  padding: 9px 18px;
  background: #1a2a3a;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
</style>
