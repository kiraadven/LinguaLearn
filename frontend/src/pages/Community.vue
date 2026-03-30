<template>
  <div class="community-page page-inner">
    <div class="community-head">
      <div>
        <h1>论坛中心</h1>
        <p>发布学习成果视频/文稿，围绕话题交流经验，打造活跃学习社区</p>
      </div>
      <button class="btn-primary" @click="goCreate">去生成新内容</button>
    </div>

    <div class="community-layout">
      <section class="feed-col">
        <div class="feed-toolbar card">
          <div class="toolbar-row">
            <input
              v-model.trim="query"
              class="input"
              placeholder="搜索标题、正文、话题..."
              @keyup.enter="reloadPosts"
            >
            <button class="btn-ghost toolbar-btn" @click="reloadPosts">搜索</button>
            <select v-model="sort" class="input sort-select" @change="reloadPosts">
              <option value="new">最新发布</option>
              <option value="hot">热门优先</option>
            </select>
          </div>
          <div class="topic-row">
            <button
              :class="['topic-chip', { active: topicFilter === '' }]"
              @click="pickTopic('')"
            >全部</button>
            <button
              v-for="t in topics"
              :key="t.topic"
              :class="['topic-chip', { active: topicFilter === t.topic }]"
              @click="pickTopic(t.topic)"
            >
              #{{ t.topic }}
              <span>{{ t.count }}</span>
            </button>
          </div>
        </div>

        <div v-if="loadingPosts" class="feed-loading card">
          <div class="spin">⟳</div>
          <p>正在加载帖子...</p>
        </div>

        <div v-else-if="posts.length === 0" class="feed-empty card">
          <div class="empty-icon">🗂️</div>
          <h3>还没有帖子</h3>
          <p>成为第一个发布学习成果的人吧。</p>
        </div>

        <div v-else class="feed-list">
          <article
            v-for="post in posts"
            :key="post.id"
            class="post-card card"
            @click="openPost(post.id)"
          >
            <header class="post-top">
              <div class="author">
                <img v-if="post.author.avatar_url" :src="post.author.avatar_url" class="author-avatar" alt="avatar">
                <div v-else class="author-avatar author-fallback">{{ (post.author.name || '?')[0]?.toUpperCase() }}</div>
                <div>
                  <div class="author-name">{{ post.author.name || '匿名用户' }}</div>
                  <div class="author-time">{{ fmtDateTime(post.created_at) }}</div>
                </div>
              </div>
              <div v-if="post.topic" class="post-topic"># {{ post.topic }}</div>
            </header>

            <h3 class="post-title">{{ post.title }}</h3>
            <p v-if="post.description" class="post-desc">{{ post.description }}</p>
            <p v-if="post.content_text" class="post-content">{{ ellipsis(post.content_text, 220) }}</p>

            <div v-if="post.image_urls?.length" class="post-images" @click.stop>
              <img
                v-for="(img, idx) in post.image_urls.slice(0, 3)"
                :key="img + idx"
                :src="img"
                alt="post image"
              >
              <div v-if="post.image_urls.length > 3" class="img-more">+{{ post.image_urls.length - 3 }}</div>
            </div>

            <div v-if="post.media?.video" class="post-video" @click.stop>
              <video :src="post.media.video.url" controls preload="metadata"></video>
            </div>

            <div class="post-tags">
              <span v-if="post.media?.video" class="tag">视频</span>
              <span v-if="post.media?.markdown" class="tag">文稿</span>
              <span v-if="post.image_urls?.length" class="tag">图文</span>
              <span v-if="post.content_text" class="tag">文字</span>
              <span v-if="post.source_lang && post.target_lang" class="tag lang">{{ post.source_lang }} → {{ post.target_lang }}</span>
            </div>

            <footer class="post-stats">
              <button class="stat-btn" @click.stop="toggleLike(post)">
                <span>{{ post.viewer_liked ? '❤️' : '🤍' }}</span>
                <span>{{ post.likes_count }}</span>
              </button>
              <div class="stat-item">💬 {{ post.comments_count }}</div>
              <div class="stat-item">▶ {{ post.views_count }}</div>
              <button class="stat-link" @click.stop="openPost(post.id)">查看详情</button>
            </footer>
          </article>

          <div v-if="canLoadMore" class="load-more-wrap">
            <button class="btn-ghost" :disabled="loadingMore" @click="loadMorePosts">
              {{ loadingMore ? '加载中...' : '加载更多' }}
            </button>
          </div>
        </div>
      </section>

      <aside class="composer-col">
        <div class="composer card" v-if="isLoggedIn">
          <div class="composer-title">发布新帖子</div>
          <p class="composer-sub">支持图文、纯文字、仅视频、仅文稿等多种方式发布。</p>

          <label class="label">标题（可留空自动使用任务名称）</label>
          <input v-model="form.title" class="input" placeholder="例如：这段新闻听力我这样精听" style="margin-bottom:10px">

          <label class="label">话题（可选）</label>
          <input v-model="form.topic" class="input" placeholder="例如：新闻听力 / 雅思 / 口语" style="margin-bottom:10px">

          <label class="label">简介（可选）</label>
          <textarea v-model="form.description" class="input textarea" placeholder="一句话介绍这条学习成果"></textarea>

          <label class="label">正文（可选，支持纯文字发帖）</label>
          <textarea v-model="form.content_text" class="input textarea" placeholder="分享你的学习方法、复盘、心得"></textarea>

          <div class="split"></div>

          <label class="label">关联你自己的已完成任务（可选）</label>
          <select v-model="form.job_id" class="input" style="margin-bottom:10px">
            <option value="">不关联任务</option>
            <option v-for="j in myJobs" :key="j.id" :value="j.id">
              {{ j.name }}
              {{ j.has_video || j.has_markdown ? `（${j.has_video ? '有视频' : ''}${j.has_video && j.has_markdown ? ' / ' : ''}${j.has_markdown ? '有文稿' : ''}）` : '' }}
            </option>
          </select>

          <div class="checks">
            <label><input type="checkbox" v-model="form.share_video"> 分享任务视频</label>
            <label><input type="checkbox" v-model="form.share_markdown"> 分享任务文稿</label>
          </div>
          <div class="tip-line">仅允许分享当前账号自己生成的任务内容，外部视频无法上传发布。</div>

          <div class="split"></div>

          <label class="label">上传配图（可选）</label>
          <input type="file" accept="image/*" multiple @change="onPickImages">
          <div class="uploading" v-if="uploadingImage">上传图片中...</div>
          <div v-if="form.image_urls.length" class="picked-images">
            <div class="picked-item" v-for="(img, idx) in form.image_urls" :key="img + idx">
              <img :src="img" alt="img">
              <button class="remove-img" @click="removeImage(idx)">✕</button>
            </div>
          </div>

          <button class="btn-primary publish-btn" :disabled="publishing" @click="publishPost">
            {{ publishing ? '发布中...' : '立即发布' }}
          </button>
        </div>

        <div class="composer card" v-else>
          <div class="composer-title">登录后发布内容</div>
          <p class="composer-sub">你可以先浏览社区，再登录发布自己的视频与文稿。</p>
          <button class="btn-primary" @click="openAuth">登录 / 注册</button>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted, inject, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { apiFetch } from '../composables/useApi.js'
