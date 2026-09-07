<template>
  <div class="admin-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <div class="logo">
          <span class="logo-icon">🗺️</span>
          <div class="logo-text" v-show="!sidebarCollapsed">
            <h1>去见山海</h1>
            <p>管理控制台</p>
          </div>
        </div>
      </div>

      <div class="sidebar-menu">
        <div v-for="group in menuGroups" :key="group.name" class="menu-group">
          <div class="menu-group-title" v-show="!sidebarCollapsed">
            <span>{{ group.name }}</span>
          </div>
          <div
            v-for="m in group.items"
            :key="m.key"
            :class="['menu-item', { active: current === m.key }]"
            @click="current = m.key"
            :title="m.label"
          >
            <span class="menu-icon">{{ m.icon }}</span>
            <span class="menu-label" v-show="!sidebarCollapsed">{{ m.label }}</span>
            <span class="menu-arrow" v-show="!sidebarCollapsed">›</span>
          </div>
        </div>
      </div>

      <div class="sidebar-footer">
        <button class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          <span v-if="!sidebarCollapsed">收起菜单</span>
          <span v-else>»</span>
        </button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="main-container">
      <!-- 顶部导航 -->
      <header class="header">
        <div class="header-left">
          <div class="breadcrumb">
            <span class="breadcrumb-home">🏠</span>
            <span class="breadcrumb-sep">/</span>
            <span class="breadcrumb-current">{{ currentModule.label }}</span>
          </div>
        </div>
        <div class="header-center">
          <div class="global-search">
            <span class="search-icon">🔍</span>
            <input
              type="text"
              placeholder="搜索功能模块、用户、行程..."
              class="search-input"
              @keyup.enter="handleSearch"
            />
            <kbd class="search-shortcut">⌘K</kbd>
          </div>
        </div>
        <div class="header-right">
          <div class="header-actions">
            <button class="action-btn" title="通知">
              🔔
              <span class="badge">3</span>
            </button>
            <button class="action-btn" title="帮助文档">
              ❓
            </button>
            <button class="action-btn" title="系统设置">
              ⚙️
            </button>
          </div>
          <div class="user-dropdown" @click="showUserMenu = !showUserMenu">
            <div class="user-avatar">
              <span>{{ adminName.charAt(0).toUpperCase() }}</span>
            </div>
            <div class="user-info">
              <div class="user-name">{{ adminName }}</div>
              <div class="user-role">{{ roleText }}</div>
            </div>
            <span class="dropdown-arrow">▼</span>
          </div>
          <div v-if="showUserMenu" class="user-menu">
            <div class="user-menu-header">
              <div class="user-menu-avatar">{{ adminName.charAt(0).toUpperCase() }}</div>
              <div>
                <div class="user-menu-name">{{ adminName }}</div>
                <div class="user-menu-role">{{ roleText }}</div>
              </div>
            </div>
            <div class="user-menu-item">👤 个人中心</div>
            <div class="user-menu-item">🔐 修改密码</div>
            <div class="user-menu-item">📋 操作日志</div>
            <div class="user-menu-divider"></div>
            <div class="user-menu-item logout" @click="logout">🚪 退出登录</div>
          </div>
        </div>
      </header>

      <!-- 标签页栏 -->
      <div class="tabs-bar">
        <div class="tab-item active">
          <span>{{ currentModule.icon }} {{ currentModule.label }}</span>
          <span class="tab-close">×</span>
        </div>
      </div>

      <!-- 内容区域 -->
      <main class="content">
        <div class="page-header">
          <div class="page-title-section">
            <h2 class="page-title">{{ currentModule.label }}</h2>
            <p class="page-description">{{ currentModule.desc }}</p>
          </div>
          <div class="page-actions">
            <button class="btn btn-default">
              📥 导出
            </button>
            <button class="btn btn-primary">
              ➕ 新建
            </button>
          </div>
        </div>

        <div class="page-content">
          <component :is="currentComp" :token="token" :user-role="role" />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onMounted as onMountedHook } from 'vue'
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
import KnowledgePanel from './panels/KnowledgePanel.vue'
import PoiHierarchyPanel from './panels/PoiHierarchyPanel.vue'
import HistoricalFigurePanel from './panels/HistoricalFigurePanel.vue'
import PoiTestPanel from './panels/PoiTestPanel.vue'
import ReservationRulesPanel from './panels/ReservationRulesPanel.vue'
import TravelTipsPanel from './panels/TravelTipsPanel.vue'

