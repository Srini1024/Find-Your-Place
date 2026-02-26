/* =============================================
   Find Your Place — Main Application Script
   ============================================= */

'use strict';

// ---- State ----
const state = {
  lat: null,
  lon: null,
  locationName: null,
  geoGranted: false,
  currentQuery: '',
  results: null,
  metadata: null,
};

// ---- DOM References ----
const els = {
  heroSection: () => document.getElementById('heroSection'),
  loadingSection: () => document.getElementById('loadingSection'),
  resultsSection: () => document.getElementById('resultsSection'),
  errorSection: () => document.getElementById('errorSection'),
  searchInput: () => document.getElementById('searchInput'),
  searchBtn: () => document.getElementById('searchBtn'),
  locationText: () => document.getElementById('locationText'),
  locationPill: () => document.getElementById('locationPill'),
  loadingSubtitle: () => document.getElementById('loadingSubtitle'),
  loadingBar: () => document.getElementById('loadingBar'),
  cardsGrid: () => document.getElementById('cardsGrid'),
  metadataBar: () => document.getElementById('metadataBar'),
  resultsTitle: () => document.getElementById('resultsTitle'),
  resultsSubtitle: () => document.getElementById('resultsSubtitle'),
  errorTitle: () => document.getElementById('errorTitle'),
  errorMessage: () => document.getElementById('errorMessage'),
  newSearchBtn: () => document.getElementById('newSearchBtn'),
  retryBtn: () => document.getElementById('retryBtn'),
  modalOverlay: () => document.getElementById('modalOverlay'),
  modal: () => document.getElementById('modal'),
  modalClose: () => document.getElementById('modalClose'),
  modalContent: () => document.getElementById('modalContent'),

  // Pipeline steps
  step: (n) => document.getElementById(`step${n}`),
  connector: (n) => document.getElementById(`connector${n}`),
  stepIcon: (n) => document.querySelector(`#step${n} .step-status-icon`),
};

// ---- Section Management ----
function showSection(name) {
  ['heroSection', 'loadingSection', 'resultsSection', 'errorSection'].forEach(id => {
    document.getElementById(id).classList.add('hidden');
  });
  document.getElementById(name).classList.remove('hidden');
}

// ---- Geolocation ----
function requestGeolocation() {
  if (!navigator.geolocation) {
    showToast('Geolocation is not supported by your browser.', 'error');
    detectLocationSilently();
    return;
  }

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      state.lat = pos.coords.latitude;
      state.lon = pos.coords.longitude;
      state.geoGranted = true;

      // Reverse geocode with Nominatim
      try {
        const resp = await fetch(
          `https://nominatim.openstreetmap.org/reverse?lat=${state.lat}&lon=${state.lon}&format=json`,
          { headers: { 'User-Agent': 'FindYourPlace-App/1.0' } }
        );
        const data = await resp.json();
        const city = data.address?.city || data.address?.town || data.address?.village || '';
        const country = data.address?.country || '';
        state.locationName = city ? `${city}, ${country}` : data.display_name?.split(',')[0];
      } catch {
        state.locationName = `${state.lat.toFixed(3)}, ${state.lon.toFixed(3)}`;
      }

      updateLocationPill(state.locationName, 'browser');
      showToast('📍 Location detected!', 'success');
    },
    (err) => {
      let msg = 'Location access denied. We\'ll detect your location automatically.';
      if (err.code === 1) msg = 'Location permission denied. You can still search!';
      showToast(msg, 'info');
      detectLocationSilently();
    },
    { timeout: 10000, maximumAge: 300000 }
  );
}

function updateLocationPill(name, source) {
  const text = els.locationText();
  text.textContent = name || 'Location detected';
  const pill = els.locationPill();
  pill.style.borderColor = 'rgba(34, 197, 94, 0.3)';
  pill.style.color = 'var(--accent-green)';
}

