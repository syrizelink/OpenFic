import { expect, test } from "@playwright/test";
import postcss from "postcss";

import { inlineStyle, safeCSSValue, scopeCSS } from "../src/features/plugins/declarative-css";

test.use({ video: "off" });

test("compiles nesting without browser CSSOM or native scope", () => {
  expect(typeof window).toBe("undefined");
  const result = scopeCSS(
    `
    :scope { --color: teal; }
    .card { color: var(--color); & > button { padding: 4px; }
      @media (min-width: 1px) { letter-spacing: 1px; }
    }
    @supports (display: grid) { @container (min-width: 1px) { .item { display: grid; } } }
  `,
    "instance-a",
  );
  expect(result.warnings).toEqual([]);
  expect(result.css).not.toContain("@scope");
  expect(result.css).not.toContain("&");
  expect(result.css).toContain(".card > button:where(");
  expect(result.css).toContain("@media");
  expect(result.css).toContain("@supports");
  expect(result.css).toContain("@container");
  const sheet = postcss.parse(result.css);
  sheet.walkRules((rule) => expect(rule.selector).toContain('data-plugin-style-root="instance-a"'));
});

test("namespaces keyframes, animation lists, fallback variables and inline styles", () => {
  const result = scopeCSS(
    `
    @keyframes pulse { from { opacity: .5; } to { opacity: 1; } }
    @media (min-width: 1px) { @-webkit-keyframes "other name" { 0%, 100% { opacity: 1; } } }
    @keyframes red { to { opacity: 1; } }
    :scope { --color: red; --first: var(--second); --second: pulse 1s linear; }
    .a { ANIMATION: var(--first, pulse 1s), "other name" 2s; animation-name: red; color: var(--color); }
  `,
    "instance-a",
  );
  expect(result.warnings).toEqual([]);
  const pulse = result.animations.get("pulse")!;
  expect(result.css).toContain("--color: red");
  expect(result.css).toContain("--second: " + pulse + " 1s linear");
  expect(result.css).toContain("var(--first, " + pulse + " 1s)");
  expect(result.css).toContain('"' + result.animations.get("other name") + '" 2s');
  expect(result.animationVariables).toEqual(new Set(["--first", "--second"]));
  const style = inlineStyle(
    {
      style: {
        animation: "var(--inline, pulse 1s)",
        "--inline": "var(--second)",
        "--second": "pulse 2s",
        "--color": "red",
        animationName: "red",
      },
    },
    result.animations,
    result.animationVariables,
  );
  expect(style).toMatchObject({
    animation: "var(--inline, " + pulse + " 1s)",
    "--second": pulse + " 2s",
    "--color": "red",
    animationName: result.animations.get("red"),
  });
  const sheet = postcss.parse(result.css);
  sheet.walkAtRules(/keyframes$/, (rule) => {
    expect(rule.params).toMatch(/^instance-a-kf/);
    rule.walkRules((frame) => expect(frame.selector).not.toContain("data-plugin"));
  });
  expect(
    scopeCSS("@keyframes pulse { to {opacity:1} }", "instance-b").animations.get("pulse"),
  ).not.toBe(pulse);
});

test("escaped and quoted animation identifiers are parsed without rewriting timing keywords", () => {
  const result = scopeCSS(
    String.raw`
    @keyframes p\75 lse { to { opacity: 1; } }
    @keyframes linear { to { opacity: 1; } }
    .x { animation: p\75 lse 1s linear; animation-name: linear; }
  `,
    "instance-a",
  );
  expect(result.animations.has("pulse")).toBe(true);
  expect(result.css).toContain(result.animations.get("pulse") + " 1s linear");
  expect(result.css).toContain("animation-name: " + result.animations.get("linear"));
});

test("drops global registrations and unsafe declarations without dropping valid rules", () => {
  const result = scopeCSS(
    String.raw`
    @import "https://invalid.example/global.css";
    @font-face { font-family: bad; src: url(https://invalid.example/font); }
    @property --global { syntax: "*"; inherits: true; }
    @page { margin: 0; }
    @scope (body) { button { color: red; } }
    .ok { color: teal; background: u\72l(javascript:alert(1)); behavior: url(https://example.com/x); }
    .also { background: image-set("file:///private" 1x); }
  `,
    "instance-a",
  );
  expect(result.css).toContain("color: teal");
  for (const forbidden of [
    "@import",
    "@font-face",
    "@property",
    "@page",
    "@scope",
    "javascript",
    "behavior",
    "file:",
  ])
    expect(result.css).not.toContain(forbidden);
  expect(result.warnings).toContain("A plugin style declaration was rejected.");
});

