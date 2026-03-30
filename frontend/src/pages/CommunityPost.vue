<template>
  <div class="cp-page page-inner">
    <div class="cp-topbar">
      <button class="back-btn" @click="$router.push('/community')">← 返回论坛</button>
      <div class="top-title">社区详情</div>
    </div>

    <div v-if="loading" class="cp-center card">
      <div class="spin">⟳</div>
      <p>加载帖子中...</p>
    </div>
    <div v-else-if="!post" class="cp-center card">
      <p>帖子不存在或已被删除</p>
    </div>

    <div v-else class="cp-layout">
      <main class="cp-main">
        <article class="post-head card">
          <div class="meta-row">
            <div class="author">
              <img v-if="post.author.avatar_url" :src="post.author.avatar_url" class="avatar" alt="avatar">
              <div v-else class="avatar fallback">{{ (post.author.name || '?')[0]?.toUpperCase() }}</div>
              <div>
                <div class="author-name">{{ post.author.name || '匿名用户' }}</div>
                <div class="author-time">{{ fmtDateTime(post.created_at) }}</div>
              </div>
            </div>
            <div v-if="post.topic" class="topic"># {{ post.topic }}</div>
          </div>

          <h1 class="title">{{ post.title }}</h1>
          <p v-if="post.description" class="desc">{{ post.description }}</p>
          <p v-if="post.content_text" class="content">{{ post.content_text }}</p>

          <div v-if="post.image_urls?.length" class="images">
            <img v-for="(img, idx) in post.image_urls" :key="img + idx" :src="img" alt="image">
          </div>

          <div v-if="post.media?.video" class="video-wrap">
            <video :src="post.media.video.url" controls preload="metadata"></video>
          </div>

          <div v-if="post.media?.markdown" class="markdown-wrap">
            <div class="section-title">📘 共享文稿（支持查词）</div>
            <div class="md-view" ref="mdViewRef"
                 v-html="markdownHtml"
                 @click="onWordClick"
                 @mouseover="onMdHover"
                 @mouseout="onMdOut"
                 @mouseleave="onMdLeave"></div>
          </div>

          <div class="stats-row">
            <button class="stat-btn" @click="togglePostLike">
              <span>{{ post.viewer_liked ? '❤️' : '🤍' }}</span>
              <span>{{ post.likes_count }}</span>
            </button>
            <div class="stat-item">💬 {{ post.comments_count }}</div>
            <div class="stat-item">▶ {{ post.views_count }}</div>
            <div class="stat-item" v-if="post.source_lang && post.target_lang">{{ post.source_lang }} → {{ post.target_lang }}</div>
          </div>
        </article>
      </main>

      <aside class="cp-comments card">
        <div class="c-title">评论区</div>

        <div class="comment-box" v-if="isLoggedIn">
          <textarea
            v-model.trim="commentText"
            class="input comment-input"
            placeholder="写下你的想法..."
          ></textarea>
          <button class="btn-primary" :disabled="submittingComment" @click="submitComment">
            {{ submittingComment ? '发送中...' : '发布评论' }}
          </button>
        </div>
        <div class="comment-box" v-else>
          <p class="login-tip">登录后可参与评论和点赞互动。</p>
          <button class="btn-primary" @click="openAuth">登录 / 注册</button>
        </div>

        <div v-if="loadingComments" class="comment-loading">评论加载中...</div>
        <div v-else-if="comments.length === 0" class="comment-empty">还没有评论，来发第一条吧。</div>
        <div v-else class="comment-list">
          <div class="comment-item" v-for="c in comments" :key="c.id">
            <div class="comment-meta">
              <div class="comment-author">
                <img v-if="c.author.avatar_url" :src="c.author.avatar_url" class="comment-avatar" alt="avatar">
                <div v-else class="comment-avatar fallback">{{ (c.author.name || '?')[0]?.toUpperCase() }}</div>
                <div>
                  <div class="name">{{ c.author.name || '匿名用户' }}</div>
                  <div class="time">{{ fmtDateTime(c.created_at) }}</div>
                </div>
              </div>
              <button class="mini-like" @click="toggleCommentLike(c)">{{ c.viewer_liked ? '👍' : '👍🏻' }} {{ c.likes_count }}</button>
            </div>
            <div class="comment-content">{{ c.content }}</div>
          </div>
        </div>
      </aside>
    </div>

    <Teleport to="body">
      <Transition name="dt">
        <div v-if="tooltip.visible"
             :class="['dict-tooltip', { 'left-side': tooltip.side === 'left' }]"
             :style="tooltipStyle"
             @mouseenter="cancelHide"
             @mouseleave="scheduleHide">
          <div v-if="tooltip.loading" class="dt-loading">
            <span class="dt-spin">⟳</span> 查询中…
          </div>
          <div v-else-if="tooltip.notFound" class="dt-not-found">
            未找到 "{{ tooltip.word }}"
          </div>
          <template v-else-if="tooltip.data">
            <div class="dt-head">
              <span class="dt-word">{{ tooltip.data.word }}</span>
              <span v-if="tooltip.data.phonetic" class="dt-phonetic">{{ tooltip.data.phonetic }}</span>
              <button v-if="tooltip.data.audio" class="dt-audio" @click="playAudio" title="播放发音">🔊</button>
            </div>
            <div v-for="(m, i) in tooltip.data.meanings" :key="i" class="dt-meaning">
              <span v-if="m.pos" class="dt-pos">{{ m.pos }}</span>
              <p class="dt-def">{{ m.definition }}</p>
              <p v-if="tooltip.data.translated_meanings?.[i]" class="dt-def-trans">{{ tooltip.data.translated_meanings[i] }}</p>
              <p v-if="m.example" class="dt-ex">"{{ m.example }}"</p>
            </div>
          </template>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, inject } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { apiFetch } from '../composables/useApi.js'
