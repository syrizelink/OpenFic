import axios from "axios";
import { Info } from "lucide-react";
import { useTranslation } from "react-i18next";

import { InfoTooltip } from "./info-tooltip";

import "./toast.css";

function getErrorDetail(error: unknown): string {
  if (typeof error === "string") return error.trim();

  if (axios.isAxiosError(error)) {
    const data: unknown = error.response?.data;
    const responseDetail =
      typeof data === "string" ? data : data == null ? "" : JSON.stringify(data, null, 2);
    const status = error.response
      ? `HTTP ${error.response.status} ${error.response.statusText || ""}`.trim()
      : "";
    return [status, error.code, error.message, responseDetail].filter(Boolean).join("\n");
  }

  if (error instanceof Error) return `${error.name}: ${error.message}`;
  if (error == null) return "";
  return String(error);
}

export function ErrorToastDetails({ message, error }: { message: string; error: unknown }) {
  const { t } = useTranslation();
  const detail = getErrorDetail(error) || t("common.initializationUnknownError");

  return (
    <span className="error-toast-message">
      {message}
      <InfoTooltip
        content={<span className="error-toast-tooltip-content">{detail}</span>}
        className="error-toast-tooltip"
      >
        <button
          type="button"
          className="error-toast-info"
          aria-label={t("common.errorDetails")}
        >
          <Info size={14} />
        </button>
      </InfoTooltip>
    </span>
  );
}
