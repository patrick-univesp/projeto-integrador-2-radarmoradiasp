(function () {
  function iniciarAutocomplete(campo, lista, aoSelecionar, comRuas) {
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

    function renderizar(sugestoes) {
      lista.innerHTML = '';
      opcoes = [];
      ativa = -1;

      if (sugestoes.length === 0) {
        const vazio = document.createElement('li');
        vazio.className = 'sugestoes__vazio';
        vazio.textContent = comRuas ? 'Nenhuma região ou rua encontrada' : 'Nenhuma região encontrada';
        lista.appendChild(vazio);
        lista.hidden = false;
        campo.setAttribute('aria-expanded', 'true');
        return;
      }

      sugestoes.forEach((s, indice) => {
        const li = document.createElement('li');
        li.id = lista.id + '-' + indice;
        li.className = 'sugestoes__item';
        li.setAttribute('role', 'option');
        li.dataset.slug = s.slug || '';
        li.dataset.url = s.url;
        li.textContent = s.texto;
        if (s.tipo === 'rua') {
          const tipo = document.createElement('span');
          tipo.className = 'sugestoes__tipo';
          tipo.textContent = 'rua';
          li.appendChild(tipo);
        }
        li.addEventListener('mousedown', function (e) {
          e.preventDefault();
          aoSelecionar(li.dataset);
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

      const url = '/api/sugestoes/?q=' + encodeURIComponent(termo) + (comRuas ? '&ruas=1' : '');
      fetch(url, { signal: controller.signal })
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
        aoSelecionar(opcoes[ativa].dataset);
      }
    });

    campo.addEventListener('blur', function () {
      // Espera o "mousedown" da opção rodar antes de fechar a lista — "click"
      // vem depois do "blur" e chegaria tarde demais.
      setTimeout(fechar, 150);
    });
  }

  // Busca da home: selecionar uma sugestão navega direto pra página da região
  // ou da rua (cada sugestão traz a própria URL).
  function navegar(item) {
    window.location.href = item.url;
  }

  // Comparação entre regiões: dois campos na mesma página, cada um só troca
  // o seu lado — preenche o próprio campo com o slug e reenvia o form (GET),
  // sem navegar pra fora da tela de comparação. Por isso só aceita região.
  function preencherESubmeter(campo, item) {
    campo.value = item.slug;
    campo.form.submit();
  }

  document.querySelectorAll('[data-autocomplete]').forEach(function (campo) {
    const lista = document.getElementById(campo.getAttribute('aria-controls'));
    const ehFormulario = campo.dataset.autocomplete === 'form';
    const aoSelecionar = ehFormulario ? (item) => preencherESubmeter(campo, item) : navegar;
    iniciarAutocomplete(campo, lista, aoSelecionar, !ehFormulario);
  });
})();
