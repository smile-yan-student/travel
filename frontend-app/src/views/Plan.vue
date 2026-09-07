<template>
  <div class="plan" v-if="plan">
    <!-- 顶部摘要 -->
    <header class="head">
      <button class="back" @click="goHome">← 重新规划</button>
      <div class="head-main">
        <div class="title-row">
          <h1>{{ plan.destination }}</h1>
          <span :class="['badge', plan.source === 'ai' ? 'ai' : 'rule']">
            {{ plan.source === 'ai' ? 'AI大模型' : '规则引擎' }}
          </span>
        </div>
        <div class="sub">
          {{ plan.days }}天 · {{ plan.group_type }} · {{ plan.budget_level }} · {{ plan.style }}
        </div>
        <div class="stat-row">
          <div class="stat">
            <div class="stat-num">¥{{ plan.total_budget }}</div>
            <div class="stat-label">总预算(估)</div>
          </div>
          <div class="stat">
            <div class="stat-num">{{ plan.day_plans.length }}</div>
            <div class="stat-label">天数</div>
          </div>
          <div class="stat">
            <div class="stat-num">{{ plan.all_pois.length }}</div>
            <div class="stat-label">点位</div>
          </div>
        </div>
        <div v-if="plan.weather && plan.weather.tips" class="weather">
          🌤 {{ plan.weather.tips }}
        </div>
        <div v-if="plan.departure_message" class="departure">
          <span class="dep-quote">“</span>{{ plan.departure_message }}<span class="dep-quote">”</span>
        </div>
      </div>
    </header>

    <main class="content">
      <!-- 地图 -->
      <div class="card map-card" ref="mapCardEl">
        <div class="card-title">🗺 行程地图</div>
        <MapView ref="mapView" :days="plan.day_plans" :pois="plan.all_pois" :center="plan.city_center" />
      </div>

      <!-- 预算拆解 -->
      <div class="card">
        <div class="card-title">💰 预算参考</div>
        <div class="budget-grid">
          <div v-for="(v, k) in plan.budget_breakdown" :key="k" class="budget-item">
            <div class="b-val">¥{{ v }}</div>
            <div class="b-label">{{ k }}</div>
          </div>
        </div>
      </div>

      <!-- 天数 Tab -->
      <div class="tabs">
        <button
          v-for="(d, i) in plan.day_plans"
          :key="d.day"
          :class="['tab', { active: activeDay === i }]"
          @click="activeDay = i"
        >第{{ d.day }}天</button>
      </div>

      <!-- 当日行程（支持拖拽排序） -->
      <transition name="fade" mode="out-in">
        <DayCard
          :key="activeDay"
          :day="plan.day_plans[activeDay]"
          :draggable="true"
          @reorder="onReorder"
          @focus-poi="onFocusPoi"
        />
      </transition>

      <p class="drag-hint">提示：拖动点位可调整顺序，路线耗时将自动重算</p>
    </main>
  </div>
  <div v-else class="empty">正在加载行程…</div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import DayCard from '../components/DayCard.vue'
import MapView from '../components/MapView.vue'
import { getRoute } from '../api'
import { getCurrentPlan } from '../store'

const router = useRouter()
const plan = ref(null)
const activeDay = ref(0)
const mapView = ref(null)
const mapCardEl = ref(null)