const router = useRouter()
const token = localStorage.getItem('admin_token') || ''
const role = localStorage.getItem('admin_role') || 'ops'
const adminName = localStorage.getItem('admin_name') || 'admin'
const sidebarCollapsed = ref(false)
const showUserMenu = ref(false)

// 所有模块定义
const allModules = [
  { key: 'dashboard', icon: '📊', label: '仪表盘', comp: DashboardPanel, desc: '系统运行概览、核心指标监控、实时数据统计', group: '系统概览' },
  { key: 'users', icon: '👥', label: '用户管理', comp: UsersPanel, desc: '用户列表、用户详情、账号状态、用户行为分析', group: '用户运营' },
  { key: 'trips', icon: '🧳', label: '行程管理', comp: TripsPanel, desc: '用户行程记录、行程详情、行程数据统计分析', group: '用户运营' },
  { key: 'convos', icon: '💬', label: '对话运营', comp: ConversationsPanel, desc: '用户对话记录、意图识别分析、对话质量监控', group: '用户运营' },
  { key: 'content', icon: '📍', label: '内容管理', comp: ContentPanel, desc: '景点内容管理、POI数据维护、内容审核', group: '内容管理' },
  { key: 'rag', icon: '🧠', label: 'RAG知识库', comp: RagPanel, desc: '人文知识库管理、向量检索、知识导入导出', group: '内容管理' },
  { key: 'knowledge', icon: '📖', label: '知识库管理(B端)', comp: KnowledgePanel, desc: '知识文档管理、分类管理、检索测试、配置管理、人工干预', group: '内容管理' },
  { key: 'poi-hierarchy', icon: '🏛️', label: 'POI层级管理', comp: PoiHierarchyPanel, desc: '主景点、内部子景点、周边附属景点的层级数据管理', group: '内容管理' },
  { key: 'historical-figures', icon: '📖', label: '历史名人管理', comp: HistoricalFigurePanel, desc: '历史名人、革命先辈、文人墨客及其相关旅行地管理', group: '内容管理' },
  { key: 'dict', icon: '📚', label: '字典管理', comp: DictPanel, desc: '旅行风格、预算档位、出行方式等系统字典', group: '内容管理' },
  { key: 'reservation-rules', icon: '📅', label: '预约规则管理', comp: ReservationRulesPanel, desc: '景点预约渠道、放票时间、开放时间、闭馆日、票价等规则管理', group: '内容管理' },
  { key: 'travel-tips', icon: '💡', label: '避坑提示管理', comp: TravelTipsPanel, desc: '目的地防骗、交通、美食、住宿等避坑提示管理，支持批量添加', group: '内容管理' },
  { key: 'ai', icon: '🤖', label: 'AI模型管理', comp: AiPanel, desc: '模型配置、模型状态监控、调用统计、性能分析', group: '系统管理' },
  { key: 'amap', icon: '🗺️', label: '地图与缓存', comp: AmapPanel, desc: '地图API配置、Key管理、缓存监控、调用统计', group: '系统管理' },
  { key: 'poi-test', icon: '🔍', label: 'POI数据测试', comp: PoiTestPanel, desc: '高德POI检索测试、数据覆盖分析、POI数据导出', group: '系统管理' },
  { key: 'config', icon: '⚙️', label: '系统配置', comp: ConfigPanel, desc: '系统参数配置、功能开关、环境变量管理', group: '系统管理' },
  { key: 'logs', icon: '📋', label: '日志监控', comp: LogPanel, desc: '系统日志、错误日志、访问日志、告警管理', group: '系统管理' },
  { key: 'admins', icon: '🔐', label: '管理员管理', comp: AdminsPanel, desc: '管理员账号、角色权限、操作日志审计', group: '系统管理' },
]

