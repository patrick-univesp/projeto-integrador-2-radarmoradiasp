(function () {
  const raiz = document.querySelector('[data-como-funciona]');
  if (!raiz) return;

  iniciarLuzes(raiz.querySelector('[data-luzes]'));

  const reduzido = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduzido || !('IntersectionObserver' in window)) return; // o HTML já está no estado final

  // --i escalona a animação dos filhos. Vai por CSSOM porque a CSP bloqueia style="".
  raiz.querySelectorAll('[data-escalonar]').forEach(function (lista) {
    Array.prototype.forEach.call(lista.children, function (filho, i) {
      filho.style.setProperty('--i', i);
    });
  });
  raiz.querySelectorAll('.gravacao').forEach(function (g) {
    g.style.setProperty('--n', g.querySelectorAll('.gravacao__bloco').length);
  });

  // Estação que já está na tela entra pronta, antes de o estado inicial existir:
  // assim nada pisca de pronto para vazio e de volta.
  const estacoes = raiz.querySelectorAll('[data-estacao]');
  const dobra = window.innerHeight * 0.8;
  estacoes.forEach(function (e) {
    if (e.getBoundingClientRect().top < dobra) e.classList.add('estacao--viva');
  });
  raiz.classList.add('cf--animado');

  const observador = new IntersectionObserver(function (entradas) {
    entradas.forEach(function (entrada) {
      if (!entrada.isIntersecting) return;
      entrada.target.classList.add('estacao--viva');
      observador.unobserve(entrada.target);
    });
  }, { rootMargin: '0px 0px -30% 0px' });

  estacoes.forEach(function (e) {
    if (!e.classList.contains('estacao--viva')) observador.observe(e);
  });

  function iniciarLuzes(caixa) {
    if (!caixa) return;
    const botoes = caixa.querySelectorAll('[data-bit]');
    const soma = caixa.querySelector('[data-luzes-soma]');
    const binario = caixa.querySelector('[data-luzes-binario]');
    const veredito = caixa.querySelector('[data-luzes-veredito]');
    const instrucao = caixa.querySelector('[data-luzes-instrucao]');
    let lista = null;

    if (instrucao) instrucao.hidden = false;

    botoes.forEach(function (botao) {
      botao.disabled = false;
      botao.addEventListener('click', function () {
        const aceso = botao.getAttribute('aria-pressed') === 'true';
        botao.setAttribute('aria-pressed', String(!aceso));
        atualizar();
      });
    });

    function atualizar() {
      let total = 0;
      const ressalvas = [];
      botoes.forEach(function (botao) {
        if (botao.getAttribute('aria-pressed') !== 'true') return;
        total += Number(botao.dataset.bit);
        ressalvas.push(botao.dataset.ressalva);
      });

      soma.textContent = String(total);
      binario.textContent = total.toString(2).padStart(botoes.length, '0');

      if (lista) {
        lista.remove();
        lista = null;
      }
      if (total === 0) {
        veredito.textContent = 'Nada acendeu: entra na mediana.';
        return;
      }
      veredito.textContent = 'Fica fora da mediana. A página da transação mostraria:';
      lista = document.createElement('ul');
      lista.className = 'luzes__ressalvas';
      ressalvas.forEach(function (texto) {
        const item = document.createElement('li');
        item.textContent = texto;
        lista.appendChild(item);
      });
      veredito.after(lista);
    }
  }
})();
