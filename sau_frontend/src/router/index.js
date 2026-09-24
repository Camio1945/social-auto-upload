import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import AccountManagement from '../views/AccountManagement.vue'
import MaterialManagement from '../views/MaterialManagement.vue'
import PublishCenter from '../views/PublishCenter.vue'
import About from '../views/About.vue'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard,
    meta: { filePath: 'sau_frontend/src/views/Dashboard.vue' }
  },
  {
    path: '/account-management',
    name: 'AccountManagement',
    component: AccountManagement,
    meta: { filePath: 'sau_frontend/src/views/AccountManagement.vue' }
  },
  {
    path: '/material-management',
    name: 'MaterialManagement',
    component: MaterialManagement,
    meta: { filePath: 'sau_frontend/src/views/MaterialManagement.vue' }
  },
  {
    path: '/publish-center',
    name: 'PublishCenter',
    component: PublishCenter,
    meta: { filePath: 'sau_frontend/src/views/PublishCenter.vue' }
  },
  {
    path: '/about',
    name: 'About',
    component: About,
    meta: { filePath: 'sau_frontend/src/views/About.vue' }
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router