// 按分组组织菜单
const menuGroups = computed(() => {
  const groups = {}
  allModules.forEach(m => {
    if (!groups[m.group]) {
      groups[m.group] = []
    }
    groups[m.group].push(m)
  })
  return Object.entries(groups).map(([name, items]) => ({ name, items }))
})

const current = ref('dashboard')
const currentModule = computed(() => allModules.find((m) => m.key === current.value) || allModules[0])
const currentComp = computed(() => currentModule.value.comp)
const roleText = computed(() => (role === 'super' ? '超级管理员' : '运营管理员'))

onMounted(() => {
  if (!token) {
    router.replace('/')
  }
  // 点击外部关闭用户菜单
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.user-dropdown') && !e.target.closest('.user-menu')) {
      showUserMenu.value = false
    }
  })
})

function logout() {
  localStorage.removeItem('admin_token')
  localStorage.removeItem('admin_role')
  localStorage.removeItem('admin_name')
  router.replace('/')
}

function handleSearch(e) {
  const keyword = e.target.value.toLowerCase().trim()
  if (!keyword) return
  const found = allModules.find(m =>
    m.label.toLowerCase().includes(keyword) ||
    m.key.toLowerCase().includes(keyword) ||
    m.desc.toLowerCase().includes(keyword)
  )
  if (found) {
    current.value = found.key
    e.target.value = ''
  }
}
</script>

<style scoped>
/* 全局布局 */
.admin-layout {
  display: block;
  min-height: 100vh;
  background: #f0f2f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  color: rgba(0, 0, 0, 0.88);
}

/* 侧边栏 */
.sidebar {
  width: 260px;
  background: #001529;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: fixed;
  left: 0;
  top: 0;
  height: 100vh;
  transition: width 0.2s ease;
  z-index: 100;
}
.sidebar.collapsed {
  width: 64px;
}

/* 侧边栏头部 */
.sidebar-header {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.logo-icon {
  font-size: 32px;
  flex-shrink: 0;
}
.logo-text h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  line-height: 1.2;
}
.logo-text p {
  margin: 2px 0 0 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

/* 侧边栏菜单 */
.sidebar-menu {
  flex: 1;
  padding: 12px 8px;
  overflow-y: auto;
  overflow-x: hidden;
}
.sidebar-menu::-webkit-scrollbar {
  width: 6px;
}
.sidebar-menu::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}
.menu-group {
  margin-bottom: 8px;
}
.menu-group-title {
  padding: 8px 12px 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 500;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 2px;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.65);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}
.menu-item:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}
.menu-item.active {
  background: #1677ff;
  color: #fff;
  font-weight: 500;
}
.menu-icon {
  font-size: 18px;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}
.menu-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.menu-arrow {
  color: rgba(255, 255, 255, 0.3);
  font-size: 16px;
}

