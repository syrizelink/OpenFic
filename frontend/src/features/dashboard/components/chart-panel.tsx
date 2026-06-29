import { useCallback, useEffect, useRef, useState } from "react";
import { Card } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import {
  DASHBOARD_ECHARTS_DARK_THEME_NAME,
  DASHBOARD_ECHARTS_LIGHT_THEME_NAME,
  dashboardDarkEchartsTheme,
  dashboardLightEchartsTheme,
  getDashboardEchartsThemeName,
  type DashboardEchartsThemeMode,
} from "../lib/dashboard-echarts-theme";
import { withDashboardChartTheme, type DashboardChartOption } from "../lib/dashboard-chart-options";

interface DashboardChartInstance {
  setOption: (option: DashboardChartOption, notMerge?: boolean) => void;
  showLoading: (type?: string, options?: Record<string, unknown>) => void;
  hideLoading: () => void;
  resize: () => void;
  dispose: () => void;
}

interface ChartPanelProps {
  title: string;
  option: DashboardChartOption;
  isLoading: boolean;
  themeMode: DashboardEchartsThemeMode;
  size?: "wide" | "medium" | "small";
}

let echartsLoader: Promise<{
  init: (
    element: HTMLDivElement,
    theme?: string,
    options?: { renderer?: "canvas" | "svg" }
  ) => DashboardChartInstance;
}> | null = null;

function loadEcharts() {
  if (!echartsLoader) {
    echartsLoader = Promise.all([
      import("echarts/core"),
      import("echarts/charts"),
      import("echarts/components"),
      import("echarts/renderers"),
    ]).then(([echarts, charts, components, renderers]) => {
      echarts.use([
        charts.BarChart,
        charts.LineChart,
        charts.PieChart,
        components.GraphicComponent,
        components.GridComponent,
        components.LegendComponent,
        components.TooltipComponent,
        renderers.CanvasRenderer,
      ]);
      echarts.registerTheme(DASHBOARD_ECHARTS_LIGHT_THEME_NAME, dashboardLightEchartsTheme);
      echarts.registerTheme(DASHBOARD_ECHARTS_DARK_THEME_NAME, dashboardDarkEchartsTheme);
      return { init: echarts.init };
    });
  }
  return echartsLoader;
}

export function ChartPanel({ title, option, isLoading, themeMode, size = "medium" }: ChartPanelProps) {
  const { t } = useTranslation();
  const elementRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<DashboardChartInstance | null>(null);
  const latestOptionRef = useRef(withDashboardChartTheme(option, themeMode));
  const latestLoadingRef = useRef(isLoading);
  const hideLoadingTimerRef = useRef<number | null>(null);
  const applyOptionFrameRef = useRef<number | null>(null);
  const [isChartReady, setIsChartReady] = useState(false);

  const showChartLoading = useCallback((chart: DashboardChartInstance) => {
    chart.showLoading("default", { text: "", spinnerRadius: 12, lineWidth: 2, zlevel: 0 });
  }, []);

  const clearScheduledOptionApply = useCallback(() => {
    if (applyOptionFrameRef.current === null) return;
    window.cancelAnimationFrame(applyOptionFrameRef.current);
    applyOptionFrameRef.current = null;
  }, []);

  const applyLatestOption = useCallback(() => {
    clearScheduledOptionApply();
    applyOptionFrameRef.current = window.requestAnimationFrame(() => {
      applyOptionFrameRef.current = null;
      if (!latestLoadingRef.current) chartRef.current?.setOption(latestOptionRef.current, true);
    });
  }, [clearScheduledOptionApply]);

  const hideChartLoadingSoon = useCallback(() => {
    if (hideLoadingTimerRef.current !== null) window.clearTimeout(hideLoadingTimerRef.current);
    hideLoadingTimerRef.current = window.setTimeout(() => {
      hideLoadingTimerRef.current = null;
      if (latestLoadingRef.current) return;
      chartRef.current?.hideLoading();
      applyLatestOption();
    }, 180);
  }, [applyLatestOption]);

  useEffect(() => {
    latestOptionRef.current = withDashboardChartTheme(option, themeMode);
    if (!latestLoadingRef.current) applyLatestOption();
  }, [applyLatestOption, option, themeMode]);

  useEffect(() => {
    latestLoadingRef.current = isLoading;
    if (!chartRef.current) return;
    if (isLoading) {
      if (hideLoadingTimerRef.current !== null) {
        window.clearTimeout(hideLoadingTimerRef.current);
        hideLoadingTimerRef.current = null;
      }
      showChartLoading(chartRef.current);
      return;
    }
    hideChartLoadingSoon();
  }, [hideChartLoadingSoon, isLoading, showChartLoading]);

  useEffect(() => {
    if (!elementRef.current) return undefined;
    let isCancelled = false;
    let resizeObserver: ResizeObserver | null = null;
    setIsChartReady(false);

    loadEcharts().then((echarts) => {
      if (isCancelled || !elementRef.current) return;
      chartRef.current = echarts.init(elementRef.current, getDashboardEchartsThemeName(themeMode), { renderer: "canvas" });
      showChartLoading(chartRef.current);
      if (!latestLoadingRef.current) hideChartLoadingSoon();
      setIsChartReady(true);
      resizeObserver = new ResizeObserver(() => chartRef.current?.resize());
      resizeObserver.observe(elementRef.current);
    });

    return () => {
      isCancelled = true;
      if (hideLoadingTimerRef.current !== null) window.clearTimeout(hideLoadingTimerRef.current);
      clearScheduledOptionApply();
      resizeObserver?.disconnect();
      chartRef.current?.dispose();
      chartRef.current = null;
      hideLoadingTimerRef.current = null;
    };
  }, [clearScheduledOptionApply, hideChartLoadingSoon, showChartLoading, themeMode]);

  return (
    <Card className="dashboard-chart-card" data-size={size}>
      <div className="dashboard-chart-title-row">
        <div className="dashboard-chart-title">{title}</div>
      </div>
      <div className="dashboard-chart-frame">
        {!isChartReady ? (
          <div className="dashboard-chart-mount-loading" aria-label={t("dashboard.charts.loading")} role="status">
            <div className="dashboard-chart-mount-spinner" />
          </div>
        ) : null}
        <div ref={elementRef} className="dashboard-chart" data-ready={isChartReady} data-size={size} />
      </div>
    </Card>
  );
}