// Auto-detect on load (silent IP-based)
async function detectLocationSilently() {
  try {
    const resp = await fetch('http://ip-api.com/json/?fields=status,city,regionName,country');
    const data = await resp.json();
    if (data.status === 'success') {
      const loc = [data.city, data.country].filter(Boolean).join(', ');
      els.locationText().textContent = loc || 'Location detected';
    }
  } catch {
    els.locationText().textContent = 'Location via IP';
  }
}

// ---- Pipeline Loading Animation ----
const PIPELINE_STEPS = [
  { id: 1, subtitle: '🌍 Finding your location...', progress: 15 },
  { id: 2, subtitle: '🗺️ Discovering nearby places via OpenStreetMap...', progress: 35 },
  { id: 3, subtitle: '🔍 Deep-diving Reddit, blogs & the web with Tavily...', progress: 70 },
  { id: 4, subtitle: '✨ Crafting your personalized Top 5...', progress: 90 },
];

let currentStep = 0;
let stepTimers = [];

function resetPipelineUI() {
  currentStep = 0;
  stepTimers.forEach(clearTimeout);
  stepTimers = [];
  for (let i = 1; i <= 4; i++) {
    const step = els.step(i);
    step.className = 'pipeline-step';
    els.stepIcon(i).className = 'step-status-icon';
  }
  for (let i = 1; i <= 3; i++) {
    const conn = els.connector(i);
    if (conn) conn.className = 'pipeline-connector';
  }
  els.loadingBar().style.width = '0%';
}

function activatePipelineStep(stepNum, subtitle, progress) {
  // Mark previous as done
  if (stepNum > 1) {
    const prevStep = els.step(stepNum - 1);
    prevStep.className = 'pipeline-step done';
    els.stepIcon(stepNum - 1).className = 'step-status-icon check';
    const conn = els.connector(stepNum - 1);
    if (conn) conn.classList.add('active');
  }

  // Activate current
  const step = els.step(stepNum);
  step.className = `pipeline-step active`;
  els.stepIcon(stepNum).className = 'step-status-icon spinning';

  // Update subtitle
  els.loadingSubtitle().textContent = subtitle;

  // Update progress bar
  els.loadingBar().style.width = `${progress}%`;
}

function finalizePipelineUI() {
  // Mark step 4 done
  els.step(4).className = 'pipeline-step done';
  els.stepIcon(4).className = 'step-status-icon check';
  els.loadingBar().style.width = '100%';
  els.loadingSubtitle().textContent = '🎉 Your Top 5 are ready!';
}

function startPipelineAnimation(estimatedMs) {
  // Distribute step timings across estimated duration
  const intervals = [
    Math.floor(estimatedMs * 0.08),
    Math.floor(estimatedMs * 0.25),
    Math.floor(estimatedMs * 0.55),
    Math.floor(estimatedMs * 0.80),
  ];

  PIPELINE_STEPS.forEach((step, idx) => {
    const timer = setTimeout(() => {
      activatePipelineStep(step.id, step.subtitle, step.progress);
    }, intervals[idx]);
    stepTimers.push(timer);
  });
}

// ---- Search ----
async function performSearch(query) {
  if (!query || !query.trim()) {
    showToast('Please enter a search query!', 'error');
    return;
  }

  state.currentQuery = query.trim();
  resetPipelineUI();
  showSection('loadingSection');

  // Start pipeline animation (estimate 30-60s for full pipeline)
  startPipelineAnimation(35000);

  const payload = {
    query: state.currentQuery,
    lat: state.lat,
    lon: state.lon,
    location_name: state.locationName,
  };

  try {
    const startTime = Date.now();
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    // Clear pending step timers
    stepTimers.forEach(clearTimeout);
    stepTimers = [];

    const elapsed = Date.now() - startTime;
    finalizePipelineUI();

    // Brief delay to show final state
    await sleep(800);

    const data = await response.json();

    if (!response.ok || !data.success) {
      showError(
        data.recommendations?.length === 0 ? '🔍 No Results Found' : '⚠️ Something went wrong',
        data.error || 'Unable to find recommendations. Please try again.'
      );
      return;
    }

    state.results = data.recommendations;
    state.metadata = data.metadata;
    renderResults(data.recommendations, data.metadata);
    showSection('resultsSection');

  } catch (err) {
    stepTimers.forEach(clearTimeout);
    console.error('Search failed:', err);
    showError('🌐 Connection Error', 'Failed to reach the server. Please check your connection and try again.');
  }
}

