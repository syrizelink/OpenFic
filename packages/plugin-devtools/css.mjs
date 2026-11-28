// Generated from src/css.ts; do not edit.
import postcss, {} from "postcss";
import nesting from "postcss-nesting";
import selectorParser from "postcss-selector-parser";
import valueParser from "postcss-value-parser";
function decode(value) {
    return value.replace(/\\([0-9a-f]{1,6})\s?|\\(.)/gi, (_, hex, char) => hex ? String.fromCodePoint(Math.min(parseInt(hex, 16), 0x10ffff)) : char);
}
export function safeHref(value) {
    if (typeof value !== "string")
        return;
    try {
        const parsed = new URL(value);
        if (["https:", "http:"].includes(parsed.protocol))
            return parsed.href;
    }
    catch {
        // Invalid URLs render as text.
    }
}
function safeResource(value) {
    return Boolean(safeHref(value) ||
        /^data:image\/(?:png|jpeg|gif|webp|avif);base64,[a-z0-9+/=\s]+$/i.test(value));
}
function parseValue(value) {
    // value-parser treats the optional whitespace terminating a hex escape as a token
    // boundary. Six-digit escapes preserve the identifier without decoding syntax.
    return valueParser(value.replace(/\\(?:([0-9a-f]{1,6})(?:\r\n|[ \t\r\n\f])?|[^\r\n\f])/gi, (escape, hex) => (hex ? "\\" + hex.padStart(6, "0") : escape)));
}
export function safeCSSValue(value) {
    const decoded = decode(value).replace(/\/\*[\s\S]*?\*\//g, "");
    if (/expression\s*\(|javascript\s*:|vbscript\s*:|-moz-binding|behavior\s*:/i.test(decoded))
        return false;
    let valid = true;
    valueParser(decoded).walk((node) => {
        if ("unclosed" in node && node.unclosed)
            valid = false;
        if (node.type !== "function")
            return;
        const name = node.value.toLowerCase();
        if (name === "url") {
            const raw = valueParser.stringify(node.nodes).trim();
            const resource = node.nodes.length === 1 && node.nodes[0].type === "string" ? node.nodes[0].value : raw;
            if (!safeResource(resource))
                valid = false;
            return false;
        }
        if (/^(?:-webkit-)?image-set$/.test(name))
            for (const child of node.nodes)
                if (child.type === "string" && !safeResource(child.value))
                    valid = false;
    });
    return valid;
}
const animationProperty = /^(?:-webkit-)?animation(?:-name)?$/;
const animationKeywords = new Set("none infinite normal reverse alternate alternate-reverse forwards backwards both running paused ease ease-in ease-out ease-in-out linear step-start step-end initial inherit unset revert revert-layer".split(" "));
function rename(value, animations, nameOnly = false) {
    const parsed = parseValue(value);
    function visit(nodes) {
        for (const node of nodes) {
            if (node.type === "word" || node.type === "string") {
                const name = decode(node.value);
                if (animations.has(name) &&
                    (nameOnly || node.type === "string" || !animationKeywords.has(name))) {
                    node.value = animations.get(name);
                    if (node.type === "string")
                        node.quote = '"';
                }
            }
            else if (node.type === "function" && decode(node.value).toLowerCase() === "var") {
                const comma = node.nodes.findIndex((child) => child.type === "div" && child.value === ",");
                if (comma >= 0)
                    visit(node.nodes.slice(comma + 1));
            }
        }
    }
    visit(parsed.nodes);
    return parsed.toString();
}
function variableRefs(value) {
    const result = new Set();
    parseValue(value).walk((node) => {
        if (node.type === "function" && decode(node.value).toLowerCase() === "var") {
            const first = node.nodes.find((child) => child.type !== "space" && child.type !== "comment");
            if (first?.type === "word" && first.value.startsWith("--"))
                result.add(decode(first.value));
        }
    });
    return result;
}
function animationVariables(entries, inherited = new Set()) {
    const variables = new Set(inherited);
    for (const [property, value] of entries)
        if (animationProperty.test(property))
            for (const ref of variableRefs(value))
                variables.add(ref);
    let expanded = true;
    while (expanded) {
        expanded = false;
        for (const [property, value] of entries) {
            if (!variables.has(property))
                continue;
            for (const ref of variableRefs(value))
                if (!variables.has(ref)) {
                    variables.add(ref);
                    expanded = true;
                }
        }
    }
    return variables;
}
export function inlineStyle(props, animations, variables = new Set()) {
    const supplied = props.style;
    const result = {};
    if (supplied && typeof supplied === "object" && !Array.isArray(supplied)) {
        const entries = Object.entries(supplied)
            .filter(([, value]) => typeof value === "string")
            .map(([key, value]) => [
            key.startsWith("--") ? key : key.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase()),
            String(value),
        ]);
        const refs = animationVariables(entries, variables);
        for (const [key, value] of Object.entries(supplied)) {
            if (typeof value !== "string" && typeof value !== "number")
                continue;
            if (/^(?:behavior|-?moz-?binding)$/i.test(key) || !safeCSSValue(String(value)))
                continue;
            const normalized = key.startsWith("--")
                ? key
                : key.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
            const property = key.startsWith("--")
                ? key
                : key.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase());
            result[normalized] =
                typeof value === "string" && (animationProperty.test(property) || refs.has(property))
                    ? rename(value, animations, property.endsWith("animation-name"))
                    : value;
        }
    }
    if (props.bold || props.inverse)
        result.fontWeight = "bold";
    if (props.italic)
        result.fontStyle = "italic";
    if (props.dimColor)
        result.opacity = 0.65;
    if (props.inverse)
        result.background = "var(--gray-a4)";
    return result;
}
const budgetWarning = "Plugin stylesheet exceeds the depth/rule budget.";
const supportedGroups = new Set(["media", "supports", "container"]);
function isKeyframes(node) {
    return node.type === "atrule" && /^(?:-webkit-)?keyframes$/i.test(node.name ?? "");
}
function frameRule(rule) {
    return Boolean(rule.parent && isKeyframes(rule.parent));
}
function rootNode(node) {
    return ((node.type === "tag" && ["html", "body"].includes(node.value.toLowerCase())) ||
        (node.type === "pseudo" && [":root", ":scope"].includes(node.value.toLowerCase())));
}
/** Keep every matched subject inside the instance, including sibling/functional selectors. */
function scopedSelector(selector, scope) {
    const anchor = '[data-plugin-style-root="' + scope + '"]';
    const ast = selectorParser().astSync(selector);
    let count = 0;
    ast.walk(() => {
        if (++count > 4096)
            throw new Error(budgetWarning);
    });
    ast.walk((node) => {
        if (node.type !== "selector")
            return;
        // html > body, html.foo body.bar and :root body refer to the same plugin root.
        const nodes = [...node.nodes];
        let end = 0;
        const conditions = [];
        let roots = 0;
        while (end < nodes.length) {
            let next = end;
            while (next < nodes.length && nodes[next].type !== "combinator")
                next++;
            const compound = nodes.slice(end, next);
            if (!compound.some(rootNode))
                break;
            roots++;
            conditions.push(...compound.filter((part) => !rootNode(part)).map((part) => part.clone()));
            end = next;
            if (next >= nodes.length || !["", ">"].includes(nodes[next].value?.trim() ?? ""))
                break;
            // Leave the final combinator in place if the following compound is not a root.
            let stop = next + 1;
            while (stop < nodes.length && nodes[stop].type !== "combinator")
                stop++;
            if (!nodes.slice(next + 1, stop).some(rootNode))
                break;
            end = next + 1;
        }
        if (roots > 1) {
            for (const part of nodes.slice(0, end))
                part.remove();
            const replacement = [...selectorParser().astSync(anchor).first.nodes, ...conditions];
            for (const part of replacement.toReversed())
                node.prepend(part);
        }
    });
    ast.walk((node) => {
        if (rootNode(node))
            node.replaceWith(selectorParser().astSync(anchor).first.first.clone());
    });
    for (const selector of ast.nodes) {
        const guard = selectorParser()
            .astSync(":where(" + anchor + ", " + anchor + " *)")
            .first.first.clone();
        const lastCombinator = selector.nodes.findLastIndex((node) => node.type === "combinator");
        const pseudoElement = selector.nodes
            .slice(lastCombinator + 1)
            .find((node) => node.type === "pseudo" &&
            (node.value.startsWith("::") ||
                /^:(?:before|after|first-line|first-letter)$/i.test(node.value)));
        if (pseudoElement)
            selector.insertBefore(pseudoElement, guard);
        else
            selector.append(guard);
    }
    return ast.toString();
}
/** Pure PostCSS compilation: no CSSOM, browser parsing, @scope or network requests. */
export function scopeCSS(source, scope) {
    const animations = new Map();
    let variables = new Set();
    const warnings = new Set();
    const result = (css = "") => ({
        css,
        animations,
        animationVariables: variables,
        warnings: [...warnings],
    });
    if (!source)
        return result();
    if (!/^[a-zA-Z][\w-]{0,127}$/.test(scope)) {
        warnings.add("Invalid plugin style scope.");
        return result();
    }
    if (new TextEncoder().encode(source).length > 65536) {
        warnings.add(budgetWarning);
        return result();
    }
    try {
        const sheet = postcss.parse(source, { from: undefined });
        let count = 0;
        function sanitize(container, depth = 0, frames = false) {
            for (const node of [...(container.nodes ?? [])]) {
                if (++count > 8192 || depth > 32) {
                    node.remove();
                    warnings.add(budgetWarning);
                    continue;
                }
                node.raws = {};
                if (node.type === "comment") {
                    node.remove();
                    continue;
                }
                if (node.type === "atrule") {
                    node.name = decode(node.name).toLowerCase();
                    if (frames || !node.nodes || (!supportedGroups.has(node.name) && !isKeyframes(node))) {
                        node.remove();
                        warnings.add("Only component styles, media/supports/container queries and keyframes are supported.");
                        continue;
                    }
                    if (isKeyframes(node)) {
                        const name = parseValue(node.params).nodes.filter((part) => part.type !== "space" && part.type !== "comment");
                        if (name.length !== 1 || !["word", "string"].includes(name[0].type)) {
                            node.remove();
                            warnings.add("Invalid plugin keyframes.");
                            continue;
                        }
                        const original = decode(name[0].value);
                        if (!animations.has(original))
                            animations.set(original, scope +
                                "-kf" +
                                animations.size +
                                "-" +
                                (/^[a-zA-Z_][\w-]*$/.test(original) ? original : "animation"));
                        node.params = animations.get(original);
                    }
                    sanitize(node, depth + 1, isKeyframes(node));
                }
                else if (node.type === "rule") {
                    if (frames &&
                        !node.selector
                            .split(",")
                            .every((part) => /^(?:from|to|(?:\d+(?:\.\d+)?|\.\d+)%)$/i.test(part.trim()))) {
                        node.remove();
                        warnings.add("Invalid plugin keyframes.");
                        continue;
                    }
                    sanitize(node, depth + 1, frames);
                }
                else if (node.type === "decl") {
                    node.prop = decode(node.prop);
                    if (!node.prop.startsWith("--"))
                        node.prop = node.prop.toLowerCase();
                    if (/^(?:behavior|-?moz-?binding)$/i.test(node.prop) ||
                        !/^(?:--[\w-]+|-?[a-zA-Z][\w-]*)$/.test(node.prop) ||
                        !safeCSSValue(node.value)) {
                        node.remove();
                        warnings.add("A plugin style declaration was rejected.");
                    }
                }
            }
        }
        sanitize(sheet);
        // Flatten nesting before selector rewriting, including declarations inside nested media rules.
        const compiled = postcss([nesting()])
            .process(sheet, { from: undefined, map: false })
            .sync().root;
        let rules = 0;
        compiled.walkRules((rule) => {
            if (++rules > 2048) {
                rule.remove();
                warnings.add(budgetWarning);
                return;
            }
            if (frameRule(rule))
                return;
            try {
                rule.selector = scopedSelector(rule.selector, scope);
            }
            catch {
                rule.remove();
                warnings.add("A plugin style selector was rejected.");
            }
        });
        const entries = [];
        compiled.walkDecls((decl) => {
            entries.push([decl.prop, decl.value]);
        });
        variables = animationVariables(entries);
        compiled.walkDecls((decl) => {
            if (animationProperty.test(decl.prop) || variables.has(decl.prop))
                decl.value = rename(decl.value, animations, decl.prop.endsWith("animation-name"));
        });
        const css = compiled.toString();
        if (css.length > 512 * 1024) {
            warnings.add(budgetWarning);
            return result();
        }
        return result(css);
    }
    catch {
        warnings.add("Invalid plugin stylesheet.");
        return result();
    }
}
