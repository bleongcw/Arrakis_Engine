"use client";

import { useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Uncaught error:", error);
  }, [error]);

  return (
    <div className="flex items-center justify-center min-h-[50vh] p-4">
      <Card className="max-w-md w-full">
        <CardHeader>
          <CardTitle className="text-lg text-destructive">Something went wrong</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            An unexpected error occurred. This is usually temporary — try again or return to the dashboard.
          </p>
          {error.message && (
            <pre className="text-xs bg-muted rounded-md p-3 overflow-x-auto whitespace-pre-wrap break-words">
              {error.message}
            </pre>
          )}
          <div className="flex gap-2">
            <Button size="sm" onClick={reset}>
              Try again
            </Button>
            <Button size="sm" variant="outline" onClick={() => (window.location.href = "/dashboard")}>
              Go to Dashboard
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
