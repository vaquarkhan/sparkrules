/* sparkrules benchmark charts */

const COLORS = {
  primary: '#6366f1',
  primaryLight: 'rgba(99, 102, 241, 0.15)',
  accent: '#10b981',
  accentLight: 'rgba(16, 185, 129, 0.15)',
  purple: '#8b5cf6',
  purpleLight: 'rgba(139, 92, 246, 0.15)',
  rose: '#f43f5e',
  roseLight: 'rgba(244, 63, 94, 0.15)',
  amber: '#f59e0b',
  amberLight: 'rgba(245, 158, 11, 0.15)',
  slate: '#64748b',
  slateLight: 'rgba(100, 116, 139, 0.15)',
};

const SHARED_OPTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        font: { family: 'Inter', size: 12, weight: '500' },
        padding: 16,
        usePointStyle: true,
        pointStyle: 'circle',
      },
    },
    tooltip: {
      backgroundColor: '#0f172a',
      titleColor: '#f8fafc',
      bodyColor: '#cbd5e1',
      borderColor: '#334155',
      borderWidth: 1,
      padding: 12,
      cornerRadius: 8,
      titleFont: { family: 'Inter', weight: '600', size: 13 },
      bodyFont: { family: 'Inter', size: 13 },
    },
  },
  scales: {
    x: {
      grid: { color: '#e2e8f0', drawBorder: false },
      ticks: { color: '#64748b', font: { family: 'Inter', size: 11 } },
    },
    y: {
      grid: { color: '#e2e8f0', drawBorder: false },
      ticks: { color: '#64748b', font: { family: 'Inter', size: 11 } },
    },
  },
};

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('scalingChart')) renderScalingChart();
  if (document.getElementById('costChart')) renderCostChart();
  if (document.getElementById('timingBreakdownChart')) renderTimingBreakdown();
  if (document.getElementById('fireCountChart')) renderFireCountChart();
  if (document.getElementById('versionComparisonChart')) renderVersionComparison();
  if (document.getElementById('workerTypeChart')) renderWorkerTypeChart();
  if (document.getElementById('phaseStackChart')) renderPhaseStack();
  if (document.getElementById('featureMatrixChart')) renderFeatureMatrix();
  if (document.getElementById('distributedChart')) renderDistributedChart();
  if (document.getElementById('useCaseChart')) renderUseCaseChart();
  if (document.getElementById('ruleComplexityChart')) renderRuleComplexity();
  if (document.getElementById('pypiTrendChart')) loadLiveEcosystemStats();
  if (document.getElementById('engineLatencyChart')) renderEngineLatency();
  if (document.getElementById('rowsPerDollarChart')) renderRowsPerDollar();
});

function renderScalingChart() {
  new Chart(document.getElementById('scalingChart'), {
    type: 'line',
    data: {
      labels: ['10', '25', '50', '100'],
      datasets: [
        {
          label: 'G.1X workers (rows/sec, millions)',
          data: [3.28, 8.2, 16.4, 32.8],
          borderColor: COLORS.primary,
          backgroundColor: COLORS.primaryLight,
          borderWidth: 3,
          pointRadius: 6,
          pointHoverRadius: 8,
          pointBackgroundColor: COLORS.primary,
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          tension: 0.3,
          fill: true,
        },
        {
          label: 'G.2X workers (rows/sec, millions)',
          data: [4.5, 11.3, 22.5, 45.0],
          borderColor: COLORS.accent,
          backgroundColor: COLORS.accentLight,
          borderWidth: 3,
          pointRadius: 6,
          pointHoverRadius: 8,
          pointBackgroundColor: COLORS.accent,
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          tension: 0.3,
          fill: true,
        },
      ],
    },
    options: {
      ...SHARED_OPTS,
      scales: {
        ...SHARED_OPTS.scales,
        x: { ...SHARED_OPTS.scales.x, title: { display: true, text: 'Workers', color: '#475569' } },
        y: {
          ...SHARED_OPTS.scales.y,
          title: { display: true, text: 'Million rows / sec', color: '#475569' },
          beginAtZero: true,
        },
      },
    },
  });
}

