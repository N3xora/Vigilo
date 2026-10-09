import Link from "next/link";
import { DraftBanner } from "../../components/DraftBanner";
import { Footer } from "../../components/Footer";
import { brand } from "../../lib/brand";

export const metadata = { title: `Trust and security — ${brand.name}` };

const sections: { title: string; points: string[] }[] = [
  {
    title: "How scans stay safe",
    points: [
      "Passive scans only make requests a normal visitor or search crawler would make.",
      "Active scans (path enumeration, deeper probing) run only after you prove you control the target with a DNS record, a well-known file or a meta tag.",
      "Every outbound scan request goes through an egress guard that refuses private and internal addresses and pins the resolved IP, so a hostname cannot be switched to an internal address mid-scan (SSRF and DNS rebinding).",
      "The authorization decision for each scan is written to the audit log.",
    ],
  },
  {
    title: "How we handle what scans find",
    points: [
      "Anything that looks like a secret in captured evidence is redacted before storage. Only a fingerprint is kept, never the raw value.",
      "Evidence bundles are deleted after 90 days. Reports and scores are kept while your account exists.",
      "Only already-redacted finding summaries are sent to the LLM provider that writes remediation guidance. Raw evidence and credentials are never sent.",
    ],
  },
  {
    title: "Access control",
    points: [
      "Sign-in is handled by Clerk. We store an account identifier, not your password.",
      "Organisations have four roles: viewer, member, admin and owner. The server checks the role on every request, and data is scoped to the organisation.",
      "API keys and share-link tokens are shown once and stored only as SHA-256 hashes. API requests are rate-limited per organisation.",
      "Ownership of an organisation can be transferred, and there is always exactly one owner.",
    ],
  },
  {
    title: "Audit trail",
    points: [
      "Security-relevant actions (members, roles, keys, billing, scan authorization) are recorded in an append-only audit log that admins can read in the console.",
      "The log is append-only at the database level. It outlives deleted accounts, with the person anonymised.",
    ],
  },
  {
    title: "Your data and deleting it",
    points: [
      "You can delete your account yourself under Account in the console. That removes your account, the organisations you own with everything in them, stored files and your sign-in.",
      "Our payment provider keeps invoices it is legally required to keep.",
    ],
  },
  {
    title: "Subprocessors",
    points: [
      "Cloud hosting and database, email delivery, authentication (Clerk), billing (merchant of record) and an LLM provider. The Privacy Policy describes what each receives.",
    ],
  },
];

export default function TrustPage() {
  return (
    <>
      <DraftBanner />
      <main className="flex-1 mx-auto w-full max-w-2xl px-6 py-12 space-y-8">
        <div>
          <Link href="/" className="text-sm hover:underline">
            &larr; Back to {brand.name}
          </Link>
          <h1 className="mt-4 text-2xl font-bold">Trust and security</h1>
          <p className="mt-2">
            What {brand.name} does today to protect your data and the sites it
            scans. This page lists practices that exist in the product. It
            does not claim certifications.
          </p>
        </div>

        {sections.map((s) => (
          <section key={s.title} className="space-y-2">
            <h2 className="text-lg font-semibold">{s.title}</h2>
            <ul className="list-disc pl-6 space-y-1">
              {s.points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </section>
        ))}

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">What we do not have yet</h2>
          <p>
            No SOC 2 or ISO 27001 report, and no third-party penetration test
            has been published. If you need either for procurement, tell us.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Report a vulnerability</h2>
          <p>
            Email{" "}
            <a href={`mailto:${brand.securityEmail}`} className="underline">
              {brand.securityEmail}
            </a>{" "}
            with steps to reproduce. See also the{" "}
            <Link href="/privacy" className="underline">
              Privacy Policy
            </Link>{" "}
            and{" "}
            <Link href="/aup" className="underline">
              Acceptable Use Policy
            </Link>
            .
          </p>
        </section>
      </main>
      <Footer />
    </>
  );
}
