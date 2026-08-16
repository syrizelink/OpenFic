import { Box, Button, Flex, Text } from "@radix-ui/themes";
import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

import "./app-crash-fallback.css";

interface AppCrashFallbackProps {
  error: unknown;
}

/**
 * 应用崩溃兜底页：顶层 ErrorBoundary 捕获到未处理的渲染异常时展示。
 */
export function AppCrashFallback({ error }: AppCrashFallbackProps) {
  const { t } = useTranslation();
  const isError = error instanceof Error;
  const message = isError ? error.message : String(error);
  const stack = isError ? error.stack : undefined;

  return (
    <Box className="app-crash-fallback-shell">
      <Flex
        direction="column"
        align="center"
        justify="center"
        gap="3"
        className="app-crash-fallback-stage"
      >
        <Text
          size="3"
          weight="bold"
          className="app-crash-fallback-title"
        >
          {t("common.crashTitle")}
        </Text>
        {message ? (
          <Text
            size="2"
            color="gray"
            className="app-crash-fallback-message"
          >
            {message}
          </Text>
        ) : null}
        <Button
          variant="soft"
          color="gray"
          onClick={() => window.location.reload()}
        >
          <RefreshCw size={16} />
          {t("common.retry")}
        </Button>
        {stack ? (
          <details className="app-crash-fallback-details">
            <summary>{t("common.crashDetails")}</summary>
            <pre className="app-crash-fallback-stack">{stack}</pre>
          </details>
        ) : null}
      </Flex>
    </Box>
  );
}
