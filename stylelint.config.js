// Lint de static/css/ (#19), sobre stylelint-config-standard. Boa parte das
// regras padrão do config-standard empurra pra uma convenção de formatação
// mais espaçada e pra uma reescrita "modernizada" de notação de cor — nenhuma
// das duas é bug, e aplicar as duas aqui reescreveria os valores exatos de
// tokens.css já auditados (contraste WCAG, ver interface.md) sem ganho
// nenhum. Cada bloco abaixo desliga por um motivo concreto, não “porque
// incomodou”.
module.exports = {
  extends: "stylelint-config-standard",
  ignoreFiles: ["static/vendor/**", "staticfiles/**", "node_modules/**"],
  rules: {
    // Nomenclatura BEM-ish em português (`.transacoes__item`, `--r-ink-alto`)
    // não bate com o padrão kebab-case simples que o config-standard espera.
    "custom-property-pattern": null,
    "selector-class-pattern": null,

    // tokens.css declara toda cor duas vezes de propósito — hex primeiro,
    // oklch() por cima (fallback pra navegador sem suporte a oklch). Isso é
    // "duplicata" pro linter, mas é a técnica documentada, não descuido.
    "declaration-block-no-duplicate-custom-properties": null,

    // Reescreveria oklch(0.505 0.135 45) -> oklch(50.5% 0.135 45deg) e por
    // aí em diante em toda cor do tokens.css — mudança de notação, não de
    // valor, mas mecânica demais pra arriscar num arquivo onde já se
    // reverteu ajuste de contraste por engano (CLAUDE.md).
    "lightness-notation": null,
    "hue-degree-notation": null,
    "alpha-value-notation": null,
    "color-function-notation": null,
    "color-function-alias-notation": null,
    "color-hex-length": null,

    // -webkit-mask-image, -webkit-backdrop-filter e -webkit-text-size-adjust
    // são compatibilidade real com Safari, não sobra de outra época.
    "property-no-vendor-prefix": null,

    // O projeto usa min-width/max-width consistentemente; a notação de
    // intervalo (`width >= 720px`) é só outro jeito de escrever a mesma
    // coisa — reescrever toda media query não muda nada funcional.
    "media-feature-range-notation": null,

    // Convenção de espaçamento do projeto é mais compacta que o padrão do
    // config-standard (regra colada na anterior, reset de uma linha só como
    // `ul { padding: 0; list-style: none; }`). Reformatar tudo agora é
    // churn grande sem valor — quem quiser, roda com --fix separado.
    "rule-empty-line-before": null,
    "at-rule-empty-line-before": null,
    "custom-property-empty-line-before": null,
    "comment-empty-line-before": null,
    "declaration-block-single-line-max-declarations": null,

    // "Menlo" é o nome próprio da fonte (macOS); não precisa virar minúsculo.
    "value-keyword-case": null,
  },
};
