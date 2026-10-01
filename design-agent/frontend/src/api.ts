export type TaskStatus = "queued" | "running" | "succeeded" | "failed";
export interface Check {
  name: string;
  status: "passed" | "failed" | "not_run";
  output: string;
}
export interface Task {
  id: string;
  status: TaskStatus;
  phase: string;
  interrupted_phase?: string;
  image_parser?: string;
  created_at: string;
  updated_at: string;
  revision: number;
  design_name: string;
  prd_name: string;
  instructions: string;
  branch?: string;
  worktree?: string;
  error?: string;
  checks: Check[];
  events?: { seq: number; at: string; phase: string; message: string }[];
  artifacts?: string[];
  plan?: {
    summary: string;
    files: string[];
    steps: string[];
    acceptance: string[];
  };
  report?: {
    changed_files?: string[];
    summary?: string;
    model_calls?: number;
    total_tokens?: number;
    repair_rounds?: number;
    remote_pushed?: boolean;
    image_parser?: string;
  };
}
export interface Health {
  status: string;
  target_name: string;
  base_branch: string;
  model: string;
  configured: boolean;
  image_parser: string;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function request<T>(
  url: string,
  init: RequestInit = {},
  timeout = 12000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    const body = await response.json();
    if (!response.ok)
      throw new ApiError(
        typeof body.detail === "string"
          ? body.detail
          : "请求失败，请检查输入或后台服务",
        response.status,
      );
    return body as T;
  } finally {
    clearTimeout(timer);
  }
}
