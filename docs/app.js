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
          if (visible) g.querySelector('.jornada-matches')?.classList.remove('collapsed');
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
  Object.entries(byDate).sort(([a], [b]) => a.localeCompare(b)).forEach(([day, matches], idx) => {
    matches.sort((a, b) => a.fecha.localeCompare(b.fecha));
    const group = el('div', { className: 'jornada-group' });
    const sample = matches[0];
    const label = `${fmtDate(day)} · ${sample.fase} · ${matches.length} partidos`;
    const isOpen = idx === 0;

    const matchesWrap = el('div', { className: 'jornada-matches' + (isOpen ? '' : ' collapsed') });

    const labelEl = el('div', { className: 'jornada-label' + (isOpen ? ' open' : '') },
      el('span', {}, label),
      el('span', { className: 'jornada-chevron' }, '›')
    );
    labelEl.addEventListener('click', () => {
      const open = !matchesWrap.classList.contains('collapsed');
      matchesWrap.classList.toggle('collapsed', open);
      labelEl.classList.toggle('open', !open);
    });
    group.appendChild(labelEl);

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

      const details = el('div', { className: 'match-details' },
        el('span', {}, 'Marcador probable: ', el('span', { className: 'score-badge' }, m.marcador_probable || '—')),
      );

      const note = el('div', { className: 'match-note', html: buildExplanationText(m) });

      const card = el('div', { className: 'match-card' },
        header, labelDC, barDC, labelElo, barElo, details, note
      );
      if (m.grupo) card.dataset.group = m.grupo;
      matchesWrap.appendChild(card);
    });

    group.appendChild(matchesWrap);
    container.appendChild(group);
  });
}

// ── Track record ──────────────────────────────────────────────────────────────

