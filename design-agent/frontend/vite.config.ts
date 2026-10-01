// 前端开发服务器配置；正式使用启动脚本时，FastAPI 直接提供 frontend/dist。
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5175,
    strictPort: true,
    // 开发时网页请求 /api 由 Vite 转发到后端，保持前端代码使用相对 URL。
    // strictPort 防止端口被占时悄悄换端口；host 仅监听本机回环地址。
    proxy: { "/api": "http://127.0.0.1:8011" },
  },
});
