import { useEffect, useMemo, useState } from "react";

type SchemaObject = Record<string, unknown>;

type SchemaPropertyField =
  | {
      key: string;
      label: string;
      description: string;
      kind: "enum" | "string" | "number" | "integer" | "boolean";
      enumOptions?: string[];
      defaultValue: string | boolean;
    }
  | {
      key: string;
      label: string;
      description: string;
      kind: "list";
      defaultValue: string;
    }
  | {
      key: string;
      label: string;
      description: string;
      kind: "reference";
      defaultValue: string;
    }
  | {
      key: string;
      label: string;
      description: string;
      kind: "structured_json";
      defaultValue: string;
    };

export type TaskGraphSchemaFormProps = {
  schema: SchemaObject;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
  onValidityChange?: (valid: boolean) => void;
  referenceOptions?: Record<string, string[]>;
  testIdPrefix?: string;
};

function asRecord(value: unknown): SchemaObject | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as SchemaObject)
    : null;
}

function normalizeText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function fieldLabel(key: string, schema: SchemaObject) {
  return normalizeText(schema.title) || key.replace(/_/g, " ");
}

function fieldDescription(schema: SchemaObject) {
  return normalizeText(schema.description);
}

function jsonText(value: unknown) {
  if (!value || (typeof value === "object" && Object.keys(asRecord(value) ?? {}).length === 0)) {
    return "";
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "";
  }
}

function listText(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item ?? "")).join("\n") : "";
}

function propertiesForSchema(
  schema: SchemaObject,
  value: Record<string, unknown>,
  referenceOptions: Record<string, string[]>,
): SchemaPropertyField[] {
  const properties = asRecord(schema.properties) ?? {};
  return Object.entries(properties)
    .map(([key, rawProperty]) => {
      const property = asRecord(rawProperty) ?? {};
      const type = normalizeText(property.type);
      const enumOptions = Array.isArray(property.enum)
        ? property.enum.map((item) => String(item ?? "")).filter(Boolean)
        : [];
      const title = fieldLabel(key, property);
      const description = fieldDescription(property);
      const referenceChoices = Array.isArray(referenceOptions[key])
        ? referenceOptions[key]!.map((item) => String(item ?? "")).filter(Boolean)
        : [];
      if (
        normalizeText(property.format) === "reference" ||
        normalizeText(property["x-ui-field"]) === "reference" ||
        referenceChoices.length > 0
      ) {
        return {
          key,
          label: title,
          description,
          kind: "reference" as const,
          defaultValue: String(value[key] ?? ""),
        };
      }
      if (type === "array") {
        return {
          key,
          label: title,
          description,
          kind: "list" as const,
          defaultValue: listText(value[key]),
        };
      }
      if (enumOptions.length > 0) {
        return {
          key,
          label: title,
          description,
          kind: "enum" as const,
          enumOptions,
          defaultValue: String(value[key] ?? enumOptions[0] ?? ""),
        };
      }
      if (type === "boolean") {
        return {
          key,
          label: title,
          description,
          kind: "boolean" as const,
          defaultValue: Boolean(value[key]),
        };
      }
      if (type === "number" || type === "integer") {
        return {
          key,
          label: title,
          description,
          kind: type as "number" | "integer",
          defaultValue: value[key] == null ? "" : String(value[key]),
        };
      }
      if (type === "string") {
        return {
          key,
          label: title,
          description,
          kind: "string" as const,
          defaultValue: String(value[key] ?? ""),
        };
      }
      return {
        key,
        label: title,
        description,
        kind: "structured_json" as const,
        defaultValue: jsonText(value[key]),
      };
    })
    .filter((item) => Boolean(item));
}

function parseDraftValue(field: SchemaPropertyField, rawValue: unknown) {
  if (field.kind === "boolean") {
    return { value: Boolean(rawValue), error: "" };
  }
  const text = String(rawValue ?? "");
  if (field.kind === "integer") {
    if (!text.trim()) return { value: undefined, error: "" };
    const parsed = Number.parseInt(text, 10);
    return Number.isFinite(parsed) && String(parsed) === text.trim()
      ? { value: parsed, error: "" }
      : { value: undefined, error: "Enter a whole number." };
  }
  if (field.kind === "number") {
    if (!text.trim()) return { value: undefined, error: "" };
    const parsed = Number(text);
    return Number.isFinite(parsed)
      ? { value: parsed, error: "" }
      : { value: undefined, error: "Enter a valid number." };
  }
  if (field.kind === "list") {
    const items = text
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);
    return { value: items, error: "" };
  }
  if (field.kind === "structured_json") {
    if (!text.trim()) return { value: {}, error: "" };
    try {
      const parsed = JSON.parse(text);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed)
        ? { value: parsed as Record<string, unknown>, error: "" }
        : { value: undefined, error: "Enter a JSON object." };
    } catch {
      return { value: undefined, error: "Enter valid JSON object text." };
    }
  }
  if (!text.trim()) return { value: undefined, error: "" };
  return { value: text, error: "" };
}