/* 侧边栏底部 */
.sidebar-footer {
  padding: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.collapse-btn {
  width: 100%;
  padding: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: none;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.65);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

/* 主容器 */
.main-container {
  margin-left: 260px;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 100vh;
  transition: margin-left 0.2s ease;
}
.sidebar.collapsed ~ .main-container {
  margin-left: 64px;
}

/* 顶部导航 */
.header {
  height: 64px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 24px;
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}
.header-left {
  flex-shrink: 0;
}
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}
.breadcrumb-home {
  font-size: 16px;
}
.breadcrumb-sep {
  color: #d9d9d9;
}
.breadcrumb-current {
  color: rgba(0, 0, 0, 0.88);
  font-weight: 500;
}
.header-center {
  flex: 1;
  max-width: 480px;
}
.global-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f5f5;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 8px 12px;
  transition: all 0.2s;
}
.global-search:focus-within {
  background: #fff;
  border-color: #1677ff;
  box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.1);
}
.search-icon {
  font-size: 14px;
  color: #8c8c8c;
}
.search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 14px;
  color: rgba(0, 0, 0, 0.88);
}
.search-input::placeholder {
  color: #bfbfbf;
}
.search-shortcut {
  font-size: 11px;
  color: #8c8c8c;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 2px 6px;
  font-family: monospace;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
  position: relative;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.action-btn {
  position: relative;
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.action-btn:hover {
  background: #f5f5f5;
}
.badge {
  position: absolute;
  top: 6px;
  right: 6px;
  background: #ff4d4f;
  color: #fff;
  font-size: 10px;
  min-width: 16px;
  height: 16px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  font-weight: 500;
}

/* 用户下拉 */
.user-dropdown {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.user-dropdown:hover {
  background: #f5f5f5;
}
.user-avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #1677ff 0%, #0958d9 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}
.user-info {
  text-align: left;
}
.user-name {
  font-size: 14px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.88);
  line-height: 1.2;
}
.user-role {
  font-size: 12px;
  color: #8c8c8c;
  margin-top: 2px;
}
.dropdown-arrow {
  font-size: 10px;
  color: #8c8c8c;
}
.user-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05);
  min-width: 240px;
  z-index: 1000;
  overflow: hidden;
  animation: slideDown 0.2s ease;
}
@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.user-menu-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}
.user-menu-avatar {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #1677ff 0%, #0958d9 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  font-weight: 600;
}
.user-menu-name {
  font-size: 16px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
}
.user-menu-role {
  font-size: 13px;
  color: #8c8c8c;
  margin-top: 2px;
}
.user-menu-item {
  padding: 12px 16px;
  font-size: 14px;
  color: rgba(0, 0, 0, 0.88);
  cursor: pointer;
  transition: all 0.2s;
}
.user-menu-item:hover {
  background: #f5f5f5;
}
.user-menu-item.logout {
  color: #ff4d4f;
}
.user-menu-divider {
  height: 1px;
  background: #f0f0f0;
  margin: 4px 0;
}

/* 标签页栏 */
.tabs-bar {
  height: 40px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 4px;
}
.tab-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: #f5f5f5;
  border-radius: 6px 6px 0 0;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  cursor: pointer;
  border: 1px solid #f0f0f0;
  border-bottom: none;
}
.tab-item.active {
  background: #fff;
  color: #1677ff;
  font-weight: 500;
}
.tab-close {
  font-size: 16px;
  color: #bfbfbf;
  cursor: pointer;
  line-height: 1;
}
.tab-close:hover {
  color: #8c8c8c;
}

/* 内容区域 */
.content {
  flex: 1;
  padding: 24px;
  overflow-x: hidden;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
.page-title-section {
  flex: 1;
}
.page-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
  line-height: 1.3;
}
.page-description {
  margin: 0;
  font-size: 14px;
  color: #8c8c8c;
}
.page-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.btn-default {
  background: #fff;
  border-color: #d9d9d9;
  color: rgba(0, 0, 0, 0.88);
}
.btn-default:hover {
  border-color: #1677ff;
  color: #1677ff;
}
.btn-primary {
  background: #1677ff;
  color: #fff;
}
.btn-primary:hover {
  background: #4096ff;
}
.page-content {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02);
  min-height: calc(100vh - 280px);
}

/* 响应式 */
@media (max-width: 1400px) {
  .header-center {
    max-width: 360px;
  }
}
@media (max-width: 1200px) {
  .sidebar {
    width: 64px;
  }
  .main-container {
    margin-left: 64px;
  }
  .sidebar .logo-text,
  .sidebar .menu-label,
  .sidebar .menu-group-title,
  .sidebar .menu-arrow,
  .sidebar-footer .collapse-btn span:first-child {
    display: none;
  }
  .header-center {
    display: none;
  }
  .user-info {
    display: none;
  }
}
</style>
