import { randomInt } from "node:crypto";

const ADJECTIVES = [
  "sunny",
  "happy",
  "quiet",
  "brave",
  "calm",
  "clever",
  "gentle",
  "swift",
  "bright",
  "cozy",
  "fancy",
  "lucky",
  "merry",
  "proud",
  "shiny",
  "witty",
];

const NOUNS = [
  "panda",
  "river",
  "maple",
  "comet",
  "otter",
  "cloud",
  "tiger",
  "lemon",
  "robin",
  "coral",
  "pearl",
  "cedar",
  "falcon",
  "mochi",
  "sakura",
  "breeze",
];

/**
 * 読みやすいランダム slug を生成する。
 * 例: "sunny-panda-4821"
 */
export function generateSlug(): string {
  const adj = ADJECTIVES[randomInt(ADJECTIVES.length)];
  const noun = NOUNS[randomInt(NOUNS.length)];
  const num = String(randomInt(0, 10000)).padStart(4, "0");
  return `${adj}-${noun}-${num}`;
}

/** slug として妥当か(英小文字・数字・ハイフンのみ、1〜100文字) */
export function isValidSlug(slug: string): boolean {
  return /^[a-z0-9][a-z0-9-]{0,99}$/.test(slug);
}
