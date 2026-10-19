import type { CSSProperties } from "react";

import type { UIProps } from "./declarative-schema";

function decode(value: string) {
  return value.replace(/\\([0-9a-f]{1,6})\s?|\\(.)/gi, (_, hex: string, char: string) =>
    hex ? String.fromCodePoint(Math.min(parseInt(hex, 16), 0x10ffff)) : char,
  );
}
export function safeHref(value: unknown): string | undefined {
  if (typeof value !== "string") return;
  try {
    const parsed = new URL(value);
    if (["https:", "http:"].includes(parsed.protocol)) return parsed.href;
  } catch {
    // Invalid URLs render as text.
  }
}
export function safeCSSValue(value: string) {
  const decoded = decode(value).replace(/\/\*[\s\S]*?\*\//g, "");
  if (/expression\s*\(|javascript\s*:|vbscript\s*:|-moz-binding|behavior\s*:/i.test(decoded))
    return false;
  for (const match of decoded.matchAll(/url\s*\(\s*(['"]?)(.*?)\1\s*\)/gi)) {
    if (!safeHref(match[2]) && !/^data:image\/(?:png|jpeg|gif|webp|avif);base64,/i.test(match[2]))
      return false;
  }
  return true;
}
function rename(value: string, animations: Map<string, string>) {
  let next = value;
  for (const [from, to] of animations)
    next = next.replace(new RegExp("(?<![\\w-])" + from + "(?![\\w-])", "g"), to);
  return next;
}
export function inlineStyle(props: UIProps, animations: Map<string, string>): CSSProperties {
  const supplied = props.style;
  const result: Record<string, string | number | undefined> = {};
  if (supplied && typeof supplied === "object" && !Array.isArray(supplied)) {
    for (const [key, value] of Object.entries(supplied)) {
      if (typeof value !== "string" && typeof value !== "number") continue;
      if (/^(?:behavior|MozBinding)$/i.test(key) || !safeCSSValue(String(value))) continue;
      const normalized = key.startsWith("--")
        ? key
        : key.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase());
      result[normalized] =
        typeof value === "string" && (/^animation/.test(key) || key.startsWith("--"))
          ? rename(value, animations)
          : value;
    }
  }
  if (props.bold || props.inverse) result.fontWeight = "bold";
  if (props.italic) result.fontStyle = "italic";
  if (props.dimColor) result.opacity = 0.65;
  if (props.inverse) result.background = "var(--gray-a4)";
  return result as CSSProperties;
}

/** Parse first, then scope canonical CSSOM rules. Plugin text is never concatenated as outer rules. */
export function scopeCSS(source: string, scope: string) {
  const animations = new Map<string, string>();
  const warnings = new Set<string>();
  if (!source) return { css: "", animations, warnings: [] as string[] };
  if (!("CSSScopeRule" in window))
    return {
      css: "",
      animations,
      warnings: ["This browser does not support scoped plugin styles."],
    };
  const sheet = new CSSStyleSheet();
  try {
    sheet.replaceSync(source);
  } catch {
    return { css: "", animations, warnings: ["Invalid plugin stylesheet."] };
  }
  let scanned = 0,
    rendered = 0;
  const budgetWarning = "Plugin stylesheet exceeds the depth/rule budget.";
  function findAnimations(rules: CSSRuleList, depth = 0) {
    if (depth > 32) {
      warnings.add(budgetWarning);
      return;
    }
    for (const rule of rules) {
      if (++scanned > 2048) {
        warnings.add(budgetWarning);
        break;
      }
      if (rule instanceof CSSKeyframesRule && /^[a-zA-Z_][\w-]*$/.test(rule.name))
        animations.set(rule.name, scope + "-" + rule.name);
      else if ("cssRules" in rule) findAnimations((rule as CSSGroupingRule).cssRules, depth + 1);
    }
  }
  findAnimations(sheet.cssRules);
  const frames: string[] = [];
  function declarations(style: CSSStyleDeclaration) {
    const values = [];
    for (const key of [...style]) {
      const value = style.getPropertyValue(key);
      if (key === "behavior" || key === "-moz-binding" || !safeCSSValue(value)) {
        warnings.add("A plugin style declaration was rejected.");
        continue;
      }
      const rewritten =
        key.startsWith("animation") || key.startsWith("--") ? rename(value, animations) : value;
      values.push(
        key + ":" + rewritten + (style.getPropertyPriority(key) ? " !important" : "") + ";",
      );
    }
    return values.join("");
  }
  function rules(list: CSSRuleList, conditions: string[] = [], depth = 0): string {
    if (depth > 32) {
      warnings.add(budgetWarning);
      return "";
    }
    return [...list]
      .map((rule) => {
        if (++rendered > 2048) {
          warnings.add(budgetWarning);
          return "";
        }
        if (typeof CSSNestedDeclarations !== "undefined" && rule instanceof CSSNestedDeclarations)
          return declarations(rule.style);
        if (rule instanceof CSSStyleRule) {
          const nested = "cssRules" in rule ? rules(rule.cssRules, conditions, depth + 1) : "";
          return rule.selectorText + "{" + declarations(rule.style) + nested + "}";
        }
        if (rule instanceof CSSMediaRule)
          return (
            "@media " +
            rule.conditionText +
            "{" +
            rules(rule.cssRules, [...conditions, "@media " + rule.conditionText], depth + 1) +
            "}"
          );
        if (rule instanceof CSSSupportsRule)
          return (
            "@supports " +
            rule.conditionText +
            "{" +
            rules(rule.cssRules, [...conditions, "@supports " + rule.conditionText], depth + 1) +
            "}"
          );
        if (typeof CSSContainerRule !== "undefined" && rule instanceof CSSContainerRule)
          return (
            "@container " +
            rule.conditionText +
            "{" +
            rules(rule.cssRules, [...conditions, "@container " + rule.conditionText], depth + 1) +
            "}"
          );
        if (rule instanceof CSSKeyframesRule && animations.has(rule.name)) {
          let frameText =
            "@keyframes " +
            animations.get(rule.name) +
            "{" +
            [...rule.cssRules]
              .map((frame) => {
                const key = frame as CSSKeyframeRule;
                return key.keyText + "{" + declarations(key.style) + "}";
              })
              .join("") +
            "}";
          for (const condition of conditions.toReversed())
            frameText = condition + "{" + frameText + "}";
          frames.push(frameText);
          return "";
        }
        warnings.add(
          "Only component styles, media/supports/container queries and keyframes are supported.",
        );
        return "";
      })
      .join("");
  }
  const scoped = rules(sheet.cssRules);
  return {
    css: frames.join("") + '@scope ([data-plugin-style-root="' + scope + '"]) {' + scoped + "}",
    animations,
    warnings: [...warnings],
  };
}
