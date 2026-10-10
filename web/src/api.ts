const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export type TaskStatus = "pending" | "queued" | "running" | "completed" | "failed" | "cancelled";

export interface ExperimentTask {
  id: string;
  name: string;
  protocol_ref: string;
  workcell_id: string;
  run_mode: string;
  status: TaskStatus;
  execution_ref: string | null;
  error: string | null;
  priority: number;
}

export interface Workcell {
  id: string;
  name: string;
  devices: string[];
  transporters: string[];
  status: "idle" | "busy" | "fault" | "offline";
}

export interface CellLink {
  from_cell: string;
  to_cell: string;
  link_type: string;
  link_id: string | null;
}

export interface Transfer {
  transfer_id: string;
  labware_id: string;
  from_cell: string;
  to_cell: string;
  state: string;
}

export interface ClusterView {
  id: string;
  workcells: Workcell[];
  links: CellLink[];
  transfers: Transfer[];
}

export interface ProtocolMapping {
  name: string;
  workflow_template_name: string;
  description: string;
}

export interface AdapterHealth {
  name: string;
  mode: string;
  status: string;
  call_count: number;
  recent_calls: Record<string, unknown>[];
}

export interface Health {
  status: string;
  runtime: string;
  auth: string;
  version: string;
}

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw new ApiError(await readError(response));
  }
  return (await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: { message?: string } | string };
    if (body.detail && typeof body.detail === "object" && body.detail.message) {
      return body.detail.message;
    }
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    return `请求失败（${response.status}）`;
  }
  return `请求失败（${response.status}）`;
}

export function eventSource(): EventSource {
  return new EventSource(`${API_BASE}/api/v1/events`);
}
