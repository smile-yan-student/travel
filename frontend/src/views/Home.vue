<template>
  <div class="home">
    <!-- 品牌 Hero -->
    <header class="hero">
      <div class="hero-inner">
        <div class="logo">✈️</div>
        <h1>去见山海</h1>
        <p class="slogan">{{ slogan }}</p>
        <p>{{ heroText }}</p>
        <div class="status-bar">
          <span :class="['badge', status.amap_ready ? 'real' : 'mock']">
            {{ status.amap_ready ? '高德·真实数据' : '高德·演示数据' }}
          </span>
          <span :class="['badge', status.ai_available ? 'ai' : 'rule']">
            {{ status.ai_available ? '本地AI模型' : '规则引擎(未装模型)' }}
          </span>
        </div>
      </div>
    </header>

    <!-- 对话规划（唯一入口，规划能力完全由对话提供） -->
    <main class="form">
      <div class="card">
        <ChatPlanner />
      </div>
    </main>

    <footer class="foot">{{ footerText }}</footer>
  </div>
</template>

<script setup>
defineOptions({ name: 'Home' })
import { reactive, ref, onMounted } from 'vue'
import ChatPlanner from '../components/ChatPlanner.vue'
import { getStatus, getSiteConfig } from '../api'

const status = reactive({ amap_ready: false, ai_available: false })
const slogan = ref('世界很大，替你踏平第一步')
const heroText = ref('对话就能生成旅行行程，鼓励你勇敢出发')
const footerText = ref('去见山海 · 每一次出发，都是把世界变成自己的地图')

onMounted(async () => {
  try {
    const s = await getStatus()
    Object.assign(status, s)
  } catch (e) {
    /* 后端未启动时静默 */
  }
  try {
    const cfg = await getSiteConfig()
    if (cfg.brand_slogan) slogan.value = cfg.brand_slogan
    if (cfg.brand_hero) heroText.value = cfg.brand_hero
    if (cfg.brand_footer) footerText.value = cfg.brand_footer
  } catch (e) {
    /* 接口不可用时保持默认文案 */
  }
})
</script>

<style scoped>
.hero {
  background: var(--gradient);
  color: #fff;
  padding: 44px 20px 34px;
  border-radius: 0 0 28px 28px;
  position: relative;
}
.hero-inner {
  text-align: center;
}
.logo {
  font-size: 40px;
  margin-bottom: 8px;
}
.hero h1 {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 3px;
}
.hero .slogan {
  font-size: 13px;
  font-weight: 600;
  opacity: 0.95;
  margin-top: 2px;
  letter-spacing: 1px;
}
.hero p {
  font-size: 13px;
  opacity: 0.9;
  margin-top: 6px;
}
.status-bar {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 14px;
}
.status-bar .badge.mock,
.status-bar .badge.rule {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
}
.form {
  padding: 16px 16px 30px;
  margin-top: -18px;
}
.foot {
  text-align: center;
  color: var(--text-3);
  font-size: 12px;
  padding-bottom: 12px;
}
</style>
