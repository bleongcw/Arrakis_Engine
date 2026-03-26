"use client";

import { Button } from "@/components/ui/button";

interface MoveControlsProps {
  onStart: () => void;
  onBack: () => void;
  onForward: () => void;
  onEnd: () => void;
}

export function MoveControls({ onStart, onBack, onForward, onEnd }: MoveControlsProps) {
  return (
    <div className="flex gap-2 justify-center mt-3">
      <Button variant="outline" size="sm" onClick={onStart} title="Go to start">
        &#9198;
      </Button>
      <Button variant="outline" size="sm" onClick={onBack} title="Previous move">
        &larr;
      </Button>
      <Button variant="outline" size="sm" onClick={onForward} title="Next move">
        &rarr;
      </Button>
      <Button variant="outline" size="sm" onClick={onEnd} title="Go to end">
        &#9197;
      </Button>
    </div>
  );
}
