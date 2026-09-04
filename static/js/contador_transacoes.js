(function () {
  const el = document.querySelector('[data-contador]');
  if (!el) return;

  const alvo = parseInt(el.dataset.contador, 10);
  if (!Number.isFinite(alvo)) return;

  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return; // o HTML já traz o valor final
  }

  const duracao = 900;
  let inicio = null;

  function passo(agora) {
    if (inicio === null) inicio = agora;
    const t = Math.min((agora - inicio) / duracao, 1);
    const suavizado = 1 - Math.pow(1 - t, 3); // ease-out cubic
    el.textContent = Math.floor(suavizado * alvo).toLocaleString('pt-BR');
    if (t < 1) {
      requestAnimationFrame(passo);
    } else {
      el.textContent = alvo.toLocaleString('pt-BR');
    }
  }

  requestAnimationFrame(passo);
})();
