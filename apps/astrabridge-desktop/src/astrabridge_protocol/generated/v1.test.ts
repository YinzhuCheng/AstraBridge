import fixture from "../fixtures/protocol_v1.json";
import { describe, expect, it } from "vitest";

import { SCHEMA_VERSION, validateProtocolPayload } from "./v1";

describe("AstraBridge protocol v1 generated projection", () => {
  it("accepts every shared positive fixture", () => {
    for (const [kind, payload] of Object.entries(fixture.valid)) {
      const verdict = validateProtocolPayload(kind, payload);
      expect(verdict.ok, `${kind}: ${verdict.errors.join("; ")}`).toBe(true);
    }
  });

  it("rejects every shared negative fixture", () => {
    for (const [caseId, testCase] of Object.entries(fixture.invalid)) {
      const verdict = validateProtocolPayload(testCase.kind, testCase.payload);
      expect(verdict.ok, caseId).toBe(false);
    }
  });

  it("keeps the generated protocol version explicit", () => {
    expect(SCHEMA_VERSION).toBe("astrabridge-protocol-v1");
  });
});
