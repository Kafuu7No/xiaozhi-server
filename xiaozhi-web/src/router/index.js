import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import { useUiStore } from '../stores/uiStore'
import {
  CONTROL_MODE,
  VIEW_MODE,
  resolveModeRoute,
} from './modeRouting'

const routes = [
  { path: '/', component: DashboardView, meta: { title: '总览面板', modes: [VIEW_MODE] } },
  { path: '/sensor', component: () => import('../views/SensorView.vue'), meta: { title: '环境监测', modes: [VIEW_MODE] } },
  { path: '/meow', component: () => import('../views/MeowView.vue'), meta: { title: '猫叫记录', modes: [VIEW_MODE, CONTROL_MODE] } },
  { path: '/iot', component: () => import('../views/IotControlView.vue'), meta: { title: '设备控制', modes: [CONTROL_MODE] } },
  { path: '/water', component: () => import('../views/WaterView.vue'), meta: { title: '饮水记录', modes: [VIEW_MODE, CONTROL_MODE] } },
  { path: '/voice', component: DashboardView, meta: { legacy: true } },
  { path: '/settings', component: () => import('../views/SettingsView.vue'), meta: { title: '系统设置', modes: [CONTROL_MODE] } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    return savedPosition || { top: 0, left: 0 }
  },
})

export function installModeGuard(targetRouter = router) {
  targetRouter.beforeEach((to) => {
    const uiStore = useUiStore()
    return resolveModeRoute(to, uiStore.mode)
  })
}

export default router
