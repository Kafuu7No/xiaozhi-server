import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router, { installModeGuard } from './router'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
installModeGuard(router)
app.use(router)
app.mount('#app')
