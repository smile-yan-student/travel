<template>
  <div class="explore">
    <!-- 顶部 -->
    <header class="head">
      <div class="head-main">
        <h1>🧭 周边探索</h1>
        <p>点击地图任意位置，以该点为中心探索周边可去点位</p>
      </div>
      <button v-if="center" class="clear" @click="clearAll">清空</button>
    </header>

    <main class="content">
      <!-- 参数控制 -->
      <div class="controls">
        <div class="ctl-row">
          <span class="ctl-label">半径</span>
          <div class="chips">
            <button v-for="r in RADII" :key="r.v" :class="['chip', { active: radius === r.v }]" @click="setRadius(r.v)">{{ r.label }}</button>
          </div>
        </div>
        <div class="ctl-row">
          <span class="ctl-label">类别</span>
          <div class="chips">
            <button v-for="c in CATEGORIES" :key="c" :class="['chip', { active: category === c }]" @click="setCategory(c)">{{ c }}</button>
          </div>
        </div>
      </div>

      <!-- 地图 / SVG 兜底 -->
      <div class="map-wrap">
        <div ref="mapEl" class="map-el" :style="{ display: useAmap ? 'block' : 'none' }"></div>
        <div v-if="!useAmap" class="svg-wrap" @click="onSvgClick">
          <svg :viewBox="`0 0 ${W} ${H}`" class="svg">
            <rect :width="W" :height="H" fill="#f0f6f4" rx="12" />
            <!-- 放射线 + 点位 -->
            <g v-for="(p, i) in svgPois" :key="p.id || i">
              <line :x1="svgCenter.x" :y1="svgCenter.y" :x2="p.x" :y2="p.y"
                    stroke="#64748b" stroke-width="1.5" stroke-dasharray="5 4" stroke-opacity="0.55" />
              <circle :cx="p.x" :cy="p.y" :r="activePoi === p.id ? 11 : 8"
                      :fill="catColor(p.category)" :stroke="'#fff'"
                      :stroke-width="activePoi === p.id ? 3 : 2" style="cursor:pointer" />
              <text :x="p.x" :y="p.y + 26" text-anchor="middle" font-size="10"
                    :fill="activePoi === p.id ? '#ef4444' : '#374151'" font-weight="600">{{ p.name }}</text>
            </g>
            <!-- 中心点 -->
            <g v-if="center">
              <circle :cx="svgCenter.x" :cy="svgCenter.y" r="12" fill="#ef4444" stroke="#fff" stroke-width="3" />
              <circle :cx="svgCenter.x" :cy="svgCenter.y" r="20" fill="none" stroke="#ef4444" stroke-opacity="0.4" />
              <text :x="svgCenter.x" :y="svgCenter.y - 22" text-anchor="middle" font-size="12" font-weight="700" fill="#ef4444">中心点</text>
            </g>
            <text v-if="!center" :x="W / 2" :y="H / 2" text-anchor="middle" font-size="14" fill="#94a3b8">👆 点击地图选择中心点</text>
          </svg>
        </div>
      </div>

      <div v-if="loading" class="loading"><span class="spinner"></span><span>探索中…</span></div>
      <p v-if="error" class="error">{{ error }}</p>

      <!-- 周边点位列表 -->
      <div v-if="pois.length" class="poi-list">
        <div class="list-title">
          周边 {{ pois.length }} 个点位
          <span class="sub">半径 {{ (radius / 1000).toFixed(0) }}km · 点击聚焦</span>
        </div>
        <div v-for="p in pois" :key="p.id" :class="['poi-item', { active: activePoi === p.id }]" @click="focusPoi(p)">
          <span class="dot" :style="{ background: catColor(p.category) }"></span>
          <div class="poi-info">
            <div class="poi-name">{{ p.name }}</div>
            <div class="poi-meta">{{ p.category }} · {{ (p.distance_m / 1000).toFixed(1) }}km{{ p.district ? ' · ' + p.district : '' }}</div>
          </div>
          <div v-if="p.rating" class="poi-rating">★ {{ p.rating }}</div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
defineOptions({ name: 'Explore' })
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { loadAmap } from '../utils/amap.js'
import { exploreAround } from '../api'

const RADII = [
  { v: 3000, label: '3km' },
  { v: 5000, label: '5km' },
  { v: 10000, label: '10km' },
  { v: 20000, label: '20km' },
]
const CATEGORIES = ['景点', '美食', '购物', '夜生活']
const CAT_COLOR = { 景点: '#f59e0b', 美食: '#ef4444', 购物: '#3b82f6', 夜生活: '#8b5cf6', 酒店: '#6b7280', 其他: '#6b7280' }
const DEFAULT_CENTER = { lng: 120.155, lat: 30.274 } // 杭州

const mapEl = ref(null)
const useAmap = ref(false)
const map = ref(null)
const amapCtor = ref(null)
const center = ref(null)
const pois = ref([])
const radius = ref(10000)
const category = ref('景点')
const loading = ref(false)
const error = ref('')
const activePoi = ref(null)

