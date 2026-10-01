// 前后端数据契约与 JSON 请求封装。类型用于编译期检查，不是运行时 JSON 校验。
// status 是任务整体状态，phase 是当前业务阶段；连接失败属于前端连接状态。
export type TaskStatus = "queued" | "running" | "succeeded" | "failed";
export interface Check {
  // not_run 要单独展示为“未执行”，不能当成 passed，尤其是视觉和浏览器验收。
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
  // revision 是服务端递增版本号，TaskPage 用它避免旧响应覆盖新快照。
  // 分支、计划、产物等随阶段逐步生成，所以用 ? 表示字段可能尚不存在。
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
    // 这里的模型计数来自 Developer：计划 + 编码 + 修复，不包含视觉解析调用。
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
  // 健康接口只暴露模型名称和 configured 布尔值；API key 始终留在后端。
  status: string;
  target_name: string;
  base_branch: string;
  model: string;
  configured: boolean;
  image_parser: string;
}
export class ApiError extends Error {
  // 保存 HTTP 状态码，页面可区分 404、409 等明确业务错误与网络错误。
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
  // 泛型 T 让调用处声明期待的数据形状，如 request<Task>(...)。
  // 默认 12 秒只限制这次 HTTP 请求，不限制后台长任务；上传单独使用 60 秒。
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    // 本封装专用于 JSON API；changes.diff 等文本文件由页面直接 fetch/text。
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
    // 无论请求成功或失败都清掉定时器，避免结束后仍触发无用 abort。
    clearTimeout(timer);
  }
}
