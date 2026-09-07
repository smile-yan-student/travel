<template>
  <div class="panel">
    <h2>🗺️ 高德与缓存管理</h2>
    <p class="tip">地图数据源与缓存治理（M8）</p>

    <div class="info-grid" v-if="amap">
      <div class="info-item">
        <span>当前生效数据源</span>
        <b :class="amap.provider === 'mock' ? 'bad' : 'ok'">
          {{ providerText }}
        </b>
      </div>
      <div class="info-item">
        <span>高德 Web 服务 Key</span>
        <b :class="amap.key_configured ? 'ok' : 'bad'">
          {{ amap.key_configured ? amap.key_masked : '未配置' }}
        </b>
      </div>
      <div class="info-item">
        <span>高德 Key 来源</span>
        <b>{{ sourceText }}</b>
      </div>
      <div class="info-item">
        <span>高德数据模式</span>
        <b :class="amap.amap_ready ? 'ok' : 'bad'">
          {{ amap.mode === 'real' ? '真实数据' : '演示数据' }}
        </b>
      </div>
      <div class="info-item">
        <span>腾讯地图 Key</span>
        <b :class="amap.tencent_key_configured ? 'ok' : 'bad'">
          {{ amap.tencent_key_configured ? amap.tencent_key_masked : '未配置' }}
        </b>
      </div>
      <div class="info-item">
        <span>腾讯 Key 来源</span>
        <b>{{ tencentSourceText }}</b>
      </div>
      <div class="info-item">
        <span>腾讯数据模式</span>
        <b :class="amap.tencent_ready ? 'ok' : 'bad'">
          {{ amap.tencent_mode === 'real' ? '真实数据' : '演示数据' }}
        </b>
      </div>
    </div>

    <!-- API Key 管理 -->
    <div v-if="userRole === 'super'" class="key-mgr">
      <h3>API Key 管理（仅超级管理员）</h3>
      <p class="tip">
        高德优先、腾讯兜底、都不可用则诚实降级为演示数据。保存后立即生效并自动探测有效性；
        更换 Key 会自动清空旧缓存。清空后回退到环境变量配置。
      </p>
      <div class="key-row">
        <input
          v-model="newKey"
          type="password"
          placeholder="粘贴新的高德 Web 服务 Key（Web服务类型，非 Web端 JS Key）"
          autocomplete="off"
        />
        <button class="primary" @click="saveKey" :disabled="saving">
          {{ saving ? '保存中…' : '保存高德并探测' }}
        </button>
        <button class="ghost" @click="clearKey">清空高德(回退环境变量)</button>
      </div>
      <div class="key-row">
        <input
          v-model="newTencentKey"
          type="password"
          placeholder="粘贴新的腾讯地图 Key（腾讯位置服务，WebService API）"
          autocomplete="off"
        />
        <button class="primary" @click="saveTencentKey" :disabled="saving">
          {{ saving ? '保存中…' : '保存腾讯并探测' }}
        </button>
        <button class="ghost" @click="clearTencentKey">清空腾讯(回退环境变量)</button>
      </div>
      <p v-if="keyMsg" :class="['key-msg', keyMsg.ok ? 'ok' : 'bad']">{{ keyMsg.text }}</p>
    </div>
    <p v-else class="muted">API Key 修改仅超级管理员可操作。</p>

    <div class="info-grid" v-if="cacheInfo">
      <div class="info-item">
        <span>缓存总条目</span>
        <b>{{ cacheInfo.total }}</b>
      </div>
      <div class="info-item">
        <span>Geo 缓存</span>
        <b>{{ cacheInfo.by_type.geo || 0 }}</b>
      </div>
      <div class="info-item">
        <span>POI 缓存</span>
        <b>{{ cacheInfo.by_type.poi || 0 }}</b>
      </div>
      <div class="info-item">
        <span>Route 缓存</span>
        <b>{{ cacheInfo.by_type.route || 0 }}</b>
      </div>
      <div class="info-item">
        <span>Weather 缓存</span>
        <b>{{ cacheInfo.by_type.weather || 0 }}</b>
      </div>
      <div class="info-item">
        <span>TTL（geo/poi/route/weather）</span>
        <b class="mono">
          {{ fmtTtl(cacheInfo.ttl.geo) }}/{{ fmtTtl(cacheInfo.ttl.poi) }}/{{
            fmtTtl(cacheInfo.ttl.route)
          }}/{{ fmtTtl(cacheInfo.ttl.weather) }}
        </b>
      </div>
    </div>

    <div class="actions">
      <button class="danger" @click="clearCache">一键清空缓存</button>
      <button class="ghost" @click="load">刷新状态</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { adminRequest } from '../../../api'

const props = defineProps({ token: String, userRole: String })
const amap = ref(null)
const cacheInfo = ref(null)
const newKey = ref('')
const newTencentKey = ref('')
const saving = ref(false)
const keyMsg = ref(null)

