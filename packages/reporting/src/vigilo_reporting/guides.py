"""Hand-written, step-by-step fixes for the findings people most often get
stuck on. Used by `template_remediation()` in place of the one-line manifest
text. The LLM path (ADR-0004) is untouched: it still only adds prose around
findings that already exist, and a report without any LLM shows these guides.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FixGuide:
    steps: list[str]
    agent_prompt: str
    estimated_effort: str


_SUPABASE_RLS = FixGuide(
    steps=[
        "In the Supabase dashboard, open the Table Editor and list every table in the "
        "`public` schema, plus any other schema exposed through the API.",
        "Turn row level security on for each one: "
        "`alter table public.<table> enable row level security;`. With RLS on and no policy, "
        "the anon and authenticated roles can read and write nothing.",
        "Add the narrowest policy each table needs. Rows a signed-in user owns: "
        '`create policy "read own rows" on public.<table> for select to authenticated '
        "using ((select auth.uid()) = user_id);` and the same shape with `with check` for "
        "insert and update. Data that really is public gets a select-only policy for that "
        "one table.",
        "Views skip RLS by default. On Postgres 15 or later create them with "
        "`with (security_invoker = true)`, or keep them out of the exposed schema.",
        "Check it the way a visitor would: request "
        "`<project>.supabase.co/rest/v1/<table>?select=*` with only the anon key. You should "
        "get an empty list or an error, not rows. Then scan again.",
    ],
    agent_prompt=(
        "My Supabase project lets the public anon key read tables it should not. Fix it with "
        "row level security:\n"
        "1. List every table in the public schema (and any other exposed schema).\n"
        "2. For each, run `alter table <table> enable row level security;`.\n"
        "3. Write the narrowest policies the app actually needs. Use "
        "`(select auth.uid()) = user_id` for rows a user owns, with `using` for select and "
        "delete and `with check` for insert and update. Only add a policy for anon where the "
        "data is meant to be public.\n"
        "4. Recreate any view with `security_invoker = true`, or move it out of the exposed "
        "schema.\n"
        "5. Never put the service_role key in client code.\n"
        "Show me the SQL as a migration file, list which tables stay public and why, and tell "
        "me how to verify with a request that uses only the anon key."
    ),
    estimated_effort="medium",
)

GUIDES: dict[str, FixGuide] = {"VG-DAT-002": _SUPABASE_RLS}


def get_guide(check_id: str) -> FixGuide | None:
    return GUIDES.get(check_id)
