import { Box, Button, Flex, Text } from "@radix-ui/themes";
import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Spinner } from "./spinner";

import "./global-loading.css";

interface GlobalLoadingProps {
  error?: string | null;
  onRetry?: () => void;
}

/**
 * Global Loading Component
 *
 * Displayed when the application is initializing or waiting for the backend to become ready.
 */
export function GlobalLoading({ error, onRetry }: GlobalLoadingProps) {
  const { t } = useTranslation();
  const hasError = Boolean(error);
  const spinnerLabel = hasError ? t("common.retryInitialization") : t("common.loading");

  return (
    <Box className="global-loading-shell">
      <Flex
        className="global-loading-stage"
        data-error={hasError ? "true" : "false"}
        direction="column"
        align="center"
        justify="center"
      >
        <Box
          className="global-loading-spinner-shell"
          data-error={hasError ? "true" : "false"}
        >
          <Spinner
            className="global-loading-spinner"
            size={24}
            aria-label={spinnerLabel}
          />
        </Box>

        {hasError ? (
          <Text
            as="p"
            className="global-loading-error"
            size="2"
          >
            {error}
          </Text>
        ) : null}

        {hasError ? (
          <Button
            className="global-loading-retry"
            onClick={onRetry}
            variant="ghost"
            color="gray"
            aria-label={t("common.retryInitialization")}
          >
            <RefreshCw size={18} />
          </Button>
        ) : null}
      </Flex>
    </Box>
  );
}
