/* app.js — CupCast frontend
 * Fetches predictions.json, backtest.json y track_record.json y renderiza la UI.
 * Sin dependencias externas.
 */

// ── Banderas (flagcdn.com, sin descarga local) ────────────────────────────────

const TEAM_FLAGS = {
  // Grupos WC 2026
  Mexico: 'mx', 'South Africa': 'za', 'South Korea': 'kr', Czechia: 'cz',
  Canada: 'ca', 'Bosnia and Herzegovina': 'ba', Qatar: 'qa', Switzerland: 'ch',
  Brazil: 'br', Morocco: 'ma', Haiti: 'ht', Scotland: 'gb-sct',
  USA: 'us', Paraguay: 'py', Australia: 'au', Turkey: 'tr',
  Germany: 'de', 'Curaçao': 'cw', "Côte d'Ivoire": 'ci', Ecuador: 'ec',
  Netherlands: 'nl', Japan: 'jp', Sweden: 'se', Tunisia: 'tn',
  Belgium: 'be', Egypt: 'eg', Iran: 'ir', 'New Zealand': 'nz',
  Spain: 'es', 'Cape Verde': 'cv', 'Saudi Arabia': 'sa', Uruguay: 'uy',
  France: 'fr', Senegal: 'sn', Iraq: 'iq', Norway: 'no',
  Argentina: 'ar', Algeria: 'dz', Austria: 'at', Jordan: 'jo',
  Portugal: 'pt', 'DR Congo': 'cd', Uzbekistan: 'uz', Colombia: 'co',
  England: 'gb-eng', Croatia: 'hr', Ghana: 'gh', Panama: 'pa',
};

function flagImg(team, displaySize = 20) {
  const code = TEAM_FLAGS[team];
  if (!code) return null;
  const img = document.createElement('img');
  img.src = `https://flagcdn.com/w20/${code}.png`;
  img.alt = team;
  img.width = displaySize;
  img.height = Math.round(displaySize * 0.75);
  img.style.cssText = 'vertical-align:middle;margin-right:5px;border-radius:2px;';
  return img;
}

// ── Utilidades ────────────────────────────────────────────────────────────────

function pct(v) { return (v * 100).toFixed(1) + '%'; }

function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' });
}

function fmtDatetime(iso) {
  const d = new Date(iso);
  const local = d.toLocaleString('es-ES', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
  const utcTime = d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' });
  return `${local} (${utcTime} UTC)`;
}

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (k === 'className') e.className = v;
    else if (k === 'html') e.innerHTML = v;
    else e.setAttribute(k, v);
  });
  children.forEach(c => c && e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
  return e;
}

// ── Colores por grupo ─────────────────────────────────────────────────────────

const GROUP_COLORS = {
  A: '#1d4ed8', B: '#7c3aed', C: '#db2777', D: '#dc2626',
  E: '#ea580c', F: '#d97706', G: '#65a30d', H: '#16a34a',
  I: '#0891b2', J: '#0e7490', K: '#6d28d9', L: '#be185d',
};

// ── Favoritos ─────────────────────────────────────────────────────────────────

function renderFavoritos(favoritos) {
  const container = document.getElementById('favoritos-grid');
  const maxP = favoritos[0]?.prob_campeon || 1;

  favoritos.slice(0, 20).forEach((f, i) => {
    const barPct = (f.prob_campeon / maxP * 100).toFixed(1);
    const rankEl = el('span', { className: 'favorito-rank' + (i < 3 ? ' top3' : '') }, String(i + 1));
    const bar = el('div', { className: 'favorito-bar-track' },
      el('div', { className: 'favorito-bar-fill', style: `width:${barPct}%` })
    );
    const teamSpan = el('span', { className: 'favorito-team' });
    const flag = flagImg(f.equipo, 20);
    if (flag) teamSpan.appendChild(flag);
    teamSpan.appendChild(document.createTextNode(f.equipo));
    const inner = el('div', { className: 'favorito-inner' }, teamSpan, bar);
    const prob = el('span', { className: 'favorito-prob' }, pct(f.prob_campeon));
    container.appendChild(el('div', { className: 'favorito-row' }, rankEl, inner, prob));
  });
}

// ── Próximos partidos ─────────────────────────────────────────────────────────

