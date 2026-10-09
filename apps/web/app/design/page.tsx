import { notFound } from "next/navigation";
import { Badge, Button, Card, EmptyState, Input, ProductTile, UsageMeter } from "@/components/ui";

// Design-system check page. Not linked anywhere; hidden in production.
export default function DesignPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return (
    <main className="mx-auto flex max-w-[1120px] flex-col gap-10 px-4 py-10">
      <h1 className="text-[28px] font-bold leading-[34px] text-nx-text">Design primitives</h1>

      <section className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold text-nx-text">Buttons</h2>
        <div className="flex flex-wrap items-center gap-3">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button loading>Saving</Button>
          <Button disabled>Disabled</Button>
          <Button size="sm">Small</Button>
          <Button size="lg">Large</Button>
        </div>
      </section>

      <section className="grid max-w-xl gap-4">
        <h2 className="text-xl font-semibold text-nx-text">Inputs</h2>
        <Input label="Organization name" placeholder="Acme Platform" hint="Shown to your team." />
        <Input label="Slug" defaultValue="Acme!" error="Use lowercase letters, numbers and dashes." />
        <Input label="Locked" disabled defaultValue="read only" />
      </section>

      <section className="flex flex-wrap gap-2">
        <Badge>Neutral</Badge>
        <Badge tone="accent">Beta</Badge>
        <Badge tone="success">Enabled</Badge>
        <Badge tone="warning">Past due</Badge>
        <Badge tone="danger">Suspended</Badge>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <ProductTile name="Vigilo" pitch="Scan a live URL for security and compliance issues." status="enabled" action={<Button size="sm">Open</Button>} />
        <ProductTile name="Sentinel" pitch="Paste a log sample and find the lines worth reading." status="beta" action={<Button size="sm" variant="secondary">Enable</Button>} />
        <ProductTile name="Gateway" pitch="One governed entry point for every model call." status="available" />
      </section>

      <Card className="grid max-w-xl gap-4">
        <UsageMeter label="Vigilo scans" used={2} limit={3} />
        <UsageMeter label="Targets" used={25} limit={25} />
        <UsageMeter label="API requests" used={1200} limit={null} />
      </Card>

      <EmptyState
        title="No members yet"
        body="Invite teammates so they can run scans and read reports."
        action={<Button>Invite a teammate</Button>}
      />
    </main>
  );
}
