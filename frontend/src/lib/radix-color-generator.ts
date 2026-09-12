/**
 * Radix Custom palette generator adapted from radix-ui/website.
 * Source: https://github.com/radix-ui/website/blob/main/components/generate-radix-colors.tsx
 * The source repository is MIT licensed.
 */

import * as RadixColors from "@radix-ui/colors";
import BezierEasing from "bezier-easing";
import Color from "colorjs.io";

type ArrayOf12<T> = [T, T, T, T, T, T, T, T, T, T, T, T];

const arrayOf12 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] as const;
const grayScaleNames = ["gray", "mauve", "slate", "sage", "olive", "sand"] as const;
const scaleNames = [
  ...grayScaleNames,
  "tomato",
  "red",
  "ruby",
  "crimson",
  "pink",
  "plum",
  "purple",
  "violet",
  "iris",
  "indigo",
  "blue",
  "cyan",
  "teal",
  "jade",
  "green",
  "grass",
  "brown",
  "orange",
  "sky",
  "mint",
  "lime",
  "yellow",
  "amber",
] as const;

type ScaleName = (typeof scaleNames)[number];

const lightColors = Object.fromEntries(
  scaleNames.map((scaleName) => [
    scaleName,
    Object.values(RadixColors[`${scaleName}P3`]).map((value) => new Color(value).to("oklch")),
  ]),
) as Record<ScaleName, ArrayOf12<Color>>;

const darkColors = Object.fromEntries(
  scaleNames.map((scaleName) => [
    scaleName,
    Object.values(RadixColors[`${scaleName}DarkP3`]).map((value) => new Color(value).to("oklch")),
  ]),
) as Record<ScaleName, ArrayOf12<Color>>;

const lightGrayColors = Object.fromEntries(
  grayScaleNames.map((scaleName) => [
    scaleName,
    Object.values(RadixColors[`${scaleName}P3`]).map((value) => new Color(value).to("oklch")),
  ]),
) as Record<(typeof grayScaleNames)[number], ArrayOf12<Color>>;

const darkGrayColors = Object.fromEntries(
  grayScaleNames.map((scaleName) => [
    scaleName,
    Object.values(RadixColors[`${scaleName}DarkP3`]).map((value) => new Color(value).to("oklch")),
  ]),
) as Record<(typeof grayScaleNames)[number], ArrayOf12<Color>>;

export interface GeneratedRadixColors {
  accentScale: ArrayOf12<string>;
  accentScaleAlpha: ArrayOf12<string>;
  accentScaleWideGamut: ArrayOf12<string>;
  accentScaleAlphaWideGamut: ArrayOf12<string>;
  accentContrast: string;
  grayScale: ArrayOf12<string>;
  grayScaleAlpha: ArrayOf12<string>;
  grayScaleWideGamut: ArrayOf12<string>;
  grayScaleAlphaWideGamut: ArrayOf12<string>;
  graySurface: string;
  graySurfaceWideGamut: string;
  accentSurface: string;
  accentSurfaceWideGamut: string;
  background: string;
}

