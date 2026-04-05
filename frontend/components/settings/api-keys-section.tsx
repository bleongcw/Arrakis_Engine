"use client";

import { useState, useEffect } from "react";
import { SettingsSection } from "./settings-section";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { fetchSettings, updateApiKeys } from "@/lib/api";
import type { ApiKeyStatus } from "@/lib/types";

/** Provider key configuration for the UI. */
const PROVIDER_KEYS = [
  { slug: "anthropic", label: "Anthropic", bodyField: "anthropic_key", configuredKey: "anthropic_configured", hintKey: "anthropic_key_hint", placeholder: "sk-ant-...", envVar: "ARRAKIS_ANTHROPIC_API_KEY" },
  { slug: "openai", label: "OpenAI", bodyField: "openai_key", configuredKey: "openai_configured", hintKey: "openai_key_hint", placeholder: "sk-...", envVar: "ARRAKIS_OPENAI_API_KEY" },
  { slug: "google", label: "Google (Gemini)", bodyField: "google_key", configuredKey: "google_configured", hintKey: "google_key_hint", placeholder: "AIza...", envVar: "ARRAKIS_GOOGLE_API_KEY" },
  { slug: "xai", label: "xAI (Grok)", bodyField: "xai_key", configuredKey: "xai_configured", hintKey: "xai_key_hint", placeholder: "xai-...", envVar: "ARRAKIS_XAI_API_KEY" },
  { slug: "mistral", label: "Mistral", bodyField: "mistral_key", configuredKey: "mistral_configured", hintKey: "mistral_key_hint", placeholder: "...", envVar: "ARRAKIS_MISTRAL_API_KEY" },
  { slug: "deepseek", label: "DeepSeek", bodyField: "deepseek_key", configuredKey: "deepseek_configured", hintKey: "deepseek_key_hint", placeholder: "sk-...", envVar: "ARRAKIS_DEEPSEEK_API_KEY" },
  { slug: "qwen", label: "Qwen", bodyField: "qwen_key", configuredKey: "qwen_configured", hintKey: "qwen_key_hint", placeholder: "sk-...", envVar: "ARRAKIS_QWEN_API_KEY" },
] as const;

const DEFAULT_STATUS: ApiKeyStatus = {
  anthropic_configured: false, anthropic_key_hint: null,
  openai_configured: false, openai_key_hint: null,
  google_configured: false, google_key_hint: null,
  xai_configured: false, xai_key_hint: null,
  mistral_configured: false, mistral_key_hint: null,
  deepseek_configured: false, deepseek_key_hint: null,
  qwen_configured: false, qwen_key_hint: null,
  ollama_configured: true,
};

export function ApiKeysSection() {
  const [status, setStatus] = useState<ApiKeyStatus>(DEFAULT_STATUS);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const loadStatus = () => {
    fetchSettings()
      .then((s) => setStatus(s.api_keys))
      .catch(() => {});
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleUpdate = async (provider: typeof PROVIDER_KEYS[number]) => {
    const value = (keys[provider.slug] || "").trim();
    if (!value) return;

    setSaving(provider.slug);
    setMessage(null);
    try {
      await updateApiKeys({ [provider.bodyField]: value });
      setMessage({ type: "success", text: `${provider.label} key updated.` });
      setKeys((prev) => ({ ...prev, [provider.slug]: "" }));
      loadStatus();
    } catch (err) {
      setMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to update key.",
      });
    } finally {
      setSaving(null);
    }
  };

  const anyConfigured = PROVIDER_KEYS.some(
    (p) => status[p.configuredKey as keyof ApiKeyStatus]
  );

  return (
    <SettingsSection
      title="API Keys"
      description="API keys for LLM coaching. Stored in .env file. Only masked hints are shown. Ollama runs locally and needs no key."
    >
      <div className="space-y-4">
        {/* Status indicators */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {PROVIDER_KEYS.map((p) => {
            const configured = status[p.configuredKey as keyof ApiKeyStatus];
            return (
              <span
                key={p.slug}
                className={
                  configured
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-amber-600 dark:text-amber-400"
                }
              >
                {configured ? "\u2713" : "\u26A0"} {p.label}{" "}
                {configured ? "configured" : "not configured"}
              </span>
            );
          })}
        </div>

        {anyConfigured && (
          <p className="text-xs text-muted-foreground">
            Keys detected from environment. Leave fields empty to keep current keys. Only fill in to replace.
          </p>
        )}

        {/* Key inputs — 2 columns on desktop */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {PROVIDER_KEYS.map((p) => {
            const hint = status[p.hintKey as keyof ApiKeyStatus] as string | null;
            return (
              <div key={p.slug} className="space-y-1.5">
                <Label htmlFor={`key_${p.slug}`}>
                  {p.label} API Key
                  <span className="ml-1.5 text-[10px] text-muted-foreground font-normal">
                    {p.envVar}
                  </span>
                </Label>
                <div className="flex gap-2">
                  <Input
                    id={`key_${p.slug}`}
                    type="password"
                    value={keys[p.slug] || ""}
                    onChange={(e) => {
                      setKeys((prev) => ({ ...prev, [p.slug]: e.target.value }));
                      setMessage(null);
                    }}
                    placeholder={hint || p.placeholder}
                    className="flex-1"
                  />
                  <Button
                    size="sm"
                    onClick={() => handleUpdate(p)}
                    disabled={!(keys[p.slug] || "").trim() || saving === p.slug}
                  >
                    {saving === p.slug ? "..." : "Update"}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>

        {message && (
          <p
            className={`text-sm ${
              message.type === "success"
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-destructive"
            }`}
          >
            {message.text}
          </p>
        )}
      </div>
    </SettingsSection>
  );
}
