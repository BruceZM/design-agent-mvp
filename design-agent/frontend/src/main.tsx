// 浏览器入口：index.html 提供 #root，React 接管该节点并加载全局样式。
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
// ! 是 TypeScript 非空断言；依赖 HTML 中确实存在 id="root"，并非运行时检查。
// StrictMode 在开发模式额外检查 effect 的建立/清理，帮助发现重复订阅等问题。
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