// ---- Result Rendering ----
function renderResults(recommendations, metadata) {
  const grid = els.cardsGrid();
  grid.innerHTML = '';

  // Update header
  const queryDisplay = `"${metadata?.query || state.currentQuery}"`;
  els.resultsTitle().textContent = `Top ${recommendations.length} Picks`;
  els.resultsSubtitle().textContent = `For ${queryDisplay} near ${metadata?.location || 'your area'}`;

  // Metadata bar
  const metaBar = els.metadataBar();
  metaBar.innerHTML = '';
  if (metadata) {
    const chips = [
      { label: 'Location via', value: formatSource(metadata.location_source) },
      { label: 'Places scouted', value: metadata.total_discovered || '–' },
      { label: 'Deeply analyzed', value: metadata.total_analyzed || '–' },
      { label: 'AI model', value: metadata.llm_model || 'GPT-4o' },
      { label: 'Type', value: (metadata.place_type || 'general').toUpperCase() },
    ];
    chips.forEach(c => {
      const chip = document.createElement('div');
      chip.className = 'meta-chip';
      chip.innerHTML = `<span>${c.label} </span><span>${c.value}</span>`;
      metaBar.appendChild(chip);
    });
  }

  // Render each recommendation card
  recommendations.forEach((rec, idx) => {
    const card = buildRecCard(rec, idx + 1);
    grid.appendChild(card);
  });
}

function formatSource(source) {
  const map = { 'browser': '📱 Browser GPS', 'ip-api': '🌐 IP Address', 'query_text': '💬 Your query' };
  return map[source] || source || '–';
}

