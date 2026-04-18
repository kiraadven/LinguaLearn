import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import VueKonva from 'vue-konva'
import App from './App.vue'
import './style.css'

import HomePage    from './pages/Home.vue'
import CreatePage  from './pages/Create.vue'
import ResultsPage from './pages/Results.vue'
import ProfilePage from './pages/Profile.vue'
import JobDetail   from './pages/JobDetail.vue'
import QuizPage    from './pages/Quiz.vue'
import AiTutorPage from './pages/AiTutor.vue'
import MembershipPage from './pages/Membership.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/',            component: HomePage    },
    { path: '/create',      component: CreatePage  },
    { path: '/results',     component: ResultsPage },
    { path: '/results/:id', component: JobDetail   },
    { path: '/quiz',        component: QuizPage       },
    { path: '/tutor',       component: AiTutorPage    },
    { path: '/membership',  component: MembershipPage },
    { path: '/profile',     component: ProfilePage    },
  ],
  scrollBehavior() { return { top: 0 } }
})

createApp(App).use(router).use(VueKonva).mount('#app')
