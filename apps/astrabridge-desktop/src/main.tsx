import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { bootstrapFail, bootstrapNote, scheduleBootstrapReady } from "./bootstrapShell";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

async function start() {
  const root = document.getElementById("root");
  if (!root) {
    throw new Error("AstraBridge root container is missing.");
  }

  bootstrapNote("正在装载 AstraBridge 工作台...");
  const { default: App } = await import("./App");

  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>,
  );

  scheduleBootstrapReady("AstraBridge 已完成界面装载。");
}

void start().catch((error) => {
  bootstrapFail(error);
  console.error("AstraBridge bootstrap failed.", error);
});