const sourceText = computed(() => {
  const s = amap.value?.key_source
  return s === 'site' ? '后台配置' : s === 'env' ? '环境变量' : '未配置'
})

const tencentSourceText = computed(() => {
  const s = amap.value?.tencent_key_source
  return s === 'site' ? '后台配置' : s === 'env' ? '环境变量' : '未配置'
})

const providerText = computed(() => {
  const p = amap.value?.provider
  return p === 'amap' ? '高德地图（真实）' : p === 'tencent' ? '腾讯地图（真实）' : '演示数据（无可用 Key）'
})

function fmtTtl(sec) {
  if (sec >= 86400) return Math.round(sec / 86400) + 'd'
  if (sec >= 3600) return Math.round(sec / 3600) + 'h'
  return Math.round(sec / 60) + 'm'
}

async function load() {
  amap.value = await adminRequest('/amap', {}, props.token)
  cacheInfo.value = await adminRequest('/cache', {}, props.token)
}

async function saveKey() {
  if (!newKey.value.trim()) {
    keyMsg.value = { ok: false, text: '请先粘贴要保存的 Key' }
    return
  }
  saving.value = true
  keyMsg.value = null
  try {
    const res = await adminRequest('/amap/key', {
      method: 'POST',
      body: JSON.stringify({ amap_key: newKey.value.trim() }),
    }, props.token)
    if (res.probed) {
      keyMsg.value = { ok: true, text: '保存成功，已探测为可用，当前为真实数据模式' }
    } else {
      keyMsg.value = {
        ok: false,
        text: '已保存，但探测未通过（Key 类型不符/无效/网络异常），应用处于演示数据模式',
      }
    }
    newKey.value = ''
    await load()
  } catch (e) {
    keyMsg.value = { ok: false, text: '保存失败：' + e.message }
  } finally {
    saving.value = false
  }
}

async function clearKey() {
  if (!confirm('确认清空后台保存的高德 Key，回退到环境变量配置？')) return
  await adminRequest('/amap/key', { method: 'POST', body: JSON.stringify({ amap_key: '' }) }, props.token)
  keyMsg.value = { ok: true, text: '已清空后台高德 Key，回退到环境变量配置' }
  await load()
}

async function saveTencentKey() {
  if (!newTencentKey.value.trim()) {
    keyMsg.value = { ok: false, text: '请先粘贴要保存的腾讯 Key' }
    return
  }
  saving.value = true
  keyMsg.value = null
  try {
    const res = await adminRequest('/tencent/key', {
      method: 'POST',
      body: JSON.stringify({ tencent_key: newTencentKey.value.trim() }),
    }, props.token)
    if (res.probed) {
      keyMsg.value = { ok: true, text: '腾讯 Key 保存成功，已探测为可用' }
    } else {
      keyMsg.value = {
        ok: false,
        text: '腾讯 Key 已保存，但探测未通过（Key 无效/未开通 WebService 服务/网络异常）',
      }
    }
    newTencentKey.value = ''
    await load()
  } catch (e) {
    keyMsg.value = { ok: false, text: '保存失败：' + e.message }
  } finally {
    saving.value = false
  }
}

async function clearTencentKey() {
  if (!confirm('确认清空后台保存的腾讯 Key，回退到环境变量配置？')) return
  await adminRequest('/tencent/key', { method: 'POST', body: JSON.stringify({ tencent_key: '' }) }, props.token)
  keyMsg.value = { ok: true, text: '已清空后台腾讯 Key，回退到环境变量配置' }
  await load()
}

async function clearCache() {
  if (!confirm('确认清空全部高德缓存？')) return
  await adminRequest('/cache/clear', { method: 'POST' }, props.token)
  alert('缓存已清空')
  load()
}
onMounted(load)
</script>

<style scoped>
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
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
.actions {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}
.actions button,
.key-row button {
  padding: 9px 18px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
}
.danger {
  background: #d33;
  color: #fff;
  border: none;
}
.ghost {
  background: #fff;
  color: #1a2a3a;
  border: 1px solid #ccd2dc;
}
.key-mgr {
  background: #fff;
  border: 1px solid #e6e9ef;
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 18px;
}
.key-mgr h3 {
  margin: 0 0 6px;
  font-size: 15px;
}
.key-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.key-row input {
  flex: 1;
  min-width: 260px;
  padding: 9px 12px;
  border: 1px solid #dfe3ea;
  border-radius: 8px;
  font-size: 13px;
}
.key-row .primary {
  background: #1a9e5c;
  color: #fff;
  border: none;
}
.key-msg {
  margin-top: 10px;
  font-size: 13px;
}
.key-msg.ok {
  color: #1a9e5c;
}
.key-msg.bad {
  color: #d33;
}
.muted {
  color: #a0a8b4;
  margin-bottom: 14px;
}
</style>
