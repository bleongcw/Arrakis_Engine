"use client";

import { useState, useEffect } from "react";
import { SettingsSection } from "./settings-section";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchSettings, updateCoachingSettings } from "@/lib/api";
import { PROVIDERS } from "@/lib/providers";
import type { Provider } from "@/lib/types";

interface CoachingForm {
  default_provider: Provider;
  anthropic_model: string;
  openai_model: string;
  gemini_model: string;
  grok_model: string;
  mistral_model: string;
  deepseek_model: string;
  qwen_model: string;
  ollama_model: string;
  ollama_base_url: string;
  tone: "encouraging" | "balanced" | "technical";
  detail_level: "concise" | "standard" | "detailed";
  focus_areas: string[];
  custom_instructions: string;
}

const ALL_FOCUS_AREAS = [
  { key: "openings", label: "Openings" },
  { key: "tactics", label: "Tactics" },
  { key: "endgames", label: "Endgames" },
  { key: "time_management", label: "Time Management" },
  { key: "positional_play", label: "Positional Play" },
];

const DEFAULTS: CoachingForm = {
  default_provider: "claude",
  anthropic_model: "claude-opus-4-6",
  openai_model: "gpt-5.4-pro",
  gemini_model: "gemini-2.5-pro",
  grok_model: "grok-3",
  mistral_model: "mistral-medium-latest",
  deepseek_model: "deepseek-reasoner",
  qwen_model: "qwen3-235b-a22b",
  ollama_model: "deepseek-r1:8b",
  ollama_base_url: "http://localhost:11434",
  tone: "balanced",
  detail_level: "standard",
  focus_areas: ["openings", "tactics", "endgames", "time_management", "positional_play"],
  custom_instructions: "",
};

const MODEL_FIELDS: { key: keyof CoachingForm; label: string; placeholder: string }[] = [
  { key: "anthropic_model", label: "Claude Model", placeholder: "claude-opus-4-6" },
  { key: "openai_model", label: "ChatGPT Model", placeholder: "gpt-5.4-pro" },
  { key: "gemini_model", label: "Gemini Model", placeholder: "gemini-2.5-pro" },
  { key: "grok_model", label: "Grok Model", placeholder: "grok-3" },
  { key: "mistral_model", label: "Mistral Model", placeholder: "mistral-medium-latest" },
  { key: "deepseek_model", label: "DeepSeek Model", placeholder: "deepseek-reasoner" },
  { key: "qwen_model", label: "Qwen Model", placeholder: "qwen3-235b-a22b" },
  { key: "ollama_model", label: "Ollama Model", placeholder: "deepseek-r1:8b" },
];

