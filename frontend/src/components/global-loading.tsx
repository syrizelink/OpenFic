import { Box, Button, Flex } from "@radix-ui/themes";
import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import "./global-loading.css";

interface GlobalLoadingProps {
  error?: boolean;
  onRetry?: () => void;
}

/**
 * Global Loading Component
 *
 * Displayed when the application is initializing or waiting for the backend to become ready.
 */
export function GlobalLoading({ error, onRetry }: GlobalLoadingProps) {
  const { t } = useTranslation();

  return (
    <Box className="global-loading-shell">
      <Flex className="global-loading-stage" direction="column" align="center" justify="center">
        <Box className="global-loading-orbit" data-error={error ? "true" : "false"} aria-hidden="true">
          <span className="global-loading-ring global-loading-ring-outer" />
          <span className="global-loading-ring global-loading-ring-middle" />
          <span className="global-loading-ring global-loading-ring-inner" />
          <span className="global-loading-core" />
        </Box>

        {error ? (
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