function renderCostChart() {
  new Chart(document.getElementById('costChart'), {
    type: 'bar',
    data: {
      labels: ['10 × G.1X', '25 × G.1X', '50 × G.1X', '100 × G.1X', '50 × G.2X', '50 × G.8X'],
      datasets: [
        {
          label: 'USD per 1B rows',
          data: [0.28, 0.28, 0.28, 0.29, 0.41, 0.64],
          backgroundColor: [
            COLORS.primary, COLORS.primary, COLORS.primary, COLORS.primary,
            COLORS.accent, COLORS.purple,
          ],
          borderRadius: 8,
          borderSkipped: false,
        },
      ],
    },
    options: {
      ...SHARED_OPTS,
      plugins: {
        ...SHARED_OPTS.plugins,
        legend: { display: false },
        tooltip: {
          ...SHARED_OPTS.plugins.tooltip,
          callbacks: {
            label: (ctx) => `$${ctx.parsed.y.toFixed(2)} per 1B rows`,
          },
        },
      },
      scales: {
        ...SHARED_OPTS.scales,
        y: {
          ...SHARED_OPTS.scales.y,
          beginAtZero: true,
          ticks: {
            ...SHARED_OPTS.scales.y.ticks,
            callback: (v) => `$${v.toFixed(2)}`,
          },
        },
      },
    },
  });
}

function renderTimingBreakdown() {
  new Chart(document.getElementById('timingBreakdownChart'), {
    type: 'doughnut',
    data: {
      labels: ['Scoring (apply_with_counts)', 'Write parquet to S3', 'Read consolidated input', 'Cluster startup overhead'],
      datasets: [{
        data: [24.25, 36.91, 1.65, 76.19],
        backgroundColor: [COLORS.primary, COLORS.amber, COLORS.accent, COLORS.slate],
        borderColor: '#fff',
        borderWidth: 3,
        hoverOffset: 8,
      }],
    },
    options: {
      ...SHARED_OPTS,
      scales: {},
      plugins: {
        ...SHARED_OPTS.plugins,
        tooltip: {
          ...SHARED_OPTS.plugins.tooltip,
          callbacks: {
            label: (ctx) => `${ctx.label}: ${ctx.parsed.toFixed(2)}s`,
          },
        },
      },
      cutout: '55%',
    },
  });
}

function renderFireCountChart() {
  new Chart(document.getElementById('fireCountChart'), {
    type: 'bar',
    data: {
      labels: [
        'r_r21_vendor_vts', 'r_r29_solo_rider', 'r_r19_weekend_trip',
        'r_r27_medium_trip', 'r_r20_vendor_cmt', 'r_r17_rush_hour_pm',
        'r_r16_rush_hour_am', 'r_r28_long_trip', 'r_r18_late_night',
        'r_r13_airport_jfk_pickup',
      ],
      datasets: [{
        label: 'Rule fires (millions)',
        data: [59.72, 56.46, 21.93, 21.84, 19.75, 16.07, 8.53, 6.56, 5.89, 3.98],
        backgroundColor: COLORS.primary,
        borderRadius: 6,
      }],
    },
    options: {
      ...SHARED_OPTS,
      indexAxis: 'y',
      plugins: {
        ...SHARED_OPTS.plugins,
        legend: { display: false },
        tooltip: {
          ...SHARED_OPTS.plugins.tooltip,
          callbacks: {
            label: (ctx) => `${ctx.parsed.x.toFixed(2)}M fires (${((ctx.parsed.x / 79.48) * 100).toFixed(1)}% of 79.5M rows)`,
          },
        },
      },
      scales: {
        x: {
          ...SHARED_OPTS.scales.x,
          title: { display: true, text: 'Fires (millions)', color: '#475569' },
          beginAtZero: true,
        },
        y: { ...SHARED_OPTS.scales.y, grid: { display: false } },
      },
    },
  });
}

function renderVersionComparison() {
  new Chart(document.getElementById('versionComparisonChart'), {
    type: 'bar',
    data: {
      labels: ['sparkrules 1.1.0', 'sparkrules 1.2.0'],
      datasets: [
        {
          label: 'Scoring time (seconds, lower is better)',
          data: [31.5, 24.25],
          backgroundColor: [COLORS.slate, COLORS.primary],
          borderRadius: 8,
        },
      ],
    },
    options: {
      ...SHARED_OPTS,
      plugins: {
        ...SHARED_OPTS.plugins,
        legend: { display: false },
        tooltip: {
          ...SHARED_OPTS.plugins.tooltip,
          callbacks: { label: (ctx) => `${ctx.parsed.y.toFixed(2)}s scoring wallclock` },
        },
      },
      scales: {
        ...SHARED_OPTS.scales,
        y: {
          ...SHARED_OPTS.scales.y,
          beginAtZero: true,
          title: { display: true, text: 'Seconds', color: '#475569' },
        },
      },
    },
  });
}