export function CoachingSection() {
  const [form, setForm] = useState<CoachingForm>(DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  useEffect(() => {
    fetchSettings()
      .then((s) => {
        if (s.coaching) {
          setForm({
            default_provider: (s.coaching.default_provider || DEFAULTS.default_provider) as Provider,
            anthropic_model: s.coaching.anthropic_model || DEFAULTS.anthropic_model,
            openai_model: s.coaching.openai_model || DEFAULTS.openai_model,
            gemini_model: s.coaching.gemini_model || DEFAULTS.gemini_model,
            grok_model: s.coaching.grok_model || DEFAULTS.grok_model,
            mistral_model: s.coaching.mistral_model || DEFAULTS.mistral_model,
            deepseek_model: s.coaching.deepseek_model || DEFAULTS.deepseek_model,
            qwen_model: s.coaching.qwen_model || DEFAULTS.qwen_model,
            ollama_model: s.coaching.ollama_model || DEFAULTS.ollama_model,
            ollama_base_url: s.coaching.ollama_base_url || DEFAULTS.ollama_base_url,
            tone: s.coaching.tone || DEFAULTS.tone,
            detail_level: s.coaching.detail_level || DEFAULTS.detail_level,
            focus_areas: s.coaching.focus_areas || DEFAULTS.focus_areas,
            custom_instructions: s.coaching.custom_instructions || "",
          });
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      await updateCoachingSettings(form);
      setStatus({ type: "success", msg: "Coaching settings saved." });
    } catch (err) {
      setStatus({
        type: "error",
        msg: err instanceof Error ? err.message : "Failed to save.",
      });
    } finally {
      setSaving(false);
    }
  };

  const toggleFocus = (area: string) => {
    setForm((prev) => ({
      ...prev,
      focus_areas: prev.focus_areas.includes(area)
        ? prev.focus_areas.filter((a) => a !== area)
        : [...prev.focus_areas, area],
    }));
    setStatus(null);
  };

  const cloudProviders = PROVIDERS.filter(p => p.group === "cloud");
  const localProviders = PROVIDERS.filter(p => p.group === "local");

  return (
    <SettingsSection
      title="Coaching"
      description="Customize how the AI coach analyzes games and delivers feedback."
    >
      <div className="space-y-5">
        {/* Custom Instructions */}
        <div className="space-y-2">
          <Label htmlFor="custom_instructions">Custom Instructions</Label>
          <textarea
            id="custom_instructions"
            value={form.custom_instructions}
            onChange={(e) => {
              setForm((prev) => ({ ...prev, custom_instructions: e.target.value }));
              setStatus(null);
            }}
            placeholder="e.g. Always mention pawn structure. Use sports analogies. Focus on time management habits."
            rows={4}
            maxLength={2000}
            className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          />
          <p className="text-xs text-muted-foreground">
            Free-form instructions injected into the coaching prompt. These guide the AI coach on tone, focus, analogies, or any special preferences. ({form.custom_instructions.length}/2000)
          </p>
        </div>

        {/* Tone & Detail Level */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Coaching Tone</Label>
            <Select
              value={form.tone}
              onValueChange={(v) => {
                if (v) {
                  setForm((prev) => ({ ...prev, tone: v as CoachingForm["tone"] }));
                  setStatus(null);
                }
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="encouraging">Encouraging — extra praise, gentle on mistakes</SelectItem>
                <SelectItem value="balanced">Balanced — warm but honest</SelectItem>
                <SelectItem value="technical">Technical — precise terminology, direct feedback</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Detail Level</Label>
            <Select
              value={form.detail_level}
              onValueChange={(v) => {
                if (v) {
                  setForm((prev) => ({ ...prev, detail_level: v as CoachingForm["detail_level"] }));
                  setStatus(null);
                }
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="concise">Concise — short narratives, fewer tips</SelectItem>
                <SelectItem value="standard">Standard — balanced length</SelectItem>
                <SelectItem value="detailed">Detailed — thorough analysis, more tips</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Focus Areas */}
        <div className="space-y-2">
          <Label>Focus Areas</Label>
          <p className="text-xs text-muted-foreground mb-2">
            Select areas the coach should emphasize when relevant to the game.
          </p>
          <div className="flex flex-wrap gap-3">
            {ALL_FOCUS_AREAS.map(({ key, label }) => (
              <label
                key={key}
                className="flex items-center gap-2 cursor-pointer select-none"
              >
                <input
                  type="checkbox"
                  checked={form.focus_areas.includes(key)}
                  onChange={() => toggleFocus(key)}
                  className="h-4 w-4 rounded border-input accent-primary"
                />
                <span className="text-sm">{label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Default Provider */}
        <div className="space-y-2">
          <Label>Default Provider</Label>
          <Select
            value={form.default_provider}
            onValueChange={(v) => {
              if (v) {
                setForm((prev) => ({ ...prev, default_provider: v as Provider }));
                setStatus(null);
              }
            }}
          >
            <SelectTrigger className="w-[240px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectLabel>Cloud</SelectLabel>
                {cloudProviders.map(p => (
                  <SelectItem key={p.slug} value={p.slug}>{p.name}</SelectItem>
                ))}
              </SelectGroup>
              <SelectGroup>
                <SelectLabel>Local</SelectLabel>
                {localProviders.map(p => (
                  <SelectItem key={p.slug} value={p.slug}>{p.name}</SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>

        {/* Model Overrides */}
        <div className="space-y-2">
          <Label>Model Overrides</Label>
          <p className="text-xs text-muted-foreground mb-2">
            Customize the model used for each provider. Leave as default unless you need a specific model version.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {MODEL_FIELDS.map(({ key, label, placeholder }) => (
              <div key={key} className="space-y-1">
                <Label htmlFor={key} className="text-xs">{label}</Label>
                <Input
                  id={key}
                  value={form[key] as string}
                  onChange={(e) => {
                    setForm((prev) => ({ ...prev, [key]: e.target.value }));
                    setStatus(null);
                  }}
                  placeholder={placeholder}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Ollama Base URL */}
        <div className="space-y-2">
          <Label htmlFor="ollama_base_url">Ollama Server URL</Label>
          <Input
            id="ollama_base_url"
            value={form.ollama_base_url}
            onChange={(e) => {
              setForm((prev) => ({ ...prev, ollama_base_url: e.target.value }));
              setStatus(null);
            }}
            placeholder="http://localhost:11434"
            className="max-w-md"
          />
          <p className="text-xs text-muted-foreground">
            URL of the Ollama server. Default is http://localhost:11434 for local installation.
          </p>
        </div>

        {/* Save */}
        <div className="flex items-center gap-3">
          <Button onClick={handleSave} disabled={saving} size="sm">
            {saving ? "Saving..." : "Save"}
          </Button>
          {status && (
            <span
              className={`text-sm ${
                status.type === "success"
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-destructive"
              }`}
            >
              {status.msg}
            </span>
          )}
        </div>
      </div>
    </SettingsSection>
  );
}
