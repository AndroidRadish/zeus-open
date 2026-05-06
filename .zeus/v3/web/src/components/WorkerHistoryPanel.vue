<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Activity, Cpu, History, FileText } from 'lucide-vue-next'
import { useTaskStore } from '../stores/taskStore'
import { useUiStore } from '../stores/uiStore'

const { t } = useI18n()
const taskStore = useTaskStore()
const uiStore = useUiStore()

const activeWorkers = computed(() => taskStore.workers || [])
const history = computed(() => taskStore.workerHistory || [])
const historyOffset = ref(0)
const historyLimit = 50
const loadingMore = ref(false)

function statusColorClass(status: string) {
  if (status === 'completed') return 'status-completed'
  if (status === 'failed') return 'status-failed'
  if (status === 'running') return 'status-running'
  return 'status-pending'
}

function formatTime(ts: string | null) {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function formatDuration(ms: number | null) {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const min = Math.floor(ms / 60000)
  const sec = Math.floor((ms % 60000) / 1000)
  return `${min}m ${sec}s`
}

async function loadMore() {
  if (loadingMore.value) return
  loadingMore.value = true
  historyOffset.value += historyLimit
  await taskStore.fetchWorkerHistory(historyLimit, historyOffset.value)
  loadingMore.value = false
}

onMounted(() => {
  taskStore.fetchWorkers()
  taskStore.fetchWorkerHistory(historyLimit, 0)
})
</script>

<template>
  <section class="glass-card panel worker-history-panel">
    <div class="panel-head">
      <h2>{{ t('agents.title') }}</h2>
    </div>

    <!-- Active Workers Summary -->
    <div class="active-section">
      <div class="section-label">
        <Cpu :size="14" />
        <span>{{ t('agents.activeWorkers') }}</span>
        <span class="count-badge">{{ activeWorkers.length }}</span>
      </div>
      <div v-if="activeWorkers.length" class="active-list">
        <div v-for="w in activeWorkers" :key="w.worker_id" class="active-card">
          <div class="active-top">
            <span class="mono bold">{{ w.worker_id }}</span>
            <span class="status-pill" :class="statusColorClass(w.task_status)">
              <span class="status-dot"></span>
              {{ w.task_status }}
            </span>
          </div>
          <div class="active-task">
            <span class="mono">{{ w.task_id }}</span>
            <span class="task-title">{{ w.task_title }}</span>
          </div>
          <div class="active-meta">
            <span v-if="w.step" class="step-tag">{{ w.step }}</span>
            <div class="progress-row">
              <div class="mini-track">
                <div class="mini-fill" :style="{ width: (w.percent || 0) + '%' }"></div>
              </div>
              <span class="percent">{{ w.percent || 0 }}%</span>
            </div>
            <span class="hb-time">
              <Activity :size="10" class="hb-icon" />
              {{ formatTime(w.heartbeat_at) }}
            </span>
          </div>
        </div>
      </div>
      <div v-else class="empty-mini">{{ t('agents.empty') }}</div>
    </div>

    <!-- History -->
    <div class="history-section">
      <div class="section-label">
        <History :size="14" />
        <span>{{ t('agents.historyTitle') }}</span>
      </div>
      <div class="table-wrap custom-scrollbar">
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ t('agents.worker') }}</th>
              <th>{{ t('agents.task') }}</th>
              <th>{{ t('agents.status') }}</th>
              <th>{{ t('agents.duration') }}</th>
              <th>{{ t('agents.startedAt') }}</th>
              <th>{{ t('agents.endedAt') }}</th>
              <th>{{ t('agents.result') }}</th>
              <th class="th-logs"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="run in history" :key="run.id">
              <td class="mono bold">{{ run.worker_id }}</td>
              <td class="mono">{{ run.task_id }}</td>
              <td>
                <span class="status-pill" :class="statusColorClass(run.status)">
                  <span class="status-dot"></span>
                  {{ run.status }}
                </span>
              </td>
              <td>{{ formatDuration(run.duration_ms) }}</td>
              <td>{{ formatTime(run.started_at) }}</td>
              <td>{{ formatTime(run.ended_at) }}</td>
              <td>
                <span v-if="run.result_summary" class="result-text" :title="run.result_summary">
                  {{ run.result_summary }}
                </span>
                <span v-else class="muted">—</span>
              </td>
              <td>
                <button class="btn-log" :title="t('actions.logs')" @click="uiStore.openLogs(run.task_id)">
                  <FileText :size="14" />
                </button>
              </td>
            </tr>
            <tr v-if="history.length === 0">
              <td colspan="8" class="empty-cell">{{ t('agents.empty') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="load-more-wrap">
        <button class="btn-load-more" :disabled="loadingMore" @click="loadMore">
          {{ loadingMore ? '...' : t('agents.loadMore') }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.panel {
  overflow: hidden;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--z-border);
}

.panel-head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--z-text-primary);
  font-family: var(--font-display);
}