function renderWorkerTypeChart() {
  new Chart(document.getElementById('workerTypeChart'), {
    type: 'bar',
    data: {
      labels: ['G.1X', 'G.2X', 'G.4X', 'G.8X'],
      datasets: [
        { label: 'vCPU per worker', data: [4, 8, 16, 32], backgroundColor: COLORS.primary, borderRadius: 6 },
        { label: 'GB RAM per worker', data: [16, 32, 64, 128], backgroundColor: COLORS.accent, borderRadius: 6 },
        { label: 'DPUs per worker', data: [1, 2, 4, 8], backgroundColor: COLORS.purple, borderRadius: 6 },
      ],
    },
    options: {
      ...SHARED_OPTS,
      scales: {
        ...SHARED_OPTS.scales,
        y: { ...SHARED_OPTS.scales.y, beginAtZero: true },
      },
    },
  });
}

function renderPhaseStack() {
  new Chart(document.getElementById('phaseStackChart'), {
    type: 'bar',
    data: {
      labels: ['1.1.0 (10 workers)', '1.2.0 (10 workers)', '1.2.0 (25 workers proj)', '1.2.0 (50 workers proj)'],
      datasets: [
        { label: 'Read (s)', data: [46.6, 1.65, 1.0, 0.7], backgroundColor: COLORS.accent, borderRadius: 4 },
        { label: 'Scoring (s)', data: [111.0, 24.25, 9.7, 4.9], backgroundColor: COLORS.primary, borderRadius: 4 },
        { label: 'Write (s)', data: [26.2, 36.91, 20.0, 12.0], backgroundColor: COLORS.amber, borderRadius: 4 },
      ],
    },
    options: {
      ...SHARED_OPTS,
      scales: {
        ...SHARED_OPTS.scales,
        x: { ...SHARED_OPTS.scales.x, stacked: true },
        y: { ...SHARED_OPTS.scales.y, stacked: true, beginAtZero: true, title: { display: true, text: 'Seconds', color: '#475569' } },
      },
    },
  });
}

function renderFeatureMatrix() {
  new Chart(document.getElementById('featureMatrixChart'), {
    type: 'radar',
    data: {
      labels: [
        'Linear scale-out',
        'DRL syntax',
        'Spark SQL compilation',
        'SQL pushdown classifier',
        'Multi-cloud',
        'Streaming support',
        'Open source',
      ],
      datasets: [
        {
          label: 'sparkrules 1.2.0',
          data: [5, 5, 5, 5, 5, 5, 5],
          borderColor: COLORS.primary,
          backgroundColor: COLORS.primaryLight,
          borderWidth: 2,
          pointBackgroundColor: COLORS.primary,
          pointBorderColor: '#fff',
          pointRadius: 5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } },
      scales: {
        r: {
          suggestedMin: 0,
          suggestedMax: 5,
          ticks: { display: false, stepSize: 1 },
          pointLabels: { font: { family: 'Inter', size: 12, weight: '600' }, color: '#334155' },
          grid: { color: '#e2e8f0' },
          angleLines: { color: '#cbd5e1' },
        },
      },
    },
  });
}

function renderDistributedChart() {
  new Chart(document.getElementById('distributedChart'), {
    type: 'bar',
    data: {
      labels: ['10M rows', '100M rows', '1B rows', '10B rows'],
      datasets: [
        {
          label: '10 × G.1X (minutes)',
          data: [0.05, 0.5, 5.1, 51],
          backgroundColor: COLORS.slateLight,
          borderColor: COLORS.slate,
          borderWidth: 2,
          borderRadius: 6,
        },
        {
          label: '25 × G.1X (minutes)',
          data: [0.02, 0.2, 2.0, 20],
          backgroundColor: COLORS.primaryLight,
          borderColor: COLORS.primary,
          borderWidth: 2,
          borderRadius: 6,
        },
        {
          label: '50 × G.1X (minutes)',
          data: [0.01, 0.1, 1.0, 10.2],
          backgroundColor: COLORS.accentLight,
          borderColor: COLORS.accent,
          borderWidth: 2,
          borderRadius: 6,
        },
        {
          label: '100 × G.1X (minutes)',
          data: [0.005, 0.05, 0.5, 5.1],
          backgroundColor: COLORS.purpleLight,
          borderColor: COLORS.purple,
          borderWidth: 2,
          borderRadius: 6,
        },
      ],
    },
    options: {
      ...SHARED_OPTS,
      scales: {
        ...SHARED_OPTS.scales,
        y: {
          ...SHARED_OPTS.scales.y,
          beginAtZero: true,
          type: 'logarithmic',
          title: { display: true, text: 'Minutes (log scale)', color: '#475569' },
        },
      },
    },
  });
}

