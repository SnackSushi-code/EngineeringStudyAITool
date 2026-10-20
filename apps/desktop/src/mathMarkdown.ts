export function normalizeMathMarkdown(content: string): string {
  let normalized = content;

  // Convert fenced math blocks into remark-math display blocks.
  normalized = normalized.replace(
    /(^|\n)[ \t]*```[ \t]*math[ \t]*\r?\n([\s\S]*?)\n[ \t]*```[ \t]*(?=\n|$)/gi,
    (_match, prefix: string, math: string) =>
      `${prefix}$$\n${math.trim()}\n$$`,
  );

  // Convert LaTeX display delimiters.
  normalized = normalized.replace(
    /\\\[([\s\S]*?)\\\]/g,
    (_match, math: string) => `$$\n${math.trim()}\n$$`,
  );

  // Convert LaTeX inline delimiters.
  normalized = normalized.replace(
    /\\\(([\s\S]*?)\\\)/g,
    (_match, math: string) => `$${math.trim()}$`,
  );

  // Convert single-line $$...$$ into proper multiline display math.
  normalized = normalized.replace(
    /\$\$[ \t]*([\s\S]*?)[ \t]*\$\$/g,
    (_match, math: string) => `$$\n${math.trim()}\n$$`,
  );

  // Convert equation-like inline code to math while preserving ordinary code.
  normalized = normalized.replace(
    /`([^`\n]+)`/g,
    (match: string, code: string) => {
      const candidate = code.trim();

      const looksLikeMath =
        candidate.includes("=") ||
        /(?:\\text\{|\\boxed\{|\\mathrm\{|\\frac\{|\\sqrt\{)/i.test(candidate);

      return looksLikeMath ? `$${candidate}$` : match;
    },
  );

  // Recognize genuinely bare standalone LaTeX equations.
  const lines = normalized.split(/\r?\n/);
  let inCodeFence = false;
  let inDisplayMath = false;

  normalized = lines
    .map((line) => {
      if (/^\s*```/.test(line)) {
        inCodeFence = !inCodeFence;
        return line;
      }

      if (!inCodeFence && /^\s*\$\$\s*$/.test(line)) {
        inDisplayMath = !inDisplayMath;
        return line;
      }

      if (inCodeFence || inDisplayMath || !line.trim()) {
        return line;
      }

      const candidate = line.trim();

      const looksLikeBareLatex =
        /\\(?:boxed|text|mathrm|frac|sqrt)\s*\{/.test(candidate) ||
        /\\(?:times|cdot|Omega|alpha|beta)\b/.test(candidate);

      if (
        looksLikeBareLatex &&
        !/^\s*(?:[-*+]|\d+[.)])\s/.test(line) &&
        !/[.!?]\s*$/.test(candidate)
      ) {
        return `$$\n${candidate}\n$$`;
      }

      return line;
    })
    .join("\n");

  return normalized.trim();
}
