(function () {
  const input = document.getElementById('q');
  if (!input) return;

  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  const padrao = 'Digite um bairro, rua ou CEP de São Paulo';

  const exemplos = [
    'Pinheiros',
    'Mooca',
    'Vila Mariana',
    'Itaim Bibi',
    'Tatuapé',
    '01310-100',
    '04538-133',
    '03162-020',
    '05407-002',
    '04001-001',
    'Avenida Paulista',
    'Rua Augusta',
    'Rua Oscar Freire',
    'Avenida Faria Lima',
    'Avenida Rebouças'
  ];

  for (let i = exemplos.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [exemplos[i], exemplos[j]] = [exemplos[j], exemplos[i]];
  }

  const fila = [];
  for (let i = 0; i < exemplos.length; i++) {
    fila.push(padrao);
    fila.push(exemplos[i]);
  }

  let index = 0;
  let charIndex = padrao.length;
  let apagando = true;
  let timeoutId = null;
  let ativo = true;

  function ciclo() {
    if (!ativo) return;

    const textoAtual = fila[index];

    if (!apagando) {
      charIndex++;
      input.setAttribute('placeholder', textoAtual.slice(0, charIndex));

      if (charIndex === textoAtual.length) {
        apagando = true;
        const espera = textoAtual === padrao ? 2400 : 1400;
        timeoutId = setTimeout(ciclo, espera);
        return;
      }
      const vel = textoAtual === padrao ? 28 : (35 + Math.random() * 20);
      timeoutId = setTimeout(ciclo, vel);
    } else {
      charIndex--;
      input.setAttribute('placeholder', textoAtual.slice(0, charIndex));

      if (charIndex === 0) {
        apagando = false;
        index = (index + 1) % fila.length;
        timeoutId = setTimeout(ciclo, 250);
        return;
      }
      timeoutId = setTimeout(ciclo, 18);
    }
  }

  function parar() {
    ativo = false;
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    input.setAttribute('placeholder', padrao);
  }

  function retomar() {
    if (input.value.trim() !== '') return;
    ativo = true;
    charIndex = 0;
    apagando = false;
    ciclo();
  }

  input.addEventListener('focus', parar);
  input.addEventListener('blur', retomar);

  timeoutId = setTimeout(ciclo, 2200);
})();