.active-section,
.history-section {
  padding: 1rem 1.25rem;
}

.active-section {
  border-bottom: 1px solid var(--z-border);
}

.section-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--z-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 0.75rem;
}

.count-badge {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  background: rgba(255, 255, 255, 0.08);
  color: var(--z-text-primary);
}

.active-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.active-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  min-width: 260px;
  flex: 1;
}

.active-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.4rem;
}

.active-task {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin-bottom: 0.5rem;
}

.task-title {
  font-size: 0.78rem;
  color: var(--z-text-secondary);
}

.active-meta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.step-tag {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.45rem;
  border-radius: 0.3rem;
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(34, 211, 238, 0.10);
  color: var(--z-accent-cyan);
  border: 1px solid rgba(34, 211, 238, 0.18);
  text-transform: capitalize;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.mini-track {
  width: 60px;
  height: 4px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  overflow: hidden;
}

.mini-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--z-accent-cyan), #22d3ee);
  border-radius: 999px;
  transition: width 0.4s ease;
}

.percent {
  font-size: 0.7rem;
  color: var(--z-text-secondary);
  font-family: var(--font-mono);
}

.hb-time {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.72rem;
  color: var(--z-text-secondary);
}

.hb-icon {
  animation: pulseIcon 1.4s ease-in-out infinite;
}

@keyframes pulseIcon {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.empty-mini {
  text-align: center;
  color: var(--z-text-muted);
  font-size: 0.85rem;
  padding: 1rem;
}

.table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

.data-table thead {
  background: rgba(255, 255, 255, 0.02);
}

.data-table th {
  padding: 0.7rem 0.8rem;
  text-align: left;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--z-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.data-table td {
  padding: 0.75rem 0.8rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  color: #e2e8f0;
}

.data-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.025);
}

.mono {
  font-family: var(--font-mono);
}

.bold {
  font-weight: 600;
}

.muted {
  color: var(--z-text-muted);
  font-size: 0.8rem;
}

.result-text {
  font-size: 0.78rem;
  color: var(--z-text-secondary);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
}

.th-logs {
  width: 48px;
}

.btn-log {
  appearance: none;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  color: var(--z-text-secondary);
  width: 32px;
  height: 32px;
  border-radius: 0.35rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-log:hover {
  background: rgba(255,255,255,0.08);
  color: var(--z-accent-cyan);
  border-color: rgba(34,211,238,0.25);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  background: rgba(255, 255, 255, 0.06);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
}

.status-running .status-dot {
  background: var(--z-accent-cyan);
  box-shadow: 0 0 6px var(--z-accent-cyan);
}

.status-running {
  background: rgba(34, 211, 238, 0.10);
  color: var(--z-accent-cyan);
}

.status-completed .status-dot {
  background: #34d399;
  box-shadow: 0 0 6px #34d399;
}

.status-completed {
  background: rgba(52, 211, 153, 0.10);
  color: #34d399;
}

.status-failed .status-dot {
  background: #f87171;
  box-shadow: 0 0 6px #f87171;
}

.status-failed {
  background: rgba(248, 113, 113, 0.10);
  color: #f87171;
}

.status-pending .status-dot {
  background: var(--z-text-muted);
}

.status-pending {
  background: rgba(148, 163, 184, 0.08);
  color: var(--z-text-muted);
}

.empty-cell {
  text-align: center;
  color: var(--z-text-muted);
  padding: 2rem 1rem;
}

.load-more-wrap {
  display: flex;
  justify-content: center;
  padding: 0.75rem;
}

.btn-load-more {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--z-text-secondary);
  padding: 0.4rem 1rem;
  border-radius: 0.35rem;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-load-more:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  color: var(--z-text-primary);
}

.btn-load-more:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
