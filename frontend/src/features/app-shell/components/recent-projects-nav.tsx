import { Text, Tooltip } from "@radix-ui/themes";
import { X } from "lucide-react";
import { Link } from "react-router";

import { getProjectInitial, type RecentProject } from "@/lib/recent-projects";

import "./recent-projects-nav.css";

interface RecentProjectsNavProps {
  projects: RecentProject[];
  currentProjectId: string | undefined;
  isExpanded: boolean;
  ariaLabel: string;
  closeLabel: string;
  onRemove: (slot: number) => void;
}

interface RecentProjectNavItemProps {
  project: RecentProject;
  isActive: boolean;
  isExpanded: boolean;
  closeLabel: string;
  onRemove: (slot: number) => void;
}

function RecentProjectNavItem({
  project,
  isActive,
  isExpanded,
  closeLabel,
  onRemove,
}: RecentProjectNavItemProps) {
  const link = (
    <Link
      to={`/projects/${project.projectId}`}
      aria-label={project.title}
      aria-current={isActive ? "page" : undefined}
      className="app-sidebar-recent-project__link"
    >
      <span
        aria-hidden="true"
        className={`app-sidebar-recent-project__icon app-sidebar-recent-project__icon--${project.color}`}
      >
        {getProjectInitial(project.title)}
      </span>
      <Text
        size="2"
        weight={isActive ? "bold" : "medium"}
        className="app-sidebar-recent-project__title"
      >
        {project.title}
      </Text>
    </Link>
  );

  return (
    <div
      className="app-sidebar-recent-project"
      data-active={isActive ? "true" : "false"}
      data-expanded={isExpanded ? "true" : "false"}
    >
      {isExpanded ? (
        link
      ) : (
        <Tooltip
          content={project.title}
          side="right"
        >
          {link}
        </Tooltip>
      )}
      <button
        type="button"
        className="app-sidebar-recent-project__close"
        aria-label={`${closeLabel} ${project.title}`}
        onClick={(event) => {
          event.stopPropagation();
          onRemove(project.slot);
        }}
      >
        <X size={10} />
      </button>
    </div>
  );
}

export function RecentProjectsNav({
  projects,
  currentProjectId,
  isExpanded,
  ariaLabel,
  closeLabel,
  onRemove,
}: RecentProjectsNavProps) {
  if (projects.length === 0) return null;

  return (
    <nav
      aria-label={ariaLabel}
      className="app-sidebar-recent-projects"
    >
      {projects.map((project) => (
        <RecentProjectNavItem
          key={project.slot}
          project={project}
          isActive={project.projectId === currentProjectId}
          isExpanded={isExpanded}
          closeLabel={closeLabel}
          onRemove={onRemove}
        />
      ))}
    </nav>
  );
}
