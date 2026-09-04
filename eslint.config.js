// Lint de static/js/ (#19). Vendorizado (static/vendor/) fica de fora —
// MapLibre GL é terceiro, não é código nosso pra corrigir estilo.
const js = require("@eslint/js");
const globals = require("globals");

module.exports = [
  { ignores: ["static/vendor/**", "node_modules/**"] },
  js.configs.recommended,
  {
    files: ["static/js/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        ...globals.browser,
        // static/vendor/maplibre-gl.js expõe esse global via <script> comum
        // (sem module/import) — não é variável não declarada do nosso código.
        maplibregl: "readonly",
      },
    },
    rules: {
      "no-unused-vars": "error",
      // "Vazamento de escopo global": todo script daqui é um IIFE
      // (`(function () { ... })()`), nunca declara no escopo global.
      "no-implicit-globals": "error",
      // CSP de produção (config/settings/production.py) é script-src 'self',
      // sem unsafe-eval — código que dependesse de eval já quebraria em
      // produção; o lint pega isso antes do deploy.
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
    },
  },
];