test("validates URL forms and inline styles using the same resource policy", () => {
  for (const value of [
    "url(https://example.com/x.png)",
    "url('data:image/png;base64,AAAA')",
    "image-set('https://example.com/x.png' 1x)",
    "var(--color)",
  ])
    expect(safeCSSValue(value), value).toBe(true);
  for (const value of [
    String.raw`u\72l(ja\76 ascript:alert(1))`,
    "url(file:///secret)",
    "url(data:image/svg+xml;base64,AAAA)",
    "expression(alert(1))",
    "image-set('javascript:evil' 1x)",
    "url('https://example.com/unclosed)",
  ])
    expect(safeCSSValue(value), value).toBe(false);
  expect(
    inlineStyle(
      {
        style: {
          color: "teal",
          background: "url(file:///secret)",
          MozBinding: "url(https://example.com)",
          padding: 4,
        },
      },
      new Map(),
    ),
  ).toEqual({ color: "teal", padding: 4 });
});

test("rejects malformed styles, invalid scopes and excessive input and rule depth", () => {
  expect(scopeCSS(".x {", "instance-a").css).toBe("");
  expect(scopeCSS("button{color:red}", 'bad"] body').css).toBe("");
  expect(scopeCSS("/*" + "x".repeat(65536) + "*/", "instance-a").css).toBe("");
  const deep = scopeCSS(".a {".repeat(40) + "color:red" + "}".repeat(40), "instance-a");
  expect(deep.warnings).toContain("Plugin stylesheet exceeds the depth/rule budget.");
  const many = scopeCSS(".a{color:red}".repeat(2100), "instance-a");
  expect(many.warnings).toContain("Plugin stylesheet exceeds the depth/rule budget.");
  expect(scopeCSS("", "instance-a")).toMatchObject({ css: "", warnings: [] });
});

test("browser renders roots, nesting, form fields, pseudos and portals while containing hostile selectors", async ({
  page,
}) => {
  await page.setContent(`
    <style>body,button,input,textarea{color:rgb(30,30,30)}</style>
    <button id="outside">Outside</button>
    <div data-plugin-style-root="instance-a"><button class="target">Inside</button><input><textarea></textarea><span class="pseudo">Text</span></div>
    <button id="after">After</button>
    <div data-plugin-style-root="instance-b"><button class="target">Other plugin</button></div>
    <div data-plugin-style-root="instance-a" data-portal><button class="target">Portal</button></div>
  `);
  const result = scopeCSS(
    String.raw`
    html > body { --root-color: rgb(10,20,30); }
    :root .target { color: var(--root-color); @media (min-width: 1px) { letter-spacing: 2px; } }
    b\6f dy input, :scope textarea { color: rgb(40,50,60); }
    .pseudo::before { content: "Scoped"; color: rgb(70,80,90); }
    :is(:scope + #after, #outside), :scope ~ button, :not(.missing)#outside { color: rgb(255,0,0) !important; }
  `,
    "instance-a",
  );
  expect(result.warnings).toEqual([]);
  await page.addStyleTag({ content: result.css });
  for (const selector of ["#outside", "#after", '[data-plugin-style-root="instance-b"] button'])
    await expect(page.locator(selector)).toHaveCSS("color", "rgb(30, 30, 30)");
  const targets = page.locator('[data-plugin-style-root="instance-a"] button');
  for (const button of await targets.all()) {
    await expect(button).toHaveCSS("color", "rgb(10, 20, 30)");
    await expect(button).toHaveCSS("letter-spacing", "2px");
  }
  for (const selector of ["input", "textarea"])
    await expect(page.locator(selector)).toHaveCSS("color", "rgb(40, 50, 60)");
  expect(
    await page.locator(".pseudo").evaluate((el) => getComputedStyle(el, "::before").content),
  ).toBe('"Scoped"');
});
