import { PRODUCTS } from "../../../lib/nexora/catalog";
import { getActiveOrg, listUsage } from "../../../lib/nexora/data";
import { Card, EmptyState, UsageMeter } from "../../../components/ui";

export default async function UsagePage() {
  const org = await getActiveOrg();
  const rows = await listUsage(org.id);

  return (
    <div className="space-y-6">
      <h1 className="text-[28px] font-bold leading-[34px] text-nx-text">Usage</h1>
      {rows.length === 0 ? (
        <EmptyState title="Nothing used yet" body="Enable a product and run something. Meters appear here as soon as there is usage." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {rows.map((row) => (
            <Card key={`${row.slug}-${row.meter}`} className="space-y-3">
              <h2 className="text-lg font-semibold text-nx-text">{PRODUCTS.find((p) => p.slug === row.slug)?.name}</h2>
              <UsageMeter label={row.meter} used={row.used} limit={row.limit} />
              <p className="text-xs text-nx-text-muted">Resets {row.resetsOn}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
