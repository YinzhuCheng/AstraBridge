import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DogfoodLedgerSummary } from "./DogfoodLedgerSummary";

describe("DogfoodLedgerSummary", () => {
  afterEach(() => cleanup());

  it("renders internal-ledger copy without task buttons", () => {
    render(<DogfoodLedgerSummary locale="en" />);

    expect(screen.getByText("Dogfood remains an internal ledger")).toBeInTheDocument();
    expect(screen.getByText(/acceptance is no longer presented here as product cards/i)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders Chinese internal-ledger copy", () => {
    render(<DogfoodLedgerSummary locale="zh-CN" />);

    expect(screen.getByText("狗粮运行保留为内部台账")).toBeInTheDocument();
    expect(screen.getByText(/入口验收不再作为产品卡片/)).toBeInTheDocument();
    expect(screen.queryByText(/[�]/)).not.toBeInTheDocument();
  });
});