import { useAuth } from '../composables/useAuth.js'

const router = useRouter()
const { isLoggedIn } = useAuth()
const openAuth = inject('openAuth', () => {})
const toast = inject('toast', () => {})

const posts = ref([])
const topics = ref([])
const loadingPosts = ref(false)
const loadingMore = ref(false)
const page = ref(1)
const totalPages = ref(1)
const pageSize = 12

const query = ref('')
const sort = ref('new')
const topicFilter = ref('')

const myJobs = ref([])
const publishing = ref(false)
const uploadingImage = ref(false)

const form = reactive({
  title: '',
  topic: '',
  description: '',
  content_text: '',
  job_id: '',
  share_video: false,
  share_markdown: false,
  image_urls: [],
})

const canLoadMore = computed(() => page.value < totalPages.value)

onMounted(async () => {
  await Promise.all([fetchTopics(), loadPosts(true)])
  if (isLoggedIn.value) {
    await fetchMyJobs()
  }
})

watch(isLoggedIn, async (v) => {
  if (v) {
    await fetchMyJobs()
  } else {
    myJobs.value = []
  }
})

function goCreate() {
  if (!isLoggedIn.value) {
    openAuth()
    return
  }
  router.push('/create')
}

function fmtDateTime(ts) {
  if (!ts) return '--'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function ellipsis(text, n = 180) {
  const s = String(text || '')
  return s.length > n ? s.slice(0, n) + '...' : s
}

async function fetchTopics() {
  try {
    const d = await apiFetch('/api/community/topics?limit=100')
    topics.value = d.topics || []
  } catch {
    topics.value = []
  }
}

async function fetchMyJobs() {
  try {
    const d = await apiFetch('/api/community/my-jobs?limit=200')
    myJobs.value = d.jobs || []
  } catch (e) {
    myJobs.value = []
    toast('获取可发布任务失败: ' + e.message, 'err')
  }
}

async function loadPosts(reset = false) {
  if (reset) {
    page.value = 1
    loadingPosts.value = true
  } else {
    loadingMore.value = true
  }

  try {
    const targetPage = reset ? 1 : page.value + 1
    const params = new URLSearchParams()
    if (topicFilter.value) params.set('topic', topicFilter.value)
    if (query.value) params.set('q', query.value)
    params.set('sort', sort.value)
    params.set('page', String(targetPage))
    params.set('page_size', String(pageSize))

    const d = await apiFetch(`/api/community/posts?${params.toString()}`)
    const next = d.posts || []
    const pg = d.pagination || { page: targetPage, total_pages: 1 }

    if (reset) {
      posts.value = next
    } else {
      posts.value = [...posts.value, ...next]
    }

    page.value = pg.page || targetPage
    totalPages.value = pg.total_pages || 1
  } catch (e) {
    toast('加载帖子失败: ' + e.message, 'err')
  } finally {
    loadingPosts.value = false
    loadingMore.value = false
  }
}

async function reloadPosts() {
  await loadPosts(true)
}

async function loadMorePosts() {
  if (!canLoadMore.value || loadingMore.value) return
  await loadPosts(false)
}

function pickTopic(topic) {
  topicFilter.value = topic
  loadPosts(true)
}

function openPost(id) {
  router.push(`/community/${id}`)
}

async function toggleLike(post) {
  if (!isLoggedIn.value) {
    openAuth()
    return
  }
  try {
    const d = await apiFetch(`/api/community/posts/${post.id}/like`, { method: 'POST' })
    post.viewer_liked = !!d.liked
    post.likes_count = Number(d.likes_count || 0)
  } catch (e) {
    toast('点赞失败: ' + e.message, 'err')
  }
}

async function onPickImages(e) {
  if (!isLoggedIn.value) {
    openAuth()
    return
  }
  const files = Array.from(e.target.files || [])
  if (!files.length) return

  uploadingImage.value = true
  try {
    for (const file of files.slice(0, 8)) {
      const fd = new FormData()
      fd.append('image', file)
      const d = await apiFetch('/api/community/upload-image', {
        method: 'POST',
        body: fd,
      })
      if (d.url) form.image_urls.push(d.url)
    }
  } catch (err) {
    toast('上传图片失败: ' + err.message, 'err')
  } finally {
    uploadingImage.value = false
    if (e.target) e.target.value = ''
  }
}

function removeImage(idx) {
  form.image_urls.splice(idx, 1)
}

async function publishPost() {
  if (!isLoggedIn.value) {
    openAuth()
    return
  }

  if ((form.share_video || form.share_markdown) && !form.job_id) {
    toast('勾选分享视频/文稿时，请先选择来源任务', 'warn')
    return
  }

  publishing.value = true
  try {
    const payload = {
      title: form.title,
      topic: form.topic,
      description: form.description,
      content_text: form.content_text,
      job_id: form.job_id || null,
      share_video: !!form.share_video,
      share_markdown: !!form.share_markdown,
      image_urls: form.image_urls,
    }

    const d = await apiFetch('/api/community/posts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (d.post) {
      posts.value.unshift(d.post)
      resetForm()
      toast('发布成功，已展示在社区信息流', 'ok')
      await fetchTopics()
    }
  } catch (e) {
    toast('发布失败: ' + e.message, 'err')
  } finally {
    publishing.value = false
  }
}

function resetForm() {
  form.title = ''
  form.topic = ''
  form.description = ''
  form.content_text = ''
  form.job_id = ''
  form.share_video = false
  form.share_markdown = false
  form.image_urls = []
}
</script>

<style scoped>
.community-page {
  max-width: 1320px;
  margin: 0 auto;
  padding: 24px 22px 80px;
}
.community-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.community-head h1 {
  font-size: 30px;
  font-weight: 800;
  margin-bottom: 6px;
}
.community-head p {
  color: var(--text2);
  font-size: 14px;
}
.community-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 16px;
  align-items: start;
}
@media (max-width: 1120px) {
  .community-layout { grid-template-columns: 1fr; }
}