function renderPartidos(partidos) {
  const container = document.getElementById('partidos-container');
  if (!partidos.length) {
    container.appendChild(el('p', { className: 'section-note' }, 'No hay partidos pendientes.'));
    return;
  }

  // Agrupar por fecha
  const byDate = {};
  partidos.forEach(m => {
    const day = m.fecha.slice(0, 10);
    if (!byDate[day]) byDate[day] = [];
    byDate[day].push(m);
  });

  // ── Barra de filtros ──────────────────────────────────────────────────────
  const grupos = [...new Set(partidos.filter(m => m.grupo).map(m => m.grupo))].sort();
  if (grupos.length) {
    const bar = el('div', { className: 'filtro-bar' });

    const mkBtn = (label, filtro, color) => {
      const btn = el('button', { className: 'filtro-btn', 'data-filtro': filtro }, label);
      if (color) btn.style.setProperty('--filtro-color', color);
      btn.addEventListener('click', () => {
        bar.querySelectorAll('.filtro-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        container.querySelectorAll('.match-card').forEach(c => {
          c.style.display = (filtro === 'Todos' || c.dataset.group === filtro) ? '' : 'none';
        });
        container.querySelectorAll('.jornada-group').forEach(g => {
          const visible = [...g.querySelectorAll('.match-card')].some(c => c.style.display !== 'none');
          g.style.display = visible ? '' : 'none';
        });
      });
      return btn;
    };

    bar.appendChild(mkBtn('Todos', 'Todos', null));
    grupos.forEach(g => bar.appendChild(mkBtn('Grupo ' + g, g, GROUP_COLORS[g])));

    bar.querySelector('.filtro-btn').classList.add('active'); // "Todos" activo por defecto
    container.appendChild(bar);
  }

  // ── Partidos agrupados por fecha ──────────────────────────────────────────
  Object.entries(byDate).sort(([a], [b]) => a.localeCompare(b)).forEach(([day, matches]) => {
    matches.sort((a, b) => a.fecha.localeCompare(b.fecha));
    const group = el('div', { className: 'jornada-group' });
    const sample = matches[0];
    const label = `${fmtDate(day)} · ${sample.fase}`;
    group.appendChild(el('div', { className: 'jornada-label' }, label));

    matches.forEach(m => {
      const ph  = (m.prob_local * 100).toFixed(0);
      const pd  = (m.prob_empate * 100).toFixed(0);
      const pa  = (m.prob_visitante * 100).toFixed(0);
      const phe = (m.prob_local_elo * 100).toFixed(0);
      const pde = (m.prob_empate_elo * 100).toFixed(0);
      const pae = (m.prob_visitante_elo * 100).toFixed(0);

      const teamsSpan = el('span', { className: 'match-teams' });
      const flagH = flagImg(m.local, 20);
      const flagA = flagImg(m.visitante, 20);
      if (flagH) teamsSpan.appendChild(flagH);
      teamsSpan.appendChild(document.createTextNode(m.local + ' vs '));
      if (flagA) teamsSpan.appendChild(flagA);
      teamsSpan.appendChild(document.createTextNode(m.visitante));

      const d = new Date(m.fecha);
      const localTime = d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
      const utcTime   = d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' });
      const matchRight = el('div', { className: 'match-right' });
      if (m.grupo) {
        const badge = el('span', { className: 'group-badge' }, 'Grupo ' + m.grupo);
        badge.style.background = GROUP_COLORS[m.grupo] || 'var(--primary)';
        matchRight.appendChild(badge);
      }
      matchRight.appendChild(el('span', { className: 'match-meta' }, `${localTime} (${utcTime} UTC)`));

      const header = el('div', { className: 'match-header' }, teamsSpan, matchRight);

      const labelDC  = el('div', { className: 'prob-label' }, 'Forma reciente');
      const barDC    = el('div', { className: 'prob-bar' },
        el('div', { className: 'prob-home', style: `width:${ph}%` }, ph + '%'),
        el('div', { className: 'prob-draw', style: `width:${pd}%` }, pd + '%'),
        el('div', { className: 'prob-away', style: `width:${pa}%` }, pa + '%'),
      );
      const labelElo = el('div', { className: 'prob-label' }, 'Historial y reputación');
      const barElo   = el('div', { className: 'prob-bar prob-bar-secondary' },
        el('div', { className: 'prob-home', style: `width:${phe}%` }, phe + '%'),
        el('div', { className: 'prob-draw', style: `width:${pde}%` }, pde + '%'),
        el('div', { className: 'prob-away', style: `width:${pae}%` }, pae + '%'),
      );

      const detailTeams = el('span');
      const fDH = flagImg(m.local, 16); const fDA = flagImg(m.visitante, 16);
      if (fDH) detailTeams.appendChild(fDH);
      detailTeams.appendChild(document.createTextNode(m.local + ' · Empate · '));
      if (fDA) detailTeams.appendChild(fDA);
      detailTeams.appendChild(document.createTextNode(m.visitante));

      const details = el('div', { className: 'match-details' },
        el('span', {}, 'Marcador probable: ', el('span', { className: 'score-badge' }, m.marcador_probable || '—')),
        detailTeams,
      );

      const note = el('div', { className: 'match-note', html: buildExplanationText(m) });

      const card = el('div', { className: 'match-card' },
        header, labelDC, barDC, labelElo, barElo, details, note
      );
      if (m.grupo) card.dataset.group = m.grupo;
      group.appendChild(card);
    });

    container.appendChild(group);
  });
}