function buildRecCard(rec, rank) {
  const card = document.createElement('div');
  card.className = `rec-card rank-${rank}`;
  card.setAttribute('data-rank', rank);
  card.setAttribute('role', 'article');
  card.setAttribute('aria-label', `Recommendation ${rank}: ${rec.name}`);

  const mapsUrl = rec.lat && rec.lon
    ? `https://www.google.com/maps?q=${rec.lat},${rec.lon}`
    : `https://www.google.com/maps/search/${encodeURIComponent(rec.name + ' ' + (rec.address || ''))}`;

  const websiteLink = rec.website
    ? `<a href="${escHtml(rec.website)}" class="action-btn action-btn-web" target="_blank" rel="noopener">
         <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1H11V6M11 1L5 7M2 3H1V11H9V10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
         Website
       </a>`
    : '';

  const highlights = (rec.highlights || []).slice(0, 3)
    .map(h => `<div class="highlight-chip">${escHtml(h)}</div>`)
    .join('');

  const sources = (rec.sources || []).slice(0, 3)
    .map(url => `<a href="${escHtml(url)}" class="source-link" target="_blank" rel="noopener" title="${escHtml(url)}">
      ${sourceIcon(url)} ${domainName(url)}
    </a>`)
    .join('');

  const redditBadge = rec.has_reddit
    ? `<span class="badge badge-reddit">🔴 Reddit</span>`
    : '';

  card.innerHTML = `
    <div class="rec-card-inner">
      <div class="rec-rank">
        <div class="rank-number">#${rank}</div>
        <div class="rank-label">${rankLabel(rank)}</div>
      </div>
      <div class="rec-body">
        <div class="rec-header">
          <div class="rec-name">${escHtml(rec.name)}</div>
          <div class="rec-badges">
            ${redditBadge}
            ${rec.category ? `<span class="badge badge-category">${escHtml(rec.category)}</span>` : ''}
          </div>
        </div>
        ${rec.tagline ? `<div class="rec-tagline">${escHtml(rec.tagline)}</div>` : ''}
        <div class="rec-why">${escHtml(rec.why_visit || '')}</div>
        ${highlights ? `<div class="rec-highlights">${highlights}</div>` : ''}
        ${rec.reddit_says ? `
          <div class="rec-reddit">
            <div class="rec-reddit-label">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><circle cx="6" cy="6" r="6"/><path d="M10 6a.67.67 0 00-1.14-.48 3.31 3.31 0 00-1.78-.56l.3-1.41 1 .2a.47.47 0 10.05-.43l-1.13-.22a.1.1 0 00-.12.08l-.34 1.57a3.32 3.32 0 00-1.79.56.67.67 0 10-.73 1.08 1.3 1.3 0 000 .17c0 .87 1 1.57 2.22 1.57s2.22-.7 2.22-1.57a1.3 1.3 0 000-.17A.67.67 0 0010 6zM4.62 6.47a.47.47 0 110-.94.47.47 0 010 .94zm2.63.9c-.29.29-.84.31-1.25.31s-1-.02-1.25-.31a.1.1 0 01.14-.14c.2.2.61.27 1.11.27s.91-.07 1.11-.27a.1.1 0 01.14.14zm-.07-.9a.47.47 0 110-.94.47.47 0 010 .94z" fill="white"/></svg>
              What Reddit says
            </div>
            <div class="rec-reddit-text">${escHtml(rec.reddit_says || '')}</div>
          </div>
        ` : ''}
        ${rec.web_says ? `
          <div class="rec-reddit" style="border-color:rgba(14, 165, 233, 0.2);background:rgba(14, 165, 233, 0.04);margin-top:8px">
            <div class="rec-reddit-label" style="color:var(--accent-blue, #0ea5e9)">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 11A5 5 0 106 1a5 5 0 000 10zM1 6h10M6 1c-1.38 0-2.5 2.24-2.5 5 0 2.76 1.12 5 2.5 5s2.5-2.24 2.5-5C8.5 3.24 7.38 1 6 1z" stroke="currentColor" stroke-width="1.2"/></svg>
              What the Web says
            </div>
            <div class="rec-reddit-text">${escHtml(rec.web_says || '')}</div>
          </div>
        ` : ''}
        ${rec.insider_tip ? `
          <div class="rec-reddit" style="border-color:rgba(245,158,11,0.15);background:rgba(245,158,11,0.04)">
            <div class="rec-reddit-label" style="color:var(--accent-gold)">💡 Insider Tip</div>
            <div class="rec-reddit-text">${escHtml(rec.insider_tip)}</div>
          </div>
        ` : ''}
        <div class="rec-footer">
          <div class="rec-meta-items">
            ${rec.distance ? `<div class="rec-meta-item">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="5" r="3" stroke="currentColor" stroke-width="1.3"/><path d="M6 9s-3-3-3-6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
              ${escHtml(rec.distance)}
            </div>` : ''}
            ${rec.best_for ? `<div class="rec-meta-item">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="4.5" cy="3.5" r="2" stroke="currentColor" stroke-width="1.3"/><path d="M1 10s0-2.5 3.5-2.5S8 10 8 10" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><circle cx="8.5" cy="3.5" r="1.5" stroke="currentColor" stroke-width="1.3"/><path d="M9 7.5c1.5 0 2 1.5 2 2.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
              ${escHtml(rec.best_for)}
            </div>` : ''}
          </div>
          <div class="rec-actions">
            <a href="${mapsUrl}" class="action-btn action-btn-map" target="_blank" rel="noopener">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1C4.07 1 2.5 2.57 2.5 4.5 2.5 7.38 6 11 6 11s3.5-3.62 3.5-6.5C9.5 2.57 7.93 1 6 1zm0 4.75a1.25 1.25 0 110-2.5 1.25 1.25 0 010 2.5z" stroke="currentColor" stroke-width="1.2" /></svg>
              Map
            </a>
            ${websiteLink}
          </div>
          ${sources ? `<div class="rec-sources">${sources}</div>` : ''}
        </div>
      </div>
    </div>
  `;

  // Add click handler for expanded modal view
  card.addEventListener('click', (e) => {
    if (!e.target.closest('a')) {
      openModal(rec, rank);
    }
  });

  return card;
}

