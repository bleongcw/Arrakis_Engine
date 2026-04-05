"use client";

import { useState, useEffect } from "react";
import { SettingsSection } from "./settings-section";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchSettings, updateCoachingSettings } from "@/lib/api";

interface CoachingForm {
  default_provider: "claude" | "openai";
  anthropic_model: string;
  openai_model: string;
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
  openai_model: "chatgpt-5.4-pro",
  tone: "balanced",
  detail_level: "standard",
  focus_areas: ["openings", "tactics", "endgames", "time_management", "positional_play"],
  custom_instructions: "",
};

export function CoachingSection() {
  const [form, setForm] = useState<CoachingForm>(DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  useEffect(() => {
    fetchSettings()
      .then((s) => {
        if (s.coaching) {
          setForm({
            default_provider: s.coaching.default_provider || DEFAULTS.default_provider,
            anthropic_model: s.coaching.anthropic_model || DEFAULTS.anthropic_model,
            openai_model: s.coaching.openai_model || DEFAULTS.openai_model,
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

        {/* Provider & Models */}
        <div className="space-y-2">
          <Label>Default Provider</Label>
          <Select
            value={form.default_provider}
            onValueChange={(v) => {
              if (v) {
                setForm((prev) => ({ ...prev, default_provider: v as CoachingForm["default_provider"] }));
                setStatus(null);
              }
            }}
          >
            <SelectTrigger className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="claude">Claude (Anthropic)</SelectItem>
              <SelectItem value="openai">OpenAI</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="anthropic_model">Anthropic Model</Label>
            <Input
              id="anthropic_model"
              value={form.anthropic_model}
              onChange={(e) => {
                setForm((prev) => ({ ...prev, anthropic_model: e.target.value }));
                setStatus(null);
              }}
              placeholder="claude-opus-4-6"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="openai_model">OpenAI Model</Label>
            <Input
              id="openai_model"
              value={form.openai_model}
              onChange={(e) => {
                setForm((prev) => ({ ...prev, openai_model: e.target.value }));
                setStatus(null);
              }}
              placeholder="chatgpt-5.4-pro"
            />
          </div>
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
