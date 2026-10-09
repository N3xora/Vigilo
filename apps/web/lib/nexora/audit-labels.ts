import type { AuditEntryResponse } from "../types";

function str(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

// One plain sentence per recorded action. Anything not listed falls back to the
// action name with underscores turned into spaces, so a new action is readable
// before it gets a sentence here.
export function describeAudit(e: AuditEntryResponse): string {
  const d = e.details;
  const s = e.subject;
  switch (e.action) {
    case "org_created":
      return "Created the organisation";
    case "invite_created":
      return `Invited ${s}${str(d.role) ? ` as ${d.role}` : ""}`;
    case "invite_resent":
      return `Sent ${s} a new invitation link`;
    case "invite_revoked":
      return "Withdrew an invitation";
    case "invite_accepted":
      return `${s} accepted an invitation${str(d.role) ? ` and joined as ${d.role}` : ""}`;
    case "member_role_changed":
      return `Changed ${s}'s role${str(d.previous) ? ` from ${d.previous}` : ""} to ${str(d.role) ?? "another role"}`;
    case "member_removed":
      return `Removed ${s} from the organisation`;
    case "member_left":
      return `${s} left the organisation`;
    case "ownership_transferred":
      return `Handed the organisation to ${s}`;
    case "product_enabled":
      return `Enabled ${s}`;
    case "api_key_created":
      return `Created API key ${s}${str(d.name) ? ` (${d.name})` : ""}`;
    case "api_key_revoked":
      return `Revoked API key ${s}`;
    case "branding_updated":
      return `Updated report branding${Array.isArray(d.fields) && d.fields.length ? ` (${d.fields.join(", ")})` : ""}`;
    case "target_added":
      return `Added target ${s}`;
    case "monitor_enabled":
      return `Turned on monitoring for ${s}`;
    case "monitor_disabled":
      return `Turned off monitoring for ${s}`;
    case "share_link_created":
      return "Created a public share link for a report";
    case "share_link_revoked":
      return "Revoked a public share link";
    case "checkout_started":
      return `Started checkout for the ${s} plan${str(d.interval) ? ` (${d.interval}ly)` : ""}`;
    case "billing_portal_opened":
      return "Opened the billing portal";
    case "subscription_updated":
      return `Subscription changed to ${str(d.plan_id) ?? "a plan"}, now ${str(d.status) ?? "updated"}`;
    case "finding_suppressed":
      return `Accepted a risk (${str(d.check_id) ?? s})`;
    case "finding_unsuppressed":
      return `Reopened an accepted risk (${str(d.check_id) ?? s})`;
    case "scan_authorized":
      return `Scan of ${s} authorised`;
    case "scan_denied":
      return `Scan of ${s} refused${str(d.reason) ? `: ${d.reason}` : ""}`;
    case "scan_execution_denied":
      return `Scan of ${s} blocked by network safety rules`;
    case "quota_exceeded":
      return `Plan limit reached (${str(d.meter) ?? "quota"}) for ${s}`;
    case "ownership_verified":
      return `Verified ownership of ${s}${str(d.method) ? ` by ${d.method}` : ""}`;
    case "monitor_scan_authorized":
      return `Scheduled scan of ${s} authorised`;
    default:
      return e.action.replace(/_/g, " ");
  }
}
