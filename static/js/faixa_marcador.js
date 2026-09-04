(function () {
  // Posição em atributo data-, não em <style> inline — a CSP de produção
  // (#11) bloqueia style inline sem aviso nenhum. .style.left é CSSOM, a CSP
  // não restringe isso.
  document.querySelectorAll('.faixa__marcador[data-pos]').forEach(function (el) {
    el.style.left = el.dataset.pos + '%';
  });
})();