function renderUseCaseChart() {
  new Chart(document.getElementById('useCaseChart'), {
    type: 'bar',
    data: {
      labels: [
        'Credit card fraud (Visa peak)',
        'RTB ad bidding',
        'CloudTrail analysis',
        'IoT sensor stream',
        'Claims adjudication',
        'Banking TX monitoring',
        'Telco CDR',
      ],
      datasets: [
        {
          label: 'Required rps',
          data: [65000, 10000000, 12000, 1000000, 3000, 500000, 250000],
          backgroundColor: COLORS.slate,
          borderRadius: 6,
          stack: 'a',
        },
        {
          label: 'sparkrules capacity (headroom)',
          data: [3215000, 12500000, 3268000, 2280000, 3277000, 6054000, 3027000],
          backgroundColor: COLORS.accent,
          borderRadius: 6,
          stack: 'a',
        },
      ],
    },
    options: {
      ...SHARED_OPTS,
      indexAxis: 'y',
      scales: {
        x: {
          ...SHARED_OPTS.scales.x,
          type: 'logarithmic',
          title: { display: true, text: 'Rows per second (log scale)', color: '#475569' },
        },
        y: { ...SHARED_OPTS.scales.y, stacked: true, grid: { display: false } },
      },
    },
  });
}

function renderRuleComplexity() {
  new Chart(document.getElementById('ruleComplexityChart'), {
    type: 'bar',
    data: {
      labels: ['10 × G.1X', '25 × G.1X', '50 × G.1X', '50 × G.2X', '100 × G.2X'],
      datasets: [
        {
          label: '1B rows × 12 complex rules',
          data: [4.0, 1.5, 0.75, 0.5, 0.25],
          backgroundColor: COLORS.accent,
          borderRadius: 6,
        },
        {
          label: '1B rows × 30 SQL rules',
          data: [5.1, 2.0, 1.0, 0.66, 0.33],
          backgroundColor: COLORS.primary,
          borderRadius: 6,
        },
      ],
    },
    options: {
      ...SHARED_OPTS,
      scales: {
        ...SHARED_OPTS.scales,
        y: {
          ...SHARED_OPTS.scales.y,
          beginAtZero: true,
          title: { display: true, text: 'Minutes (lower is better)', color: '#475569' },
        },
      },
    },
  });
}

/* ============================================================
 * Live ecosystem stats (PyPI + GitHub)
 * Renders on compare.html. Graceful fallback when APIs fail.
 * ============================================================ */

