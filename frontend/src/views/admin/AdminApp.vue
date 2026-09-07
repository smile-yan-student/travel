<template>
  <div class="admin-app">
    <aside class="sidebar">
      <div class="brand">🗺️ 去见山海<br /><small>管理后台</small></div>
      <nav>
        <button
          v-for="m in modules"
          :key="m.key"
          :class="['nav-item', { active: current === m.key }]"
          @click="current = m.key"
        >
          <span>{{ m.icon }}</span>
          <span class="label">{{ m.label }}</span>
          <span class="prio">{{ m.prio }}</span>
        </button>
      </nav>
      <div class="side-foot">
        <span>👤 {{ adminName }}（{{ roleText }}）</span>
        <a href="#/" class="back-link">返回应用</a>
        <button class="logout" @click="logout">退出登录</button>
      </div>
    </aside>
    <main class="content">
      <component :is="currentComp" :token="token" :user-role="role" />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import DashboardPanel from './panels/DashboardPanel.vue'
import UsersPanel from './panels/UsersPanel.vue'
import TripsPanel from './panels/TripsPanel.vue'
import ConversationsPanel from './panels/ConversationsPanel.vue'
import ContentPanel from './panels/ContentPanel.vue'
import AiPanel from './panels/AiPanel.vue'
import AmapPanel from './panels/AmapPanel.vue'
import ConfigPanel from './panels/ConfigPanel.vue'
import AdminsPanel from './panels/AdminsPanel.vue'
import LogPanel from './panels/LogPanel.vue'
import DictPanel from './panels/DictPanel.vue'
import RagPanel from './panels/RagPanel.vue'
import MajorAttractionsPanel from './panels/MajorAttractionsPanel.vue'

const router = useRouter()
const token = localStorage.getItem('admin_token') || ''
const role = localStorage.getItem('admin_role') || 'ops'
const adminName = localStorage.getItem('admin_name') || 'admin'

const modules = [
  { key: 'dashboard', icon: '📊', label: '仪表盘', comp: DashboardPanel, prio: 'P0' },
  { key: 'users', icon: '👥', label: '用户管理', comp: UsersPanel, prio: 'P0' },
  { key: 'trips', icon: '🧳', label: '行程与足迹', comp: TripsPanel, prio: 'P1' },
  { key: 'convos', icon: '💬', label: '对话运营', comp: ConversationsPanel, prio: 'P1' },
  { key: 'content', icon: '📍', label: '内容与景点', comp: ContentPanel, prio: 'P2' },
  { key: 'ai', icon: '🤖', label: 'AI 模型', comp: AiPanel, prio: 'P2' },
  { key: 'amap', icon: '🗺️', label: '高德与缓存', comp: AmapPanel, prio: 'P2' },
  { key: 'config', icon: '⚙️', label: '系统配置', comp: ConfigPanel, prio: 'P2' },
  { key: 'logs', icon: '📋', label: '日志监控', comp: LogPanel, prio: 'P1' },
  { key: 'dict', icon: '📚', label: '字典数据', comp: DictPanel, prio: 'P2' },
  { key: 'rag', icon: '🧠', label: 'RAG知识库', comp: RagPanel, prio: 'P1' },
  { key: 'major-attractions', icon: '🏛️', label: '主要景点库', comp: MajorAttractionsPanel, prio: 'P1' },
  { key: 'admins', icon: '🔐', label: '管理员', comp: AdminsPanel, prio: 'P0' },
]

const current = ref('dashboard')
const currentComp = computed(() => modules.find((m) => m.key === current.value).comp)
const roleText = computed(() => (role === 'super' ? '超级管理员' : '运营'))

onMounted(() => {
  if (!token) {
    router.replace('/admin')
  }
})

function logout() {
  localStorage.removeItem('admin_token')
  localStorage.removeItem('admin_role')
  localStorage.removeItem('admin_name')
  router.replace('/admin')
}
</script>

<style scoped>
.admin-app {
  display: flex;
  min-height: 100vh;
  background: #f4f6f9;
}
.sidebar {
  width: 200px;
  background: #1a2a3a;
  color: #c9d4e0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  height: 100vh;
}
.brand {
  padding: 22px 18px 16px;
  font-size: 17px;
  font-weight: 700;
  color: #fff;
  line-height: 1.5;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.brand small {
  font-size: 11px;
  font-weight: 400;
  color: #7e93a8;
}
nav {
  flex: 1;
  padding: 10px 8px;
  overflow-y: auto;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 10px;
  margin-bottom: 2px;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: #c9d4e0;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
}
.nav-item .label {
  flex: 1;
}
.nav-item .prio {
  font-size: 10px;
  color: #7e93a8;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.nav-item.active {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  font-weight: 600;
}
.side-foot {
  padding: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.back-link {
  color: #8fa8c0;
  text-decoration: none;
  font-size: 12px;
}
.logout {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 7px;
  cursor: pointer;
  font-size: 12px;
}
.content {
  flex: 1;
  padding: 20px 24px;
  overflow-x: hidden;
}
</style>