let centerMarker = null
let layerMarkers = [] // { marker, poi }
let layerLines = []

// ---------- SVG 兜底归一化 ----------
const W = 1000
const H = 520
const PAD = 80
const svgSpan = 0.24 // 覆盖约 ±24km

const svgBox = computed(() => {
  const c = center.value || DEFAULT_CENTER
  return { minLng: c.lng - svgSpan, maxLng: c.lng + svgSpan, minLat: c.lat - svgSpan, maxLat: c.lat + svgSpan }
})
const svgCenter = computed(() => {
  const b = svgBox.value
  const c = center.value || DEFAULT_CENTER
  return {
    x: PAD + ((c.lng - b.minLng) / (b.maxLng - b.minLng)) * (W - 2 * PAD),
    y: PAD + ((b.maxLat - c.lat) / (b.maxLat - b.minLat)) * (H - 2 * PAD),
  }
})
const svgPois = computed(() => {
  const b = svgBox.value
  return pois.value.map((p) => ({
    ...p,
    x: PAD + ((p.lng - b.minLng) / (b.maxLng - b.minLng)) * (W - 2 * PAD),
    y: PAD + ((b.maxLat - p.lat) / (b.maxLat - b.minLat)) * (H - 2 * PAD),
  }))
})

function onSvgClick(evt) {
  const rect = evt.currentTarget.getBoundingClientRect()
  const x = ((evt.clientX - rect.left) / rect.width) * W
  const y = ((evt.clientY - rect.top) / rect.height) * H
  if (x < PAD || x > W - PAD || y < PAD || y > H - PAD) return
  const b = svgBox.value
  const lng = b.minLng + ((x - PAD) / (W - 2 * PAD)) * (b.maxLng - b.minLng)
  const lat = b.maxLat - ((y - PAD) / (H - 2 * PAD)) * (b.maxLat - b.minLat)
  selectCenter(lng, lat)
}

function catColor(c) {
  return CAT_COLOR[c] || CAT_COLOR['其他']
}

// ---------- 高德地图 ----------
async function initAmap() {
  const AMap = await loadAmap()
  if (!AMap) return false
  amapCtor.value = AMap
  await nextTick()
  map.value = new AMap.Map(mapEl.value, {
    zoom: 13,
    center: [DEFAULT_CENTER.lng, DEFAULT_CENTER.lat],
  })
  map.value.on('click', (e) => {
    if (e.lnglat) selectCenter(e.lnglat.lng, e.lnglat.lat)
  })
  return true
}

function clearLayer() {
  layerMarkers.forEach(({ marker }) => marker.setMap(null))
  layerLines.forEach((l) => l.setMap(null))
  layerMarkers = []
  layerLines = []
  if (centerMarker) {
    centerMarker.setMap(null)
    centerMarker = null
  }
  activePoi.value = null
}

function poiMarkerEl(color) {
  const el = document.createElement('div')
  el.style.cssText =
    `width:16px;height:16px;border-radius:50%;background:${color};` +
    'border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.35);cursor:pointer;'
  return el
}

function centerEl() {
  const wrap = document.createElement('div')
  wrap.style.cssText = 'position:relative;width:26px;height:26px;'
  const dot = document.createElement('div')
  dot.style.cssText =
    'position:absolute;inset:0;border-radius:50%;background:#ef4444;' +
    'border:3px solid #fff;box-shadow:0 0 0 7px rgba(239,68,68,.28);'
  wrap.appendChild(dot)
  return wrap
}

async function selectCenter(lng, lat) {
  center.value = { lng, lat }
  error.value = ''
  loading.value = true
  clearLayer()
  if (useAmap.value && amapCtor.value) {
    centerMarker = new amapCtor.value.Marker({ position: [lng, lat], content: centerEl(), anchor: 'center' })
    centerMarker.setMap(map.value)
    map.value.setCenter([lng, lat])
    map.value.setZoom(Math.max(map.value.getZoom(), 14))
  }
  try {
    const res = await exploreAround({ lng, lat, radius: radius.value, categories: [category.value] })
    pois.value = res.pois || []
    renderRadial()
  } catch (e) {
    error.value = '探索失败：' + (e.message || '请检查后端服务')
    pois.value = []
  } finally {
    loading.value = false
  }
}