async function loadLiveEcosystemStats() {
  // Fallback values used if network calls fail. Kept conservative so we never
  // invent numbers; they mirror the last-known-good snapshot.
  const FALLBACK = {
    srulesMonth: '—',
    srulesWeek: '—',
    nativeMonth: '—',
    nativeWeek: '—',
    ghStars: '—',
    ghForks: '—',
    srulesVersion: '1.2.0',
    nativeVersion: '0.1.0',
  };

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };

  const fmt = (n) => {
    if (typeof n !== 'number' || !isFinite(n)) return '—';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return n.toLocaleString();
  };

  // Paint fallbacks immediately so the page is never blank.
  setText('stat-srules-month', FALLBACK.srulesMonth);
  setText('stat-srules-week', FALLBACK.srulesWeek);
  setText('stat-native-month', FALLBACK.nativeMonth);
  setText('stat-native-week', FALLBACK.nativeWeek);
  setText('stat-gh-stars', FALLBACK.ghStars);
  setText('stat-gh-forks', FALLBACK.ghForks);
  setText('stat-srules-version', FALLBACK.srulesVersion);
  setText('stat-native-version', FALLBACK.nativeVersion);

  // pypistats recent downloads
  const fetchRecent = async (pkg) => {
    try {
      const r = await fetch(`https://pypistats.org/api/packages/${pkg}/recent`);
      if (!r.ok) throw new Error('bad status ' + r.status);
      const j = await r.json();
      return j.data || null;
    } catch (_) {
      return null;
    }
  };

  const [srulesRecent, nativeRecent] = await Promise.all([
    fetchRecent('sparkrules'),
    fetchRecent('sparkrules-native'),
  ]);

  if (srulesRecent) {
    setText('stat-srules-month', fmt(srulesRecent.last_month));
    setText('stat-srules-week', fmt(srulesRecent.last_week));
  }
  if (nativeRecent) {
    setText('stat-native-month', fmt(nativeRecent.last_month));
    setText('stat-native-week', fmt(nativeRecent.last_week));
  }

  // PyPI version via pypi.org JSON API
  const fetchVersion = async (pkg) => {
    try {
      const r = await fetch(`https://pypi.org/pypi/${pkg}/json`);
      if (!r.ok) throw new Error('bad status ' + r.status);
      const j = await r.json();
      return j.info && j.info.version;
    } catch (_) {
      return null;
    }
  };

  const [srulesVer, nativeVer] = await Promise.all([
    fetchVersion('sparkrules'),
    fetchVersion('sparkrules-native'),
  ]);
  if (srulesVer) setText('stat-srules-version', 'v' + srulesVer);
  if (nativeVer) setText('stat-native-version', 'v' + nativeVer);

  // GitHub repo stats
  try {
    const r = await fetch('https://api.github.com/repos/vaquarkhan/sparkrules');
    if (r.ok) {
      const j = await r.json();
      if (typeof j.stargazers_count === 'number') setText('stat-gh-stars', fmt(j.stargazers_count));
      if (typeof j.forks_count === 'number') setText('stat-gh-forks', fmt(j.forks_count));
    }
  } catch (_) { /* keep fallback */ }

  // Daily download trend (last 180 days)
  const fetchDaily = async (pkg) => {
    try {
      const r = await fetch(`https://pypistats.org/api/packages/${pkg}/overall?mirrors=true`);
      if (!r.ok) throw new Error('bad status ' + r.status);
      const j = await r.json();
      return j.data || [];
    } catch (_) {
      return [];
    }
  };

  const [srulesDaily, nativeDaily] = await Promise.all([
    fetchDaily('sparkrules'),
    fetchDaily('sparkrules-native'),
  ]);

  renderPypiTrend(srulesDaily, nativeDaily);
}

