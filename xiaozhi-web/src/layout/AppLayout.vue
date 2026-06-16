<template>
  <div class="drawer lg:drawer-open">
    <input id="sidebar" type="checkbox" class="drawer-toggle" />

    <div class="drawer-content flex min-h-screen flex-col bg-[#F5F6FA]">
      <header class="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div class="navbar px-4 lg:px-6">
          <label for="sidebar" class="btn btn-ghost btn-sm mr-2 lg:hidden">
            <Menu :size="18" />
          </label>

          <div class="flex-1">
            <div class="text-base font-semibold text-slate-900">{{ route.meta.title }}</div>
            <div class="text-xs text-slate-400">XiaoZhi 猫咪饮水控制系统</div>
          </div>

          <div class="hidden items-center gap-2 rounded-full border border-slate-200 px-3 py-1.5 text-sm text-slate-500 lg:flex">
            <span
              class="h-2.5 w-2.5 rounded-full"
              :class="store.connected ? 'bg-emerald-500' : 'bg-slate-300'"
            />
            {{ store.connected ? `设备在线 · ${store.deviceId || '未命名设备'}` : '设备离线' }}
          </div>
        </div>
      </header>

      <main class="min-h-screen flex-1 p-4 lg:p-6">
        <slot />
      </main>
    </div>

    <div class="drawer-side z-40">
      <label for="sidebar" class="drawer-overlay" />
      <aside class="flex min-h-full w-64 flex-col border-r border-slate-200 bg-white">
        <div class="border-b border-slate-200 px-5 py-5">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white">
              <Cpu :size="18" />
            </div>
            <div>
              <div class="text-sm font-semibold text-slate-900">XiaoZhi</div>
              <div class="text-xs text-slate-400">猫咪饮水控制系统</div>
            </div>
          </div>
        </div>

        <nav class="flex-1 px-3 py-4">
          <ul class="menu gap-1 p-0">
            <li v-for="item in menuItems" :key="item.to">
              <RouterLink
                :to="item.to"
                class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm"
                :class="route.path === item.to
                  ? 'bg-slate-900 text-white'
                  : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900'"
                @click="closeSidebar"
              >
                <component :is="item.icon" :size="18" />
                {{ item.label }}
              </RouterLink>
            </li>
          </ul>
        </nav>

        <div class="border-t border-slate-200 px-5 py-4">
          <div class="rounded-xl bg-slate-50 px-4 py-3">
            <div class="section-label">设备状态</div>
            <div class="mt-2 flex items-center gap-2 text-sm text-slate-500">
              <span
                class="h-2.5 w-2.5 rounded-full"
                :class="store.connected ? 'bg-emerald-500' : 'bg-slate-300'"
              />
              {{ store.connected ? store.state : '离线等待中' }}
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
import {
  Cat,
  Cpu,
  Droplets,
  LayoutDashboard,
  Menu,
  Mic,
  Settings,
  Sliders,
  Thermometer,
} from 'lucide-vue-next'
import { useDeviceStore } from '../stores/deviceStore'

const route = useRoute()
const store = useDeviceStore()

const menuItems = [
  { to: '/', label: '总览面板', icon: LayoutDashboard },
  { to: '/sensor', label: '温湿度监控', icon: Thermometer },
  { to: '/meow', label: '猫叫检测', icon: Cat },
  { to: '/iot', label: 'IoT 控制', icon: Sliders },
  { to: '/water', label: '饮水管理', icon: Droplets },
  { to: '/voice', label: '语音助手', icon: Mic },
  { to: '/settings', label: '系统设置', icon: Settings },
].filter((item) => item.to !== '/voice')

function closeSidebar() {
  const drawer = document.getElementById('sidebar')
  if (drawer) drawer.checked = false
}
</script>
