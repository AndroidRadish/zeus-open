<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, GitBranch, FileText, Clock, Activity, Target, AlignLeft, BarChart3, ScrollText, Terminal } from 'lucide-vue-next'
import { marked } from 'marked'
import 'github-markdown-css/github-markdown-dark.css'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'
import { useTaskStore } from '../stores/taskStore'

const { t } = useI18n()
const taskStore = useTaskStore()

export interface TaskDetail {
  id: string
  title?: string
  description?: string
  status: string
  passes: boolean
  wave?: number
  scheduled_wave?: number
  rescheduled_from?: number
  depends_on?: string[]
  files?: string[]
  commit_sha?: string
  worker_id?: string
  heartbeat_at?: string
  milestone_id?: string
  type?: string
  latest_progress?: any
  latest_events?: any[]
  [key: string]: any
}

const props = defineProps<{
  open: boolean
  task: TaskDetail | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const activeTab = ref<'details' | 'logs' | 'execution'>('details')
const logsContent = ref('')
const logsLoading = ref(false)
const renderedLogs = computed(() => {
  if (!logsContent.value) return ''
  try {
    return marked.parse(logsContent.value) as string
  } catch {
    return logsContent.value
  }
})

const logsContainer = ref<HTMLElement | null>(null)

watch(() => logsContent.value, async () => {
  await nextTick()
  if (logsContainer.value) {
    logsContainer.value.querySelectorAll('pre code').forEach((el) => {
      hljs.highlightElement(el as HTMLElement)
    })
  }
})
const timeline = ref<any[]>([])
const timelineLoading = ref(false)
const taskResult = ref<any>(null)
const taskResultLoading = ref(false)

watch(() => props.open, (val) => {
  if (typeof document !== 'undefined') {
    document.body.style.overflow = val ? 'hidden' : ''
  }
  if (val && props.task) {
    activeTab.value = 'details'
    loadLogs()
    loadExecution()
  }
})

watch(() => props.task?.id, () => {
  if (props.open && props.task) {
    loadLogs()
    loadExecution()
  }
})

async function loadLogs() {
  if (!props.task) return
  logsLoading.value = true
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/tasks/${props.task.id}/logs`)
    logsContent.value = res.ok ? await res.text() : 'Failed to load logs.'
  } catch {
    logsContent.value = 'Failed to load logs.'
  } finally {
    logsLoading.value = false
  }
}

async function loadExecution() {
  if (!props.task) return
  timelineLoading.value = true
  taskResultLoading.value = true
  timeline.value = await taskStore.fetchTaskTimeline(props.task.id)
  timelineLoading.value = false
  taskResult.value = await taskStore.fetchTaskResult(props.task.id)
  taskResultLoading.value = false
}

function onClose() {
  emit('close')
}

function eventIcon(et: string) {
  if (et === 'task.started') return '▶'
  if (et === 'task.completed') return '✓'
  if (et === 'task.failed') return '✗'
  if (et === 'task.progress') return '⋯'
  if (et === 'task.retried') return '↻'
  if (et === 'task.cancelled') return '⊘'
  return '•'
}

function eventColorClass(et: string) {
  if (et === 'task.started') return 'event-started'
  if (et === 'task.completed') return 'event-completed'
  if (et === 'task.failed') return 'event-failed'
  if (et === 'task.progress') return 'event-progress'
  return 'event-default'
}

function statusClass(status: string) {
  return `status-${status || 'pending'}`
}

function progressPercent(task: TaskDetail): number {
  return task.latest_progress?.payload?.percent || 0
}

function progressStep(task: TaskDetail): string {
  return task.latest_progress?.payload?.step || ''
}

function progressMessages(task: TaskDetail): string[] {
  if (!task.latest_events) return []
  return task.latest_events
    .filter((e: any) => e.event_type === 'task.progress')
    .slice(0, 3)
    .map((e: any) => e.payload?.message || e.payload?.step || '')
}


</script>

<template>
  <Transition name="drawer">
    <div v-if="open" class="drawer-overlay" @click.self="onClose">
      <aside class="drawer" role="dialog" aria-modal="true">
        <div class="drawer-head">
          <div class="drawer-title">
            <span class="title-mono">{{ task?.id }}</span>
            <span
              class="status-pill"
              :class="statusClass(task?.status || 'pending')"
            >
              {{ task?.status || 'pending' }}
            </span>
          </div>
          <button class="drawer-close" aria-label="Close" @click="onClose">
            <X :size="18" />
          </button>
        </div>

        <div v-if="task" class="drawer-body custom-scrollbar">
          <!-- Progress block -->
          <div v-if="task.status === 'running' && task.latest_progress" class="detail-block progress-block">
            <div class="block-label"><BarChart3 :size="14" /> {{ t('tasks.progress') }}</div>
            <div class="progress-row">
              <span class="progress-step">{{ progressStep(task) || t('tasks.progress') }}</span>
              <span class="progress-percent">{{ progressPercent(task) }}%</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: progressPercent(task) + '%' }"></div>
            </div>
            <div v-if="progressMessages(task).length" class="progress-messages">
              <div v-for="(msg, i) in progressMessages(task)" :key="i" class="progress-msg">
                {{ msg }}
              </div>
            </div>
          </div>

          <!-- Tabs -->
          <div class="detail-tabs">
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'details' }"
              @click="activeTab = 'details'"
            >
              <AlignLeft :size="13" /> {{ t('tasks.detail') }}
            </button>
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'logs' }"
              @click="activeTab = 'logs'"
            >
              <ScrollText :size="13" /> {{ t('tasks.logs') }}
            </button>
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'execution' }"
              @click="activeTab = 'execution'"
            >
              <Terminal :size="13" /> {{ t('tasks.execution') }}
            </button>
          </div>

          <!-- Details tab -->
          <div v-if="activeTab === 'details'" class="tab-content">
            <div class="detail-block">
              <div class="block-label"><AlignLeft :size="14" /> {{ t('tasks.titleCol') }}</div>
              <div class="block-value">{{ task.title || t('tasks.unnamed') }}</div>
            </div>

            <div v-if="task.description" class="detail-block">
              <div class="block-label"><AlignLeft :size="14" /> {{ t('tasks.description') }}</div>
              <div class="block-value text-secondary">{{ task.description }}</div>
            </div>

            <div class="detail-grid">
              <div class="detail-block">
                <div class="block-label"><Activity :size="14" /> {{ t('tasks.result') }}</div>
                <div class="block-value">
                  <span class="result-pill" :class="task.passes ? 'pass' : 'fail'">
                    {{ task.passes ? t('result.pass') : t('result.fail') }}
                  </span>
                </div>
              </div>
              <div class="detail-block">
                <div class="block-label"><Target :size="14" /> {{ t('tasks.wave') }}</div>
                <div class="block-value mono">{{ task.wave ?? '-' }}</div>
              </div>
              <div v-if="task.scheduled_wave !== undefined" class="detail-block">
                <div class="block-label"><Target :size="14" /> {{ t('tasks.scheduledWave') }}</div>
                <div class="block-value mono">{{ task.scheduled_wave }}</div>
              </div>
              <div v-if="task.rescheduled_from !== undefined" class="detail-block">
                <div class="block-label"><Target :size="14" /> {{ t('tasks.rescheduledFrom') }}</div>
                <div class="block-value mono">{{ task.rescheduled_from }}</div>
              </div>
            </div>

            <div v-if="task.depends_on?.length" class="detail-block">
              <div class="block-label"><GitBranch :size="14" /> {{ t('tasks.dependsOn') }}</div>
              <div class="tag-list">
                <span v-for="d in task.depends_on" :key="d" class="tag mono">{{ d }}</span>
              </div>
            </div>

            <div v-if="task.files?.length" class="detail-block">
              <div class="block-label"><FileText :size="14" /> {{ t('tasks.files') }}</div>
              <ul class="file-list">
                <li v-for="f in task.files" :key="f" class="file-item mono">{{ f }}</li>
              </ul>
            </div>

            <div class="detail-grid">
              <div v-if="task.commit_sha" class="detail-block">
                <div class="block-label"><Activity :size="14" /> {{ t('tasks.commitSha') }}</div>
                <div class="block-value mono">{{ task.commit_sha }}</div>
              </div>
              <div v-if="task.worker_id" class="detail-block">
                <div class="block-label"><Activity :size="14" /> {{ t('tasks.worker') }}</div>
                <div class="block-value mono">{{ task.worker_id }}</div>
              </div>
              <div v-if="task.heartbeat_at" class="detail-block">
                <div class="block-label"><Clock :size="14" /> {{ t('tasks.heartbeat') }}</div>
                <div class="block-value mono">{{ new Date(task.heartbeat_at).toLocaleString() }}</div>
              </div>
              <div v-if="task.milestone_id" class="detail-block">
                <div class="block-label"><Target :size="14" /> {{ t('tasks.milestone') }}</div>
                <div class="block-value mono">{{ task.milestone_id }}</div>
              </div>
            </div>
          </div>

          <!-- Logs tab -->
          <div v-if="activeTab === 'logs'" class="tab-content">
            <div v-if="logsLoading" class="logs-loading">{{ t('tasks.loadingLogs') }}</div>
            <div v-else-if="renderedLogs" ref="logsContainer" class="markdown-body" v-html="renderedLogs"></div>
            <div v-else class="logs-loading">{{ t('tasks.noLogs') }}</div>
          </div>

          <!-- Execution tab -->
          <div v-if="activeTab === 'execution'" class="tab-content">
            <!-- Timeline -->
            <div class="detail-block">
              <div class="block-label"><Clock :size="14" /> {{ t('tasks.timeline') }}</div>
              <div v-if="timelineLoading" class="logs-loading">Loading…</div>
              <div v-else-if="!timeline.length" class="muted">No execution events</div>
              <div v-else class="timeline">
                <div v-for="(ev, idx) in timeline" :key="idx" class="timeline-item">
                  <div class="timeline-marker" :class="eventColorClass(ev.event_type)">
                    <span class="timeline-icon">{{ eventIcon(ev.event_type) }}</span>
                  </div>
                  <div class="timeline-body">
                    <div class="timeline-meta">
                      <span class="timeline-type">{{ ev.event_type }}</span>
                      <span class="timeline-time">{{ new Date(ev.ts).toLocaleString() }}</span>
                    </div>
                    <div v-if="ev.payload && Object.keys(ev.payload).length" class="timeline-payload">
                      <pre class="payload-pre">{{ JSON.stringify(ev.payload, null, 2) }}</pre>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <!-- Result -->
            <div class="detail-block">
              <div class="block-label"><Terminal :size="14" /> {{ t('tasks.result') }}</div>
              <div v-if="taskResultLoading" class="logs-loading">Loading…</div>
              <div v-else-if="!taskResult" class="muted">No result available</div>
              <pre v-else class="result-pre">{{ JSON.stringify(taskResult, null, 2) }}</pre>
            </div>
          </div>
        </div>

        <div v-else class="drawer-body empty">
          {{ t('tasks.empty') }}
        </div>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(6px);
  display: flex;
  justify-content: flex-end;
}

.drawer {
  width: 100%;
  max-width: 520px;
  height: 100%;
  background: rgba(10, 12, 24, 0.98);
  border-left: 1px solid var(--z-border);
  display: flex;
  flex-direction: column;
  box-shadow: -16px 0 48px rgba(0,0,0,0.45);
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--z-border);
}

.drawer-title {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.title-mono {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 1rem;
  color: #ffffff;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  background: rgba(255,255,255,0.08);
  color: #e2e8f0;
}
.status-pill.status-completed { background: rgba(52,211,153,0.15); color: var(--z-success); }
.status-pill.status-running { background: rgba(34,211,238,0.15); color: var(--z-accent-cyan); }
.status-pill.status-failed { background: rgba(251,113,133,0.15); color: var(--z-danger); }
.status-pill.status-pending { background: rgba(148,163,184,0.15); color: var(--z-text-secondary); }
.status-pill.status-paused { background: rgba(167,139,250,0.15); color: var(--z-violet); }

.drawer-close {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--z-text-secondary);
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.45rem;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: all 0.2s ease;
}
.drawer-close:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }

.drawer-body {
  padding: 1.25rem;
  overflow-y: auto;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.empty {
  color: var(--z-text-muted);
  font-size: 0.9rem;
}

.detail-block {
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 0.65rem;
  padding: 0.85rem 1rem;
}

.block-label {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: var(--z-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 0.35rem;
}

.block-value {
  color: #e2e8f0;
  font-size: 0.95rem;
  line-height: 1.5;
}

.text-secondary {
  color: #cbd5e1;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

@media (max-width: 480px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}

.result-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
}
.result-pill.pass { background: rgba(52,211,153,0.12); color: var(--z-success); }
.result-pill.fail { background: rgba(251,113,133,0.12); color: var(--z-danger); }

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.tag {
  display: inline-flex;
  align-items: center;
  padding: 0.3rem 0.55rem;
  border-radius: 0.4rem;
  font-size: 0.75rem;
  background: rgba(34,211,238,0.12);
  color: var(--z-accent-cyan);
  border: 1px solid rgba(34,211,238,0.2);
}

.file-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.file-item {
  font-size: 0.8rem;
  color: #cbd5e1;
  padding: 0.35rem 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.file-item:last-child { border-bottom: none; }

.progress-block {
  background: rgba(34,211,238,0.06);
  border-color: rgba(34,211,238,0.15);
}
.progress-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}
.progress-step {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--z-accent-cyan);
  text-transform: capitalize;
}
.progress-percent {
  font-size: 0.8rem;
  color: var(--z-text-secondary);
  font-family: var(--font-mono);
}
.progress-track {
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 999px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--z-accent-cyan), #22d3ee);
  border-radius: 999px;
  transition: width 0.4s ease;
}
.progress-messages {
  margin-top: 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.progress-msg {
  font-size: 0.8rem;
  color: #cbd5e1;
  padding: 0.25rem 0;
}

.detail-tabs {
  display: flex;
  gap: 0.35rem;
  border-bottom: 1px solid var(--z-border);
  margin-bottom: 0.5rem;
}
.tab-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--z-text-secondary);
  font-size: 0.8rem;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-bottom: 2px solid transparent;
  transition: all 0.2s ease;
}
.tab-btn:hover { color: #e2e8f0; }
.tab-btn.active {
  color: var(--z-accent-cyan);
  border-bottom-color: var(--z-accent-cyan);
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.logs-loading {
  color: var(--z-text-secondary);
  font-size: 0.9rem;
  padding: 1rem 0;
}
.markdown-body {
  font-size: 0.825rem;
  line-height: 1.7;
}
.markdown-body :deep(pre) {
  border-radius: 0.5rem;
  font-size: 0.78rem;
  max-height: 360px;
  overflow-y: auto;
}
.markdown-body :deep(code) {
  font-size: 0.85em;
}
.markdown-body :deep(hr) {
  margin: 1.5em 0;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2) {
  border-bottom-color: rgba(255,255,255,0.08);
  padding-bottom: 0.3em;
}

.result-pre {
  background: rgba(0,0,0,0.35);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 0.5rem;
  padding: 0.85rem 1rem;
  font-size: 0.75rem;
  line-height: 1.5;
  color: #cbd5e1;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
  font-family: var(--font-mono);
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  position: relative;
  padding-left: 0.5rem;
}

.timeline-item {
  display: flex;
  gap: 0.75rem;
  padding: 0.5rem 0;
  position: relative;
}

.timeline-item:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 11px;
  top: 28px;
  bottom: -4px;
  width: 2px;
  background: rgba(255,255,255,0.08);
}

.timeline-marker {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  font-size: 0.7rem;
  font-weight: 700;
  margin-top: 2px;
}

.timeline-icon {
  line-height: 1;
}

.event-started { background: rgba(34,211,238,0.15); color: var(--z-accent-cyan); }
.event-completed { background: rgba(52,211,153,0.15); color: var(--z-success); }
.event-failed { background: rgba(248,113,113,0.15); color: var(--z-danger); }
.event-progress { background: rgba(251,191,36,0.15); color: var(--z-warning); }
.event-default { background: rgba(255,255,255,0.08); color: var(--z-text-secondary); }

.timeline-body {
  flex: 1;
  min-width: 0;
}

.timeline-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
  flex-wrap: wrap;
}

.timeline-type {
  font-size: 0.8rem;
  font-weight: 600;
  color: #e2e8f0;
}

.timeline-time {
  font-size: 0.7rem;
  color: var(--z-text-muted);
  font-family: var(--font-mono);
}

.timeline-payload {
  margin-top: 0.25rem;
}

.payload-pre {
  background: rgba(0,0,0,0.25);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 0.35rem;
  padding: 0.4rem 0.5rem;
  font-size: 0.72rem;
  line-height: 1.4;
  color: #cbd5e1;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 160px;
  overflow-y: auto;
  font-family: var(--font-mono);
  margin: 0;
}

/* Transitions */
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.25s ease;
}
.drawer-enter-active .drawer,
.drawer-leave-active .drawer {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .drawer,
.drawer-leave-to .drawer {
  transform: translateX(100%);
}
</style>