export function generateRadixColors({
  appearance,
  accent,
  gray,
  background,
}: {
  appearance: "light" | "dark";
  accent: string;
  gray: string;
  background: string;
}): GeneratedRadixColors {
  const allScales = appearance === "light" ? lightColors : darkColors;
  const grayScales = appearance === "light" ? lightGrayColors : darkGrayColors;
  const backgroundColor = new Color(background).to("oklch");

  const grayBaseColor = new Color(gray).to("oklch");
  const grayScaleColors = getScaleFromColor(grayBaseColor, grayScales, backgroundColor);

  const accentBaseColor = new Color(accent).to("oklch");
  let accentScaleColors = getScaleFromColor(accentBaseColor, allScales, backgroundColor);

  const backgroundHex = backgroundColor.to("srgb").toString({ format: "hex" });
  const accentBaseHex = accentBaseColor.to("srgb").toString({ format: "hex" });

  if (accentBaseHex === "#000" || accentBaseHex === "#fff") {
    accentScaleColors = grayScaleColors.map((color) => color.clone()) as ArrayOf12<Color>;
  }

  const [accent9Color, accentContrastColor] = getStep9Colors(accentScaleColors, accentBaseColor);
  accentScaleColors[8] = accent9Color;
  accentScaleColors[9] = getButtonHoverColor(accent9Color, [accentScaleColors]);

  const textChromaFloor = Math.max(
    getNumericCoordinate(accentScaleColors[8].coords[1]),
    getNumericCoordinate(accentScaleColors[7].coords[1]),
  );
  accentScaleColors[10].coords[1] = Math.min(
    textChromaFloor,
    getNumericCoordinate(accentScaleColors[10].coords[1]),
  );
  accentScaleColors[11].coords[1] = Math.min(
    textChromaFloor,
    getNumericCoordinate(accentScaleColors[11].coords[1]),
  );

  const accentScaleHex = accentScaleColors.map((color) =>
    color.to("srgb").toString({ format: "hex" }),
  ) as ArrayOf12<string>;
  const accentScaleWideGamut = accentScaleColors.map(toOklchString) as ArrayOf12<string>;
  const accentScaleAlpha = accentScaleHex.map((color) =>
    getAlphaColorSrgb(color, backgroundHex),
  ) as ArrayOf12<string>;
  const accentScaleAlphaWideGamut = accentScaleHex.map((color) =>
    getAlphaColorP3(color, backgroundHex),
  ) as ArrayOf12<string>;

  const grayScaleHex = grayScaleColors.map((color) =>
    color.to("srgb").toString({ format: "hex" }),
  ) as ArrayOf12<string>;
  const grayScaleWideGamut = grayScaleColors.map(toOklchString) as ArrayOf12<string>;
  const grayScaleAlpha = grayScaleHex.map((color) =>
    getAlphaColorSrgb(color, backgroundHex),
  ) as ArrayOf12<string>;
  const grayScaleAlphaWideGamut = grayScaleHex.map((color) =>
    getAlphaColorP3(color, backgroundHex),
  ) as ArrayOf12<string>;

  const accentSurface =
    appearance === "light"
      ? getAlphaColorSrgb(accentScaleHex[1], backgroundHex, 0.8)
      : getAlphaColorSrgb(accentScaleHex[1], backgroundHex, 0.5);
  const accentSurfaceWideGamut =
    appearance === "light"
      ? getAlphaColorP3(accentScaleWideGamut[1], backgroundHex, 0.8)
      : getAlphaColorP3(accentScaleWideGamut[1], backgroundHex, 0.5);

  return {
    accentScale: accentScaleHex,
    accentScaleAlpha,
    accentScaleWideGamut,
    accentScaleAlphaWideGamut,
    accentContrast: accentContrastColor.to("srgb").toString({ format: "hex" }),
    grayScale: grayScaleHex,
    grayScaleAlpha,
    grayScaleWideGamut,
    grayScaleAlphaWideGamut,
    graySurface: appearance === "light" ? "#ffffffcc" : "rgba(0, 0, 0, 0.05)",
    graySurfaceWideGamut:
      appearance === "light" ? "color(display-p3 1 1 1 / 80%)" : "color(display-p3 0 0 0 / 5%)",
    accentSurface,
    accentSurfaceWideGamut,
    background: backgroundHex,
  };
}

function getStep9Colors(scale: ArrayOf12<Color>, accentBaseColor: Color): [Color, Color] {
  const referenceBackgroundColor = scale[0];
  const distance = accentBaseColor.deltaEOK(referenceBackgroundColor) * 100;

  if (distance < 25) return [scale[8], getTextColor(scale[8])];
  return [accentBaseColor, getTextColor(accentBaseColor)];
}

