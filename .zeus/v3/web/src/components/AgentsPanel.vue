<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Activity } from 'lucide-vue-next'
import { useTaskStore } from '../stores/taskStore'

const { t } = useI18n()
const taskStore = useTaskStore()

const workers = computed(() => taskStore.workers || [])

function statusColorClass(status: string) {
  if (status === 'running') return 'status-running'
  if (status === 'idle') return 'status-idle'
  return 'status-offline'
}

function formatTime(ts: string) {
  try {
    return new Date(ts).toLocaleTimeString()
  } catch {
    return ts
  }
}

onMounted(() => {
  taskStore.fetchWorkers()
})
</script>

<template>
  <section class="glass-card panel agents-panel">
    <div class="panel-head">
      <h2>{{ t('agents.title') }}</h2>
      <span class="count-badge">{{ workers.length }}</span>
    </div>
    <div class="table-wrap custom-scrollbar">
      <table class="data-table">
        <thead>
          <tr>
            <th>{{ t('agents.worker') }}</th>
            <th>{{ t('agents.task') }}</th>
            <th>{{ t('agents.step') }}</th>
            <th>{{ t('agents.progress') }}</th>
            <th>{{ t('agents.heartbeat') }}</th>
            <th>{{ t('agents.status') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in workers" :key="w.worker_id">
            <td class="mono bold">{{ w.worker_id }}</td>
            <td>
              <span class="mono">{{ w.task_id }}</span>
              <div class="task-title">{{ w.task_title }}</div>
            </td>
            <td>
              <span v-if="w.step" class="step-tag">{{ w.step }}</span>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <div class="progress-row">
                <div class="mini-track">
                  <div class="mini-fill" :style="{ width: (w.percent || 0) + '%' }"></div>
                </div>
                <span class="percent">{{ w.percent || 0 }}%</span>
              </div>
            </td>
            <td>
              <span class="hb-time">
                <Activity :size="12" class="hb-icon" />
                {{ formatTime(w.heartbeat_at) }}
              </span>
            </td>
            <td>
              <span class="status-pill" :class="statusColorClass(w.task_status)">
                <span class="status-dot"></span>
                {{ w.task_status }}
              </span>
            </td>
          </tr>
          <tr v-if="workers.length === 0">
            <td colspan="6" class="empty-cell">{{ t('agents.empty') }}</td>
          </tr>
        </tbody>
      </table>
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

.count-badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.6rem;
  border-radius: 0.375rem;
  background: rgba(255,255,255,0.05);
  color: #e2e8f0;
}

.table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.data-table thead {
  background: rgba(255,255,255,0.02);
}

.data-table th {
  padding: 0.8rem 1rem;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--z-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.data-table td {
  padding: 0.9rem 1rem;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  color: #e2e8f0;
}

.data-table tbody tr:hover {
  background: rgba(255,255,255,0.025);
}

.mono { font-family: var(--font-mono); }
.bold { font-weight: 600; }
.muted { color: var(--z-text-muted); font-size: 0.8rem; }

.task-title {
  font-size: 0.78rem;
  color: var(--z-text-secondary);
  margin-top: 0.15rem;
}

.step-tag {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.5rem;
  border-radius: 0.35rem;
  font-size: 0.72rem;
  font-weight: 600;
  background: rgba(34,211,238,0.10);
  color: var(--z-accent-cyan);
  border: 1px solid rgba(34,211,238,0.18);
  text-transform: capitalize;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.mini-track {
  width: 72px;
  height: 5px;
  background: rgba(255,255,255,0.08);
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
  font-size: 0.72rem;
  color: var(--z-text-secondary);
  font-family: var(--font-mono);
  min-width: 2.2rem;
}

.hb-time {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  color: var(--z-text-secondary);
}
.hb-icon {
  animation: pulseIcon 1.4s ease-in-out infinite;
}
@keyframes pulseIcon {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  background: rgba(255,255,255,0.06);
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
}
.status-running .status-dot { background: var(--z-accent-cyan); box-shadow: 0 0 6px var(--z-accent-cyan); }
.status-running { background: rgba(34,211,238,0.10); color: var(--z-accent-cyan); }
.status-idle .status-dot { background: var(--z-warning); }
.status-idle { background: rgba(251,191,36,0.10); color: var(--z-warning); }
.status-offline .status-dot { background: var(--z-text-muted); }
.status-offline { background: rgba(148,163,184,0.08); color: var(--z-text-muted); }

.empty-cell {
  text-align: center;
  color: var(--z-text-muted);
  padding: 2.5rem 1rem;
}
</style>
