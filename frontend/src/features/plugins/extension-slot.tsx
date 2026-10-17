import { Text, Tooltip } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { Package, Puzzle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useParams } from "react-router";

import { fetchPlugins, PLUGINS_QUERY_KEY } from "./api";

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
  const { data: plugins = [] } = useQuery({
    queryKey: PLUGINS_QUERY_KEY,
    queryFn: fetchPlugins,
    refetchInterval: 5000,
  });
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
      {[...entries, { title: t("plugins.management"), href: "/extensions" }].map((entry) => (
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
            {entry.href === "/extensions" ? <Package size={20} /> : <Puzzle size={20} />}
            {expanded && <span>{entry.title}</span>}
          </Link>
        </Tooltip>
      ))}
    </nav>
  );
}
