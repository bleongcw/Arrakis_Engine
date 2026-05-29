"use client";

import { useState, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { OpponentSearch } from "@/components/hunter/opponent-search";
import { TargetedPrep } from "@/components/hunter/targeted-prep";
import { OpponentBlindSpots } from "@/components/hunter/opponent-blind-spots";
import { fetchHunterProfile, refreshHunterProfile } from "@/lib/api";
import type { OpponentProfile, HuntPlatform } from "@/lib/types";

export default function HuntPage() {
  const [profile, setProfile] = useState<OpponentProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState<{
    opponent: string;
    platform: HuntPlatform;
  } | null>(null);

  const runSearch = useCallback(
    async (opponent: string, platform: HuntPlatform) => {
      setLoading(true);
      setError(null);
      setProfile(null);
      try {
        const data = await fetchHunterProfile(opponent, platform);
        // Server returns {error: "..."} when Hunter Mode is disabled
        if ((data as { error?: string }).error) {
          setError((data as { error: string }).error);
          return;
        }
        setProfile(data);
        setLastQuery({ opponent, platform });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to fetch profile.");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  // v1.20.0: re-fetch the profile (now carrying Deep Scan results) after a
  // scan completes — served from the 24h cache, so this is a fast read.
  const reloadProfile = useCallback(async () => {
    if (!lastQuery) return;
    try {
      const data = await fetchHunterProfile(
        lastQuery.opponent,
        lastQuery.platform,
      );
      if (!(data as { error?: string }).error) setProfile(data);
    } catch {
      // Non-fatal — the scan still ran; the user can refresh manually.
    }
  }, [lastQuery]);

  const handleRefresh = useCallback(async () => {
    if (!lastQuery) return;
    setRefreshing(true);
    setError(null);
    try {
      const data = await refreshHunterProfile(
        lastQuery.opponent,
        lastQuery.platform,
      );
      setProfile(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed.");
    } finally {
      setRefreshing(false);
    }
  }, [lastQuery]);

  return (
    <div className="max-w-6xl mx-auto px-3 sm:px-4 py-6 space-y-4">
      <Card>
        <CardContent className="pt-6 space-y-4">
          <div>
            <h1 className="text-2xl font-bold">Hunter Mode</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Look up an opponent&apos;s public games on chess.com or lichess
              and surface their weakest openings (your hunting targets) and
              strongest openings (lines to avoid).
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Profiles are cached for 24 hours per opponent. The fetch covers
              the last 3 months of public games — no Stockfish analysis is
              run, so even big accounts return quickly.
            </p>
          </div>
          <OpponentSearch onSearch={runSearch} loading={loading} />
        </CardContent>
      </Card>

      {error && (
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-destructive">
              <strong>Hunt failed:</strong> {error}
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              Common causes: opponent username is misspelt, the account has
              no public games on the chosen platform, or the platform is
              rate-limiting. Try the other platform or wait a minute.
            </p>
          </CardContent>
        </Card>
      )}

      {profile && (
        <Card>
          <CardContent className="pt-6">
            <TargetedPrep
              profile={profile}
              onRefresh={handleRefresh}
              refreshing={refreshing}
            />
          </CardContent>
        </Card>
      )}

      {profile && lastQuery && (
        <Card>
          <CardContent className="pt-6">
            <OpponentBlindSpots
              opponent={lastQuery.opponent}
              platform={lastQuery.platform}
              profile={profile}
              onScanComplete={reloadProfile}
            />
          </CardContent>
        </Card>
      )}

      {!profile && !error && !loading && (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-8 text-muted-foreground">
              <p className="text-sm">
                Enter an opponent&apos;s username above to start hunting.
              </p>
              <p className="text-xs mt-2">
                Examples: <code className="px-1.5 py-0.5 bg-muted rounded">MagnusCarlsen</code>{" "}
                on chess.com,{" "}
                <code className="px-1.5 py-0.5 bg-muted rounded">DrNykterstein</code>{" "}
                on lichess.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
