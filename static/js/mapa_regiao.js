(function () {
  var elemento = document.getElementById('mapa-regiao');
  if (!elemento || typeof maplibregl === 'undefined') return;

  var slug = elemento.dataset.slug;
  var distrito = elemento.dataset.distrito;
  var ano = elemento.dataset.ano;

  // tokens.css declara --accent em oklch() por cima do hex; getComputedStyle
  // devolve o oklch() de volta, e o parser de cor do MapLibre não entende
  // isso (rejeita a camada num evento 'error' silencioso, sem exceção).
  // Canvas sempre rasteriza qualquer cor CSS válida pra pixel concreto —
  // ler o pixel de volta dá um rgb() que o MapLibre aceita.
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
  var cor = resolverCorToken('--accent', '#A14512');

  function mostrarVazio(texto) {
    var vazio = document.createElement('p');
    vazio.className = 'mapa-regiao__vazio';
    vazio.textContent = texto;
    mapa.remove();
    elemento.replaceWith(vazio);
  }

  var mapa = new maplibregl.Map({
    container: 'mapa-regiao',
    style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    center: [-46.633, -23.55],
    zoom: 11,
    attributionControl: { compact: true }
  });
  mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  mapa.on('error', function (e) {
    if (window.console) console.error('mapa-regiao:', e.error || e);
  });

  function montarPopup(props) {
    var conteudo = document.createElement('div');
    conteudo.className = 'mapa-regiao__popup';

    var endereco = document.createElement('a');
    endereco.className = 'mapa-regiao__popup-endereco';
    endereco.href = '/transacao/' + props.id + '/';
    endereco.textContent = props.endereco;
    conteudo.appendChild(endereco);

    var linhas = document.createElement('dl');
    function linha(rotulo, valor) {
      var dt = document.createElement('dt');
      dt.textContent = rotulo;
      var dd = document.createElement('dd');
      dd.textContent = valor;
      linhas.appendChild(dt);
      linhas.appendChild(dd);
    }
    linha('valor', 'R$ ' + props.valor_fmt);
    linha('R$/m²', props.rs_m2_fmt ? 'R$ ' + props.rs_m2_fmt : 'não aplicável');
    linha('data', props.data || '—');
    conteudo.appendChild(linhas);

    if (props.aproximado) {
      var aviso = document.createElement('p');
      aviso.className = 'mapa-regiao__popup-aviso';
      aviso.textContent = 'Localização aproximada: centroide da quadra, cerca de 100 m.';
      conteudo.appendChild(aviso);
    }
    return conteudo;
  }

  mapa.on('load', function () {
    fetch('/static/data/distritos.geojson')
      .then(function (r) { return r.json(); })
      .then(function (geo) {
        var contorno = geo.features.find(function (f) { return f.properties.distrito === distrito; });
        if (!contorno) return;
        mapa.addSource('contorno-distrito', { type: 'geojson', data: contorno });
        mapa.addLayer({
          id: 'contorno-distrito-preenchimento', type: 'fill', source: 'contorno-distrito',
          paint: { 'fill-color': cor, 'fill-opacity': 0.06 }
        });
        mapa.addLayer({
          id: 'contorno-distrito-linha', type: 'line', source: 'contorno-distrito',
          paint: { 'line-color': cor, 'line-width': 2 }
        });
      })
      .catch(function () {});

    fetch('/regiao/' + slug + '/pontos.geojson' + (ano ? '?ano=' + encodeURIComponent(ano) : ''))
      .then(function (r) { return r.json(); })
      .then(function (pontos) {
        if (!pontos.features.length) {
          mostrarVazio('Nenhuma transação georreferenciada nesta região.');
          return;
        }

        mapa.addSource('pontos-transacoes', { type: 'geojson', data: pontos });
        mapa.addLayer({
          id: 'pontos-transacoes-circulo',
          type: 'circle',
          source: 'pontos-transacoes',
          paint: {
            'circle-radius': 6,
            'circle-color': cor,
            'circle-stroke-width': 1.5,
            'circle-stroke-color': '#ffffff',
            'circle-opacity': ['case', ['get', 'aproximado'], 0.4, 0.9],
            'circle-stroke-opacity': ['case', ['get', 'aproximado'], 0.4, 0.9]
          }
        });

        var limites = new maplibregl.LngLatBounds();
        pontos.features.forEach(function (f) { limites.extend(f.geometry.coordinates); });
        mapa.fitBounds(limites, { padding: 32, maxZoom: 16 });

        mapa.on('click', 'pontos-transacoes-circulo', function (e) {
          new maplibregl.Popup({ closeButton: true, maxWidth: '260px' })
            .setLngLat(e.features[0].geometry.coordinates.slice())
            .setDOMContent(montarPopup(e.features[0].properties))
            .addTo(mapa);
        });
        mapa.on('mouseenter', 'pontos-transacoes-circulo', function () {
          mapa.getCanvas().style.cursor = 'pointer';
        });
        mapa.on('mouseleave', 'pontos-transacoes-circulo', function () {
          mapa.getCanvas().style.cursor = '';
        });
      })
      .catch(function () {
        mostrarVazio('Não foi possível carregar o mapa desta região agora.');
      });
  });
})();
