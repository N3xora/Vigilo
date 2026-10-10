import type { ReactNode } from "react";
import { Badge } from "./Badge";
import { Card } from "./Card";

export type ProductStatus = "enabled" | "available" | "beta" | "soon";

export function ProductTile({
  name,
  pitch,
  status,
  action,
}: {
  name: string;
  pitch: string;
  status: ProductStatus;
  action?: ReactNode;
}) {
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-nx-text">{name}</h3>
        <Badge tone={status === "enabled" ? "success" : status === "beta" ? "accent" : "neutral"}>
          {status === "enabled"
            ? "Enabled"
            : status === "beta"
              ? "Beta"
              : status === "soon"
                ? "Coming soon"
                : "Available"}
        </Badge>
      </div>
      <p className="text-sm text-nx-text-muted">{pitch}</p>
      {action && <div className="mt-auto pt-2">{action}</div>}
    </Card>
  );
}
