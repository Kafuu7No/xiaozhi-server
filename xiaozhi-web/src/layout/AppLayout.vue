<template>
  <div class="drawer lg:drawer-open">
    <input id="sidebar" type="checkbox" class="drawer-toggle" />

    <div class="drawer-content flex min-h-screen flex-col bg-[#F5F6FA]">
      <header class="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div class="navbar gap-3 px-4 lg:px-6">
          <label for="sidebar" class="btn btn-ghost btn-sm shrink-0 lg:hidden">
            <Menu :size="18" />
          </label>

          <div class="min-w-0 flex-1">
            <div class="truncate text-base font-semibold text-slate-900">{{ pageTitle }}</div>
            <div class="truncate text-xs text-slate-400">XiaoZhi 猫窝饮水控制系统</div>
          </div>

          <div class="flex shrink-0 items-center gap-2">
            <div class="lg:hidden">
              <ModeSwitch compact />
            </div>

            <div class="hidden items-center gap-2 rounded-full border border-slate-200 px-3 py-1.5 text-sm text-slate-500 lg:flex">
              <span
                class="h-2.5 w-2.5 rounded-full"
                :class="deviceStore.connected ? 'bg-emerald-500' : 'bg-slate-300'"
              />
              {{ deviceStore.connected ? `设备在线 · ${deviceStore.deviceId || '未命名设备'}` : '设备离线' }}
            </div>
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
            <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-white">
              <Cpu :size="18" />
            </div>
            <div>
              <div class="text-sm font-semibold text-slate-900">XiaoZhi</div>
              <div class="text-xs text-slate-400">猫窝饮水控制系统</div>
            </div>
          </div>

          <div class="mt-4 hidden lg:block">
            <ModeSwitch />
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
                <component :is="iconMap[item.icon]" :size="18" />
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
                :class="deviceStore.connected ? 'bg-emerald-500' : 'bg-slate-300'"
              />
              {{ deviceStore.connected ? deviceStore.state : '离线等待中' }}
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  Cat,
  Cpu,
  Droplets,
  LayoutDashboard,
  Menu,
  Settings,
  Sliders,
  Thermometer,
} from 'lucide-vue-next'
import { useDeviceStore } from '../stores/deviceStore'
import { useUiStore } from '../stores/uiStore'
import {
  MODE_OPTIONS,
  getDefaultRouteForMode,
  getModeMenuItems,
  getModeRouteTitle,
  isRouteSupportedByMode,
} from '../router/modeRouting'

const route = useRoute()
const router = useRouter()
const deviceStore = useDeviceStore()
const uiStore = useUiStore()

const iconMap = {
  dashboard: LayoutDashboard,
  sensor: Thermometer,
  meow: Cat,
  iot: Sliders,
  water: Droplets,
  settings: Settings,
}

const menuItems = computed(() => getModeMenuItems(uiStore.mode))
const pageTitle = computed(() => getModeRouteTitle(route.path, uiStore.mode, route.meta.title))

async function switchMode(nextMode) {
  if (uiStore.mode === nextMode) return
  uiStore.setMode(nextMode)
  if (!isRouteSupportedByMode(route, nextMode)) {
    await router.replace(getDefaultRouteForMode(nextMode))
  }
}

function closeSidebar() {
  const drawer = document.getElementById('sidebar')
  if (drawer) drawer.checked = false
}

const ModeSwitch = defineComponent({
  props: {
    compact: { type: Boolean, default: false },
  },
  setup(props) {
    return () => h(
      'div',
      {
        class: [
          'grid rounded-lg bg-slate-100 p-1',
          props.compact ? 'grid-cols-2 gap-1' : 'grid-cols-2 gap-1',
        ],
      },
      MODE_OPTIONS.map((option) => h(
        'button',
        {
          type: 'button',
          class: [
            'rounded-md px-2.5 py-1.5 text-xs font-medium transition',
            props.compact ? 'min-w-12' : 'min-w-20',
            uiStore.mode === option.value
              ? 'bg-white text-slate-900 shadow-sm'
              : 'text-slate-500 hover:text-slate-900',
          ],
          onClick: () => switchMode(option.value),
        },
        props.compact ? option.label.replace('模式', '') : option.label,
      )),
    )
  },
})
</script>
