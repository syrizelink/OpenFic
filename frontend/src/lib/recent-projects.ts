export const RECENT_PROJECT_COLORS = ["blue", "green", "orange", "purple", "teal", "pink"] as const;

export type RecentProjectColor = (typeof RECENT_PROJECT_COLORS)[number];

const projectInitialPattern = /[\p{L}\p{N}]/u;

export interface RecentProject {
  slot: number;
  projectId: string;
  title: string;
  color: RecentProjectColor;
  openedAt: Date;
}

interface RecentProjectInput {
  projectId: string;
  title: string;
  color: RecentProjectColor;
}

export function getProjectInitial(title: string): string {
  for (const character of title) {
    if (projectInitialPattern.test(character)) return character;
  }

  return "?";
}

export function getAvailableRecentProjectColors(
  recentProjects: RecentProject[],
): RecentProjectColor[] {
  const usedColors = new Set(recentProjects.map((project) => project.color));
  return RECENT_PROJECT_COLORS.filter((color) => !usedColors.has(color));
}

export function getRandomRecentProjectColor(
  recentProjects: RecentProject[] = [],
): RecentProjectColor {
  const availableColors = getAvailableRecentProjectColors(recentProjects);
  const colors = availableColors.length > 0 ? availableColors : RECENT_PROJECT_COLORS;
  const index = Math.floor(Math.random() * colors.length);
  return colors[index];
}

export function insertRecentProject(
  recentProjects: RecentProject[],
  project: RecentProjectInput,
): RecentProject[] {
  const existingProject = recentProjects.find((item) => item.projectId === project.projectId);

  if (existingProject?.slot === 0) {
    return recentProjects.map((item) =>
      item.slot === 0
        ? {
            ...item,
            title: project.title,
            openedAt: new Date(),
          }
        : item,
    );
  }

  const nextProjects: RecentProject[] = [
    {
      slot: 0,
      projectId: project.projectId,
      title: project.title,
      color: existingProject?.color ?? project.color,
      openedAt: new Date(),
    },
  ];

  for (const currentProject of recentProjects) {
    if (currentProject.projectId === project.projectId) continue;

    const shouldShift = !existingProject || currentProject.slot < existingProject.slot;
    const nextSlot = shouldShift ? currentProject.slot + 1 : currentProject.slot;
    if (nextSlot <= 2) nextProjects.push({ ...currentProject, slot: nextSlot });
  }

  return nextProjects.sort((projectA, projectB) => projectA.slot - projectB.slot);
}
