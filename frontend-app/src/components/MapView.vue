<template>
  <div class="map-wrap">
    <div ref="mapEl" class="map-el" :style="{ display: useAmap ? 'block' : 'none' }"></div>
    <div v-if="!useAmap" class="svg-fallback">
      <svg :viewBox="viewBox" preserveAspectRatio="xMidYMid meet" class="svg">
        <rect :width="W" :height="H" fill="#f0f6f4" rx="12" />
        <!-- 平滑路线连线（不同天不同颜色、虚线柔和） -->
        <g v-for="(d, di) in dayPaths" :key="di">
          <path
            :d="d.path"
            :stroke="palette[di % palette.length]"
            stroke-width="3"
            fill="none"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-opacity="0.65"
            stroke-dasharray="8 6"
          />
          <text
            :x="d.pts[0] ? d.pts[0].x : 0"
            :y="(d.pts[0] ? d.pts[0].y : 0) - 12"
            :fill="palette[di % palette.length]"
            font-size="13"
            font-weight="700"
          >第{{ di + 1 }}天</text>
        </g>
        <!-- 点位（中心对齐） -->
        <g v-for="p in plotted" :key="p.poi.id">
          <circle
            :cx="p.x" :cy="p.y" :r="selectedId === p.poi.id ? 10 : 7"
            :fill="selectedId === p.poi.id ? '#ef4444' : catColor(p.poi.category)"
            :stroke="'#fff'"
            :stroke-width="selectedId === p.poi.id ? 3 : 2"
          />
          <text
            :x="p.x" :y="p.y + 22"
            text-anchor="middle"
            font-size="10.5"
            :fill="selectedId === p.poi.id ? '#ef4444' : '#374151'"
            font-weight="600"
          >{{ p.poi.name }}</text>
        </g>
      </svg>
      <p class="hint">未配置高德 JS Key，展示点位示意；配置后自动切换为真实地图</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  days: { type: Array, default: () => [] },
  pois: { type: Array, default: () => [] },
  center: { type: Object, default: () => ({ lng: 116.407, lat: 39.904 }) },
})

const mapEl = ref(null)
const useAmap = ref(false)
const map = ref(null)
const selectedId = ref(null)
let amapCtor = null
const markerMap = {} // poi.id -> { marker, el, baseCss }
let lastHighlight = null
const W = 1000
const H = 520

const palette = ['#00b8a9', '#f8b500', '#3b82f6', '#ef4444', '#8b5cf6', '#10b981', '#f97316', '#06b6d4']
const CAT_COLOR = { 景点: '#f59e0b', 美食: '#ef4444', 购物: '#3b82f6', 夜生活: '#8b5cf6', 酒店: '#6b7280', 其他: '#6b7280' }
function catColor(c) {
  return CAT_COLOR[c] || CAT_COLOR['其他']
}

// ---------- SVG 归一化与平滑路径 ----------
const plotted = computed(() => {
  const all = []
  props.days.forEach((d) => d.items.forEach((it) => all.push(it)))
  if (!all.length) props.pois.forEach((p) => all.push({ poi: p }))
  return all
})

const dayPaths = computed(() => {
  return props.days.map((d) => {
    const pts = d.items.map((it) => norm(it.poi.lng, it.poi.lat))
    return { pts, path: smoothSvgPath(pts) }
  })
})

const viewBox = computed(() => `0 0 ${W} ${H}`)

function norm(lng, lat) {
  const pts = plotted.value
  if (!pts.length) return { x: W / 2, y: H / 2 }
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  pts.forEach((p) => {
    const l = p.poi.lng, t = p.poi.lat
    if (l < minX) minX = l
    if (l > maxX) maxX = l
    if (t < minY) minY = t
    if (t > maxY) maxY = t
  })
  if (maxX - minX < 0.005) { minX -= 0.005; maxX += 0.005 }
  if (maxY - minY < 0.005) { minY -= 0.005; maxY += 0.005 }
  const pad = 80
  const x = pad + ((lng - minX) / (maxX - minX)) * (W - pad * 2)
  const y = pad + ((maxY - lat) / (maxY - minY)) * (H - pad * 2)
  return { x, y }
}

/** 平滑 SVG 路径：相邻点之间用二次贝塞尔过渡，柔和不生硬 */
function smoothSvgPath(pts) {
  if (pts.length < 2) return ''
  let d = `M ${pts[0].x} ${pts[0].y}`
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1], cur = pts[i]
    const mx = (prev.x + cur.x) / 2, my = (prev.y + cur.y) / 2
    d += ` Q ${prev.x} ${prev.y} ${mx} ${my}`
  }
  const last = pts[pts.length - 1]
  d += ` L ${last.x} ${last.y}`
  return d
}

