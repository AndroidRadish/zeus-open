const { DatabaseSync } = require('node:sqlite');
const path = require('node:path');

// Resolve --project-root from CLI args, or use CWD
let projectRoot = process.cwd();
const rootIdx = process.argv.indexOf('--project-root');
if (rootIdx !== -1 && process.argv[rootIdx + 1]) {
  projectRoot = path.resolve(process.argv[rootIdx + 1]);
}

const DB_PATH = path.join(projectRoot, '.zeus', 'v3', 'state.db');

function countStatus(db, status) {
  return db.prepare('SELECT COUNT(*) as cnt FROM task_state WHERE status = ?').get(status).cnt;
}

function status() {
  let db;
  try {
    db = new DatabaseSync(DB_PATH);
  } catch (e) {
    console.log(`state.db not found at ${DB_PATH}`);
    console.log('System has never been initialized, or --project-root is wrong.');
    return;
  }

  const total = db.prepare('SELECT COUNT(*) as cnt FROM task_state').get().cnt;
  if (total === 0) {
    console.log('0 tasks in state.db — system has never been initialized.');
    db.close();
    return;
  }

  const completed = countStatus(db, 'completed');
  const pending = countStatus(db, 'pending');
  const failed = countStatus(db, 'failed');
  const inProgress = countStatus(db, 'in_progress');

  console.log(`Tasks: ${completed}/${total} completed`);
  if (pending) console.log(`       ${pending} pending`);
  if (inProgress) console.log(`       ${inProgress} in_progress`);
  if (failed) console.log(`       ${failed} failed`);
  console.log('');

  const waves = db.prepare('SELECT wave, COUNT(*) as cnt FROM task_state GROUP BY wave ORDER BY wave').all();
  for (const w of waves) {
    const tasks = db.prepare('SELECT id, status, title FROM task_state WHERE wave = ? ORDER BY id').all(w.wave);
    const waveDone = tasks.every(t => t.status === 'completed');
    const mark = waveDone ? '✔' : '⏳';
    console.log(`Wave ${w.wave} (${w.cnt} tasks) ${mark}`);
    for (const t of tasks) {
      const icon = t.status === 'completed' ? '✔' : t.status === 'failed' ? '✘' : t.status === 'in_progress' ? '↻' : '○';
      console.log(`  ${icon} ${t.id}: ${t.title}`);
    }
    console.log('');
  }

  db.close();
}

function plan() {
  let db;
  try {
    db = new DatabaseSync(DB_PATH);
  } catch (e) {
    console.log(`state.db not found at ${DB_PATH}`);
    return;
  }

  const waves = db.prepare('SELECT wave, COUNT(*) as cnt FROM task_state GROUP BY wave ORDER BY wave').all();

  console.log('Plan (by wave):');
  for (const w of waves) {
    const tasks = db.prepare('SELECT id, status, title, depends_on FROM task_state WHERE wave = ? ORDER BY id').all(w.wave);
    const pendingCount = tasks.filter(t => t.status === 'pending' || t.status === 'failed').length;
    const statusLabel = pendingCount === 0 ? 'DONE' : `${pendingCount} remaining`;
    console.log(`Wave ${w.wave}: ${statusLabel}`);
    for (const t of tasks) {
      const deps = JSON.parse(t.depends_on || '[]');
      const depStr = deps.length ? ` (depends: ${deps.join(', ')})` : '';
      console.log(`  ${t.status === 'completed' ? '✔' : '○'} ${t.id}: ${t.title}${depStr}`);
    }
    console.log('');
  }
  db.close();
}

const cmd = process.argv.find(a => a === '--status' || a === 'status' || a === '--plan' || a === 'plan' || a === '--help' || a === 'help') || '--status';

if (cmd === '--status' || cmd === 'status') {
  status();
} else if (cmd === '--plan' || cmd === 'plan') {
  plan();
} else if (cmd === '--help' || cmd === 'help') {
  console.log('Usage: node .zeus/v3/scripts/state.js [--status|--plan] [--project-root <path>]');
  console.log('  --status        Show task completion status by wave (default)');
  console.log('  --plan          Show execution plan with dependencies');
  console.log('  --project-root  Path to business project root (default: CWD)');
} else {
  console.log(`Unknown command: ${cmd}`);
  console.log('Usage: node .zeus/v3/scripts/state.js [--status|--plan] [--project-root <path>]');
}
