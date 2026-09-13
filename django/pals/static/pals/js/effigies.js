(() => {
  const assetBase = window.PALS_EFFIGY_ASSET;
  const api = window.PALS_EFFIGY_API;
  const state = { data: null, map: null, overlay: null, layers: new Map(), hidden: new Set(), visibleTypes: new Set(), mapId: 'palpagos' };
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const hiddenKey = () => `pals.effigies.hidden.v1.${state.data?.selectedPlayer || 'none'}`;

  function loadHidden() {
    try { state.hidden = new Set(JSON.parse(localStorage.getItem(hiddenKey()) || '[]')); }
    catch { state.hidden = new Set(); }
  }

  function saveHidden() { localStorage.setItem(hiddenKey(), JSON.stringify([...state.hidden])); }

  function setHidden(marker, layer, hidden = true) {
    if (hidden) state.hidden.add(marker.id); else state.hidden.delete(marker.id);
    saveHidden();
    layer.setIcon(markerIcon(marker));
    const checkbox = layer.getPopup()?.getElement()?.querySelector('[data-hide-marker]');
    if (checkbox) checkbox.checked = hidden;
  }

  function mapFor(id) { return state.data.maps[id]; }

  function markerPosition(marker) {
    return [8192 - (marker.top / 100) * 8192, (marker.left / 100) * 8192];
  }

  function markerIcon(marker) {
    const hidden = state.hidden.has(marker.id) ? ' is-hidden' : '';
    const collected = marker.collected ? ' is-collected' : '';
    return L.divIcon({
      className: '', iconSize: [24, 24], iconAnchor: [12, 12],
      html: `<div class="effigy-pin${collected}${hidden}" data-marker-id="${esc(marker.id)}"><img src="${assetBase}icons/effigy/Lifmunk_Effigy_icon.webp" alt=""></div>`,
    });
  }

  function popupHtml(marker) {
    const hidden = state.hidden.has(marker.id);
    const collected = marker.collected ? '<br><strong>✓ Collected from save</strong>' : '';
    return `<div class="effigy-popup"><strong>${esc(marker.label)}</strong><p>${esc(marker.mapName)}<br>Coordinates: ${marker.x}, ${marker.y}${collected}</p><label><input type="checkbox" data-hide-marker="${esc(marker.id)}" ${hidden ? 'checked' : ''}> Hide for live play</label></div>`;
  }

  function bindPopup(marker, layer) {
    layer.bindPopup(popupHtml(marker));
    layer.on('popupopen', event => {
      const checkbox = event.popup.getElement()?.querySelector('[data-hide-marker]');
      if (!checkbox) return;
      checkbox.addEventListener('change', () => {
        setHidden(marker, layer, checkbox.checked);
      });
    });
    layer.on('dblclick', event => {
      L.DomEvent.stopPropagation(event.originalEvent);
      setHidden(marker, layer, !state.hidden.has(marker.id));
    });
  }

  function renderMap() {
    if (!state.map) {
      state.map = L.map('effigyMapCanvas', { crs: L.CRS.Simple, minZoom: -3, maxZoom: 2, zoomSnap: .25 });
      state.map.fitBounds([[0, 0], [8192, 8192]]);
    }
    if (state.overlay) state.map.removeLayer(state.overlay);
    const map = mapFor(state.mapId);
    state.overlay = L.imageOverlay(`${assetBase}maps/${map.image}`, [[0, 0], [8192, 8192]]).addTo(state.map);
    state.layers.forEach(layer => state.map.removeLayer(layer));
    state.layers.clear();
    const showCollected = $('#effigyShowCollected').checked;
    for (const marker of state.data.markers) {
      if (marker.map !== state.mapId || !state.visibleTypes.has(marker.type)) continue;
      if (marker.collected && !showCollected) continue;
      const layer = L.marker(markerPosition(marker), { icon: markerIcon(marker), keyboard: false });
      bindPopup(marker, layer);
      layer.addTo(state.map);
      state.layers.set(marker.id, layer);
    }
  }

  function renderControls() {
    const player = $('#effigyPlayer');
    player.innerHTML = (state.data.players || []).map(item => `<option value="${esc(item.id)}">${esc(item.label)}</option>`).join('');
    if (state.data.selectedPlayer) player.value = state.data.selectedPlayer;
    const mapSelect = $('#effigyMap');
    mapSelect.innerHTML = Object.entries(state.data.maps).map(([id, map]) => `<option value="${id}">${esc(map.name)}</option>`).join('');
    mapSelect.value = state.mapId;
    const types = [...new Set(state.data.markers.map(marker => marker.type))].sort();
    const storedTypes = new Set(JSON.parse(localStorage.getItem('pals.effigies.visible-types.v1') || '[]'));
    state.visibleTypes = storedTypes.size ? new Set(types.filter(type => storedTypes.has(type))) : new Set(types);
    $('#effigyCount').textContent = state.data.loaded ? `${state.data.collected} / ${state.data.total}` : '—';
    $('#effigyCountLabel').textContent = state.data.loaded ? 'collected from synced save' : 'Map loaded; save data not loaded';
    $('#palsMeta').textContent = state.data.loaded ? `Loaded ${state.data.total} effigy locations · ${state.data.source}` : 'Effigy map loaded · sync or upload a save to load progress';
    const counts = new Map();
    state.data.markers.forEach(marker => counts.set(marker.type, (counts.get(marker.type) || 0) + (marker.collected ? 1 : 0)));
    $('#effigyLegend').innerHTML = types.map(type => `<label class="effigy-type-toggle"><input type="checkbox" data-type-toggle="${esc(type)}" ${state.visibleTypes.has(type) ? 'checked' : ''}><span class="legend-dot"></span><span>${esc(type)}</span><span class="effigy-type-count">${counts.get(type) || 0} collected</span></label>`).join('');
    $('#effigyLegend').querySelectorAll('[data-type-toggle]').forEach(input => input.addEventListener('change', () => {
      if (input.checked) state.visibleTypes.add(input.dataset.typeToggle); else state.visibleTypes.delete(input.dataset.typeToggle);
      localStorage.setItem('pals.effigies.visible-types.v1', JSON.stringify([...state.visibleTypes]));
      renderMap();
    }));
  }

  async function load(player = '') {
    const suffix = player ? `?player=${encodeURIComponent(player)}` : '';
    const response = await fetch(`${api}${suffix}`, { credentials: 'same-origin' });
    state.data = await response.json();
    if (!state.data.ok) throw new Error(state.data.error || 'Unable to load effigy data');
    loadHidden();
    renderControls();
    renderMap();
    const selected = state.data.players?.find(player => player.id === state.data.selectedPlayer);
    $('#liveStatus').textContent = state.data.source;
    $('#effigyPlayerStatus').textContent = state.data.loaded
      ? `Showing ${selected?.label || 'selected player'} · ${state.data.collected} / ${state.data.total} collected`
      : 'No decoded player save loaded';
  }

  async function sync() {
    const button = $('#refreshLiveSave');
    button.disabled = true;
    $('#liveStatus').textContent = 'Syncing save...';
    try {
      const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const response = await fetch('/pals/api/live-save/refresh', { method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf}, credentials: 'same-origin', body: JSON.stringify({ force: true }) });
      const result = await response.json();
      if (!result.ok && !result.refreshing) throw new Error(result.error || 'Save sync failed');
      if (result.refreshing) {
        for (let attempt = 0; attempt < 30; attempt += 1) {
          await new Promise(resolve => setTimeout(resolve, 1000));
          const status = await fetch('/pals/api/live-save/status', { credentials: 'same-origin' }).then(item => item.json());
          if (!status.refreshing) {
            if (status.lastResult && !status.lastResult.ok) throw new Error(status.lastResult.error || 'Save sync failed');
            break;
          }
        }
      }
      await load($('#effigyPlayer').value);
    } catch (error) { $('#liveStatus').textContent = error.message; }
    finally { button.disabled = false; }
  }

  async function uploadSave(file) {
    if (!file) return;
    $('#liveStatus').textContent = `Uploading ${file.name}...`;
    const form = new FormData();
    form.append('files', file, file.name);
    form.append('relativePaths', JSON.stringify([file.webkitRelativePath || file.name]));
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const response = await fetch('/pals/api/upload-save', { method: 'POST', headers: {'X-CSRFToken': csrf}, credentials: 'same-origin', body: form });
    const result = await response.json();
    if (!result.ok) throw new Error(result.error || 'Upload failed');
    await load();
  }

  $('#refreshLiveSave').addEventListener('click', () => sync().catch(error => { $('#liveStatus').textContent = error.message; }));
  $('#saveUpload').addEventListener('change', event => uploadSave(event.target.files?.[0]).catch(error => { $('#liveStatus').textContent = error.message; }));
  $('#effigyPlayer').addEventListener('change', event => load(event.target.value).catch(error => { $('#liveStatus').textContent = error.message; }));
  $('#effigyMap').addEventListener('change', event => { state.mapId = event.target.value; renderMap(); });
  $('#effigyShowCollected').addEventListener('change', renderMap);
  load().catch(error => { $('#liveStatus').textContent = error.message; });
})();
