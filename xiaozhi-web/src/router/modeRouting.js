export const VIEW_MODE = 'view'
export const CONTROL_MODE = 'control'
export const MODE_STORAGE_KEY = 'xiaozhi_web_mode'

export const MODE_OPTIONS = [
  { value: VIEW_MODE, label: '查看模式' },
  { value: CONTROL_MODE, label: '控制模式' },
]

const DEFAULT_ROUTES = {
  [VIEW_MODE]: '/',
  [CONTROL_MODE]: '/iot',
}

export const VIEW_MENU_ITEMS = [
  { to: '/', label: '总览面板', icon: 'dashboard' },
  { to: '/sensor', label: '环境监测', icon: 'sensor' },
  { to: '/meow', label: '猫叫记录', icon: 'meow' },
  { to: '/water', label: '饮水记录', icon: 'water' },
]

export const CONTROL_MENU_ITEMS = [
  { to: '/iot', label: 'IoT 控制', icon: 'iot' },
  { to: '/water', label: '饮水控制', icon: 'water' },
  { to: '/meow', label: '猫叫控制', icon: 'meow' },
  { to: '/settings', label: '系统设置', icon: 'settings' },
]

export function normalizeMode(mode) {
  return mode === CONTROL_MODE ? CONTROL_MODE : VIEW_MODE
}

export function getDefaultRouteForMode(mode) {
  return DEFAULT_ROUTES[normalizeMode(mode)]
}

export function getModeMenuItems(mode) {
  return normalizeMode(mode) === CONTROL_MODE ? CONTROL_MENU_ITEMS : VIEW_MENU_ITEMS
}

export function isRouteSupportedByMode(route, mode) {
  const modes = route?.meta?.modes
  if (!Array.isArray(modes) || !modes.length) return true
  return modes.includes(normalizeMode(mode))
}

export function resolveModeRoute(route, mode) {
  if (route?.path === '/voice') {
    return {
      path: getDefaultRouteForMode(mode),
      replace: true,
    }
  }

  if (isRouteSupportedByMode(route, mode)) return null
  return {
    path: getDefaultRouteForMode(mode),
    replace: true,
  }
}

export function getModeRouteTitle(path, mode, fallback = '') {
  const item = getModeMenuItems(mode).find((menuItem) => menuItem.to === path)
  return item?.label ?? fallback
}
