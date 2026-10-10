import { brand } from "../../../lib/brand";

// RFC 9116. Expires is a rolling year so the file never goes stale.
export function GET() {
  const expires = new Date();
  expires.setUTCFullYear(expires.getUTCFullYear() + 1);
  const base = process.env.WEB_APP_URL?.replace(/\/$/, "");
  const lines = [
    `Contact: mailto:${brand.securityEmail}`,
    `Expires: ${expires.toISOString().replace(/\.\d+Z$/, "Z")}`,
    "Preferred-Languages: en",
    ...(base ? [`Canonical: ${base}/.well-known/security.txt`, `Policy: ${base}/trust`] : []),
  ];
  return new Response(lines.join("\n") + "\n", {
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}
