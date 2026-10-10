import { Client } from "pg";

// Direct access to the browser tests' own database. Used only to put a second
// *member* into an organisation: a row in this throwaway database, never an
// identity at Clerk, so the specs can exercise role changes, removal and
// ownership transfer without creating any account anywhere.
//
// Locally the database is vigilo_e2e (scripts/e2e-up.sh); CI sets E2E_DATABASE_URL.
const URL =
  process.env.E2E_DATABASE_URL ?? "postgresql://vigilo:vigilo-dev-secret@localhost:5433/vigilo_e2e";

export async function sql(statement: string, params: unknown[] = []): Promise<string> {
  const client = new Client({ connectionString: URL });
  await client.connect();
  try {
    const result = await client.query(statement, params);
    const first = result.rows[0];
    return first ? String(Object.values(first)[0]) : "";
  } finally {
    await client.end();
  }
}

export async function addMember(orgSlug: string, email: string, role: "viewer" | "member" | "admin") {
  const orgId = await sql("select id from organizations where slug = $1", [orgSlug]);
  if (!orgId) throw new Error(`no organisation with slug ${orgSlug}`);
  const accountId = await sql(
    "insert into accounts (id, email, status) values (gen_random_uuid(), $1, 'active') returning id",
    [email],
  );
  await sql(
    "insert into memberships (id, org_id, account_id, role) values (gen_random_uuid(), $1, $2, $3)",
    [orgId, accountId, role],
  );
  return { orgId, accountId };
}
