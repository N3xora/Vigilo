"""Stack awareness: turn the signals a scan observed into a short label list
and, for a few findings, one sentence on why the finding matters for that
stack. Pure functions, no I/O. A sentence is only produced when the signals
make it true; otherwise the finding shows no extra line.
"""

from __future__ import annotations

_LABELS = {
    "next.js": "Next.js",
    "vite": "Vite",
    "astro": "Astro",
    "angular": "Angular",
    "react": "React",
    "nuxt": "Nuxt",
    "vercel": "Vercel",
    "netlify": "Netlify",
    "cloudflare": "Cloudflare",
    "github-pages": "GitHub Pages",
    "aws-s3": "AWS S3",
    "aws-cloudfront": "CloudFront",
    "supabase": "Supabase",
    "firebase": "Firebase",
}


def stack_from_signals(
    hosting_signals: list[str], framework_signals: list[str], backend_providers: list[str]
) -> list[str]:
    """Stable, de-duplicated stack keys, e.g. ["next.js", "supabase", "vercel"]."""
    return sorted({*hosting_signals, *framework_signals, *backend_providers})


def stack_labels(stack: list[str]) -> list[str]:
    return [_LABELS[key] for key in stack if key in _LABELS]


def why_here(check_id: str, category: str, title: str, stack: list[str]) -> str | None:
    keys = set(stack)
    if category == "DAT" and "supabase" in keys:
        return (
            "Your app talks to Supabase straight from the browser, so database policies "
            "are the only thing between a visitor and your data."
        )
    if category == "DAT" and "firebase" in keys:
        return (
            "Your app talks to Firebase straight from the browser, so its security rules "
            "are the only thing between a visitor and your data."
        )
    if category == "CLI" and "in client bundle" in title:
        if "next.js" in keys:
            return (
                "Next.js copies every variable whose name starts with NEXT_PUBLIC_ into the "
                "page every visitor downloads, so anything with that prefix is public."
            )
        if "vite" in keys:
            return (
                "Vite copies every variable whose name starts with VITE_ into the script every "
                "visitor downloads, so anything with that prefix is public."
            )
    if category == "HDR" and keys & {"vercel", "netlify"}:
        where = "vercel.json" if "vercel" in keys else "netlify.toml or a _headers file"
        return f"On your host, response headers are set in {where}, not in your app code."
    return None
