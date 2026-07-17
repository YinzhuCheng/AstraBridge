import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TaskGraphSchemaForm } from "./TaskGraphSchemaForm";

afterEach(() => {
  cleanup();
});

describe("TaskGraphSchemaForm", () => {
  it("renders scalar, enum, list, reference, and structured-json fallback fields", () => {
    const onChange = vi.fn();
    const onValidityChange = vi.fn();
    render(
      <TaskGraphSchemaForm
        schema={{
          type: "object",
          properties: {
            tool: { type: "string", title: "Tool" },
            retry_count: { type: "integer", title: "Retry count" },
            approval_mode: {
              type: "string",
              title: "Approval mode",
              enum: ["ask", "auto"],
            },
            resource_refs: { type: "array", title: "Resource refs" },
            provider_ref: {
              type: "string",
              title: "Provider",
              format: "reference",
            },
            condition: { type: "object", title: "Condition" },
          },
        }}
        value={{
          tool: "web.search",
          retry_count: 2,
          approval_mode: "ask",
          resource_refs: ["file:a", "file:b"],
          provider_ref: "qwen",
          condition: { op: "equals" },
        }}
        referenceOptions={{ provider_ref: ["qwen", "kimi"] }}
        onChange={onChange}
        onValidityChange={onValidityChange}
        testIdPrefix="schema-form"
      />,
    );

    expect(screen.getByTestId("schema-form-tool")).toHaveValue("web.search");
    expect(screen.getByTestId("schema-form-retry_count")).toHaveValue(2);
    expect(screen.getByTestId("schema-form-approval_mode")).toHaveValue("ask");
    expect(screen.getByTestId("schema-form-resource_refs")).toHaveValue(
      "file:a\nfile:b",
    );
    expect(screen.getByTestId("schema-form-provider_ref")).toHaveValue("qwen");
    expect(screen.getByTestId("schema-form-condition")).toHaveValue(
      '{\n  "op": "equals"\n}',
    );

    fireEvent.change(screen.getByTestId("schema-form-tool"), {
      target: { value: "read_file" },
    });
    fireEvent.change(screen.getByTestId("schema-form-retry_count"), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByTestId("schema-form-approval_mode"), {
      target: { value: "auto" },
    });
    fireEvent.change(screen.getByTestId("schema-form-resource_refs"), {
      target: { value: "file:x\nfile:y" },
    });
    fireEvent.change(screen.getByTestId("schema-form-provider_ref"), {
      target: { value: "kimi" },
    });
    fireEvent.change(screen.getByTestId("schema-form-condition"), {
      target: { value: '{ "op": "gt", "value": 4 }' },
    });

    expect(onValidityChange).toHaveBeenLastCalledWith(true);
    expect(onChange).toHaveBeenLastCalledWith({
      tool: "read_file",
      retry_count: 3,
      approval_mode: "auto",
      resource_refs: ["file:x", "file:y"],
      provider_ref: "kimi",
      condition: { op: "gt", value: 4 },
    });
  });

  it("marks the form invalid when structured-json fallback text is malformed", () => {
    const onChange = vi.fn();
    const onValidityChange = vi.fn();
    render(
      <TaskGraphSchemaForm
        schema={{
          type: "object",
          properties: {
            condition: { type: "object", title: "Condition" },
          },
        }}
        value={{ condition: { op: "equals" } }}
        onChange={onChange}
        onValidityChange={onValidityChange}
        testIdPrefix="schema-form"
      />,
    );

    fireEvent.change(screen.getByTestId("schema-form-condition"), {
      target: { value: "{invalid json}" },
    });

    expect(onValidityChange).toHaveBeenLastCalledWith(false);
    expect(screen.getByTestId("schema-form-condition-error")).toHaveTextContent(
      "Enter valid JSON object text.",
    );
  });
});
