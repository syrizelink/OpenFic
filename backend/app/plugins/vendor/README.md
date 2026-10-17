# Claude Mods source transformer

`transpiler.js` is Sucrase 3.35.1 bundled with esbuild 0.25.12 for QuickJS. It transforms TypeScript, JSX (h/Fragment), and ES module syntax; user machines do not need Node. Bundled dependencies retain their licenses in LICENSES.txt.

Rebuild in a temporary npm project with these exact versions. Entry:

```js
import { transform } from "sucrase";
globalThis.__transpile = code => transform(code, { transforms: ["typescript", "jsx", "imports"], jsxPragma: "h", jsxFragmentPragma: "Fragment", production: true, disableESTransforms: true }).code;
```

Command: `esbuild entry.js --bundle --format=iife --platform=browser --minify --outfile=transpiler.js`.
