import { createRouter, createWebHashHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Plan from '../views/Plan.vue'
import Explore from '../views/Explore.vue'
import Me from '../views/Me.vue'
import AdminLogin from '../views/admin/AdminLogin.vue'
import AdminApp from '../views/admin/AdminApp.vue'
import { isLoggedIn } from '../utils/user'

// 不需要登录的路由白名单
const PUBLIC_PATHS = ['/me', '/admin']

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'home', component: Home, meta: { requiresAuth: true } },
    { path: '/plan', name: 'plan', component: Plan, meta: { requiresAuth: true } },
    { path: '/explore', name: 'explore', component: Explore, meta: { requiresAuth: true } },
    { path: '/me', name: 'me', component: Me },
    // 管理后台：登录页 + 后台应用（后台独立鉴权，不走 C 端登录守卫）
    { path: '/admin', name: 'admin-login', component: AdminLogin },
    { path: '/admin/app', name: 'admin-app', component: AdminApp },
    // 兜底：未知路径一律重定向到默认对话板块
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

/**
 * 全局路由守卫：所有业务页面必须登录后才能访问。
 * 未登录时跳转到 /me，并通过 query 传递 redirect（登录后跳回原页面）。
 * /me 页面检测到 redirect 参数时自动打开登录弹窗。
 */
router.beforeEach((to, from, next) => {
  // 白名单路由直接放行
  if (PUBLIC_PATHS.some((p) => to.path.startsWith(p))) {
    next()
    return
  }

  // 需要登录的路由
  if (to.meta.requiresAuth && !isLoggedIn()) {
    next({ path: '/me', query: { redirect: to.fullPath, auth: 'login' } })
    return
  }

  next()
})

export default router