function renderPypiTrend(srulesDaily, nativeDaily) {
  const canvas = document.getElementById('pypiTrendChart');
  const fallback = document.getElementById('pypiTrendFallback');
  if (!canvas) return;

  // pypistats returns rows per category ("with_mirrors" and "without_mirrors").
  // We reduce to a single series per package by summing "without_mirrors" per date.
  const toDailySeries = (rows) => {
    if (!rows || !rows.length) return { labels: [], values: [] };
    const byDate = {};
    for (const row of rows) {
      if (row.category !== 'without_mirrors') continue;
      byDate[row.date] = (byDate[row.date] || 0) + (row.downloads || 0);
    }
    const sortedDates = Object.keys(byDate).sort();
    // Cap to last 180 points so the chart stays readable
    const tail = sortedDates.slice(-180);
    return {
      labels: tail,
      values: tail.map((d) => byDate[d]),
    };
  };

  const srulesSeries = toDailySeries(srulesDaily);
  const nativeSeries = toDailySeries(nativeDaily);

  if (srulesSeries.labels.length === 0 && nativeSeries.labels.length === 0) {
    canvas.classList.add('hidden');
    if (fallback) fallback.classList.remove('hidden');
    return;
  }

  // Align both series on sparkrules' label set (primary package)
  const labels = srulesSeries.labels.length ? srulesSeries.labels : nativeSeries.labels;
  const nativeByDate = {};
  nativeSeries.labels.forEach((d, i) => { nativeByDate[d] = nativeSeries.values[i]; });
  const nativeAligned = labels.map((d) => nativeByDate[d] || 0);

  new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'sparkrules',
          data: srulesSeries.values.length ? srulesSeries.values : labels.map(() => 0),
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99, 102, 241, 0.15)',
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0.25,
          fill: true,
        },
        {
          label: 'sparkrules-native',
          data: nativeAligned,
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.15)',
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0.25,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0f172a',
          titleColor: '#f8fafc',
          bodyColor: '#cbd5e1',
          borderColor: '#334155',
          borderWidth: 1,
          padding: 12,
          cornerRadius: 8,
          callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()} dl` },
        },
      },
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: '#94a3b8',
            font: { family: 'Inter', size: 10 },
            maxTicksLimit: 8,
            autoSkip: true,
          },
        },
        y: {
          grid: { color: 'rgba(148, 163, 184, 0.12)' },
          ticks: {
            color: '#94a3b8',
            font: { family: 'Inter', size: 10 },
            callback: (v) => v >= 1000 ? (v / 1000).toFixed(1) + 'K' : v,
          },
          beginAtZero: true,
        },
      },
    },
  });
}

/* ============================================================
 * Competitive charts on compare.html
 * ============================================================ */

function renderEngineLatency() {
  new Chart(document.getElementById('engineLatencyChart'), {
    type: 'bar',
    data: {
      labels: [
        'sparkrules · 100 × G.1X',
        'sparkrules · 50 × G.1X',
        'sparkrules · 25 × G.1X',
        'IBM ODM (8-core)',
        'FICO Blaze (8-core)',
        'Drools single-JVM',
        'Camunda DMN',
      ],
      datasets: [
        {
          label: '1B rows wallclock (minutes)',
          data: [5.1, 10.2, 20, 30, 35, 45, 60],
          backgroundColor: [
            COLORS.primary, COLORS.primary, COLORS.primary,
            COLORS.slate, COLORS.slate, COLORS.slate, COLORS.slate,
          ],
          borderRadius: 6,
        },
      ],
    },
    options: {
      ...SHARED_OPTS,
      indexAxis: 'y',
      plugins: {
        ...SHARED_OPTS.plugins,
        legend: { display: false },
        tooltip: {
          ...SHARED_OPTS.plugins.tooltip,
          callbacks: { label: (ctx) => `${ctx.parsed.x.toFixed(1)} min for 1B rows` },
        },
      },
      scales: {
        x: {
          ...SHARED_OPTS.scales.x,
          beginAtZero: true,
          title: { display: true, text: 'Wallclock minutes (log scale)', color: '#475569' },
          type: 'logarithmic',
        },
        y: { ...SHARED_OPTS.scales.y, grid: { display: false } },
      },
    },
  });
}

function renderRowsPerDollar() {
  // Rows scored per USD of infrastructure cost (higher = better)
  // sparkrules: ~3.57B rows/$ (1B rows / $0.28)
  // Drools-on-Spark antipattern: ~0.1B rows/$ (manual sharding overhead)
  // IBM ODM: hard to express per-row cost due to license; normalized here to public benchmarks
  new Chart(document.getElementById('rowsPerDollarChart'), {
    type: 'bar',
    data: {
      labels: [
        'sparkrules (25 × G.1X)',
        'Hand-written Spark SQL',
        'sparkrules (100 × G.2X)',
        'Drools-on-Spark (antipattern)',
        'Camunda DMN',
        'IBM ODM',
        'FICO Blaze',
      ],
      datasets: [
        {
          label: 'Million rows per USD',
          data: [3571, 5000, 581, 100, 40, 20, 10],
          backgroundColor: [
            COLORS.primary, COLORS.slate, COLORS.primary,
            COLORS.rose, COLORS.amber, COLORS.amber, COLORS.amber,
          ],
          borderRadius: 6,
        },
      ],
    },
    options: {
      ...SHARED_OPTS,
      indexAxis: 'y',
      plugins: {
        ...SHARED_OPTS.plugins,
        legend: { display: false },
        tooltip: {
          ...SHARED_OPTS.plugins.tooltip,
          callbacks: {
            label: (ctx) => `${ctx.parsed.x.toLocaleString()} M rows / $1 infra`,
          },
        },
      },
      scales: {
        x: {
          ...SHARED_OPTS.scales.x,
          type: 'logarithmic',
          title: { display: true, text: 'Million rows per $1 (log scale)', color: '#475569' },
        },
        y: { ...SHARED_OPTS.scales.y, grid: { display: false } },
      },
    },
  });
}
