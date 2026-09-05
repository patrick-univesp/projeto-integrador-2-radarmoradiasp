(function () {
  var elemento = document.getElementById('mapa-transacao');
  if (!elemento || typeof maplibregl === 'undefined') return;

  var lon = parseFloat(elemento.dataset.lon);
  var lat = parseFloat(elemento.dataset.lat);
  if (isNaN(lon) || isNaN(lat)) return;

  // T3/T4: coordenada sem precisão de lote — ponto vira halo difuso.
  var difuso = elemento.dataset.fuzzy === '1';
  // --accent literal: tokens.css declara a cor em oklch() e o parser do
  // MapLibre rejeita oklch num evento 'error' silencioso (ver mapa_regiao.js).
  var cor = '#A14512';

  var mapa = new maplibregl.Map({
    container: 'mapa-transacao',
    style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    center: [lon, lat],
    zoom: difuso ? 15 : 16.5,
    attributionControl: { compact: true }
  });
  mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  mapa.on('error', function (e) {
    if (window.console) console.error('mapa-transacao:', e.error || e);
  });

  mapa.on('load', function () {
    mapa.addSource('ponto', {
      type: 'geojson',
      data: { type: 'Point', coordinates: [lon, lat] }
    });
    mapa.addLayer({
      id: 'ponto-halo',
      type: 'circle',
      source: 'ponto',
      paint: {
        'circle-radius': difuso ? 13 : 8,
        'circle-color': cor,
        'circle-opacity': difuso ? 0.22 : 0.85,
        'circle-stroke-width': difuso ? 1 : 1.5,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-opacity': difuso ? 0.5 : 0.9
      }
    });
    if (difuso) {
      mapa.addLayer({
        id: 'ponto-centro',
        type: 'circle',
        source: 'ponto',
        paint: { 'circle-radius': 3, 'circle-color': cor, 'circle-opacity': 0.9 }
      });
    }
  });
})();
