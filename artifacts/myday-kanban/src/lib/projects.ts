export interface Project {
  id: number;
  name: string;
}

const PROJECT_COLORS = [
  "bg-violet-100 text-violet-700",
  "bg-blue-100 text-blue-700",
  "bg-emerald-100 text-emerald-700",
  "bg-red-100 text-red-700",
  "bg-amber-100 text-amber-700",
  "bg-cyan-100 text-cyan-700",
  "bg-pink-100 text-pink-700",
];

export function projectColor(id: number): string {
  return PROJECT_COLORS[(id - 1) % PROJECT_COLORS.length];
}

export function projectInitials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export async function fetchProjects(): Promise<Project[]> {
  const base = import.meta.env.BASE_URL?.replace(/\/$/, "") ?? "";
  const res = await fetch(`${base}/api/projects`);
  if (!res.ok) return [];
  return res.json();
}