/** 点击行程卡片 → 地图聚焦对应点位，并平滑滚动到地图让用户看到高亮 */
function onFocusPoi(poi) {
  if (mapView.value) {
    mapView.value.focusPoi(poi)
  }
  if (mapCardEl.value) {
    mapCardEl.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

onMounted(() => {
  // 从全局状态读取行程数据（不使用本地存储，避免新旧数据混淆）
  const currentPlan = getCurrentPlan()
  if (currentPlan) {
    plan.value = currentPlan
  } else {
    // 没有行程数据时返回对话页面
    router.replace('/')
  }
})

function goHome() {
  router.push('/')
}

async function onReorder(from, to) {
  const items = plan.value.day_plans[activeDay.value].items
  const [moved] = items.splice(from, 1)
  items.splice(to, 0, moved)
  await recomputeRoutes(activeDay.value)
}

function toMinutes(t) {
  const [h, m] = String(t || '09:00').split(':').map(Number)
  return (h || 0) * 60 + (m || 0)
}
function fmtMinutes(min) {
  return `${String(Math.floor(min / 60) % 24).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`
}

async function recomputeRoutes(di) {
  const items = plan.value.day_plans[di].items
  // 首项无站前交通，清空残留值
  items[0].transport = ''
  items[0].transit_min = 0
  items[0].distance_m = 0
  // 先重算站间交通
  for (let i = 1; i < items.length; i++) {
    const prev = items[i - 1].poi
    const cur = items[i].poi
    try {
      const r = await getRoute([prev.lng, prev.lat], [cur.lng, cur.lat], plan.value.traffic_mode || '混合')
      items[i].transport = r.transport
      items[i].transit_min = r.transit_min
      items[i].distance_m = r.distance_m
    } catch (e) {
      /* 后端不可用时保持原值 */
    }
  }
  // 时间轴联动：从每日开始时间按「路上耗时+停留」顺序重排
  let cur = toMinutes(plan.value.daily_start_time || '09:00')
  const SLOT_OF = (h) => (h < 11 ? '上午' : h < 14 ? '中午' : h < 18 ? '下午' : '晚上')
  for (let i = 0; i < items.length; i++) {
    if (i > 0) cur += items[i].transit_min
    items[i].start_time = fmtMinutes(cur)
    items[i].slot = SLOT_OF(Math.floor(cur / 60) % 24)
    cur += items[i].duration_min
  }
}
</script>

<style scoped>
.head {
  background: var(--gradient);
  color: #fff;
  padding: 20px 18px 26px;
  border-radius: 0 0 26px 26px;
  position: relative;
}
.back {
  color: #fff;
  font-size: 13px;
  background: rgba(255, 255, 255, 0.18);
  padding: 6px 12px;
  border-radius: 999px;
}
.head-main {
  margin-top: 10px;
}
.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.title-row h1 {
  font-size: 26px;
  font-weight: 700;
}
.sub {
  font-size: 13px;
  opacity: 0.9;
  margin-top: 2px;
}
.stat-row {
  display: flex;
  gap: 26px;
  margin-top: 16px;
}
.stat-num {
  font-size: 22px;
  font-weight: 700;
}
.stat-label {
  font-size: 12px;
  opacity: 0.85;
}
.weather {
  margin-top: 14px;
  background: rgba(255, 255, 255, 0.16);
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 12.5px;
}
.departure {
  margin-top: 12px;
  background: rgba(255, 255, 255, 0.2);
  border: 1px dashed rgba(255, 255, 255, 0.5);
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.6;
  letter-spacing: 0.5px;
}
.dep-quote {
  color: #ffe9a8;
  font-size: 18px;
  font-weight: 700;
  margin: 0 2px;
}
.content {
  padding: 14px 14px 60px;
  margin-top: -16px;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
}
.map-card {
  padding: 14px;
}
.budget-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.budget-item {
  text-align: center;
  background: #f7faf9;
  border-radius: 12px;
  padding: 10px 4px;
}
.b-val {
  font-size: 16px;
  font-weight: 700;
  color: var(--primary-dark);
}
.b-label {
  font-size: 12px;
  color: var(--text-2);
  margin-top: 2px;
}
.tabs {
  display: flex;
  gap: 8px;
  margin: 18px 0 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.tab {
  flex-shrink: 0;
  padding: 8px 18px;
  border-radius: 999px;
  background: #eef2f1;
  color: var(--text-2);
  font-size: 13px;
  font-weight: 500;
}
.tab.active {
  background: var(--primary);
  color: #fff;
  font-weight: 600;
}
.drag-hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-3);
  margin-top: 10px;
}
</style>
