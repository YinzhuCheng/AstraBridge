export function DogfoodLedgerSummary({ locale }: { locale: "en" | "zh-CN" }) {
  const isZh = locale === "zh-CN";

  return (
    <section className="manager-section" data-testid="dogfood-ledger-summary">
      <div>
        <span className="eyebrow">{isZh ? "内部台账" : "Internal ledger"}</span>
        <h4>{isZh ? "狗粮运行保留为内部台账" : "Dogfood remains an internal ledger"}</h4>
      </div>
      <p className="muted compact-copy">
        {isZh
          ? "这里记录预算、截图、阻塞、里程碑和下一步；数据只保存在工作区 `.astrabridge` 或本地证据目录中。"
          : "This area records budgets, captures, blockers, milestones, and next steps under the workspace-local `.astrabridge` state."}
      </p>
      <p className="muted compact-copy">
        {isZh
          ? "自动化、插件、技能、多模态能力路由和联网的入口验收不再作为产品卡片出现在这里。"
          : "Automation, plugin, skill, multimodal route, and web-entry acceptance is no longer presented here as product cards."}
      </p>
      <p className="muted compact-copy">
        {isZh
          ? "后续狗粮验证通过 in-app browser、Playwright 或浏览器 smoke 记录截图与报告，而不是在此页提供跳转任务按钮。"
          : "Later dogfood validation should capture screenshots and reports through the in-app browser, Playwright, or browser smoke instead of task buttons on this page."}
      </p>
    </section>
  );
}
