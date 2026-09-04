(function () {
  const campo = document.getElementById('q');
  const lista = document.getElementById('sugestoes-lista');
  if (!campo || !lista) return;

  const ESPERA_MS = 250;
  let timeoutId = null;
  let controller = null;
  let ativa = -1;
  let opcoes = [];

  function fechar() {
    lista.hidden = true;
    lista.innerHTML = '';
    campo.setAttribute('aria-expanded', 'false');
    campo.removeAttribute('aria-activedescendant');
    ativa = -1;
    opcoes = [];
  }

  function destacar(indice) {
    opcoes.forEach((li) => li.classList.remove('sugestoes__item--ativo'));
    ativa = indice;
    if (ativa >= 0 && opcoes[ativa]) {
      opcoes[ativa].classList.add('sugestoes__item--ativo');
      campo.setAttribute('aria-activedescendant', opcoes[ativa].id);
    } else {
      campo.removeAttribute('aria-activedescendant');
    }
  }

  function navegarPara(slug) {
    window.location.href = '/regiao/' + slug + '/';
  }

  function renderizar(sugestoes) {
    lista.innerHTML = '';
    opcoes = [];
    ativa = -1;

    if (sugestoes.length === 0) {
      const vazio = document.createElement('li');
      vazio.className = 'sugestoes__vazio';
      vazio.textContent = 'Nenhuma região encontrada';
      lista.appendChild(vazio);
      lista.hidden = false;
      campo.setAttribute('aria-expanded', 'true');
      return;
    }

    sugestoes.forEach((s, indice) => {
      const li = document.createElement('li');
      li.id = 'sugestao-' + indice;
      li.className = 'sugestoes__item';
      li.setAttribute('role', 'option');
      li.dataset.slug = s.slug;
      li.textContent = s.texto;
      li.addEventListener('mousedown', function (e) {
        e.preventDefault();
        navegarPara(li.dataset.slug);
      });
      lista.appendChild(li);
      opcoes.push(li);
    });

    lista.hidden = false;
    campo.setAttribute('aria-expanded', 'true');
  }

  function buscar(termo) {
    if (controller) controller.abort();
    controller = new AbortController();

    fetch('/api/sugestoes/?q=' + encodeURIComponent(termo), { signal: controller.signal })
      .then((r) => r.json())
      .then((dados) => renderizar(dados.sugestoes || []))
      .catch((erro) => {
        if (erro.name !== 'AbortError') fechar();
      });
  }

  // Nenhuma rua de SP começa com dígito: primeiro caractere numérico vira CEP,
  // sem sugestão nenhuma (#28) — só a máscara; a busca em si é o form submetendo.
  function ehModoCep(valor) {
    return /^\d/.test(valor);
  }

  function mascararCep(valor) {
    const digitos = valor.replace(/\D/g, '').slice(0, 8);
    return digitos.length > 5 ? digitos.slice(0, 5) + '-' + digitos.slice(5) : digitos;
  }

  campo.addEventListener('input', function () {
    let termo = campo.value;

    if (ehModoCep(termo)) {
      const mascarado = mascararCep(termo);
      if (mascarado !== termo) campo.value = mascarado;
      clearTimeout(timeoutId);
      fechar();
      return;
    }

    termo = termo.trim();
    clearTimeout(timeoutId);
    if (!termo) {
      fechar();
      return;
    }
    timeoutId = setTimeout(function () {
      buscar(termo);
    }, ESPERA_MS);
  });

  campo.addEventListener('keydown', function (e) {
    if (lista.hidden || opcoes.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      destacar((ativa + 1) % opcoes.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      destacar(ativa <= 0 ? opcoes.length - 1 : ativa - 1);
    } else if (e.key === 'Escape') {
      fechar();
    } else if (e.key === 'Enter' && ativa >= 0 && opcoes[ativa]) {
      e.preventDefault();
      navegarPara(opcoes[ativa].dataset.slug);
    }
  });

  campo.addEventListener('blur', function () {
    // Espera o "mousedown" da opção rodar antes de fechar a lista — "click"
    // vem depois do "blur" e chegaria tarde demais.
    setTimeout(fechar, 150);
  });
})();
