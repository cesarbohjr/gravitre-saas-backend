import { Button } from "@/components/ui/button";
import type { Range } from "@/lib/metrics-api";

type RangeSwitcherProps = {
  value: Range;
  onChange: (value: Range) => void;
};

const options: Range[] = ["7d", "30d", "90d"];

export function RangeSwitcher({ value, onChange }: RangeSwitcherProps) {
  return (
    <div className="flex gap-2">
      {options.map((opt) => (
        <Button
          key={opt}
          size="sm"
          variant={value === opt ? "primary" : "secondary"}
          onClick={() => onChange(opt)}
        >
          {opt}
        </Button>
      ))}
    </div>
  );
}
