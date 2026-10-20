import { describe, expect, test } from "vitest";
import { normalizeMathMarkdown } from "./mathMarkdown";

describe("normalizeMathMarkdown", () => {
  test("normalizes single-line display math", () => {
    const input = '$$ V = 1.5 \\text{A} \\times 22 \\Omega $$';

    expect(normalizeMathMarkdown(input)).toBe(
      '$$\nV = 1.5 \\text{A} \\times 22 \\Omega\n$$',
    );
  });

  test("preserves ordinary inline code", () => {
    const input = "Run `npm run build` before testing.";

    expect(normalizeMathMarkdown(input)).toBe(input);
  });

  test("normalizes bare LaTeX equation lines", () => {
    const input = "V = 1.5 \\text{A} \\times 22 \\Omega";

    expect(normalizeMathMarkdown(input)).toBe(
      "$$\nV = 1.5 \\text{A} \\times 22 \\Omega\n$$",
    );
  });

  test("preserves inline and boxed LaTeX used by Gemini responses", () => {
    const input = String.raw`Substitute $I = 3\ \text{A}$ and $R = 5\ \Omega$.

$$
V = 3\ \text{A} \times 5\ \Omega
$$

$$
\boxed{V = 15\ \text{V}}
$$`;

    const result = normalizeMathMarkdown(input);

    expect(result).toContain(String.raw`$I = 3\ \text{A}$`);
    expect(result).toContain(String.raw`$R = 5\ \Omega$`);
    expect(result).toContain(String.raw`V = 3\ \text{A} \times 5\ \Omega`);
    expect(result).toContain(String.raw`\boxed{V = 15\ \text{V}}`);
  });
});
  test("wraps a bare boxed final answer from Gemini in display math", () => {
    const input = String.raw`Final Answer:

\boxed{V = 15\ \text{V}}`;

    expect(normalizeMathMarkdown(input)).toContain(
      String.raw`$$
\boxed{V = 15\ \text{V}}
$$`,
    );
  });
  test("wraps a bare boxed final answer as display math", () => {
    const input = String.raw`\boxed{V = 15\ \text{V}}`;

    const result = normalizeMathMarkdown(input);

    expect(result).toBe(String.raw`$$
\boxed{V = 15\ \text{V}}
$$`);
  });
