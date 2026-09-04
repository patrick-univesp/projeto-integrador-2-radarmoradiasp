(function () {
  const painel = document.getElementById('serie-painel');
  if (!painel) return;

  const mesEl = document.getElementById('serie-painel-mes');
  const valorEl = document.getElementById('serie-painel-valor');
  const nEl = document.getElementById('serie-painel-n');
  const avisoEl = document.getElementById('serie-painel-aviso');

  const pontos = document.querySelectorAll('.serie__ponto-grupo');
  if (!pontos.length) return;

  function ativarPonto(ponto) {
    pontos.forEach(function (p) {
      p.classList.remove('serie__ponto-grupo--ativo');
    });
    ponto.classList.add('serie__ponto-grupo--ativo');

    const mes = ponto.dataset.mes;
    const valor = ponto.dataset.valor;
    const n = ponto.dataset.n;
    const fraco = ponto.dataset.fraco === '1';

    if (mesEl && mes) mesEl.textContent = mes;
    if (valorEl && valor) valorEl.textContent = valor;
    if (nEl && n) nEl.textContent = '(' + n + ')';
    if (avisoEl) {
      if (fraco) {
        avisoEl.classList.remove('serie__painel-aviso--oculto');
      } else {
        avisoEl.classList.add('serie__painel-aviso--oculto');
      }
    }
  }

  pontos.forEach(function (ponto) {
    ponto.addEventListener('pointerenter', function () {
      ativarPonto(ponto);
    });
    ponto.addEventListener('click', function () {
      ativarPonto(ponto);
    });
    ponto.addEventListener('focus', function () {
      ativarPonto(ponto);
    });
  });
})();
