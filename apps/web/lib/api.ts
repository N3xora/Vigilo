// A thin fetch wrapper over apps/api. Works from both Server Components
// (plain server-to-server fetch, no CORS involved) and Client Components
// (the CORS middleware in apps/api/src/vigilo_api/main.py is scoped to
// exactly this: browser calls for PDF export and share-link management).
import type {
  AccountResponse,
  AlertResponse,
  ApiErrorBody,
  ApiKeyCreateResponse,
  ApiKeyResponse,
  AuditPageResponse,
  BrandingProfileResponse,
  BillingSummaryResponse,
  CheckoutResponse,
  DeleteAccountResponse,
  DeletionBlocker,
  PortalResponse,
  MonitorResponse,
  OrgInviteCreateResponse,
  OrgInviteResponse,
  OrgMemberResponse,
  OrgProductResponse,
  OrgResponse,
  OrgUsageResponse,
  PdfStatusResponse,
  PlanResponse,
  ScanReportResponse,
  ScanStatusResponse,
  ScanSubmissionResponse,
  ScoreHistoryEntry,
  ShareLinkCreateResponse,
  ShareLinkResponse,
  SuppressionResponse,
  TargetResponse,
  VerificationCheckResponse,
  VerificationInitiateResponse,
  VerificationMethod,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null) {
    super(body?.message ?? `API request failed with status ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { token?: string | null; orgId?: string | null },
): Promise<T> {
  const { token, orgId, ...rest } = init ?? {};
  const headers = new Headers(rest.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  // Which organisation a list/create call acts in; the API defaults to the
  // caller's personal organisation when this is absent.
  if (orgId) headers.set("X-Org-Id", orgId);
  if (rest.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // no JSON body on this error response
    }
    throw new ApiError(response.status, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  submitScan: (body: { target_url: string; email: string }) =>
    request<ScanSubmissionResponse>("/v1/scans", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getScanStatus: (scanJobId: string) => request<ScanStatusResponse>(`/v1/scans/${scanJobId}`),

  getScanReport: (scanJobId: string, token?: string | null) =>
    request<ScanReportResponse>(`/v1/scans/${scanJobId}/report`, { token }),

  getShareReport: (token: string) => request<ScanReportResponse>(`/v1/share/${token}`),

  requestReportPdf: (scanJobId: string) =>
    request<PdfStatusResponse>(`/v1/scans/${scanJobId}/report/pdf`, { method: "POST" }),

  getReportPdfStatus: (scanJobId: string) =>
    request<PdfStatusResponse>(`/v1/scans/${scanJobId}/report/pdf`),

  createShareLink: (scanJobId: string, token: string, expiresInDays?: number | null) =>
    request<ShareLinkCreateResponse>(`/v1/scans/${scanJobId}/share-links`, {
      method: "POST",
      token,
      body: JSON.stringify({ expires_in_days: expiresInDays ?? null }),
    }),

  listShareLinks: (scanJobId: string, token: string) =>
    request<ShareLinkResponse[]>(`/v1/scans/${scanJobId}/share-links`, { token }),

  revokeShareLink: (shareLinkId: string, token: string) =>
    request<{ share_link_id: string; revoked_at: string }>(
      `/v1/share-links/${shareLinkId}/revoke`,
      { method: "POST", token },
    ),

  listOrgs: (token: string) => request<OrgResponse[]>("/v1/orgs", { token }),

  createOrg: (body: { name: string; slug: string }, token: string) =>
    request<OrgResponse>("/v1/orgs", { method: "POST", token, body: JSON.stringify(body) }),

  listOrgMembers: (orgId: string, token: string) =>
    request<OrgMemberResponse[]>(`/v1/orgs/${orgId}/members`, { token }),

  listOrgInvites: (orgId: string, token: string) =>
    request<OrgInviteResponse[]>(`/v1/orgs/${orgId}/invites`, { token }),

  createOrgInvite: (orgId: string, body: { email: string; role: string }, token: string) =>
    request<OrgInviteCreateResponse>(`/v1/orgs/${orgId}/invites`, {
      method: "POST",
      token,
      body: JSON.stringify(body),
    }),

  resendOrgInvite: (orgId: string, inviteId: string, token: string) =>
    request<OrgInviteCreateResponse>(`/v1/orgs/${orgId}/invites/${inviteId}/resend`, {
      method: "POST",
      token,
    }),

  revokeOrgInvite: (orgId: string, inviteId: string, token: string) =>
    request<void>(`/v1/orgs/${orgId}/invites/${inviteId}`, { method: "DELETE", token }),

  changeMemberRole: (orgId: string, accountId: string, role: string, token: string) =>
    request<OrgMemberResponse>(`/v1/orgs/${orgId}/members/${accountId}`, {
      method: "PATCH",
      token,
      body: JSON.stringify({ role }),
    }),

  transferOrgOwnership: (
    orgId: string,
    body: { new_owner_account_id: string; confirm_slug: string },
    token: string,
  ) =>
    request<OrgMemberResponse>(`/v1/orgs/${orgId}/transfer-ownership`, {
      method: "POST",
      token,
      body: JSON.stringify(body),
    }),

  removeOrgMember: (orgId: string, accountId: string, token: string) =>
    request<void>(`/v1/orgs/${orgId}/members/${accountId}`, { method: "DELETE", token }),

  acceptOrgInvite: (inviteToken: string, token: string) =>
    request<OrgResponse>(`/v1/invites/${encodeURIComponent(inviteToken)}/accept`, {
      method: "POST",
      token,
    }),

  getAuditLog: (
    orgId: string,
    token: string,
    query: { cursor?: string; action?: string; limit?: number } = {},
  ) => {
    const params = new URLSearchParams();
    if (query.cursor) params.set("cursor", query.cursor);
    if (query.action) params.set("action", query.action);
    if (query.limit) params.set("limit", String(query.limit));
    const qs = params.toString();
    return request<AuditPageResponse>(`/v1/orgs/${orgId}/audit${qs ? `?${qs}` : ""}`, { token });
  },

  listOrgProducts: (orgId: string, token: string) =>
    request<OrgProductResponse[]>(`/v1/orgs/${orgId}/products`, { token }),

  enableOrgProduct: (orgId: string, slug: string, token: string) =>
    request<OrgProductResponse>(`/v1/orgs/${orgId}/products/${slug}/enable`, {
      method: "POST",
      token,
    }),

  getOrgUsage: (orgId: string, token: string) =>
    request<OrgUsageResponse[]>(`/v1/orgs/${orgId}/usage`, { token }),

  getDeletionCheck: (token: string) =>
    request<{ blockers: DeletionBlocker[] }>("/v1/me/deletion-check", { token }),

  deleteAccount: (confirmEmail: string, token: string) =>
    request<DeleteAccountResponse>("/v1/me/delete", {
      method: "POST",
      token,
      body: JSON.stringify({ confirm_email: confirmEmail }),
    }),

  getMe: (token: string) => request<AccountResponse>("/v1/me", { token }),

  getTarget: (targetId: string, token: string) =>
    request<TargetResponse>(`/v1/targets/${targetId}`, { token }),

  getTargetMonitor: (targetId: string, token: string) =>
    request<MonitorResponse>(`/v1/targets/${targetId}/monitors`, { token }),

  createTargetMonitor: (
    targetId: string,
    token: string,
    body: { cadence_hours: number; quiet_start_utc?: number | null; quiet_end_utc?: number | null },
  ) =>
    request<MonitorResponse>(`/v1/targets/${targetId}/monitors`, {
      method: "POST",
      token,
      body: JSON.stringify(body),
    }),

  disableMonitor: (monitorId: string, token: string) =>
    request<MonitorResponse>(`/v1/monitors/${monitorId}/disable`, { method: "POST", token }),

  getTargetScoreHistory: (targetId: string, token: string) =>
    request<ScoreHistoryEntry[]>(`/v1/targets/${targetId}/scores`, { token }),

  getTargetAlerts: (targetId: string, token: string) =>
    request<AlertResponse[]>(`/v1/targets/${targetId}/alerts`, { token }),

  listTargets: (token: string, orgId?: string | null) =>
    request<TargetResponse[]>("/v1/targets", { token, orgId }),

  createTarget: (origin: string, token: string, orgId?: string | null) =>
    request<TargetResponse>("/v1/targets", {
      method: "POST",
      token,
      orgId,
      body: JSON.stringify({ origin }),
    }),

  initiateVerification: (targetId: string, method: VerificationMethod, token: string) =>
    request<VerificationInitiateResponse>(`/v1/targets/${targetId}/verification`, {
      method: "POST",
      token,
      body: JSON.stringify({ method }),
    }),

  checkVerification: (targetId: string, proofId: string, token: string) =>
    request<VerificationCheckResponse>(
      `/v1/targets/${targetId}/verification/${proofId}/check`,
      { method: "POST", token },
    ),

  listPlans: () => request<PlanResponse[]>("/v1/plans"),

  createCheckout: (
    planId: string,
    interval: "month" | "year",
    token: string,
    orgId?: string | null,
  ) =>
    request<CheckoutResponse>("/v1/billing/checkout", {
      method: "POST",
      token,
      orgId,
      body: JSON.stringify({ plan_id: planId, interval }),
    }),

  getBillingSummary: (token: string, orgId?: string | null) =>
    request<BillingSummaryResponse>("/v1/billing/summary", { token, orgId }),

  createPortal: (token: string, orgId?: string | null) =>
    request<PortalResponse>("/v1/billing/portal", { method: "POST", token, orgId }),

  createApiKey: (name: string, scopes: string[], token: string, orgId?: string | null) =>
    request<ApiKeyCreateResponse>("/v1/me/api-keys", {
      method: "POST",
      token,
      orgId,
      body: JSON.stringify({ name, scopes }),
    }),

  listApiKeys: (token: string, orgId?: string | null) =>
    request<ApiKeyResponse[]>("/v1/me/api-keys", { token, orgId }),

  revokeApiKey: (apiKeyId: string, token: string, orgId?: string | null) =>
    request<ApiKeyResponse>(`/v1/me/api-keys/${apiKeyId}/revoke`, {
      method: "POST",
      token,
      orgId,
    }),

  suppressFinding: (
    targetId: string,
    body: { fingerprint: string; check_id: string; reason: string; expires_at?: string | null },
    token: string,
  ) =>
    request<SuppressionResponse>(`/v1/targets/${targetId}/findings/suppress`, {
      method: "POST",
      token,
      body: JSON.stringify(body),
    }),

  listSuppressions: (targetId: string, token: string) =>
    request<SuppressionResponse[]>(`/v1/targets/${targetId}/suppressions`, { token }),

  revokeSuppression: (targetId: string, suppressionId: string, token: string) =>
    request<SuppressionResponse>(`/v1/targets/${targetId}/suppressions/${suppressionId}/revoke`, {
      method: "POST",
      token,
    }),

  getBrandingProfile: (token: string, orgId?: string | null) =>
    request<BrandingProfileResponse>("/v1/me/branding-profile", { token, orgId }),

  updateBrandingProfile: (
    body: {
      logo_url?: string;
      primary_color?: string;
      footer_text?: string;
      custom_domain?: string;
    },
    token: string,
    orgId?: string | null,
  ) =>
    request<BrandingProfileResponse>("/v1/me/branding-profile", {
      method: "PUT",
      token,
      orgId,
      body: JSON.stringify(body),
    }),
};

export function apiBaseUrl(): string {
  return API_BASE_URL;
}