function getButtonHoverColor(source: Color, scales: ArrayOf12<Color>[]) {
  const [sourceLightness, sourceChroma, hue] = source.coords;
  const lightness = getNumericCoordinate(sourceLightness);
  const chroma = getNumericCoordinate(sourceChroma);
  const nextLightness =
    lightness > 0.4 ? lightness - 0.03 / (lightness + 0.1) : lightness + 0.03 / (lightness + 0.1);
  const nextChroma = lightness > 0.4 && hue !== null && !Number.isNaN(hue) ? chroma * 0.93 : chroma;
  const hoverColor = new Color("oklch", [nextLightness, nextChroma, hue]);

  let closestColor = hoverColor;
  let minimumDistance = Infinity;

  scales.forEach((scale) => {
    scale.forEach((color) => {
      const distance = hoverColor.deltaEOK(color);
      if (distance < minimumDistance) {
        minimumDistance = distance;
        closestColor = color;
      }
    });
  });

  hoverColor.coords[1] = closestColor.coords[1];
  hoverColor.coords[2] = closestColor.coords[2];
  return hoverColor;
}

function getScaleFromColor(
  source: Color,
  scales: Record<string, ArrayOf12<Color>>,
  backgroundColor: Color,
): ArrayOf12<Color> {
  const allColors: { scale: string; color: Color; distance: number }[] = [];

  Object.entries(scales).forEach(([name, scale]) => {
    scale.forEach((color) => {
      allColors.push({ scale: name, distance: source.deltaEOK(color), color });
    });
  });

  allColors.sort((a, b) => a.distance - b.distance);
  const closestColors = allColors.filter(
    (color, index, colors) => index === colors.findIndex((value) => value.scale === color.scale),
  );
  const grayScaleNamesSet = grayScaleNames as readonly string[];

  if (
    !closestColors.every((color) => grayScaleNamesSet.includes(color.scale)) &&
    grayScaleNamesSet.includes(closestColors[0].scale)
  ) {
    while (grayScaleNamesSet.includes(closestColors[1].scale)) closestColors.splice(1, 1);
  }

  const colorA = closestColors[0];
  const colorB = closestColors[1];
  const a = colorB.distance;
  const b = colorA.distance;
  const c = colorA.color.deltaEOK(colorB.color);
  const cosA = (b ** 2 + c ** 2 - a ** 2) / (2 * b * c);
  const cosB = (a ** 2 + c ** 2 - b ** 2) / (2 * a * c);
  const tanC1 = Math.cos(Math.acos(cosA)) / Math.sin(Math.acos(cosA));
  const tanC2 = Math.cos(Math.acos(cosB)) / Math.sin(Math.acos(cosB));
  const ratio = Math.max(0, tanC1 / tanC2) * 0.5;
  const scaleA = scales[colorA.scale];
  const scaleB = scales[colorB.scale];
  const scale = arrayOf12.map((index) =>
    new Color(Color.mix(scaleA[index], scaleB[index], ratio)).to("oklch"),
  ) as ArrayOf12<Color>;

  const baseColor = scale
    .slice()
    .sort((aColor, bColor) => source.deltaEOK(aColor) - source.deltaEOK(bColor))[0];
  if (!baseColor) throw new Error("Unable to generate a color scale");

  const sourceChroma = getNumericCoordinate(source.coords[1]);
  const baseChroma = getNumericCoordinate(baseColor.coords[1]);
  const chromaRatio = baseChroma === 0 ? 1 : sourceChroma / baseChroma;

  scale.forEach((color) => {
    color.coords[1] = Math.min(
      sourceChroma * 1.5,
      getNumericCoordinate(color.coords[1]) * chromaRatio,
    );
    color.coords[2] = source.coords[2];
  });

  if (getNumericCoordinate(scale[0].coords[0]) > 0.5) {
    const lightnessScale = scale.map(({ coords }) => getNumericCoordinate(coords[0]));
    const backgroundLightness = Math.max(
      0,
      Math.min(1, getNumericCoordinate(backgroundColor.coords[0])),
    );
    const newLightnessScale = transposeProgressionStart(
      backgroundLightness,
      [1, ...lightnessScale],
      lightModeEasing,
    );

    newLightnessScale.shift();
    newLightnessScale.forEach((lightness, index) => {
      scale[index].coords[0] = lightness;
    });
    return scale;
  }

  const ease: [number, number, number, number] = [...darkModeEasing];
  const referenceBackgroundLightness = getNumericCoordinate(scale[0].coords[0]);
  const backgroundLightness = Math.max(
    0,
    Math.min(1, getNumericCoordinate(backgroundColor.coords[0])),
  );
  const lightnessRatio = backgroundLightness / referenceBackgroundLightness;

  if (lightnessRatio > 1) {
    const maximumRatio = 1.5;
    const metaRatio = (lightnessRatio - 1) * (maximumRatio / (maximumRatio - 1));

    for (let index = 0; index < ease.length; index += 1) {
      ease[index] = lightnessRatio > maximumRatio ? 0 : Math.max(0, ease[index] * (1 - metaRatio));
    }
  }

  const lightnessScale = scale.map(({ coords }) => getNumericCoordinate(coords[0]));
  const newLightnessScale = transposeProgressionStart(
    getNumericCoordinate(backgroundColor.coords[0]),
    lightnessScale,
    ease,
  );

  newLightnessScale.forEach((lightness, index) => {
    scale[index].coords[0] = lightness;
  });
  return scale;
}

