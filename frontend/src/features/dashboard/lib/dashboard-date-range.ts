export interface DashboardDateRange {
  startDate: string;
  endDate: string;
}

function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function getDefaultDashboardDateRange(today = new Date()): DashboardDateRange {
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - 29);
  return {
    startDate: formatDate(startDate),
    endDate: formatDate(today),
  };
}
