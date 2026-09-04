/* Transição cinematográfica de busca com zoom no distrito - Radar da Moradia SP */
document.addEventListener('DOMContentLoaded', function() {
  const formBusca = document.querySelector('.hero__busca');
  const inputBusca = document.getElementById('q');
  const overlay = document.getElementById('radarTransicao');
  const mapaEl = document.getElementById('radarTransicaoMapa');
  if (!formBusca || !overlay || !mapaEl) return;

  const svg = mapaEl.querySelector('svg');

  const COORDENADAS_CENTRO = {
    'mooca': { nome: 'Mooca', origin: '49.5% 31.6%', slug: 'mooca' },
    'itaim-bibi': { nome: 'Itaim Bibi', origin: '30.5% 37.6%', slug: 'itaim-bibi' },
    'tatuape': { nome: 'Tatuapé', origin: '56.3% 28.1%', slug: 'tatuape' },
    'santana': { nome: 'Santana', origin: '42.2% 21.9%', slug: 'santana' },
    'vila-mariana': { nome: 'Vila Mariana', origin: '41.7% 34.9%', slug: 'vila-mariana' },
    'butanta': { nome: 'Butantã', origin: '21.1% 32.6%', slug: 'butanta' },
    'se': { nome: 'Sé', origin: '42.5% 29.0%', slug: 'se' },
    'pinheiros': { nome: 'Pinheiros', origin: '34.5% 32.6%', slug: 'pinheiros' }
  };

  function detectarRegiao(termo) {
    const limpo = (termo || '').trim().toLowerCase();
    for (const [slug, info] of Object.entries(COORDENADAS_CENTRO)) {
      if (limpo.includes(slug) || limpo.includes(info.nome.toLowerCase())) {
        return info;
      }
    }
    // Teste padrão: Mooca
    return COORDENADAS_CENTRO['mooca'];
  }

  function dispararTransicao(regiao, urlDestino) {
    if (!overlay || !svg) return;

    // 1. Destaca o distrito alvo
    svg.querySelectorAll('.distrito').forEach(d => d.classList.remove('distrito--alvo'));
    const pathAlvo = svg.querySelector('#distrito-' + regiao.slug);
    if (pathAlvo) {
      pathAlvo.classList.add('distrito--alvo');
    }

    // 3. Reseta o zoom e define ponto de foco (centro do distrito)
    svg.classList.remove('radar-transicao--zoom');
    svg.style.transformOrigin = regiao.origin;

    // 4. Exibe o overlay com o mapa COMPLETO de São Paulo
    overlay.classList.add('radar-transicao--ativa');

    // 5. Breve pausa para registrar o mapa inteiro e o ponto aceso antes do zoom
    setTimeout(function() {
      svg.classList.add('radar-transicao--zoom');
    }, 250);

    // 6. Conclui e navega para o destino ao final de 1.2s
    setTimeout(function() {
      window.location.href = urlDestino;
    }, 1200);
  }

  // Intercepta a submissão do formulário de busca
  formBusca.addEventListener('submit', function(e) {
    e.preventDefault();
    const termo = inputBusca ? inputBusca.value : '';
    const regiao = detectarRegiao(termo);
    const destino = '/regiao/' + regiao.slug + '/';
    dispararTransicao(regiao, destino);
  });

  // Intercepta também cliques nos atalhos rápidos da home
  document.querySelectorAll('.hero__atalhos .atalho').forEach(function(link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      const href = this.getAttribute('href');
      const partes = href.split('/').filter(Boolean);
      const slug = partes[partes.length - 1] || 'mooca';
      const regiao = COORDENADAS_CENTRO[slug] || detectarRegiao(this.textContent);
      dispararTransicao(regiao, href);
    });
  });
});