function getTextColor(background: Color): Color {
  const white = new Color("oklch", [1, 0, 0]);

  if (Math.abs(white.contrastAPCA(background)) < 40) {
    const [, chroma, hue] = background.coords;
    return new Color("oklch", [0.25, Math.max(0.08 * getNumericCoordinate(chroma), 0.04), hue]);
  }

  return white;
}

function getNumericCoordinate(value: number | null): number {
  return value ?? 0;
}

function getNumericCoordinates(coords: Color["coords"]): number[] {
  return coords.map(getNumericCoordinate);
}

function getAlphaColor(
  targetRgb: number[],
  backgroundRgb: number[],
  rgbPrecision: number,
  alphaPrecision: number,
  targetAlpha?: number,
) {
  const [targetR, targetG, targetB] = targetRgb.map((channel) =>
    Math.round(channel * rgbPrecision),
  );
  const [backgroundR, backgroundG, backgroundB] = backgroundRgb.map((channel) =>
    Math.round(channel * rgbPrecision),
  );

  if (
    targetR === undefined ||
    targetG === undefined ||
    targetB === undefined ||
    backgroundR === undefined ||
    backgroundG === undefined ||
    backgroundB === undefined
  ) {
    throw new Error("Color is undefined");
  }

  let desiredRgb = 0;
  if (targetR > backgroundR || targetG > backgroundG || targetB > backgroundB) {
    desiredRgb = rgbPrecision;
  }

  const alphaR = (targetR - backgroundR) / (desiredRgb - backgroundR);
  const alphaG = (targetG - backgroundG) / (desiredRgb - backgroundG);
  const alphaB = (targetB - backgroundB) / (desiredRgb - backgroundB);
  const isPureGray = [alphaR, alphaG, alphaB].every((alpha) => alpha === alphaR);

  if (!targetAlpha && isPureGray) {
    const value = desiredRgb / rgbPrecision;
    return [value, value, value, alphaR] as const;
  }

  const clampRgb = (value: number) =>
    Number.isNaN(value) ? 0 : Math.min(rgbPrecision, Math.max(0, value));
  const clampAlpha = (value: number) =>
    Number.isNaN(value) ? 0 : Math.min(alphaPrecision, Math.max(0, value));
  const maxAlpha = targetAlpha ?? Math.max(alphaR, alphaG, alphaB);
  const alpha = clampAlpha(Math.ceil(maxAlpha * alphaPrecision)) / alphaPrecision;
  let red = clampRgb(((backgroundR * (1 - alpha) - targetR) / alpha) * -1);
  let green = clampRgb(((backgroundG * (1 - alpha) - targetG) / alpha) * -1);
  let blue = clampRgb(((backgroundB * (1 - alpha) - targetB) / alpha) * -1);

  red = Math.ceil(red);
  green = Math.ceil(green);
  blue = Math.ceil(blue);

  const blendedRed = blendAlpha(red, alpha, backgroundR);
  const blendedGreen = blendAlpha(green, alpha, backgroundG);
  const blendedBlue = blendAlpha(blue, alpha, backgroundB);

  if (desiredRgb === 0) {
    if (targetR <= backgroundR && targetR !== blendedRed) red += targetR > blendedRed ? 1 : -1;
    if (targetG <= backgroundG && targetG !== blendedGreen)
      green += targetG > blendedGreen ? 1 : -1;
    if (targetB <= backgroundB && targetB !== blendedBlue) blue += targetB > blendedBlue ? 1 : -1;
  } else {
    if (targetR >= backgroundR && targetR !== blendedRed) red += targetR > blendedRed ? 1 : -1;
    if (targetG >= backgroundG && targetG !== blendedGreen)
      green += targetG > blendedGreen ? 1 : -1;
    if (targetB >= backgroundB && targetB !== blendedBlue) blue += targetB > blendedBlue ? 1 : -1;
  }

  return [red / rgbPrecision, green / rgbPrecision, blue / rgbPrecision, alpha] as const;
}

