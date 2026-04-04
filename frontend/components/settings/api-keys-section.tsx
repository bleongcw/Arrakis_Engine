"use client";

import { useState, useEffect } from "react";
import { SettingsSection } from "./settings-section";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { fetchSettings, updateApiKeys } from "@/lib/api";

interface KeyStatus {
  anthropic_configured: boolean;
  anthropic_key_hint: string | null;
  openai_configured: boolean;
  openai_key_hint: string | null;
}

export function ApiKeysSection() {
  const [status, setStatus] = useState<KeyStatus>({
    anthropic_configured: false,
    anthropic_key_hint: null,
    openai_configured: false,
    openai_key_hint: null,
  });
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
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

  const handleUpdate = async (key: "anthropic" | "openai") => {
    const value = key === "anthropic" ? anthropicKey : openaiKey;
    if (!value.trim()) return;

    setSaving(key);
    setMessage(null);
    try {
      await updateApiKeys(
        key === "anthropic" ? { anthropic_key: value } : { openai_key: value },
      );
      setMessage({ type: "success", text: `${key === "anthropic" ? "Anthropic" : "OpenAI"} key updated.` });
      if (key === "anthropic") setAnthropicKey("");
      else setOpenaiKey("");
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

  return (
    <SettingsSection
      title="API Keys"
      description="API keys for LLM coaching. Stored in .env as ARRAKIS_ANTHROPIC_API_KEY / ARRAKIS_OPENAI_API_KEY. Only masked hints are shown."
    >
      <div className="space-y-4">
        {/* Status indicators */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <span className={status.anthropic_configured ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}>
            {status.anthropic_configured ? "\u2713" : "\u26A0"} Anthropic{" "}
            {status.anthropic_configured ? "configured" : "not configured"}
          </span>
          <span className={status.openai_configured ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}>
            {status.openai_configured ? "\u2713" : "\u26A0"} OpenAI{" "}
            {status.openai_configured ? "configured" : "not configured"}
          </span>
        </div>

        {(status.anthropic_configured || status.openai_configured) && (
          <p className="text-xs text-muted-foreground">
            Keys detected from environment. Leave fields empty to keep current keys. Only fill in to replace.
          </p>
        )}

        {/* Anthropic */}
        <div className="space-y-2">
          <Label htmlFor="anthropic_key">Anthropic API Key</Label>
          <div className="flex gap-2">
            <Input
              id="anthropic_key"
              type="password"
              value={anthropicKey}
              onChange={(e) => {
                setAnthropicKey(e.target.value);
                setMessage(null);
              }}
              placeholder={status.anthropic_key_hint || "sk-ant-..."}
              className="flex-1"
            />
            <Button
              size="sm"
              onClick={() => handleUpdate("anthropic")}
              disabled={!anthropicKey.trim() || saving === "anthropic"}
            >
              {saving === "anthropic" ? "..." : "Update"}
            </Button>
          </div>
        </div>

        {/* OpenAI */}
        <div className="space-y-2">
          <Label htmlFor="openai_key">OpenAI API Key</Label>
          <div className="flex gap-2">
            <Input
              id="openai_key"
              type="password"
              value={openaiKey}
              onChange={(e) => {
                setOpenaiKey(e.target.value);
                setMessage(null);
              }}
              placeholder={status.openai_key_hint || "sk-..."}
              className="flex-1"
            />
            <Button
              size="sm"
              onClick={() => handleUpdate("openai")}
              disabled={!openaiKey.trim() || saving === "openai"}
            >
              {saving === "openai" ? "..." : "Update"}
            </Button>
          </div>
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