export function TaskGraphSchemaForm({
  schema,
  value,
  onChange,
  onValidityChange,
  referenceOptions,
  testIdPrefix = "task-graph-schema-form",
}: TaskGraphSchemaFormProps) {
  const effectiveReferenceOptions = useMemo(
    () => referenceOptions ?? {},
    [referenceOptions],
  );
  const fields = useMemo(
    () => propertiesForSchema(schema, value, effectiveReferenceOptions),
    [effectiveReferenceOptions, schema, value],
  );
  const [draft, setDraft] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(fields.map((field) => [field.key, field.defaultValue])),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    setDraft(Object.fromEntries(fields.map((field) => [field.key, field.defaultValue])));
    setErrors({});
  }, [fields]);

  useEffect(() => {
    if (!fields.length) {
      onValidityChange?.(true);
      return;
    }
    const nextErrors: Record<string, string> = {};
    const parsedValue: Record<string, unknown> = {};
    for (const field of fields) {
      const parsed = parseDraftValue(field, draft[field.key]);
      if (parsed.error) {
        nextErrors[field.key] = parsed.error;
        continue;
      }
      if (parsed.value !== undefined) {
        parsedValue[field.key] = parsed.value;
      }
    }
    setErrors(nextErrors);
    const valid = Object.keys(nextErrors).length === 0;
    onValidityChange?.(valid);
    if (valid) {
      const nextSerialized = JSON.stringify(parsedValue);
      const currentSerialized = JSON.stringify(value ?? {});
      if (nextSerialized !== currentSerialized) {
        onChange(parsedValue);
      }
    }
  }, [draft, fields, onChange, onValidityChange, value]);

  if (!fields.length) return null;

  return (
    <div className="task-graph-schema-form" data-testid={`${testIdPrefix}-root`}>
      {fields.map((field) => {
        const fieldTestId = `${testIdPrefix}-${field.key}`;
        const error = errors[field.key];
        const description = field.description ? (
          <small className="task-graph-muted">{field.description}</small>
        ) : null;
        if (field.kind === "boolean") {
          return (
            <label className="task-graph-checkbox" key={field.key}>
              <input
                type="checkbox"
                data-testid={fieldTestId}
                checked={Boolean(draft[field.key])}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    [field.key]: event.target.checked,
                  }))
                }
              />
              <span>{field.label}</span>
              {description}
            </label>
          );
        }
        if (field.kind === "enum") {
          return (
            <label className="task-graph-field" key={field.key}>
              <span>{field.label}</span>
              <select
                data-testid={fieldTestId}
                value={String(draft[field.key] ?? "")}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    [field.key]: event.target.value,
                  }))
                }
              >
                <option value="">Unspecified</option>
                {(field.enumOptions ?? []).map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              {description}
            </label>
          );
        }
        if (field.kind === "reference") {
          const options = effectiveReferenceOptions[field.key] ?? [];
          return (
            <label className="task-graph-field" key={field.key}>
              <span>{field.label}</span>
              {options.length ? (
                <select
                  data-testid={fieldTestId}
                  value={String(draft[field.key] ?? "")}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                >
                  <option value="">Unspecified</option>
                  {options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  data-testid={fieldTestId}
                  value={String(draft[field.key] ?? "")}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                />
              )}
              {description}
            </label>
          );
        }
        if (field.kind === "list" || field.kind === "structured_json") {
          return (
            <label className="task-graph-field" key={field.key}>
              <span>{field.label}</span>
              <textarea
                data-testid={fieldTestId}
                value={String(draft[field.key] ?? "")}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    [field.key]: event.target.value,
                  }))
                }
              />
              {description}
              {error ? (
                <small
                  className="task-graph-danger"
                  data-testid={`${fieldTestId}-error`}
                >
                  {error}
                </small>
              ) : null}
            </label>
          );
        }
        return (
          <label className="task-graph-field" key={field.key}>
            <span>{field.label}</span>
            <input
              data-testid={fieldTestId}
              type={field.kind === "number" || field.kind === "integer" ? "number" : "text"}
              value={String(draft[field.key] ?? "")}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  [field.key]: event.target.value,
                }))
              }
            />
            {description}
            {error ? (
              <small
                className="task-graph-danger"
                data-testid={`${fieldTestId}-error`}
              >
                {error}
              </small>
            ) : null}
          </label>
        );
      })}
    </div>
  );
}
