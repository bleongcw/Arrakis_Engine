"use client";

import { useState, useEffect } from "react";
import { SettingsSection } from "./settings-section";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { fetchSettings, updateAnalysisSettings } from "@/lib/api";

interface AnalysisForm {
  stockfish_path: string;
  depth: number;
  threads: number;
  hash_mb: number;
  move_time_limit: number;
  months_lookback: number;
}

const DEFAULTS: AnalysisForm = {
  stockfish_path: "stockfish",
  depth: 22,
  threads: 6,
  hash_mb: 512,
  move_time_limit: 10.0,
  months_lookback: 6,
};

export function AnalysisSection() {
  const [form, setForm] = useState<AnalysisForm>(DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  useEffect(() => {
    fetchSettings()
      .then((s) => {
        setForm(s.analysis);
      })
      .catch(() => {
        // Use defaults if settings endpoint fails
      });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      await updateAnalysisSettings(form);
      setStatus({ type: "success", msg: "Settings saved." });
    } catch (err) {
      setStatus({
        type: "error",
        msg: err instanceof Error ? err.message : "Failed to save.",
      });
    } finally {
      setSaving(false);
    }
  };

  const update = (field: keyof AnalysisForm, value: string | number) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setStatus(null);
  };

  return (
    <SettingsSection
      title="Analysis"
      description="Configure Stockfish engine and data harvesting settings."
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="sf_path">Stockfish Path</Label>
          <Input
            id="sf_path"
            value={form.stockfish_path}
            onChange={(e) => update("stockfish_path", e.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label htmlFor="depth">Search Depth</Label>
            <Input
              id="depth"
              type="number"
              min={1}
              max={30}
              value={form.depth}
              onChange={(e) => update("depth", Number(e.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="threads">CPU Threads</Label>
            <Input
              id="threads"
              type="number"
              min={1}
              max={32}
              value={form.threads}
              onChange={(e) => update("threads", Number(e.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="hash_mb">Hash Memory (MB)</Label>
            <Input
              id="hash_mb"
              type="number"
              min={64}
              max={4096}
              value={form.hash_mb}
              onChange={(e) => update("hash_mb", Number(e.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="move_time">Time per Move (s)</Label>
            <Input
              id="move_time"
              type="number"
              min={1}
              max={60}
              step={0.5}
              value={form.move_time_limit}
              onChange={(e) => update("move_time_limit", Number(e.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="months">Months to Fetch</Label>
            <Input
              id="months"
              type="number"
              min={1}
              max={24}
              value={form.months_lookback}
              onChange={(e) => update("months_lookback", Number(e.target.value))}
            />
          </div>
        </div>

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