// ---- Modal ----
function openModal(rec, rank) {
  const content = els.modalContent();
  const mapsUrl = rec.lat && rec.lon
    ? `https://www.google.com/maps?q=${rec.lat},${rec.lon}`
    : `https://www.google.com/maps/search/${encodeURIComponent(rec.name)}`;

  content.innerHTML = `
    <div style="margin-bottom:24px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap">
        <div style="font-family:'Outfit',sans-serif;font-size:2.5rem;font-weight:900;line-height:1;
          background:var(--gradient-fire);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">#${rank}</div>
        <div>
          <h2 style="font-family:'Outfit',sans-serif;font-size:1.6rem;font-weight:700;color:var(--text-primary);line-height:1.2">${escHtml(rec.name)}</h2>
          ${rec.tagline ? `<p style="color:var(--accent-orange-bright);font-style:italic;margin-top:4px">${escHtml(rec.tagline)}</p>` : ''}
        </div>
      </div>
      
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px">
        ${rec.category ? `<span class="badge badge-category">${escHtml(rec.category)}</span>` : ''}
        ${rec.has_reddit ? `<span class="badge badge-reddit">🔴 Reddit Verified</span>` : ''}
        ${rec.distance ? `<span class="badge" style="background:rgba(232,98,10,0.1);color:#FDBA74;border:1px solid rgba(232,98,10,0.22)">📍 ${escHtml(rec.distance)}</span>` : ''}
      </div>

      <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border-subtle);border-radius:var(--radius-md);padding:18px;margin-bottom:16px">
        <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);margin-bottom:8px">Why Visit</div>
        <p style="color:var(--text-secondary);line-height:1.7;font-size:0.95rem">${escHtml(rec.why_visit || '')}</p>
      </div>

      ${rec.highlights?.length ? `
        <div style="margin-bottom:16px">
          <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);margin-bottom:10px">Highlights</div>
          <div style="display:flex;flex-direction:column;gap:8px">
            ${rec.highlights.map(h => `
              <div style="display:flex;align-items:center;gap:10px;color:var(--text-secondary);font-size:0.9rem">
                <span style="color:var(--accent-orange);font-size:1.2rem">&rarr;</span>
                ${escHtml(h)}
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}

      ${rec.reddit_says ? `
        <div class="rec-reddit" style="margin-bottom:16px">
          <div class="rec-reddit-label">🔴 What Reddit says</div>
          <div class="rec-reddit-text">${escHtml(rec.reddit_says)}</div>
        </div>
      ` : ''}

      ${rec.web_says ? `
        <div class="rec-reddit" style="border-color:rgba(14, 165, 233, 0.2);background:rgba(14, 165, 233, 0.04);margin-bottom:16px">
          <div class="rec-reddit-label" style="color:var(--accent-blue, #0ea5e9)">🌐 What the Web says</div>
          <div class="rec-reddit-text">${escHtml(rec.web_says)}</div>
        </div>
      ` : ''}

      ${rec.insider_tip ? `
        <div class="rec-reddit" style="border-color:rgba(245,158,11,0.15);background:rgba(245,158,11,0.04);margin-bottom:16px">
          <div class="rec-reddit-label" style="color:var(--accent-gold)">💡 Insider Tip</div>
          <div class="rec-reddit-text">${escHtml(rec.insider_tip)}</div>
        </div>
      ` : ''}

      ${rec.best_for ? `
        <div style="margin-bottom:20px;padding:12px 16px;background:rgba(34,197,94,0.05);border:1px solid rgba(34,197,94,0.15);border-radius:var(--radius-sm)">
          <span style="font-size:0.8rem;color:var(--accent-green);font-weight:600">Best for:</span>
          <span style="font-size:0.9rem;color:var(--text-secondary);margin-left:8px">${escHtml(rec.best_for)}</span>
        </div>
      ` : ''}

      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <a href="${mapsUrl}" class="action-btn action-btn-map" target="_blank" rel="noopener" style="padding:10px 18px;font-size:0.9rem">
          📍 Open in Maps
        </a>
        ${rec.website ? `<a href="${escHtml(rec.website)}" class="action-btn action-btn-web" target="_blank" rel="noopener" style="padding:10px 18px;font-size:0.9rem">
          🌐 Visit Website
        </a>` : ''}
      </div>

      ${rec.sources?.length ? `
        <div style="margin-top:20px">
          <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);margin-bottom:8px">Sources</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            ${rec.sources.map(url => `
              <a href="${escHtml(url)}" class="source-link" target="_blank" rel="noopener">${sourceIcon(url)} ${domainName(url)}</a>
            `).join('')}
          </div>
        </div>
      ` : ''}
    </div>
  `;

  els.modalOverlay().classList.remove('hidden');
}

function closeModal() {
  els.modalOverlay().classList.add('hidden');
}

// ---- Error ----
function showError(title, message) {
  els.errorTitle().textContent = title;
  els.errorMessage().textContent = message;
  showSection('errorSection');
}

// ---- Toast Notifications ----
function showToast(message, type = 'info') {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const colors = { success: '#10B981', error: '#EF4444', info: '#3B82F6', warning: '#F59E0B' };
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  Object.assign(toast.style, {
    position: 'fixed',
    bottom: '24px',
    left: '50%',
    transform: 'translateX(-50%) translateY(0)',
    background: 'var(--bg-card)',
    border: `1px solid ${colors[type] || colors.info}40`,
    borderLeft: `3px solid ${colors[type] || colors.info}`,
    color: 'var(--text-primary)',
    padding: '12px 20px',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.88rem',
    fontFamily: 'Inter, sans-serif',
    zIndex: '999',
    boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
    backdropFilter: 'blur(10px)',
    maxWidth: '380px',
    textAlign: 'center',
    transition: 'opacity 0.3s ease',
    opacity: '0',
  });
  document.body.appendChild(toast);
  requestAnimationFrame(() => { toast.style.opacity = '1'; });
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ---- Helpers ----
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function rankLabel(rank) {
  return ['PICK', '2ND', '3RD', '4TH', '5TH'][rank - 1] || `#${rank}`;
}

