import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { formatCents, formatRelative } from "@/lib/format";

// M7-C7
describe("formatCents", () => {
  it.each([
    [0, "$0.00"],
    [5, "$0.05"],
    [1234, "$12.34"],
    [100, "$1.00"],
    [50, "$0.50"],
    [99, "$0.99"],
    [123456789, "$1234567.89"],
    [-5, "-$0.05"],
  ])("formats %i cents as %s", (cents, expected) => {
    expect(formatCents(cents)).toBe(expected);
  });

  it.each([0.5, 1.25, Number.NaN, Number.POSITIVE_INFINITY])("rejects non-integer %s", (value) => {
    expect(() => formatCents(value)).toThrow(TypeError);
  });

  it("money code uses only integer/string math (INV-1)", () => {
    const source = readFileSync(resolve(process.cwd(), "src/lib/format.ts"), "utf8");
    const match = /\/\/ money:start\n([\s\S]*?)\/\/ money:end/.exec(source);
    expect(match).not.toBeNull();
    const code = (match?.[1] ?? "")
      .split("\n")
      .map((line) => line.replace(/\/\/.*$/, ""))
      .join("\n");
    expect(code).toContain("function formatCents");
    expect(code).not.toMatch(/\//);
    for (const banned of ["toFixed", "parseFloat", "Math.", "Decimal", "Intl", "toLocaleString"]) {
      expect(code).not.toContain(banned);
    }
  });
});

describe("formatRelative", () => {
  const now = Date.parse("2026-11-10T12:00:00Z");
  it.each([
    ["2026-11-10T11:59:30Z", "now"],
    ["2026-11-10T11:55:00Z", "5m"],
    ["2026-11-10T09:00:00Z", "3h"],
    ["2026-11-08T12:00:00Z", "2d"],
  ])("%s -> %s", (iso, expected) => {
    expect(formatRelative(iso, now)).toBe(expected);
  });
});
