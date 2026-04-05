import type { Provider } from "./types";

export interface ProviderMeta {
  slug: Provider;
  name: string;
  color: string;
  group: "cloud" | "local";
}

/**
 * Static provider metadata for UI rendering.
 * Order determines display order in dropdowns.
 */
export const PROVIDERS: ProviderMeta[] = [
  { slug: "claude",   name: "Claude",          color: "#7c3aed", group: "cloud" },
  { slug: "openai",   name: "ChatGPT",         color: "#059669", group: "cloud" },
  { slug: "gemini",   name: "Gemini",          color: "#4285f4", group: "cloud" },
  { slug: "grok",     name: "Grok",            color: "#1d9bf0", group: "cloud" },
  { slug: "mistral",  name: "Mistral",         color: "#f97316", group: "cloud" },
  { slug: "deepseek", name: "DeepSeek",        color: "#6366f1", group: "cloud" },
  { slug: "qwen",     name: "Qwen",            color: "#ef4444", group: "cloud" },
  { slug: "ollama",   name: "Ollama (Local)",   color: "#737373", group: "local" },
];

export const CLOUD_PROVIDERS = PROVIDERS.filter(p => p.group === "cloud");
export const LOCAL_PROVIDERS = PROVIDERS.filter(p => p.group === "local");

export function getProviderMeta(slug: Provider): ProviderMeta {
  return PROVIDERS.find(p => p.slug === slug) ?? PROVIDERS[0];
}