function renderRadial() {
  if (!useAmap.value || !amapCtor.value || !center.value) return
  const AMap = amapCtor.value
  const c = center.value
  pois.value.forEach((p) => {
    // 中心 → 点位 放射线（虚线，呈放射状）
    const line = new AMap.Polyline({
      path: [[c.lng, c.lat], [p.lng, p.lat]],
      strokeColor: '#64748b',
      strokeWeight: 1.5,
      strokeOpacity: 0.5,
      strokeStyle: 'dashed',
      lineJoin: 'round',
      lineCap: 'round',
    })
    line.setMap(map.value)
    layerLines.push(line)
    // 点位 marker（类别色圆点 + 名称）
    const el = poiMarkerEl(catColor(p.category))
    const marker = new AMap.Marker({
      position: [p.lng, p.lat], content: el, anchor: 'center', title: p.name,
    })
    marker.setLabel({
      content: `<div style="font-size:11px;color:#fff;background:${catColor(p.category)};padding:1px 7px;border-radius:9px;white-space:nowrap;max-width:130px;overflow:hidden;text-overflow:ellipsis">${p.name}</div>`,
      direction: 'top',
    })
    marker.on('click', () => focusPoi(p))
    marker.setMap(map.value)
    layerMarkers.push({ marker, poi: p })
  })
  if (centerMarker) map.value.setFitView([centerMarker, ...layerMarkers.map((x) => x.marker)], false, [70, 70, 70, 70])
}

function focusPoi(p) {
  activePoi.value = p.id
  if (map.value && amapCtor.value) {
    map.value.setZoom(Math.max(map.value.getZoom(), 15))
    map.value.setCenter([p.lng, p.lat])
    layerMarkers.forEach(({ marker, poi }) => {
      const el = marker.getContent()
      if (poi && poi.id === p.id) {
        el.style.cssText =
          'width:24px;height:24px;border-radius:50%;background:#ef4444;' +
          'border:3px solid #fff;box-shadow:0 0 0 6px rgba(239,68,68,.3);'
      } else {
        el.style.cssText = poiMarkerEl(catColor(poi.category)).style.cssText
      }
    })
  }
}

function setRadius(v) {
  radius.value = v
  if (center.value) selectCenter(center.value.lng, center.value.lat)
}
function setCategory(c) {
  category.value = c
  if (center.value) selectCenter(center.value.lng, center.value.lat)
}
function clearAll() {
  clearLayer()
  center.value = null
  pois.value = []
  if (map.value) map.value.setZoom(13)
}

onMounted(async () => {
  const AMAP_KEY = import.meta.env.VITE_AMAP_WEB_KEY || ''
  if (AMAP_KEY) {
    useAmap.value = true
    const ok = await initAmap()
    if (!ok) useAmap.value = false
  }
})

onBeforeUnmount(() => {
  if (map.value) {
    map.value.destroy()
    map.value = null
  }
})
</script>

<style scoped>
.head {
  background: var(--gradient);
  color: #fff;
  padding: 18px 18px 24px;
  border-radius: 0 0 26px 26px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.back {
  color: #fff;
  font-size: 13px;
  background: rgba(255, 255, 255, 0.18);
  padding: 6px 12px;
  border-radius: 999px;
  flex-shrink: 0;
}
.clear {
  margin-left: auto;
  color: #fff;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.18);
  padding: 6px 12px;
  border-radius: 999px;
  flex-shrink: 0;
}
.head-main h1 {
  font-size: 20px;
  font-weight: 700;
}
.head-main p {
  font-size: 12px;
  opacity: 0.88;
  margin-top: 2px;
}
.content {
  padding: 14px 14px 60px;
  margin-top: -14px;
}
.controls {
  background: #fff;
  border: 1.5px solid var(--border);
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 12px;
}
.ctl-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.ctl-row:last-child {
  margin-bottom: 0;
}
.ctl-label {
  font-size: 13px;
  color: var(--text-2);
  flex-shrink: 0;
  width: 34px;
  font-weight: 600;
}
.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.chip {
  padding: 6px 14px;
  border-radius: 999px;
  background: #f0f4f3;
  color: var(--text-2);
  font-size: 13px;
  border: 1.5px solid transparent;
}
.chip.active {
  background: var(--gradient);
  color: #fff;
  font-weight: 600;
}
.map-wrap {
  border-radius: 14px;
  overflow: hidden;
  background: #f0f6f4;
}
.map-el {
  width: 100%;
  height: 360px;
}
.svg-wrap {
  cursor: crosshair;
}
.svg {
  width: 100%;
  height: auto;
  display: block;
}
.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-2);
  font-size: 13px;
  margin-top: 12px;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.error {
  color: var(--danger);
  font-size: 13px;
  text-align: center;
  margin-top: 12px;
}
.poi-list {
  margin-top: 16px;
}
.list-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 10px;
}
.list-title .sub {
  font-size: 12px;
  color: var(--text-3);
  font-weight: 400;
  margin-left: 6px;
}
.poi-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1.5px solid var(--border);
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
}
.poi-item.active {
  border-color: var(--primary);
  background: #f3faf8;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.poi-info {
  flex: 1;
  min-width: 0;
}
.poi-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.poi-meta {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 2px;
}
.poi-rating {
  font-size: 13px;
  font-weight: 700;
  color: #f59e0b;
  flex-shrink: 0;
}
</style>
