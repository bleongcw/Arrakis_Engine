"use client";

import { PlayersSection } from "@/components/settings/players-section";
import { AnalysisSection } from "@/components/settings/analysis-section";
import { CoachingSection } from "@/components/settings/coaching-section";
import { ApiKeysSection } from "@/components/settings/api-keys-section";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Settings</h2>
      <PlayersSection />
      <AnalysisSection />
      <CoachingSection />
      <ApiKeysSection />
    </div>
  );
}
