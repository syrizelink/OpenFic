import { Text, Tooltip } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { Puzzle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useParams } from "react-router";

import { pluginsQueryOptions } from "./api";

import "./plugins.css";

export function ExtensionSlot({
  expanded,
  onNavigate,
}: {
  expanded: boolean;
  onNavigate: () => void;
}) {
  const { t } = useTranslation();
  const { projectId } = useParams();
  const location = useLocation();
  const { data: plugins = [] } = useQuery(pluginsQueryOptions);
  const entries = plugins
    .filter((plugin) => plugin.status === "enabled")
    .flatMap((plugin) =>
      plugin.views
        .filter((view) => view.slot === "sidebar.extensions")
        .map((view) => ({
          title: view.title,
          href: `/extensions/${plugin.id}/${view.id}`,
        })),
    );
  if (entries.length === 0) return null;
  return (
    <nav
      className="extension-slot"
      aria-label={t("plugins.region")}
    >
      {expanded && (
        <Text
          size="1"
          color="gray"
        >
          {t("plugins.region")}
        </Text>
      )}
      {entries.map((entry) => (
        <Tooltip
          key={entry.href}
          content={entry.title}
        >
          <Link
            className="extension-slot-link"
            aria-label={entry.title}
            aria-current={location.pathname === entry.href ? "page" : undefined}
            to={`${entry.href}${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`}
            onClick={onNavigate}
          >
            <Puzzle size={20} />
            {expanded && <span>{entry.title}</span>}
          </Link>
        </Tooltip>
      ))}
    </nav>
  );
}
