import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function NotFound() {
  return (
    <div className="flex items-center justify-center min-h-[50vh] p-4">
      <Card className="max-w-md w-full text-center">
        <CardHeader>
          <CardTitle className="text-lg">Page not found</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            The page you&apos;re looking for doesn&apos;t exist or has been moved.
          </p>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90"
          >
            Go to Dashboard
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
