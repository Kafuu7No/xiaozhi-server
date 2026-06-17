import test from 'node:test'
import assert from 'node:assert/strict'

import {
  CONTROL_MODE,
  VIEW_MODE,
  getDefaultRouteForMode,
  getModeMenuItems,
  getModeRouteTitle,
  isRouteSupportedByMode,
  normalizeMode,
  resolveModeRoute,
} from './modeRouting.js'

test('normalizes persisted modes', () => {
  assert.equal(normalizeMode(VIEW_MODE), VIEW_MODE)
  assert.equal(normalizeMode(CONTROL_MODE), CONTROL_MODE)
  assert.equal(normalizeMode('broken'), VIEW_MODE)
  assert.equal(normalizeMode(null), VIEW_MODE)
})

test('returns default routes by mode', () => {
  assert.equal(getDefaultRouteForMode(VIEW_MODE), '/')
  assert.equal(getDefaultRouteForMode(CONTROL_MODE), '/iot')
  assert.equal(getDefaultRouteForMode('broken'), '/')
})

test('checks route support by active mode', () => {
  assert.equal(isRouteSupportedByMode({ meta: { modes: [VIEW_MODE] } }, VIEW_MODE), true)
  assert.equal(isRouteSupportedByMode({ meta: { modes: [VIEW_MODE] } }, CONTROL_MODE), false)
  assert.equal(isRouteSupportedByMode({ meta: { modes: [VIEW_MODE, CONTROL_MODE] } }, CONTROL_MODE), true)
})

test('resolves unsupported route with replace navigation', () => {
  assert.deepEqual(resolveModeRoute({ path: '/iot', meta: { modes: [CONTROL_MODE] } }, VIEW_MODE), {
    path: '/',
    replace: true,
  })
  assert.equal(resolveModeRoute({ path: '/water', meta: { modes: [VIEW_MODE, CONTROL_MODE] } }, VIEW_MODE), null)
})

test('resolves legacy voice route to the active mode default with replace navigation', () => {
  assert.deepEqual(resolveModeRoute({ path: '/voice', meta: {} }, VIEW_MODE), {
    path: '/',
    replace: true,
  })
  assert.deepEqual(resolveModeRoute({ path: '/voice', meta: {} }, CONTROL_MODE), {
    path: '/iot',
    replace: true,
  })
})

test('builds mode menus and mode-aware shared route titles', () => {
  assert.deepEqual(
    getModeMenuItems(VIEW_MODE).map((item) => [item.to, item.label]),
    [
      ['/', '总览面板'],
      ['/sensor', '环境监测'],
      ['/meow', '猫叫记录'],
      ['/water', '饮水记录'],
    ],
  )
  assert.deepEqual(
    getModeMenuItems(CONTROL_MODE).map((item) => [item.to, item.label]),
    [
      ['/iot', 'IoT 控制'],
      ['/water', '饮水控制'],
      ['/meow', '猫叫控制'],
      ['/settings', '系统设置'],
    ],
  )
  assert.equal(getModeRouteTitle('/water', VIEW_MODE, 'fallback'), '饮水记录')
  assert.equal(getModeRouteTitle('/water', CONTROL_MODE, 'fallback'), '饮水控制')
  assert.equal(getModeRouteTitle('/settings', VIEW_MODE, '系统设置'), '系统设置')
})