function domainName(url) {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return url.slice(0, 30);
  }
}

function sourceIcon(url) {
  const u = url.toLowerCase();
  if (u.includes('reddit.com')) return '🔴';
  if (u.includes('yelp.com')) return '⭐';
  if (u.includes('tripadvisor.com')) return '✈️';
  if (u.includes('timeout.com') || u.includes('eater.com')) return '📰';
  if (u.includes('wordpress') || u.includes('medium') || u.includes('blog')) return '📝';
  return '🌐';
}

// ---- Event Listeners ----
function initEventListeners() {
  // Search button
  els.searchBtn().addEventListener('click', () => {
    performSearch(els.searchInput().value);
  });

  // Enter key in input
  els.searchInput().addEventListener('keydown', (e) => {
    if (e.key === 'Enter') performSearch(els.searchInput().value);
  });

  // Suggestion chips
  document.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const query = chip.getAttribute('data-query');
      els.searchInput().value = query;
      performSearch(query);
    });
  });

  // New search
  els.newSearchBtn().addEventListener('click', () => {
    showSection('heroSection');
    els.searchInput().value = '';
    els.searchInput().focus();
  });

  // Retry
  els.retryBtn().addEventListener('click', () => {
    if (state.currentQuery) {
      performSearch(state.currentQuery);
    } else {
      showSection('heroSection');
    }
  });

  // Modal close
  els.modalClose().addEventListener('click', closeModal);
  els.modalOverlay().addEventListener('click', (e) => {
    if (e.target === els.modalOverlay()) closeModal();
  });

  // Escape key closes modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !els.modalOverlay().classList.contains('hidden')) {
      closeModal();
    }
  });
}

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  requestGeolocation();

  // Animate hero elements in
  setTimeout(() => {
    document.querySelectorAll('.feature-pill').forEach((el, i) => {
      setTimeout(() => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(10px)';
        el.style.transition = 'all 0.4s ease';
        requestAnimationFrame(() => {
          el.style.opacity = '1';
          el.style.transform = 'translateY(0)';
        });
      }, i * 80);
    });
  }, 300);
});