// ── Track record ──────────────────────────────────────────────────────────────

function renderTrackRecord(tr) {
  document.getElementById('sec-track').classList.remove('hidden');
  const ag = tr.agregados;

  // Métricas
  const grid = document.getElementById('track-metricas');
  const dcBetter = ag.baseline_log_loss !== undefined && ag.log_loss < ag.baseline_log_loss;
  const metrics = [
    { label: 'Log-loss', val: ag.log_loss.toFixed(4),  sub: ag.baseline_log_loss ? `Elo: ${ag.baseline_log_loss.toFixed(4)}` : '', better: dcBetter },
    { label: 'Brier',    val: ag.brier.toFixed(4),     sub: ag.baseline_brier    ? `Elo: ${ag.baseline_brier.toFixed(4)}`    : '', better: dcBetter },
    { label: 'Hit rate', val: pct(ag.hit_rate),         sub: 'outcome más probable', better: null },
    { label: 'Partidos', val: tr.metadata.partidos_resueltos, sub: 'resueltos', better: null },
  ];
  metrics.forEach(m => {
    const cls = m.better === true ? 'metrica-better' : m.better === false ? 'metrica-worse' : '';
    grid.appendChild(el('div', { className: 'metrica-card' },
      el('div', { className: 'metrica-label' }, m.label),
      el('div', { className: `metrica-val ${cls}` }, String(m.val)),
      el('div', { className: 'metrica-sub' }, m.sub),
    ));
  });

  // Calibración
  if (tr.calibracion?.length) {
    document.getElementById('track-calibracion').appendChild(
      renderCalibration(tr.calibracion, 'Calibración (predicho vs observado)')
    );
  }

  // Tabla de partidos
  const tabla = el('table', { className: 'track-table' });
  tabla.appendChild(el('thead', {},
    el('tr', {},
      el('th', {}, 'Partido'),
      el('th', {}, 'Probabilidades'),
      el('th', {}, 'Resultado'),
      el('th', {}, 'Brier'),
    )
  ));
  const tbody = el('tbody');

  // Ordenar por fecha descendente (más reciente primero)
  const partidos = [...tr.partidos].sort((a, b) => b.fecha.localeCompare(a.fecha));

  partidos.forEach(p => {
    const phome = (p.prob_local * 100).toFixed(0);
    const pdraw = (p.prob_empate * 100).toFixed(0);
    const paway = (p.prob_visitante * 100).toFixed(0);
    const probStr = `${phome}% / ${pdraw}% / ${paway}%`;

    const winnerLabel = { local: p.local, empate: 'Empate', visitante: p.visitante }[p.ganador];
    const winnerCls   = p.acertado ? 'tag-win' : 'tag-loss';

    const matchTd = el('td');
    const fTH = flagImg(p.local, 16); const fTA = flagImg(p.visitante, 16);
    if (fTH) matchTd.appendChild(fTH);
    matchTd.appendChild(document.createTextNode(p.local + ' vs '));
    if (fTA) matchTd.appendChild(fTA);
    matchTd.appendChild(document.createTextNode(p.visitante + (p.sorpresa ? ' ⚡' : '')));

    const row = el('tr', { className: p.sorpresa ? 'sorpresa' : '' },
      matchTd,
      el('td', {}, probStr),
      el('td', { className: winnerCls }, `${winnerLabel}  ${p.resultado}`),
      el('td', {}, p.brier.toFixed(3)),
    );
    tbody.appendChild(row);
  });

  tabla.appendChild(tbody);
  document.getElementById('track-tabla').appendChild(tabla);
}

// ── Backtest ──────────────────────────────────────────────────────────────────

