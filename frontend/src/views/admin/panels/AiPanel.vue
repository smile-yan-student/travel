<template>
  <div class="panel">
    <h2>🤖 AI 模型管理</h2>
    <p class="tip">本地模型运行状态与生成日志（M7）</p>

    <div class="info-grid" v-if="info">
      <div class="info-item">
        <span>模型可用</span>
        <b :class="info.ai_available ? 'ok' : 'bad'">
          {{ info.ai_available ? '可用' : '不可用' }}
        </b>
      </div>
      <div class="info-item">
        <span>当前生效模型</span>
        <b>{{ info.current_model || '—' }}</b>
      </div>
      <div class="info-item">
        <span>配置模型</span>
        <b>{{ info.model_config }}</b>
      </div>
      <div class="info-item">
        <span>Ollama 地址</span>
        <b class="mono">{{ info.base_url }}</b>
      </div>
    </div>

    <div class="row">
      <h3>生成日志（最近 {{ logs.length }} 条）</h3>
      <button class="ghost" @click="load">刷新</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>类型</th>
          <th>模型</th>
          <th>状态</th>
          <th>详情</th>
          <th>时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="l in logs" :key="l.id">
          <td>{{ l.id }}</td>
          <td>{{ l.kind }}</td>
          <td>{{ l.model }}</td>
          <td>
            <span :class="['tag', l.status === 'ok' ? 'ok' : 'bad']">{{ l.status }}</span>
          </td>
          <td>{{ l.detail }}</td>
          <td>{{ l.created_at }}</td>
        </tr>
        <tr v-if="!logs.length">
          <td colspan="6" class="empty">暂无生成日志</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminRequest } from '../../../api'

const props = defineProps({ token: String })
const info = ref(null)
const logs = ref([])

async function load() {
  info.value = await adminRequest('/ai', {}, props.token)
  const res = await adminRequest('/ai/logs?limit=30', {}, props.token)
  logs.value = res.items
}
onMounted(load)
</script>

<style scoped>
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.info-item {
  background: #fff;
  border: 1px solid #e6e9ef;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.info-item span {
  font-size: 12px;
  color: #7a8494;
}
.info-item b {
  font-size: 15px;
}
.info-item .ok {
  color: #1a9e5c;
}
.info-item .bad {
  color: #d33;
}
.mono {
  font-family: ui-monospace, monospace;
  font-size: 13px;
}
.row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 6px 0 10px;
}
.ghost {
  padding: 6px 14px;
  background: #fff;
  color: #1a2a3a;
  border: 1px solid #ccd2dc;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
}
table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  font-size: 13px;
}
th,
td {
  padding: 9px 12px;
  border: 1px solid #e6e9ef;
  text-align: left;
}
th {
  background: #f4f6f9;
  font-weight: 600;
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
.tag.bad {
  background: #fdeaea;
  color: #d33;
}
.empty {
  text-align: center;
  color: #a0a8b4;
  padding: 24px;
}
</style>