.feed-toolbar {
  padding: 14px;
  border-radius: 14px;
  margin-bottom: 14px;
}
.toolbar-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.toolbar-btn { height: 41px; padding: 0 16px; }
.sort-select { width: 132px; }
.topic-row {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.topic-chip {
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text2);
  background: #fff;
  display: inline-flex;
  gap: 6px;
  align-items: center;
}
.topic-chip span {
  font-size: 11px;
  color: var(--text3);
}
.topic-chip.active {
  color: var(--accent);
  border-color: rgba(99,102,241,.35);
  background: rgba(99,102,241,.08);
}

.feed-loading,
.feed-empty {
  padding: 32px;
  text-align: center;
  border-radius: 14px;
}
.feed-loading .spin { font-size: 28px; animation: spin 1s linear infinite; }
.feed-empty .empty-icon { font-size: 44px; margin-bottom: 10px; }
.feed-empty h3 { font-size: 17px; margin-bottom: 4px; }
.feed-empty p { color: var(--text2); font-size: 13px; }

.feed-list {
  display: grid;
  gap: 12px;
}
.post-card {
  border-radius: 14px;
  padding: 14px;
  cursor: pointer;
  transition: all .18s;
}
.post-card:hover {
  transform: translateY(-1px);
  border-color: rgba(99,102,241,.35);
}
.post-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.author {
  display: flex;
  align-items: center;
  gap: 9px;
}
.author-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid var(--border);
}
.author-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}
.author-name { font-size: 13px; font-weight: 700; color: var(--text); }
.author-time { font-size: 11px; color: var(--text3); }
.post-topic {
  font-size: 12px;
  color: var(--accent);
  background: rgba(99,102,241,.08);
  border: 1px solid rgba(99,102,241,.2);
  border-radius: 999px;
  padding: 5px 10px;
}
.post-title {
  font-size: 18px;
  line-height: 1.45;
  margin-bottom: 6px;
}
.post-desc {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text2);
  margin-bottom: 6px;
}
.post-content {
  font-size: 13px;
  line-height: 1.75;
  color: var(--text2);
  white-space: pre-wrap;
  margin-bottom: 6px;
}
.post-images {
  margin: 10px 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.post-images img,
.picked-item img {
  width: 100%;
  height: 118px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid var(--border);
}
.img-more {
  border-radius: 10px;
  border: 1px dashed var(--border);
  background: var(--bg3);
  color: var(--text2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
}
.post-video {
  margin: 10px 0;
}
.post-video video {
  width: 100%;
  max-height: 320px;
  background: #000;
  border-radius: 12px;
  border: 1px solid var(--border);
}
.post-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}
.tag {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--text2);
  background: var(--bg3);
}
.tag.lang {
  color: #0f766e;
  border-color: rgba(15,118,110,.25);
  background: rgba(20,184,166,.1);
}
.post-stats {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
}
.stat-btn,
.stat-item {
  font-size: 12px;
  color: var(--text2);
  padding: 5px 9px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: #fff;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.stat-btn:hover { border-color: rgba(99,102,241,.35); color: var(--accent); }
.stat-link {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
}

.load-more-wrap {
  display: flex;
  justify-content: center;
  padding-top: 4px;
}

.composer {
  border-radius: 14px;
  padding: 14px;
  position: sticky;
  top: 72px;
}
.composer-title {
  font-size: 17px;
  font-weight: 800;
  margin-bottom: 4px;
}
.composer-sub {
  color: var(--text2);
  font-size: 12px;
  line-height: 1.6;
  margin-bottom: 12px;
}
.textarea {
  min-height: 92px;
  resize: vertical;
  margin-bottom: 10px;
}
.split {
  height: 1px;
  background: var(--border);
  margin: 10px 0;
}
.checks {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--text2);
}
.tip-line {
  font-size: 11px;
  color: #b45309;
  background: rgba(251,191,36,.15);
  border: 1px solid rgba(251,191,36,.3);
  padding: 7px 8px;
  border-radius: 8px;
}
.uploading {
  margin-top: 6px;
  font-size: 12px;
  color: var(--accent);
}
.picked-images {
  margin-top: 8px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.picked-item {
  position: relative;
}
.remove-img {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,.5);
  background: rgba(15,23,42,.6);
  color: #fff;
  font-size: 11px;
}
.publish-btn {
  margin-top: 12px;
  width: 100%;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
