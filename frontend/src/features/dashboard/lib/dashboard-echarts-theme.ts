export type DashboardEchartsThemeMode = "light" | "dark";

export const DASHBOARD_ECHARTS_LIGHT_THEME_NAME = "openfic-dashboard-light";
export const DASHBOARD_ECHARTS_DARK_THEME_NAME = "openfic-dashboard-dark";

export function getDashboardEchartsThemeName(mode: DashboardEchartsThemeMode): string {
  return mode === "dark" ? DASHBOARD_ECHARTS_DARK_THEME_NAME : DASHBOARD_ECHARTS_LIGHT_THEME_NAME;
}

const sharedTheme = {
  color: [
    "#0ea5e9",
    "#16a34a",
    "#d97706",
    "#e11d48",
    "#7c3aed",
    "#0d9488",
    "#ea580c",
    "#0284c7",
    "#65a30d",
    "#db2777",
  ],
  textStyle: {},
};

export const dashboardLightEchartsTheme = {
  ...sharedTheme,
  backgroundColor: "transparent",
  title: {
    textStyle: {
      color: "#333333",
    },
    subtextStyle: {
      color: "#aaa",
    },
  },
  line: {
    itemStyle: {
      borderWidth: 1,
    },
    lineStyle: {
      width: 2,
    },
    symbolSize: 4,
    symbol: "emptyCircle",
    smooth: false,
  },
  radar: {
    itemStyle: {
      borderWidth: 1,
    },
    lineStyle: {
      width: 2,
    },
    symbolSize: 4,
    symbol: "emptyCircle",
    smooth: false,
  },
  bar: {
    itemStyle: {
      barBorderWidth: 0,
      barBorderColor: "#ccc",
    },
  },
  pie: {
    itemStyle: {
      borderWidth: 0,
      borderColor: "#ccc",
    },
  },
  scatter: {
    itemStyle: {
      borderWidth: 0,
      borderColor: "#ccc",
    },
  },
  boxplot: {
    itemStyle: {
      borderWidth: 0,
      borderColor: "#ccc",
    },
  },
  parallel: {
    itemStyle: {
      borderWidth: 0,
      borderColor: "#ccc",
    },
  },
  sankey: {
    itemStyle: {
      borderWidth: 0,
      borderColor: "#ccc",
    },
  },
  funnel: {
    itemStyle: {
      borderWidth: 0,
      borderColor: "#ccc",
    },
  },
  gauge: {
    itemStyle: {
      borderWidth: 0,
      borderColor: "#ccc",
    },
  },
  candlestick: {
    itemStyle: {
      color: "#c23531",
      color0: "#314656",
      borderColor: "#c23531",
      borderColor0: "#314656",
      borderWidth: 1,
    },
  },
  graph: {
    itemStyle: {
      borderWidth: 0,
      borderColor: "#ccc",
    },
    lineStyle: {
      width: 1,
      color: "#aaa",
    },
    symbolSize: 4,
    symbol: "emptyCircle",
    smooth: false,
    color: [
      "#0ea5e9",
      "#16a34a",
      "#d97706",
      "#e11d48",
      "#7c3aed",
      "#0d9488",
      "#ea580c",
      "#0284c7",
      "#65a30d",
      "#db2777",
    ],
    label: {
      color: "#eee",
    },
  },
  map: {
    itemStyle: {
      areaColor: "#eeeeee",
      borderColor: "#444444",
      borderWidth: 0.5,
    },
    label: {
      color: "#000000",
    },
    emphasis: {
      itemStyle: {
        areaColor: "rgba(255,215,0,0.8)",
        borderColor: "#444444",
        borderWidth: 1,
      },
      label: {
        color: "rgb(100,0,0)",
      },
    },
  },
  geo: {
    itemStyle: {
      areaColor: "#eeeeee",
      borderColor: "#444444",
      borderWidth: 0.5,
    },
    label: {
      color: "#000000",
    },
    emphasis: {
      itemStyle: {
        areaColor: "rgba(255,215,0,0.8)",
        borderColor: "#444444",
        borderWidth: 1,
      },
      label: {
        color: "rgb(100,0,0)",
      },
    },
  },
  categoryAxis: {
    axisLine: {
      show: true,
      lineStyle: {
        color: "#333",
      },
    },
    axisTick: {
      show: true,
      lineStyle: {
        color: "#333",
      },
    },
    axisLabel: {
      show: true,
      color: "#333",
    },
    splitLine: {
      show: false,
      lineStyle: {
        color: ["#ccc"],
      },
    },
    splitArea: {
      show: false,
      areaStyle: {
        color: ["rgba(250,250,250,0.3)", "rgba(200,200,200,0.3)"],
      },
    },
  },
  valueAxis: {
    axisLine: {
      show: true,
      lineStyle: {
        color: "#333",
      },
    },
    axisTick: {
      show: true,
      lineStyle: {
        color: "#333",
      },
    },
    axisLabel: {
      show: true,
      color: "#333",
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: ["#ccc"],
      },
    },
    splitArea: {
      show: false,
      areaStyle: {
        color: ["rgba(250,250,250,0.3)", "rgba(200,200,200,0.3)"],
      },
    },
  },
  logAxis: {
    axisLine: {
      show: true,
      lineStyle: {
        color: "#333",
      },
    },
    axisTick: {
      show: true,
      lineStyle: {
        color: "#333",
      },
    },
    axisLabel: {
      show: true,
      color: "#333",
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: ["#ccc"],
      },
    },
    splitArea: {
      show: false,
      areaStyle: {
        color: ["rgba(250,250,250,0.3)", "rgba(200,200,200,0.3)"],
      },
    },
  },
  timeAxis: {
    axisLine: {
      show: true,
      lineStyle: {
        color: "#333",
      },
    },
    axisTick: {
      show: true,
      lineStyle: {
        color: "#333",
      },
    },
    axisLabel: {
      show: true,
      color: "#333",
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: ["#ccc"],
      },
    },
    splitArea: {
      show: false,
      areaStyle: {
        color: ["rgba(250,250,250,0.3)", "rgba(200,200,200,0.3)"],
      },
    },
  },
  toolbox: {
    iconStyle: {
      borderColor: "#999999",
    },
    emphasis: {
      iconStyle: {
        borderColor: "#666666",
      },
    },
  },
  legend: {
    textStyle: {
      color: "#333333",
    },
    left: "center",
    right: "auto",
    top: 0,
    bottom: 10,
  },
  tooltip: {
    axisPointer: {
      lineStyle: {
        color: "#cccccc",
        width: 1,
      },
      crossStyle: {
        color: "#cccccc",
        width: 1,
      },
    },
  },
  timeline: {
    lineStyle: {
      color: "#293c55",
      width: 1,
    },
    itemStyle: {
      color: "#293c55",
      borderWidth: 1,
    },
    controlStyle: {
      color: "#293c55",
      borderColor: "#293c55",
      borderWidth: 0.5,
    },
    checkpointStyle: {
      color: "#e43c59",
      borderColor: "rgba(194,53,49,0.5)",
    },
    label: {
      color: "#293c55",
    },
    emphasis: {
      itemStyle: {
        color: "#a9334c",
      },
      controlStyle: {
        color: "#293c55",
        borderColor: "#293c55",
        borderWidth: 0.5,
      },
      label: {
        color: "#293c55",
      },
    },
  },
  visualMap: {
    color: ["#0ea5e9", "#22c55e", "#fde68a"],
  },
  markPoint: {
    label: {
      color: "#eee",
    },
    emphasis: {
      label: {
        color: "#eee",
      },
    },
  },
  grid: {
    left: "10%",
    right: "10%",
    top: 60,
    bottom: 70,
  },
};

