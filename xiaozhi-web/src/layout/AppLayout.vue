<template>
  <div class="drawer lg:drawer-open">
    <input id="sidebar" type="checkbox" class="drawer-toggle" />

    <div class="drawer-content glass-scrollbar flex min-h-screen flex-col overflow-y-auto bg-transparent">
      <header class="sticky top-0 z-30 border-b border-white/60 bg-[#fffefa]/72 shadow-sm shadow-emerald-950/5 backdrop-blur-xl">
        <div class="navbar min-h-[4.25rem] gap-3 px-4 lg:px-7">
          <label for="sidebar" class="btn btn-ghost btn-sm shrink-0 text-[#52645a] lg:hidden">
            <Menu :size="18" />
          </label>

          <div class="min-w-0 flex-1">
            <div class="truncate text-base font-semibold text-[#17211b]">{{ pageTitle }}</div>
            <div class="truncate text-xs text-[#789083]">XiaoZhi 智能猫窝</div>
          </div>

          <div class="flex shrink-0 items-center gap-2">
            <div class="lg:hidden">
              <ModeSwitch compact />
            </div>

            <div class="status-chip hidden lg:flex">
              <span
                class="h-2.5 w-2.5 rounded-full"
                :class="deviceStore.connected ? 'bg-[#2f8f6b]' : 'bg-[#c4ccc7]'"
              />
              {{ deviceStore.connected ? `设备在线 · ${deviceStore.deviceId || '未命名设备'}` : '设备离线' }}
            </div>
          </div>
        </div>
      </header>

      <main class="min-h-screen flex-1 px-4 py-5 lg:px-7 lg:py-7">
        <slot />
      </main>
    </div>

    <div class="drawer-side z-40">
      <label for="sidebar" class="drawer-overlay" />
      <aside class="flex min-h-full w-72 flex-col border-r border-white/60 bg-[#fffefa]/78 shadow-2xl shadow-emerald-950/10 backdrop-blur-2xl">
        <div class="border-b border-white/60 px-5 py-5">
          <div class="flex items-center gap-3">
            <div class="flex h-11 w-11 items-center justify-center rounded-lg bg-[#17674c] text-white shadow-sm shadow-emerald-900/10">
              <Cpu :size="18" />
            </div>
            <div>
              <div class="text-sm font-semibold text-[#17211b]">XiaoZhi Home</div>
              <div class="text-xs text-[#789083]">猫窝、饮水与环境状态</div>
            </div>
          </div>

          <div class="mt-4 hidden lg:block">
            <ModeSwitch />
          </div>
        </div>

        <nav class="glass-scrollbar flex-1 overflow-y-auto px-3 py-4">
          <ul class="menu gap-1 p-0">
            <li v-for="item in menuItems" :key="item.to">
              <RouterLink
                :to="item.to"
                class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition"
                :class="route.path === item.to
                  ? 'bg-[#17674c] text-white shadow-sm shadow-emerald-900/10'
                  : 'text-[#66756d] hover:bg-[#eef6f0] hover:text-[#17211b]'"
                @click="closeSidebar"
              >
                <component :is="iconMap[item.icon]" :size="18" />
                {{ item.label }}
              </RouterLink>
            </li>
          </ul>
        </nav>

        <div class="border-t border-white/60 px-5 py-4">
          <div class="soft-panel px-4 py-3">
            <div class="flex items-center justify-between gap-3">
              <div class="section-label">设备状态</div>
              <span
                class="h-2.5 w-2.5 rounded-full"
                :class="deviceStore.connected ? 'bg-[#2f8f6b]' : 'bg-[#c4ccc7]'"
              />
            </div>
            <div class="mt-2 text-sm font-medium text-[#17211b]">
              {{ deviceStore.connected ? '设备在线' : '离线等待中' }}
            </div>
            <div class="mt-1 truncate text-xs text-[#789083]">
              {{ deviceStore.connected ? deviceStore.state : '等待设备重新连接' }}
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
          'grid rounded-lg bg-[#eef6f0] p-1',
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
              ? 'bg-[#fffefa] text-[#17674c] shadow-sm'
              : 'text-[#66756d] hover:text-[#17211b]',
          ],
          onClick: () => switchMode(option.value),
        },
        props.compact ? option.label.replace('模式', '') : option.label,
      )),
    )
  },
})
</script>