/** 高德平滑路线：Catmull-Rom 转三次贝塞尔后采样成密集折点（用 Polyline 渲染，兼容稳定） */
function bezierPoint(p0, c1, c2, p1, t) {
  const u = 1 - t
  const x = u * u * u * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * p1[0]
  const y = u * u * u * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * p1[1]
  return [x, y]
}

function smoothAmapPath(pts) {
  const out = []
  for (let i = 0; i < pts.length - 1; i++) {
    const p1 = pts[i], p2 = pts[i + 1]
    const p0 = pts[Math.max(0, i - 1)]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6]
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6]
    const steps = 20
    for (let s = 0; s < steps; s++) {
      out.push(bezierPoint(p1, c1, c2, p2, s / steps))
    }
  }
  out.push(pts[pts.length - 1])
  return out
}

// ---------- 真实高德地图 ----------
import { loadAmap } from '../utils/amap.js'

const AMAP_KEY = import.meta.env.VITE_AMAP_WEB_KEY || ''

/** 默认 marker 圆点（中心锚点，保证线与点精确对齐） */
function markerEl(color) {
  const el = document.createElement('div')
  el.style.cssText =
    `width:14px;height:14px;border-radius:50%;background:${color};` +
    'border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.3);'
  return el
}

async function initAmap() {
  const AMap = await loadAmap()
  if (!AMap) return false
  amapCtor = AMap
  await nextTick()
  const hasCenter = props.center && Number.isFinite(props.center.lng) && Number.isFinite(props.center.lat)
  const center = hasCenter ? [props.center.lng, props.center.lat] : [116.4, 39.9]
  map.value = new AMap.Map(mapEl.value, {
    zoom: 11,
    center,
  })
  const markers = []
  props.days.forEach((d, di) => {
    const color = palette[di % palette.length]
    const path = []
    d.items.forEach((it, i) => {
      const pos = [it.poi.lng, it.poi.lat]
      path.push(pos)
      const el = markerEl(color)
      const m = new AMap.Marker({ position: pos, content: el, anchor: 'center', title: it.poi.name })
      if (i === 0) {
        m.setLabel({ content: `<div style="color:#fff;font-size:12px;background:${color};padding:2px 8px;border-radius:10px;white-space:nowrap">第${di + 1}天</div>`, direction: 'top' })
      }
      m.setMap(map.value)
      markers.push(m)
      if (it.poi.id) markerMap[it.poi.id] = { marker: m, el, baseCss: el.style.cssText }
    })
    // 柔和平滑曲线 + 半透明 + 圆角端点（不同天不同颜色）
    if (path.length > 1) {
      new AMap.Polyline({
        path: smoothAmapPath(path),
        strokeColor: color,
        strokeWeight: 4,
        strokeOpacity: 0.65,
        strokeStyle: 'dashed',
        lineJoin: 'round',
        lineCap: 'round',
      }).setMap(map.value)
    }
  })
  if (markers.length) {
    map.value.setFitView(markers, false, [70, 70, 70, 70])
  } else {
    map.value.setZoomAndCenter(11, center)
  }
  setTimeout(() => { try { map.value && map.value.resize() } catch (e) {} }, 300)
  return true
}

function resetHighlight() {
  if (lastHighlight) {
    lastHighlight.el.style.cssText = lastHighlight.baseCss
    lastHighlight = null
  }
}

/** 聚焦到某个点位：地图中心移动 + 对应 marker 高亮（卡片点击联动） */
function focusPoi(poi) {
  selectedId.value = poi && poi.id ? poi.id : null
  if (!map.value || !amapCtor || !poi || !Number.isFinite(poi.lng)) return
  map.value.setZoom(Math.max(map.value.getZoom(), 14))
  map.value.setCenter([poi.lng, poi.lat])
  resetHighlight()
  const rec = poi.id && markerMap[poi.id]
  if (rec) {
    rec.el.style.cssText =
      'width:22px;height:22px;border-radius:50%;background:#ef4444;' +
      'border:3px solid #fff;box-shadow:0 0 0 5px rgba(239,68,68,.35);'
    lastHighlight = rec
  }
}

defineExpose({ focusPoi })

onMounted(async () => {
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
.map-wrap {
  border-radius: 14px;
  overflow: hidden;
  background: #f0f6f4;
}
.map-el {
  width: 100%;
  height: 340px;
}
.svg-fallback {
  padding: 8px;
}
.svg {
  width: 100%;
  height: auto;
  display: block;
}
.hint {
  text-align: center;
  font-size: 11.5px;
  color: var(--text-3);
  padding: 6px 0 4px;
}
</style>