function renderBacktest(bt) {
  // Tabla por torneo
  const tabla = el('table', { className: 'backtest-table' });
  tabla.appendChild(el('thead', {},
    el('tr', {},
      el('th', {}, 'Torneo'),
      el('th', {}, 'Partidos'),
      el('th', {}, 'DC Log-loss'),
      el('th', {}, 'Elo Log-loss'),
      el('th', {}, 'DC Brier'),
      el('th', {}, 'Elo Brier'),
    )
  ));
  const tbody = el('tbody');

  bt.por_torneo.forEach(t => {
    const dcWinsLL = t.log_loss < t.baseline_log_loss;
    const dcWinsB  = t.brier < t.baseline_brier;
    tbody.appendChild(el('tr', {},
      el('td', {}, t.torneo),
      el('td', {}, t.n_partidos),
      el('td', { className: dcWinsLL ? 'cell-better' : '' }, t.log_loss.toFixed(4)),
      el('td', { className: !dcWinsLL ? 'cell-better' : '' }, t.baseline_log_loss.toFixed(4)),
      el('td', { className: dcWinsB ? 'cell-better' : '' }, t.brier.toFixed(4)),
      el('td', { className: !dcWinsB ? 'cell-better' : '' }, t.baseline_brier.toFixed(4)),
    ));
  });

  // Fila global
  const g = bt.global;
  const dcWinsLL = g.log_loss < g.baseline_log_loss;
  const dcWinsB  = g.brier < g.baseline_brier;
  tbody.appendChild(el('tr', { className: 'global-row' },
    el('td', {}, `Global (${g.n_partidos} partidos)`),
    el('td', {}, ''),
    el('td', { className: dcWinsLL ? 'cell-better' : '' }, g.log_loss.toFixed(4)),
    el('td', { className: !dcWinsLL ? 'cell-better' : '' }, g.baseline_log_loss.toFixed(4)),
    el('td', { className: dcWinsB ? 'cell-better' : '' }, g.brier.toFixed(4)),
    el('td', { className: !dcWinsB ? 'cell-better' : '' }, g.baseline_brier.toFixed(4)),
  ));

  tabla.appendChild(tbody);
  document.getElementById('backtest-tabla').appendChild(tabla);

  // Calibración
  if (bt.calibracion?.length) {
    document.getElementById('backtest-calibracion').appendChild(
      renderCalibration(bt.calibracion, 'Calibración global (4 Mundiales, predicho vs observado)')
    );
  }
}

// ── Calibración SVG ───────────────────────────────────────────────────────────

function renderCalibration(buckets, title) {
  const W = 260, H = 220, PAD = 36;
  const IW = W - PAD * 2, IH = H - PAD * 2;

  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('class', 'calib-svg');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', title);

  function tx(p) { return PAD + p * IW; }
  function ty(p) { return PAD + (1 - p) * IH; }

  // Línea de referencia (calibración perfecta)
  const ref = document.createElementNS(ns, 'line');
  ref.setAttribute('x1', tx(0)); ref.setAttribute('y1', ty(0));
  ref.setAttribute('x2', tx(1)); ref.setAttribute('y2', ty(1));
  ref.setAttribute('stroke', '#d1d5db'); ref.setAttribute('stroke-width', '1');
  ref.setAttribute('stroke-dasharray', '4 3');
  svg.appendChild(ref);

  // Ejes
  ['0', '0.25', '0.5', '0.75', '1'].forEach(v => {
    const fv = parseFloat(v);
    // X tick
    const xt = document.createElementNS(ns, 'text');
    xt.setAttribute('x', tx(fv)); xt.setAttribute('y', H - 6);
    xt.setAttribute('text-anchor', 'middle'); xt.setAttribute('font-size', '9');
    xt.setAttribute('fill', '#9ca3af'); xt.textContent = v;
    svg.appendChild(xt);
    // Y tick
    const yt = document.createElementNS(ns, 'text');
    yt.setAttribute('x', PAD - 6); yt.setAttribute('y', ty(fv) + 3);
    yt.setAttribute('text-anchor', 'end'); yt.setAttribute('font-size', '9');
    yt.setAttribute('fill', '#9ca3af'); yt.textContent = v;
    svg.appendChild(yt);
  });

  // Puntos por bucket
  buckets.forEach(b => {
    const cx = tx(b.predicho), cy = ty(b.observado);
    const r = Math.max(3, Math.min(8, Math.sqrt(b.n / 8)));

    const circle = document.createElementNS(ns, 'circle');
    circle.setAttribute('cx', cx); circle.setAttribute('cy', cy);
    circle.setAttribute('r', r);
    circle.setAttribute('fill', '#1d4ed8'); circle.setAttribute('opacity', '0.75');

    const t = document.createElementNS(ns, 'title');
    t.textContent = `pred ${b.predicho} → obs ${b.observado} (n=${b.n})`;
    circle.appendChild(t);
    svg.appendChild(circle);
  });

  // Etiqueta eje X
  const xl = document.createElementNS(ns, 'text');
  xl.setAttribute('x', W / 2); xl.setAttribute('y', H - 1);
  xl.setAttribute('text-anchor', 'middle'); xl.setAttribute('font-size', '9');
  xl.setAttribute('fill', '#6b7280'); xl.textContent = 'Probabilidad predicha';
  svg.appendChild(xl);

  const wrap = el('div', { className: 'calib-wrap' },
    el('div', { className: 'calib-title' }, title)
  );
  wrap.appendChild(svg);
  return wrap;
}

