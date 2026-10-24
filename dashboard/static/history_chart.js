(function () {
  const section = document.createElement('section');
  section.id = 'history-chart';
  section.className = 'panel history-panel';
  section.innerHTML =
    '<h2 class="history-title">CPU &amp; RAM, last 10 minutes</h2>' +
    '<canvas id="cpuRamChart" height="110"></canvas>';
  (document.querySelector('main.dashboard') || document.body).appendChild(section);

  const chart = new Chart(document.getElementById('cpuRamChart'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'CPU %', data: [], borderColor: '#88c0d0', backgroundColor: '#88c0d0', borderWidth: 2, pointRadius: 0, tension: 0.25 },
        { label: 'RAM %', data: [], borderColor: '#a3be8c', backgroundColor: '#a3be8c', borderWidth: 2, pointRadius: 0, tension: 0.25 }
      ]
    },
    options: {
      animation: false,
      responsive: true,
      scales: {
        x: { ticks: { color: '#d8dee9', maxTicksLimit: 8 }, grid: { color: '#4c566a' } },
        y: { min: 0, max: 20, ticks: { color: '#d8dee9' }, grid: { color: '#4c566a' } }
      },
      plugins: { legend: { labels: { color: '#d8dee9' } } }
    }
  });

  async function refresh() {
    try {
      const res = await fetch('/api/samples?minutes=10');
      const body = await res.json();
      const rows = Array.isArray(body) ? body : (body.samples || body.data || []);
      chart.data.labels = rows.map(r => String(r.timestamp).slice(11, 19));
      chart.data.datasets[0].data = rows.map(r => r.cpu_percent);
      chart.data.datasets[1].data = rows.map(r => r.ram_percent);
      const vals = chart.data.datasets[0].data.concat(chart.data.datasets[1].data).filter(v => typeof v === 'number');
    const peak = vals.length ? Math.max(...vals) : 0;
    chart.options.scales.y.max = Math.min(100, Math.max(10, Math.ceil(peak * 1.3 / 5) * 5));
    chart.update('none');
    } catch (e) {
      console.error('chart refresh failed', e);
    }
  }

  refresh();
  setInterval(refresh, 5000);
})();