function renderTrackRecord(tr) {
  document.getElementById('sec-track').classList.remove('hidden');
  const ag = tr.agregados;

  // Métricas acumuladas
  const grid = document.getElementById('track-metricas');
  grid.appendChild(el('p', { className: 'metricas-header' },
    `Acumulado sobre ${tr.metadata.partidos_resueltos} partido${tr.metadata.partidos_resueltos !== 1 ? 's' : ''} resuelto${tr.metadata.partidos_resueltos !== 1 ? 's' : ''}. Menor error = mejor modelo.`
  ));

  const dcBetter = ag.baseline_log_loss !== undefined && ag.log_loss < ag.baseline_log_loss;
  const metrics = [
    {
      label: 'Error pred.', tooltip: 'Brier score acumulado: error cuadrático medio entre las probabilidades predichas y los resultados reales. 0 = perfecto · 2 = máximo error.',
      val: ag.brier.toFixed(4), sub: ag.baseline_brier ? `Histórico: ${ag.baseline_brier.toFixed(4)}` : '', better: dcBetter,
    },
    {
      label: 'Penalización', tooltip: 'Log-loss acumulado: penaliza las predicciones muy confiadas que resultaron erróneas. Referencia: ~1.10 = azar puro (33% a cada resultado), 0 = perfecto. Cuanto más bajo, mejor.',
      val: ag.log_loss.toFixed(4), sub: ag.baseline_log_loss ? `Histórico: ${ag.baseline_log_loss.toFixed(4)}` : '', better: dcBetter,
    },
    {
      label: 'Aciertos', tooltip: 'Hit rate: porcentaje de partidos en que el resultado más probable (local/empate/visitante) fue el correcto.',
      val: pct(ag.hit_rate), sub: 'resultado más probable', better: null,
    },
    {
      label: 'Partidos', tooltip: null,
      val: tr.metadata.partidos_resueltos, sub: 'resueltos', better: null,
    },
  ];
  metrics.forEach(m => {
    const cls = m.better === true ? 'metrica-better' : m.better === false ? 'metrica-worse' : '';
    const labelEl = m.tooltip
      ? el('div', { className: 'metrica-label th-tooltip', 'data-tooltip': m.tooltip }, m.label + ' ⓘ')
      : el('div', { className: 'metrica-label' }, m.label);
    grid.appendChild(el('div', { className: 'metrica-card' },
      labelEl,
      el('div', { className: `metrica-val ${cls}` }, String(m.val)),
      el('div', { className: 'metrica-sub' }, m.sub),
    ));
  });

  // Calibración
  if (tr.calibracion?.length) {
    document.getElementById('track-calibracion').appendChild(
      renderCalibration(tr.calibracion, 'Distribución de predicciones', tr.partidos)
    );
  }

  // Tabla de partidos agrupada por fase
  const FASE_ORDER = ['grupos', 'octavos', 'cuartos', 'semifinales', 'tercer_puesto', 'final'];
  const chronoIndex = {};
  [...tr.partidos]
    .sort((a, b) => a.fecha.localeCompare(b.fecha))
    .forEach((p, i) => { chronoIndex[p.id] = i + 1; });

  const byFase = {};
  [...tr.partidos]
    .sort((a, b) => b.fecha.localeCompare(a.fecha))
    .forEach(p => {
      const fase = p.fase || 'otros';
      if (!byFase[fase]) byFase[fase] = [];
      byFase[fase].push(p);
    });

  const fasesSorted = Object.keys(byFase).sort((a, b) => {
    const ia = FASE_ORDER.indexOf(a), ib = FASE_ORDER.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  const tabla = el('table', { className: 'track-table' });
  tabla.appendChild(el('thead', {},
    el('tr', {},
      el('th', {}),
      el('th', {}, 'Partido'),
      el('th', { className: 'col-hide-mobile' }, 'Probabilidades'),
      el('th', {}, 'Resultado'),
      el('th', { className: 'col-hide-mobile' }, el('span', { className: 'th-tooltip', 'data-tooltip': 'Brier score: error cuadrático entre las probabilidades predichas y el resultado real. 0 = predicción perfecta · 2 = máximo error.' }, 'Error pred. ⓘ')),
      el('th', {}),
    )
  ));

  fasesSorted.forEach(fase => {
    const matches = byFase[fase];
    const tbody = el('tbody');

    const headerRow = el('tr', { className: 'track-group-header' },
      el('td', { colspan: '6' },
        el('span', {}, `${fase.charAt(0).toUpperCase() + fase.slice(1)} · ${matches.length} partido${matches.length !== 1 ? 's' : ''}`),
        el('span', { className: 'jornada-chevron' }, '›'),
      )
    );
    headerRow.addEventListener('click', () => {
      const open = !tbody.classList.contains('collapsed');
      tbody.classList.toggle('collapsed', open);
      headerRow.classList.toggle('open', !open);
    });
    headerRow.classList.add('open');
    tbody.appendChild(headerRow);

    matches.forEach(p => {
      const phome = (p.prob_local * 100).toFixed(0);
      const pdraw = (p.prob_empate * 100).toFixed(0);
      const paway = (p.prob_visitante * 100).toFixed(0);
      const probStr = `${phome}% / ${pdraw}% / ${paway}%`;

      const winnerLabel = { local: p.local, empate: 'Empate', visitante: p.visitante }[p.ganador];
      const winnerCls   = p.acertado ? 'tag-win' : 'tag-loss';

      const matchTd = el('td', { className: 'match-td-stack' });
      const homeSpan = el('span', { className: 'match-team-line' });
      const fTH = flagImg(p.local, 14);
      if (fTH) homeSpan.appendChild(fTH);
      homeSpan.appendChild(document.createTextNode(p.local));
      const awaySpan = el('span', { className: 'match-team-line' });
      const fTA = flagImg(p.visitante, 14);
      if (fTA) awaySpan.appendChild(fTA);
      awaySpan.appendChild(document.createTextNode(p.visitante + (p.sorpresa ? ' ⚡' : '')));
      matchTd.appendChild(homeSpan);
      matchTd.appendChild(el('span', { className: 'match-vs' }, 'vs'));
      matchTd.appendChild(awaySpan);

      const infoBtn = el('button', { className: 'btn-info', title: 'Ver detalle' }, 'i');
      infoBtn.addEventListener('click', () => openMatchModal(p));
      tbody.appendChild(el('tr', { className: p.sorpresa ? 'sorpresa' : '' },
        el('td', { className: 'match-num' }, `#${chronoIndex[p.id]}`),
        matchTd,
        el('td', { className: 'col-hide-mobile' }, probStr),
        el('td', { className: winnerCls }, `${winnerLabel}  ${p.resultado}`),
        el('td', { className: 'col-hide-mobile' }, p.brier.toFixed(3)),
        el('td', { className: 'track-td-btn' }, infoBtn),
      ));
    });

    tabla.appendChild(tbody);
  });

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

// ── Gráficos (Chart.js) ───────────────────────────────────────────────────────

function buildCumulativeData(partidos) {
  const sorted = [...partidos].sort((a, b) => a.fecha.localeCompare(b.fecha));
  let aciertos = 0;
  return sorted.map((p, i) => {
    if (p.acertado) aciertos++;
    const d = new Date(p.fecha);
    const fecha = d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
    const shortHome = p.local.split(' ')[0];
    const shortAway = p.visitante.split(' ')[0];
    return {
      label: `${fecha}`,
      tooltip: `${fecha} · ${shortHome} vs ${shortAway} · ${p.acertado ? '✓ Acierto' : '✗ Fallo'} (${p.resultado})`,
      rate: +((aciertos / (i + 1)) * 100).toFixed(1),
    };
  });
}

let _calibChartId = 0;

function buildScatDataFromPartidos(partidos) {
  // Cada partido aporta 3 pares (probabilidad predicha, ¿ocurrió?)
  const pairs = [];
  partidos.forEach(p => {
    pairs.push({ prob: p.prob_local,     hit: p.ganador === 'local'     });
    pairs.push({ prob: p.prob_empate,    hit: p.ganador === 'empate'    });
    pairs.push({ prob: p.prob_visitante, hit: p.ganador === 'visitante' });
  });

  const bucketSize = 0.1;
  const buckets = [];
  for (let lo = 0; lo < 1; lo = +(lo + bucketSize).toFixed(1)) {
    const hi = +(lo + bucketSize).toFixed(1);
    const inRange = pairs.filter(p => p.prob >= lo && p.prob < hi);
    if (!inRange.length) continue;
    const predicho = inRange.reduce((s, p) => s + p.prob, 0) / inRange.length;
    const observado = inRange.filter(p => p.hit).length / inRange.length;
    buckets.push({ predicho: +predicho.toFixed(3), observado: +observado.toFixed(3), n: inRange.length });
  }
  return buckets;
}

function buildBarDataFromPartidos(partidos) {
  const ranges = [
    { label: '<40%', min: 0,    max: 0.40 },
    { label: '40–50%', min: 0.40, max: 0.50 },
    { label: '50–60%', min: 0.50, max: 0.60 },
    { label: '60–70%', min: 0.60, max: 0.70 },
    { label: '>70%',  min: 0.70, max: 1.01 },
  ];
  return ranges.map(r => {
    const inRange = partidos.filter(p => {
      const conf = Math.max(p.prob_local, p.prob_empate, p.prob_visitante);
      return conf >= r.min && conf < r.max;
    });
    return {
      label: r.label,
      total: inRange.length,
      aciertos: inRange.filter(p => p.acertado).length,
    };
  }).filter(r => r.total > 0);
}

function renderCalibration(buckets, title, partidos = null) {
  const uid = ++_calibChartId;

  const noteBar = el('p', { className: 'calib-note' },
    'Agrupa los partidos según la probabilidad más alta que el modelo asignó al resultado más probable (local, empate o visitante). ' +
    'La barra muestra en qué % de casos ese resultado efectivamente ocurrió. ' +
    'n indica cuántos partidos hay en ese rango. Pasa el cursor para ver el desglose.'
  );
  const legendBar = el('div', { className: 'calib-legend' },
    el('span', { className: 'calib-legend-item' },
      el('span', { className: 'calib-dot', style: 'background:#16a34a' }), '≥60% aciertos'
    ),
    el('span', { className: 'calib-legend-item' },
      el('span', { className: 'calib-dot', style: 'background:#ea580c' }), '40–60% aciertos'
    ),
    el('span', { className: 'calib-legend-item' },
      el('span', { className: 'calib-dot', style: 'background:#dc2626' }), '<40% aciertos'
    ),
  );

  const noteScat = el('p', { className: 'calib-note' },
    'Cada partido genera 3 probabilidades (local, empate, visitante) que se evalúan por separado. ' +
    'Cada punto compara la probabilidad predicha (eje X) con la frecuencia real con que ese resultado ocurrió (eje Y). ' +
    'Sobre la diagonal: el modelo fue demasiado prudente. Bajo la diagonal: demasiado confiado. ' +
    'El tamaño del punto indica cuántas probabilidades hay en ese rango.'
  );

  const noteCum = el('p', { className: 'calib-note' },
    'Evolución del porcentaje de aciertos de izquierda a derecha en orden cronológico (el primer partido jugado está a la izquierda). ' +
    'Pasa el cursor sobre cada punto para ver el partido y resultado. ' +
    'La línea de referencia (33%) representa el acierto esperado eligiendo al azar entre los tres resultados posibles.'
  );

  const canvasBar  = el('canvas');
  const canvasScat = el('canvas');
  const canvasCum  = el('canvas');
  const wrapBar  = el('div', { className: 'calib-chart-wrap' },           noteBar,  canvasBar,  legendBar);
  const wrapScat = el('div', { className: 'calib-chart-wrap', style: 'display:none' }, noteScat, canvasScat);
  const wrapCum  = el('div', { className: 'calib-chart-wrap', style: 'display:none' }, noteCum,  canvasCum);

  const btnBar   = el('button', { className: 'calib-toggle active' }, 'Aciertos por confianza');
  const btnScatt = el('button', { className: 'calib-toggle' }, 'Calibración');
  const btnCum   = el('button', { className: 'calib-toggle' }, 'Precisión acumulada');
  const toggles  = el('div', { className: 'calib-toggles' }, btnBar, btnScatt, btnCum);

  const wrap = el('div', { className: 'calib-wrap' },
    el('div', { className: 'calib-title' }, title),
    toggles,
    wrapBar,
    wrapScat,
    wrapCum,
  );

  setTimeout(() => {
    // ── Gráfico de barras: aciertos por nivel de confianza ──
    const barData = partidos ? buildBarDataFromPartidos(partidos) : null;
    if (barData) {
      new Chart(canvasBar, {
        type: 'bar',
        data: {
          labels: barData.map(d => [d.label, `${d.total} partidos`]),
          datasets: [{
            label: '% de aciertos',
            data: barData.map(d => +((d.aciertos / d.total) * 100).toFixed(1)),
            backgroundColor: barData.map(d => {
              const rate = d.aciertos / d.total;
              return rate >= 0.6 ? 'rgba(22,163,74,.35)' : rate >= 0.4 ? 'rgba(234,88,12,.3)' : 'rgba(220,38,38,.3)';
            }),
            borderColor: barData.map(d => {
              const rate = d.aciertos / d.total;
              return rate >= 0.6 ? '#16a34a' : rate >= 0.4 ? '#ea580c' : '#dc2626';
            }),
            borderWidth: 1.5,
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (item) => `${item.parsed.y}% de aciertos`,
                afterLabel: (item) => `${barData[item.dataIndex].aciertos} de ${barData[item.dataIndex].total} partidos`,
              },
            },
          },
          scales: {
            x: { title: { display: true, text: 'Confianza del modelo (prob. máxima)', font: { size: 11 } } },
            y: { title: { display: true, text: '% de aciertos', font: { size: 11 } }, min: 0, max: 100,
              ticks: { callback: v => v + '%' } },
          },
        },
      });
    } else {
      wrapBar.appendChild(el('p', { style: 'color:var(--muted);font-size:.8rem;padding:12px 0' }, 'Sin datos de partidos individuales.'));
    }

    // ── Scatter de calibración ──
    const scatBuckets = partidos ? buildScatDataFromPartidos(partidos) : buckets;
    new Chart(canvasScat, {
      type: 'scatter',
      data: {
        datasets: [
          {
            label: 'Modelo',
            data: scatBuckets.map(b => ({ x: +(b.predicho * 100).toFixed(1), y: +(b.observado * 100).toFixed(1) })),
            backgroundColor: 'rgba(29,78,216,.75)',
            pointRadius: scatBuckets.map(b => Math.max(4, Math.min(10, Math.sqrt(b.n / 3)))),
            pointHoverRadius: 8,
          },
          {
            label: 'Calibración perfecta',
            data: [{ x: 0, y: 0 }, { x: 100, y: 100 }],
            type: 'line',
            borderColor: '#d1d5db',
            borderDash: [5, 4],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'bottom', labels: { font: { size: 11 }, boxWidth: 12 } },
          tooltip: {
            callbacks: {
              label: (item) => {
                if (item.datasetIndex === 1) return null;
                const b = scatBuckets[item.dataIndex];
                return `Predicho ${item.parsed.x}% → Observado ${item.parsed.y}% · ${b.n} probabilidades evaluadas`;
              },
            },
          },
        },
        scales: {
          x: { title: { display: true, text: 'Probabilidad predicha (%)', font: { size: 11 } }, min: 0, max: 100 },
          y: { title: { display: true, text: 'Frecuencia observada (%)', font: { size: 11 } }, min: 0, max: 100 },
        },
      },
      plugins: [{
        id: 'calib-labels',
        afterDraw(chart) {
          const { ctx, chartArea: { left, right, top, bottom } } = chart;
          ctx.save();
          ctx.font = '10px system-ui, sans-serif';
          ctx.fillStyle = 'rgba(107,114,128,.7)';
          ctx.textAlign = 'left';
          ctx.fillText('▲ demasiado prudente', left + 6, top + 14);
          ctx.textAlign = 'right';
          ctx.fillText('demasiado confiado ▼', right - 6, bottom - 6);
          ctx.restore();
        },
      }],
    });

    // ── Precisión acumulada ──
    if (partidos) {
      const cumData = buildCumulativeData(partidos);
      new Chart(canvasCum, {
        type: 'line',
        data: {
          labels: cumData.map(d => d.label),
          datasets: [
            {
              label: 'Acierto acumulado',
              data: cumData.map(d => d.rate),
              borderColor: '#1d4ed8',
              backgroundColor: 'rgba(29,78,216,.08)',
              borderWidth: 2,
              pointRadius: 4,
              pointHoverRadius: 6,
              fill: true,
              tension: 0.3,
            },
            {
              label: 'Azar (33%)',
              data: cumData.map(() => 33.3),
              borderColor: '#d1d5db',
              borderDash: [5, 4],
              borderWidth: 1.5,
              pointRadius: 0,
              fill: false,
            },
          ],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { position: 'bottom', labels: { font: { size: 11 }, boxWidth: 12 } },
            tooltip: {
              callbacks: {
                title: (items) => cumData[items[0].dataIndex].tooltip,
              label: (item) => item.datasetIndex === 0
                  ? `Acierto acumulado: ${item.parsed.y}%`
                  : null,
              },
            },
          },
          scales: {
            x: { ticks: { font: { size: 10 }, maxRotation: 45 } },
            y: {
              title: { display: true, text: '% de aciertos acumulado', font: { size: 11 } },
              min: 0, max: 100,
              ticks: { callback: v => v + '%' },
            },
          },
        },
      });
    }
  }, 0);

  const allWraps   = [wrapBar, wrapScat, wrapCum];
  const allBtns    = [btnBar, btnScatt, btnCum];
  allBtns.forEach((btn, i) => {
    btn.addEventListener('click', () => {
      allWraps.forEach((w, j) => { w.style.display = j === i ? '' : 'none'; });
      allBtns.forEach((b, j) => { b.classList.toggle('active', j === i); });
    });
  });

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

// ── Modal detalle partido ─────────────────────────────────────────────────────

function openMatchModal(p) {
  const overlay = document.getElementById('match-modal');
  const content = document.getElementById('modal-content');
  content.innerHTML = '';

  // Cabecera equipos
  const teamsEl = el('div', { className: 'modal-teams' });
  const fH = flagImg(p.local, 20); const fA = flagImg(p.visitante, 20);
  if (fH) teamsEl.appendChild(fH);
  teamsEl.appendChild(document.createTextNode(p.local));
  teamsEl.appendChild(el('span', { style: 'color:var(--muted);font-weight:400' }, ' vs '));
  if (fA) teamsEl.appendChild(fA);
  teamsEl.appendChild(document.createTextNode(p.visitante));
  if (p.sorpresa) teamsEl.appendChild(el('span', { title: 'Resultado sorpresa' }, ' ⚡'));
  content.appendChild(teamsEl);
  content.appendChild(el('div', { className: 'modal-date' }, fmtDatetime(p.fecha) + (p.fase ? ' · ' + p.fase : '')));

  // Marcador predicho vs real
  const scored = p.resultado === p.marcador_probable;
  content.appendChild(el('div', { className: 'modal-scores' },
    el('div', { className: 'modal-score-card' },
      el('div', { className: 'modal-score-label' }, 'Predicción de goles'),
      el('div', { className: 'modal-score-val' }, p.marcador_probable || '—'),
    ),
    el('div', { className: 'modal-score-card' },
      el('div', { className: 'modal-score-label' }, 'Resultado real'),
      el('div', { className: 'modal-score-val ' + (scored ? 'correct' : 'wrong') }, p.resultado || '—'),
    ),
  ));

  // Probabilidades DC
  const ph  = (p.prob_local * 100).toFixed(0);
  const pd  = (p.prob_empate * 100).toFixed(0);
  const pa  = (p.prob_visitante * 100).toFixed(0);
  content.appendChild(el('div', { className: 'modal-section-title' }, 'Forma reciente (Dixon-Coles)'));
  content.appendChild(el('div', { className: 'prob-bar' },
    el('div', { className: 'prob-home', style: `width:${ph}%` }, ph + '%'),
    el('div', { className: 'prob-draw', style: `width:${pd}%` }, pd + '%'),
    el('div', { className: 'prob-away', style: `width:${pa}%` }, pa + '%'),
  ));

  // Probabilidades Elo (si existen)
  if (p.prob_local_elo != null) {
    const phe = (p.prob_local_elo * 100).toFixed(0);
    const pde = (p.prob_empate_elo * 100).toFixed(0);
    const pae = (p.prob_visitante_elo * 100).toFixed(0);
    content.appendChild(el('div', { className: 'modal-section-title' }, 'Historial y reputación (Elo)'));
    content.appendChild(el('div', { className: 'prob-bar prob-bar-secondary' },
      el('div', { className: 'prob-home', style: `width:${phe}%` }, phe + '%'),
      el('div', { className: 'prob-draw', style: `width:${pde}%` }, pde + '%'),
      el('div', { className: 'prob-away', style: `width:${pae}%` }, pae + '%'),
    ));
  }

  // Métricas del partido
  content.appendChild(el('div', { className: 'modal-metrics' },
    el('div', { className: 'modal-metric' },
      el('div', { className: 'modal-metric-label th-tooltip', 'data-tooltip': 'Brier score: error cuadrático entre las probabilidades predichas y el resultado real. 0 = predicción perfecta · 2 = máximo error.' }, 'Error pred. ⓘ'),
      el('div', { className: 'modal-metric-val' }, p.brier.toFixed(3)),
    ),
    el('div', { className: 'modal-metric' },
      el('div', { className: 'modal-metric-label th-tooltip', 'data-tooltip': 'Log-loss: penaliza especialmente las predicciones muy confiadas que resultan erróneas. Menor valor = mejor calibración.' }, 'Penalización ⓘ'),
      el('div', { className: 'modal-metric-val' }, p.log_loss.toFixed(3)),
    ),
    el('div', { className: 'modal-metric' },
      el('div', { className: 'modal-metric-label' }, 'Resultado'),
      el('div', { className: 'modal-metric-val ' + (p.acertado ? 'metrica-better' : 'metrica-worse') },
        p.acertado ? 'Acierto' : 'Fallo'
      ),
    ),
  ));

  // Fecha de congelación
  if (p.fecha_prediccion) {
    content.appendChild(el('div', { className: 'modal-frozen' },
      'Predicción congelada el ' + fmtDatetime(p.fecha_prediccion)
    ));
  }

  overlay.classList.remove('hidden');
}

function closeModal() {
  document.getElementById('match-modal').classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelector('.modal-close').addEventListener('click', closeModal);
  document.getElementById('match-modal').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
});

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