// ── Texto explicativo de la predicción ───────────────────────────────────────

function buildExplanationText(m) {
  const dcHome = m.prob_local, dcAway = m.prob_visitante;
  const elHome = m.prob_local_elo, elAway = m.prob_visitante_elo;

  const dcFavor  = dcHome > dcAway + 0.04 ? m.local  : dcAway > dcHome + 0.04 ? m.visitante  : null;
  const eloFavor = elHome > elAway + 0.04 ? m.local  : elAway > elHome + 0.04 ? m.visitante  : null;

  const dcGap  = Math.abs(dcHome - dcAway);
  const eloGap = Math.abs(elHome - elAway);
  const divergence = Math.abs(dcHome - elHome) + Math.abs(dcAway - elAway);

  if (dcFavor === eloFavor) {
    const team = dcFavor;
    if (!team) return 'Las dos perspectivas ven el partido muy igualado. Cualquier resultado es posible.';
    if (dcGap > 0.2 && eloGap > 0.2)
      return `<strong>${team}</strong> es el favorito claro según ambas perspectivas: la forma reciente y el historial apuntan en la misma dirección.`;
    return `Las dos perspectivas dan ventaja a <strong>${team}</strong>, aunque el partido sigue siendo competido.`;
  }

  const formTeam = dcFavor  || 'ningún equipo';
  const histTeam = eloFavor || 'ningún equipo';

  if (divergence > 0.2) {
    return `Los modelos discrepan: la forma reciente favorece a <strong>${formTeam}</strong>, mientras que el historial da ventaja a <strong>${histTeam}</strong>. Mayor incertidumbre de lo habitual.`;
  }
  return `Ligera discrepancia: la forma reciente apunta a <strong>${formTeam}</strong> y el historial a <strong>${histTeam}</strong>.`;
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

Promise.all([
  fetch('./predictions.json').then(r => r.ok ? r.json() : null).catch(() => null),
  fetch('./backtest.json').then(r => r.ok ? r.json() : null).catch(() => null),
  fetch('./track_record.json').then(r => r.ok ? r.json() : null).catch(() => null),
]).then(([predictions, backtest, trackRecord]) => {

  document.getElementById('loading').remove();

  // Header timestamps
  if (predictions?.metadata) {
    const m = predictions.metadata;
    if (m.generado)        document.getElementById('updated').textContent  = 'Actualizado: ' + fmtDatetime(m.generado);
    if (m.entrenado_hasta) document.getElementById('trained').textContent  = `Datos: resultados int. 1872–${m.entrenado_hasta} (~49.000 partidos)`;
    const faseStr = m.fase_actual ? `Fase: ${m.fase_actual}` : '';
    const modelStr = ' · Modelos: forma reciente + historial';
    if (faseStr) document.getElementById('data-fase').textContent = faseStr + modelStr;
  }

  if (predictions?.favoritos?.length)       renderFavoritos(predictions.favoritos);
  if (predictions?.proximos_partidos?.length) renderPartidos(predictions.proximos_partidos);

  if (trackRecord?.metadata?.partidos_resueltos > 0) renderTrackRecord(trackRecord);

  if (backtest?.por_torneo?.length) renderBacktest(backtest);

}).catch(err => {
  console.error('Error cargando datos:', err);
  const l = document.getElementById('loading');
  if (l) { l.textContent = 'Error cargando los datos. Recarga la página.'; l.style.cssText = 'color:#dc2626'; }
});
