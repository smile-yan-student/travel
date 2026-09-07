<template>
  <div id="app">
    <main class="page" :class="{ 'with-tabbar': showTabbar }">
      <!-- keep-alive 缓存对话/探索/我的页面状态，行程页不缓存（每次读取最新全局状态） -->
      <router-view v-slot="{ Component }">
        <keep-alive :include="['Home', 'Explore', 'Me']">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
    <!-- 底部三板块导航：对话 / 探索 / 我的（行程页全屏，不显示） -->
    <nav v-if="showTabbar" class="tabbar">
      <router-link
        v-for="t in tabs"
        :key="t.path"
        :to="t.path"
        :class="['tab', { active: route.path === t.path }]"
      >
        <span class="tab-icon">{{ t.icon }}</span>
        <span class="tab-label">{{ t.label }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  { path: '/', icon: '💬', label: '对话' },
  { path: '/explore', icon: '🧭', label: '探索' },
  { path: '/me', icon: '👤', label: '我的' },
]

const showTabbar = computed(() => route.path !== '/plan' && !route.path.startsWith('/admin'))
</script>

<style scoped>
.page {
  min-height: 100vh;
}
.page.with-tabbar {
  padding-bottom: 58px;
}
.tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  background: #fff;
  border-top: 1px solid var(--border);
  padding-bottom: env(safe-area-inset-bottom);
  z-index: 60;
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 0 7px;
  color: var(--text-3);
  text-decoration: none;
}
.tab-icon {
  font-size: 20px;
  line-height: 1;
}
.tab-label {
  font-size: 11px;
  font-weight: 600;
}
.tab.active {
  color: var(--primary-dark);
}
.tab.active .tab-icon {
  transform: scale(1.08);
}
</style>
