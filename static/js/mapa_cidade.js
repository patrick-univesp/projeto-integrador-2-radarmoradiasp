(function () {
  var elemento = document.getElementById('mapa-cidade');
  if (!elemento || typeof maplibregl === 'undefined') return;

  var ano = elemento.dataset.ano;

  // Mesmo motivo de mapa_regiao.js: o token vem em oklch(), que o MapLibre não
  // entende; rasterizar num canvas 1×1 devolve um rgb() que ele aceita.
  function resolverCorToken(nomeVariavel, fallback) {
    var sonda = document.createElement('span');
    sonda.style.color = 'var(' + nomeVariavel + ')';
    document.body.appendChild(sonda);
    var valor = getComputedStyle(sonda).color;
    document.body.removeChild(sonda);
    try {
      var tela = document.createElement('canvas');
      tela.width = tela.height = 1;
      var ctx = tela.getContext('2d');
      ctx.fillStyle = valor;
      ctx.fillRect(0, 0, 1, 1);
      var px = ctx.getImageData(0, 0, 1, 1).data;
      return 'rgb(' + px[0] + ',' + px[1] + ',' + px[2] + ')';
    } catch {
      return fallback;
    }
  }

  // Faixa 0 = poucas vendas no período, sem valor típico.
  var cores = [
    resolverCorToken('--surface-3', '#E8E2DC'),
    resolverCorToken('--r1', '#C9EAEE'),
    resolverCorToken('--r2', '#8BD0D8'),
    resolverCorToken('--r3', '#41B0BC'),
    resolverCorToken('--r4', '#0093A1'),
    resolverCorToken('--r5', '#006A7B')
  ];
  var contorno = resolverCorToken('--bg', '#FBF8F5');

  var mapa = new maplibregl.Map({
    container: 'mapa-cidade',
    style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    center: [-46.63, -23.65],
    zoom: 9.2,
    attributionControl: { compact: true }
  });
  mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  mapa.on('error', function (e) {
    if (window.console) console.error('mapa-cidade:', e.error || e);
  });

  function montarPopup(d) {
    var conteudo = document.createElement('div');
    conteudo.className = 'cidade__popup';

    var nome = document.createElement('a');
    nome.className = 'cidade__popup-nome';
    nome.href = d.url;
    nome.textContent = d.nome;
    conteudo.appendChild(nome);

    var valor = document.createElement('p');
    if (d.mediana_fmt) {
      valor.textContent = 'R$ ' + d.mediana_fmt + '/m² · ' + d.n + (d.n === 1 ? ' venda' : ' vendas');
    } else {
      valor.textContent = 'Poucas vendas no período (' + d.n + '): sem valor típico.';
    }
    conteudo.appendChild(valor);

    var link = document.createElement('a');
    link.href = d.url;
    link.textContent = 'Ver a região →';
    conteudo.appendChild(link);
    return conteudo;
  }

  mapa.on('load', function () {
    var url = '/mapa/distritos.json' + (ano ? '?ano=' + encodeURIComponent(ano) : '');
    Promise.all([
      fetch('/static/data/distritos.geojson').then(function (r) { return r.json(); }),
      fetch(url).then(function (r) { return r.json(); })
    ]).then(function (respostas) {
      var geo = respostas[0];
      var porDistrito = {};
      respostas[1].distritos.forEach(function (d) { porDistrito[d.distrito] = d; });

      // Do geojson só se usa a geometria e o nome; os números vêm do servidor.
      geo.features.forEach(function (f, i) {
        var d = porDistrito[f.properties.distrito];
        f.id = i;
        f.properties = { distrito: f.properties.distrito, faixa: d ? d.faixa : 0 };
      });

      mapa.addSource('distritos', { type: 'geojson', data: geo });
      mapa.addLayer({
        id: 'distritos-preenchimento',
        type: 'fill',
        source: 'distritos',
        paint: {
          'fill-color': ['match', ['get', 'faixa'],
            1, cores[1], 2, cores[2], 3, cores[3], 4, cores[4], 5, cores[5], cores[0]],
          'fill-opacity': 0.85
        }
      });
      mapa.addLayer({
        id: 'distritos-contorno',
        type: 'line',
        source: 'distritos',
        paint: { 'line-color': contorno, 'line-width': 1 }
      });

      var limites = new maplibregl.LngLatBounds();
      geo.features.forEach(function (f) {
        var aneis = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
        aneis.forEach(function (poligono) {
          poligono[0].forEach(function (c) { limites.extend(c); });
        });
      });
      mapa.fitBounds(limites, { padding: 16, duration: 0 });

      mapa.on('click', 'distritos-preenchimento', function (e) {
        var d = porDistrito[e.features[0].properties.distrito];
        if (!d) return;
        new maplibregl.Popup({ closeButton: true, maxWidth: '260px' })
          .setLngLat(e.lngLat)
          .setDOMContent(montarPopup(d))
          .addTo(mapa);
      });
      mapa.on('mouseenter', 'distritos-preenchimento', function () { mapa.getCanvas().style.cursor = 'pointer'; });
      mapa.on('mouseleave', 'distritos-preenchimento', function () { mapa.getCanvas().style.cursor = ''; });
    }).catch(function (erro) {
      if (window.console) console.error('mapa-cidade:', erro);
    });
  });
})();
