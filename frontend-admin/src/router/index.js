import { createRouter, createWebHashHistory } from 'vue-router'
import AdminLogin from '../views/admin/AdminLogin.vue'
import AdminApp from '../views/admin/AdminApp.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    // 管理后台登录页
    { path: '/', name: 'admin-login', component: AdminLogin },
    { path: '/login', name: 'admin-login-alias', component: AdminLogin },
    // 管理后台主应用
    { path: '/app', name: 'admin-app', component: AdminApp },
    // 兜底：未知路径重定向到登录页
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
