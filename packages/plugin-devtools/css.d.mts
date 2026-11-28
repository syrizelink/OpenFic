export function safeHref(value: unknown): string | undefined;
export function safeCSSValue(value: string): boolean;
export function inlineStyle(props: Record<string, unknown>, animations: Map<string, string>, variables?: Set<string>): Record<string, string | number | undefined>;
export function scopeCSS(source: string, scope: string): { css: string; warnings: string[]; animations: Map<string, string>; animationVariables: Set<string> };