import { useAuth } from '../composables/useAuth.js'

const route = useRoute()
const { isLoggedIn } = useAuth()
const openAuth = inject('openAuth', () => {})
const toast = inject('toast', () => {})

const post = ref(null)
const loading = ref(true)
const viewed = ref(false)

const comments = ref([])
const loadingComments = ref(false)
const commentText = ref('')
const submittingComment = ref(false)

const markdownHtml = ref('')
const mdViewRef = ref(null)

const postId = computed(() => Number(route.params.id || 0))

onMounted(() => {
  loadAll()
})

watch(() => route.params.id, () => {
  viewed.value = false
  loadAll()
})

function fmtDateTime(ts) {
  if (!ts) return '--'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadAll() {
  if (!postId.value) {
    post.value = null
    loading.value = false
    return
  }

  loading.value = true
  markdownHtml.value = ''
  try {
    const d = await apiFetch(`/api/community/posts/${postId.value}`)
    post.value = d.post || null

    if (post.value?.media?.markdown?.content) {
      await renderMarkdown(post.value.media.markdown.content)
    }

    await loadComments()
    await addViewOnce()
  } catch (e) {
    post.value = null
    toast('加载帖子失败: ' + e.message, 'err')
  } finally {
    loading.value = false
  }
}

async function addViewOnce() {
  if (!post.value || viewed.value) return
  viewed.value = true
  try {
    const d = await apiFetch(`/api/community/posts/${post.value.id}/view`, { method: 'POST' })
    if (post.value) post.value.views_count = Number(d.views_count || post.value.views_count || 0)
  } catch {
    // ignore
  }
}

async function loadComments() {
  if (!post.value) return
  loadingComments.value = true
  try {
    const d = await apiFetch(`/api/community/posts/${post.value.id}/comments?limit=500`)
    comments.value = d.comments || []
  } catch (e) {
    comments.value = []
    toast('加载评论失败: ' + e.message, 'err')
  } finally {
    loadingComments.value = false
  }
}

async function togglePostLike() {
  if (!post.value) return
  if (!isLoggedIn.value) {
    openAuth()
    return
  }
  try {
    const d = await apiFetch(`/api/community/posts/${post.value.id}/like`, { method: 'POST' })
    post.value.viewer_liked = !!d.liked
    post.value.likes_count = Number(d.likes_count || 0)
  } catch (e) {
    toast('点赞失败: ' + e.message, 'err')
  }
}

async function submitComment() {
  if (!post.value) return
  if (!isLoggedIn.value) {
    openAuth()
    return
  }
  if (!commentText.value.trim()) {
    toast('评论内容不能为空', 'warn')
    return
  }

  submittingComment.value = true
  try {
    const d = await apiFetch(`/api/community/posts/${post.value.id}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: commentText.value.trim() }),
    })
    if (d.comment) {
      comments.value.push(d.comment)
      commentText.value = ''
      post.value.comments_count = Number(post.value.comments_count || 0) + 1
    }
  } catch (e) {
    toast('评论发布失败: ' + e.message, 'err')
  } finally {
    submittingComment.value = false
  }
}

async function toggleCommentLike(comment) {
  if (!isLoggedIn.value) {
    openAuth()
    return
  }
  try {
    const d = await apiFetch(`/api/community/comments/${comment.id}/like`, { method: 'POST' })
    comment.viewer_liked = !!d.liked
    comment.likes_count = Number(d.likes_count || 0)
  } catch (e) {
    toast('评论点赞失败: ' + e.message, 'err')
  }
}

async function renderMarkdown(mdText) {
  try {
    let html = marked.parse(mdText || '')
    if (html instanceof Promise) html = await html
    markdownHtml.value = wrapEnglishWords(html)
  } catch (e) {
    markdownHtml.value = `<p>${String(mdText || '')}</p>`
  }
}

// Dictionary logic
const tooltip = ref({ visible: false, loading: false, notFound: false, word: '', data: null, y: 0, side: 'right', anchorX: 0 })
const dictCache = {}
let showTimer = null
let hideTimer = null
let hoverToken = 0
let activeHoverKey = ''
let requestToken = 0

const TOOLTIP_W = 300
const tooltipStyle = computed(() => {
  const MARGIN = 10
  const GAP = 20
  let x
  if (tooltip.value.side === 'left') {
    x = tooltip.value.anchorX - TOOLTIP_W - GAP
    x = Math.max(MARGIN, x)
  } else {
    x = tooltip.value.anchorX + GAP
    if (x + TOOLTIP_W > window.innerWidth - MARGIN) {
      x = window.innerWidth - TOOLTIP_W - MARGIN
    }
  }
  let y = tooltip.value.y - 10
  y = Math.max(MARGIN, Math.min(y, window.innerHeight - 300))
  return { left: `${x}px`, top: `${y}px`, width: `${TOOLTIP_W}px` }
})

function wrapEnglishWords(html) {
  const parser = new DOMParser()
  const doc = parser.parseFromString(`<div>${html}</div>`, 'text/html')
  const root = doc.body.firstChild
  const SKIP = new Set(['CODE', 'PRE', 'SCRIPT', 'STYLE'])
  const RE = /\b[a-zA-Z]+(?:['-][a-zA-Z]+)*\b/g

  function walk(node) {
    if (node.nodeType === 3) {
      const text = node.textContent
      if (!/[a-zA-Z]/.test(text)) return
      const parts = []
      let last = 0
      let m
      let changed = false
      RE.lastIndex = 0
      while ((m = RE.exec(text)) !== null) {
        if (m.index > last) parts.push(document.createTextNode(text.slice(last, m.index)))
        const s = document.createElement('span')
        s.className = 'dict-word'
        s.dataset.word = m[0].toLowerCase()
        s.textContent = m[0]
        parts.push(s)
        last = RE.lastIndex
        changed = true
      }
      if (!changed) return
      if (last < text.length) parts.push(document.createTextNode(text.slice(last)))
      const frag = document.createDocumentFragment()
      parts.forEach(p => frag.appendChild(p))
      node.parentNode.replaceChild(frag, node)
    } else if (node.nodeType === 1) {
      if (SKIP.has(node.tagName) || node.classList?.contains('dict-word')) return
      ;[...node.childNodes].forEach(walk)
    }
  }

  walk(root)
  return root.innerHTML
}

function onMdHover(e) {
  const el = e.target.closest?.('.dict-word')
  if (el) {
    hoverToken += 1
    const localHover = hoverToken
    clearTimeout(hideTimer)
    clearTimeout(showTimer)
    showTimer = setTimeout(() => {
      if (localHover !== hoverToken) return
      triggerTooltip(el.dataset.word, el)
    }, 180)
    return
  }
  if (!e.target.closest?.('.dict-tooltip')) {
    clearTimeout(showTimer)
    if (tooltip.value.visible) scheduleHide()
  }
}

function onMdOut(e) {
  if (e.target.classList?.contains('dict-word')) {
    if (!e.relatedTarget?.closest?.('.dict-word') && !e.relatedTarget?.closest?.('.dict-tooltip')) {
      hoverToken += 1
      activeHoverKey = ''
      clearTimeout(showTimer)
      scheduleHide()
    }
  }
}

function onMdLeave(e) {
  hoverToken += 1
  activeHoverKey = ''
  clearTimeout(showTimer)
  if (e.relatedTarget?.closest?.('.dict-tooltip')) return
  scheduleHide()
}

async function onWordClick(e) {
  const el = e.target.closest?.('.dict-word')
  if (!el) return
  e.preventDefault()
  e.stopPropagation()

  clearTimeout(hideTimer)
  clearTimeout(showTimer)

  const word = (el.dataset.word || '').toLowerCase().trim()
  if (!word) return

  try {
    await triggerTooltip(word, el)
  } catch {
    // ignore
  }

  const url = tooltip.value.data?.audio || dictCache[word]?.audio
  if (url) new Audio(url).play().catch(() => {})
}

function cancelHide() {
  clearTimeout(hideTimer)
}

function scheduleHide() {
  hideTimer = setTimeout(() => {
    tooltip.value.visible = false
    tooltip.value.loading = false
  }, 180)
}

async function triggerTooltip(word, el) {
  if (!word) return
  const hoverKey = `${word}__${Math.round(el?.getBoundingClientRect?.().left || 0)}`
  activeHoverKey = hoverKey

  const rect = el.getBoundingClientRect()
  tooltip.value.word = word
  tooltip.value.y = rect.top + rect.height / 2
  tooltip.value.notFound = false

  const containerRect = mdViewRef.value?.getBoundingClientRect()
  const wordCenterX = (rect.left + rect.right) / 2
  const centerX = containerRect ? (containerRect.left + containerRect.right) / 2 : window.innerWidth / 2
  const isLeft = wordCenterX < centerX
  tooltip.value.side = isLeft ? 'left' : 'right'
  tooltip.value.anchorX = isLeft ? (containerRect?.left ?? rect.left) : (containerRect?.right ?? rect.right)

  if (dictCache[word] !== undefined) {
    if (activeHoverKey !== hoverKey) return
    tooltip.value.data = dictCache[word] || null
    tooltip.value.notFound = !dictCache[word]
    tooltip.value.loading = false
    tooltip.value.visible = true
    return
  }

  tooltip.value.loading = true
  tooltip.value.data = null
  tooltip.value.visible = true

  requestToken += 1
  const localReq = requestToken

  try {
    const tgtLang = post.value?.target_lang || 'zh'
    const data = await apiFetch(`/api/dictionary/${encodeURIComponent(word)}?target_lang=${tgtLang}`)
    dictCache[word] = data
    if (localReq !== requestToken || activeHoverKey !== hoverKey) return
    tooltip.value.data = data
    tooltip.value.notFound = false
  } catch {
    dictCache[word] = null
    if (localReq !== requestToken || activeHoverKey !== hoverKey) return
    tooltip.value.notFound = true
    tooltip.value.data = null
  } finally {
    if (localReq !== requestToken || activeHoverKey !== hoverKey) return
    tooltip.value.loading = false
  }
}

function playAudio() {
  const url = tooltip.value.data?.audio
  if (url) new Audio(url).play().catch(() => {})
}

onUnmounted(() => {
  clearTimeout(showTimer)
  clearTimeout(hideTimer)
})
</script>

<style scoped>
.cp-page {
  max-width: 1360px;
  margin: 0 auto;
  padding: 20px 22px 80px;
}
.cp-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.top-title {
  font-size: 14px;
  color: var(--text2);
  font-weight: 600;
}
.back-btn {
  padding: 7px 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg3);
  color: var(--text2);
  font-size: 12px;
  font-weight: 700;
}
.back-btn:hover { color: var(--text); }

.cp-center {
  padding: 40px;
  text-align: center;
}
.spin { font-size: 28px; animation: spin 1s linear infinite; }

.cp-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 14px;
  align-items: start;
}
@media (max-width: 1120px) {
  .cp-layout { grid-template-columns: 1fr; }
}

.post-head {
  border-radius: 14px;
  padding: 16px;
}
.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.author {
  display: flex;
  align-items: center;
  gap: 8px;
}
.avatar,
.comment-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid var(--border);
}
.fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}
.author-name { font-size: 13px; font-weight: 700; }
.author-time { font-size: 11px; color: var(--text3); }
.topic {
  font-size: 12px;
  border: 1px solid rgba(99,102,241,.28);
  background: rgba(99,102,241,.08);
  color: var(--accent);
  padding: 5px 10px;
  border-radius: 999px;
}
.title {
  font-size: 28px;
  line-height: 1.3;
  margin-bottom: 8px;
}
.desc {
  color: var(--text2);
  line-height: 1.8;
  margin-bottom: 8px;
}
.content {
  white-space: pre-wrap;
  color: var(--text2);
  line-height: 1.8;
  margin-bottom: 8px;
}
.images {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}
@media (max-width: 760px) {
  .images { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.images img {
  width: 100%;
  height: 150px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid var(--border);
}
.video-wrap {
  margin: 12px 0;
}
.video-wrap video {
  width: 100%;
  border-radius: 12px;
  background: #000;
  border: 1px solid var(--border);
}
.markdown-wrap {
  margin-top: 14px;
}
.section-title {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--text2);
}

.md-view {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  line-height: 1.8;
  font-size: 14px;
}
.md-view :deep(h1) {
  font-size: 24px;
  margin: 8px 0 16px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 10px;
}
.md-view :deep(h2) {
  font-size: 18px;
  margin: 22px 0 10px;
}
.md-view :deep(h3) {
  font-size: 15px;
  margin: 16px 0 8px;
}
.md-view :deep(p) { margin: 0 0 10px; }
.md-view :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}
.md-view :deep(th),
.md-view :deep(td) {
  border: 1px solid var(--border);
  padding: 7px;
  text-align: left;
}
.md-view :deep(blockquote) {
  border-left: 3px solid var(--accent);
  background: rgba(99,102,241,.06);
  padding: 8px 10px;
  border-radius: 0 8px 8px 0;
}

.stats-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}
.stat-btn,
.stat-item {
  font-size: 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 5px 10px;
  background: var(--bg3);
  color: var(--text2);
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.stat-btn:hover { border-color: rgba(99,102,241,.35); color: var(--accent); }

.cp-comments {
  border-radius: 14px;
  padding: 14px;
  position: sticky;
  top: 72px;
  max-height: calc(100vh - 88px);
  overflow: auto;
}
.c-title {
  font-size: 18px;
  font-weight: 800;
  margin-bottom: 10px;
}
.comment-box {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}
.comment-input {
  min-height: 96px;
  resize: vertical;
}
.login-tip {
  font-size: 13px;
  color: var(--text2);
}
.comment-loading,
.comment-empty {
  font-size: 13px;
  color: var(--text2);
  padding: 8px 0;
}
.comment-list {
  display: grid;
  gap: 10px;
}
.comment-item {
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
}
.comment-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.comment-author {
  display: flex;
  align-items: center;
  gap: 8px;
}
.comment-avatar { width: 30px; height: 30px; }
.name { font-size: 12px; font-weight: 700; }
.time { font-size: 11px; color: var(--text3); }
.mini-like {
  border: 1px solid var(--border);
  background: var(--bg3);
  border-radius: 999px;
  font-size: 11px;
  padding: 4px 8px;
  color: var(--text2);
}
.comment-content {
  white-space: pre-wrap;
  line-height: 1.7;
  font-size: 13px;
  color: var(--text2);
}

:deep(.dict-word) {
  cursor: pointer;
  border-radius: 4px;
  padding: 0 2px;
  background: rgba(99,102,241,.08);
  transition: all .15s;
}
:deep(.dict-word:hover) {
  background: rgba(99,102,241,.18);
}

.dict-tooltip {
  position: fixed;
  z-index: 500;
  max-height: 300px;
  overflow: auto;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 12px 36px rgba(15,23,42,.18);
}
.dt-loading,
.dt-not-found {
  font-size: 13px;
  color: var(--text2);
}
.dt-spin { animation: spin 1s linear infinite; display: inline-block; }
.dt-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.dt-word { font-size: 18px; font-weight: 800; }
.dt-phonetic { font-size: 12px; color: var(--text3); }
.dt-audio {
  margin-left: auto;
  border: 1px solid var(--border);
  background: var(--bg3);
  border-radius: 8px;
  padding: 3px 8px;
}
.dt-meaning { margin-bottom: 8px; }
.dt-pos {
  display: inline-flex;
  font-size: 11px;
  border-radius: 999px;
  border: 1px solid var(--border);
  padding: 2px 7px;
  color: var(--text2);
  margin-bottom: 4px;
}
.dt-def { font-size: 13px; color: var(--text); line-height: 1.6; }
.dt-def-trans { font-size: 12px; color: #0f766e; margin-top: 3px; }
.dt-ex { font-size: 12px; color: var(--text2); font-style: italic; margin-top: 4px; }

.dt-enter-active, .dt-leave-active { transition: all .16s ease; }
.dt-enter-from, .dt-leave-to { opacity: 0; transform: translateY(4px); }

@keyframes spin { to { transform: rotate(360deg); } }
</style>