export const dashboardDarkEchartsTheme = {
  ...sharedTheme,
  color: ["#38bdf8", "#22c55e", "#f59e0b", "#f43f5e", "#8b5cf6", "#14b8a6", "#f97316", "#0ea5e9", "#84cc16", "#ec4899"],
  backgroundColor: "transparent",
  textStyle: {
    color: "#e8e8e8",
  },
  title: {
    textStyle: { color: "#f1f1f1" },
    subtextStyle: { color: "#9a9a9a" },
  },
  categoryAxis: {
    axisLine: { show: true, lineStyle: { color: "#5a5a5a" } },
    axisTick: { show: true, lineStyle: { color: "#5a5a5a" } },
    axisLabel: { show: true, color: "#cfcfcf" },
    splitLine: { show: false, lineStyle: { color: ["#343434"] } },
    splitArea: { show: false, areaStyle: { color: ["rgba(255,255,255,0.03)", "rgba(255,255,255,0.06)"] } },
  },
  valueAxis: {
    axisLine: { show: true, lineStyle: { color: "#5a5a5a" } },
    axisTick: { show: true, lineStyle: { color: "#5a5a5a" } },
    axisLabel: { show: true, color: "#cfcfcf" },
    splitLine: { show: true, lineStyle: { color: ["#333333"] } },
    splitArea: { show: false, areaStyle: { color: ["rgba(255,255,255,0.03)", "rgba(255,255,255,0.06)"] } },
  },
  logAxis: {
    axisLine: { show: true, lineStyle: { color: "#5a5a5a" } },
    axisTick: { show: true, lineStyle: { color: "#5a5a5a" } },
    axisLabel: { show: true, color: "#cfcfcf" },
    splitLine: { show: true, lineStyle: { color: ["#333333"] } },
    splitArea: { show: false, areaStyle: { color: ["rgba(255,255,255,0.03)", "rgba(255,255,255,0.06)"] } },
  },
  timeAxis: {
    axisLine: { show: true, lineStyle: { color: "#5a5a5a" } },
    axisTick: { show: true, lineStyle: { color: "#5a5a5a" } },
    axisLabel: { show: true, color: "#cfcfcf" },
    splitLine: { show: true, lineStyle: { color: ["#333333"] } },
    splitArea: { show: false, areaStyle: { color: ["rgba(255,255,255,0.03)", "rgba(255,255,255,0.06)"] } },
  },
  legend: {
    textStyle: { color: "#d8d8d8" },
    left: "center",
    right: "auto",
    top: 0,
    bottom: 10,
  },
  tooltip: {
    backgroundColor: "#1f1f1f",
    borderColor: "#3a3a3a",
    textStyle: { color: "#f1f1f1" },
    axisPointer: {
      lineStyle: { color: "#777777", width: 1 },
      crossStyle: { color: "#777777", width: 1 },
    },
  },
  pie: {
    itemStyle: {
      borderWidth: 0,
      borderColor: "#242424",
    },
  },
  grid: {
    left: "10%",
    right: "10%",
    top: 60,
    bottom: 70,
  },
};
