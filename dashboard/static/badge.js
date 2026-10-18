(function () {
  const style = document.createElement('style');
  style.textContent = `
    #health-badge{position:sticky;top:0;z-index:1000;display:flex;align-items:center;gap:12px;
      padding:10px 20px;font-weight:600;letter-spacing:.06em;background:#3B4252;color:#ECEFF4;
      border-bottom:3px solid #4C566A;transition:border-color .3s}
    #health-badge .dot{width:14px;height:14px;border-radius:50%;background:#4C566A;transition:background .3s}
    #health-badge .reason{font-weight:400;opacity:.8;font-size:.9em}
    #health-badge.ok{border-bottom-color:#A3BE8C}      #health-badge.ok .dot{background:#A3BE8C}
    #health-badge.warning{border-bottom-color:#EBCB8B} #health-badge.warning .dot{background:#EBCB8B}
    #health-badge.critical{border-bottom-color:#BF616A}#health-badge.critical .dot{background:#BF616A}
  `;
  document.head.appendChild(style);

  const badge = document.createElement('div');
  badge.id = 'health-badge';
  badge.innerHTML = '<span class="dot"></span><span class="label">SYSTEM: ...</span><span class="reason"></span>';
  document.body.insertBefore(badge, document.body.firstChild);

  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(url);
    return r.json();
  }

  function setState(cls, label, reason) {
    badge.className = cls;
    badge.querySelector('.label').textContent = 'SYSTEM: ' + label;
    badge.querySelector('.reason').textContent = reason;
  }

  async function update() {
    try {
      const [latestRaw, alertsRaw] = await Promise.all([
        getJSON('/api/latest'), getJSON('/api/alerts?limit=20')
      ]);
      const s = latestRaw.sample || latestRaw;
      const cpu = Number(s.cpu_percent), ram = Number(s.ram_percent);
      const alerts = Array.isArray(alertsRaw) ? alertsRaw : (alertsRaw.alerts || []);
      const now = Date.now();
      const recent = alerts.filter(a => {
        const t = Date.parse(String(a.timestamp || a.time || a.ts || '').replace(' ', 'T'));
        return !isNaN(t) && now - t < 120000;
      });
      const high = recent.some(a => /HIGH|CRIT/.test(String(a.severity || a.level || '').toUpperCase()));

      const reasons = [];
      let level = 0;
      if (cpu >= 90 || ram >= 90 || high) level = 2;
      else if (cpu >= 70 || ram >= 80 || recent.length > 0) level = 1;
      if (cpu >= 70) reasons.push('CPU ' + cpu.toFixed(0) + '%');
      if (ram >= 80) reasons.push('RAM ' + ram.toFixed(0) + '%');
      if (recent.length) reasons.push(recent.length + ' alert(s) in last 2 min');

      if (level === 2) setState('critical', 'CRITICAL', reasons.join(' | '));
      else if (level === 1) setState('warning', 'WARNING', reasons.join(' | '));
      else setState('ok', 'OK', 'CPU ' + cpu.toFixed(0) + '% | RAM ' + ram.toFixed(0) + '%');
    } catch (e) {
      setState('', 'NO DATA', 'API not reachable');
    }
  }

  update();
  setInterval(update, 2000);
})();
