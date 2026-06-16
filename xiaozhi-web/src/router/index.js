import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'

const routes = [
  { path: '/', component: DashboardView, meta: { title: '总览面板' } },
  { path: '/sensor', component: () => import('../views/SensorView.vue'), meta: { title: '温湿度监控' } },
  { path: '/meow', component: () => import('../views/MeowView.vue'), meta: { title: '猫叫检测' } },
  { path: '/iot', component: () => import('../views/IotControlView.vue'), meta: { title: 'IoT 控制' } },
  { path: '/water', component: () => import('../views/WaterView.vue'), meta: { title: '饮水管理' } },
  { path: '/voice', redirect: '/' },
  { path: '/settings', component: () => import('../views/SettingsView.vue'), meta: { title: '系统设置' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  // 每次切换页面都回到顶部，避免上一页的滚动位置被带到新页面；
  // 浏览器前进/后退时尽量恢复原位置。
  scrollBehavior(to, from, savedPosition) {
    return savedPosition || { top: 0, left: 0 }
  },
})

export default router