function blendAlpha(foreground: number, alpha: number, background: number): number {
  return Math.round(background * (1 - alpha)) + Math.round(foreground * alpha);
}

function getAlphaColorSrgb(
  targetColor: string,
  backgroundColor: string,
  targetAlpha?: number,
): string {
  const [red, green, blue, alpha] = getAlphaColor(
    getNumericCoordinates(new Color(targetColor).to("srgb").coords),
    getNumericCoordinates(new Color(backgroundColor).to("srgb").coords),
    255,
    255,
    targetAlpha,
  );

  return formatHex(new Color("srgb", [red, green, blue], alpha).toString({ format: "hex" }));
}

function getAlphaColorP3(
  targetColor: string,
  backgroundColor: string,
  targetAlpha?: number,
): string {
  const [red, green, blue, alpha] = getAlphaColor(
    getNumericCoordinates(new Color(targetColor).to("p3").coords),
    getNumericCoordinates(new Color(backgroundColor).to("p3").coords),
    255,
    1000,
    targetAlpha,
  );

  return new Color("p3", [red, green, blue], alpha)
    .toString({ precision: 4 })
    .replace("color(p3 ", "color(display-p3 ");
}

function formatHex(value: string): string {
  if (!value.startsWith("#")) return value;
  if (value.length !== 4 && value.length !== 5) return value;

  const channels = value.slice(1).split("");
  return `#${channels.map((channel) => channel + channel).join("")}`;
}

const darkModeEasing: [number, number, number, number] = [1, 0, 1, 0];
const lightModeEasing: [number, number, number, number] = [0, 2, 0, 2];

function transposeProgressionStart(
  target: number,
  values: number[],
  curve: [number, number, number, number],
): number[] {
  return values.map((value, index, allValues) => {
    const lastIndex = allValues.length - 1;
    const difference = allValues[0] - target;
    const easing = BezierEasing(...curve);
    return value - difference * easing(1 - index / lastIndex);
  });
}

function toOklchString(color: Color): string {
  const lightness = +(getNumericCoordinate(color.coords[0]) * 100).toFixed(1);
  return color
    .to("oklch")
    .toString({ precision: 4 })
    .replace(/(\S+)(.+)/, `oklch(${lightness}%$2`);
}
