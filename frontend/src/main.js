import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

import HomePage    from './pages/Home.vue'
import CreatePage  from './pages/Create.vue'
import ResultsPage from './pages/Results.vue'
import ProfilePage from './pages/Profile.vue'
import JobDetail   from './pages/JobDetail.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/',            component: HomePage    },
    { path: '/create',      component: CreatePage  },
    { path: '/results',     component: ResultsPage },
    { path: '/results/:id', component: JobDetail   },
    { path: '/profile',     component: ProfilePage },
  ],
  scrollBehavior() { return { top: 0 } }
})

createApp(App).use(router).mount('#app')
