# Components

Tokens: `replica/design/tokens.json` -> generated `apps/web/app/tokens.css` (Tailwind classes `bg-nx-*`, `text-nx-*`, `rounded-nx-*`, `shadow-nx-*`). Light and dark. Contrast: 17 light pairs and 12 dark pairs, 0 AA failures. Icons: Lucide (MIT) when needed. Font: Inter + JetBrains Mono (open). No assets from any third party.
Layout: content max 1120px, sidebar 248px, header 56px, breakpoints 640/768/1024. Spacing base 4. Radius 6/10/16.

Built in `apps/web/components/ui` and shown on `/design` (dev only):

Button
  variants  primary, secondary, ghost, danger
  sizes     sm 32, md 40, lg 48
  states    default, hover, active, focus-visible (2px accent outline), disabled, loading (keeps label, aria-busy)
  a11y      real <button>, type=button by default
  used on   all screens

Input
  states    default, hint, error (aria-invalid + aria-describedby), disabled, focus-visible
  a11y      always has a visible <label>
  used on   S10, S13, S15, S16, S20, S22

Badge          tones neutral, accent, success, warning, danger; text always paired with a border or soft bg. used on S02, S21, S23
Card           surface container, radius lg, card shadow. used on S12, S21, S23, S25
EmptyState     title, body, optional action. used on S12, S13, S15, S22
UsageMeter     role=progressbar, label, used/limit, unlimited case, turns danger at 90%. used on S21, S25
ProductTile    name, pitch, status badge (Enabled/Beta/Available), action slot. used on S02, S21

Specified, not built yet (build with the screen that needs them):
OrgSwitcher    combobox listing orgs + "Create organization"; keyboard: arrows, Enter, Esc; shows role. S20
PlanTable      per-product tiers; monthly/annual toggle (radiogroup), highlights current plan. S04, S23
MemberTable    rows with RoleSelect; owner row locked; remove needs confirm dialog. S22
RoleSelect     native <select> styled; disabled for owner. S22
AuditTable     cursor pagination, filter by actor/action. S26
Toast          role=status, 5s, dismissible, error toasts persist. all
Modal          focus trap, Esc closes, returns focus. confirm destructive actions (delete org, revoke key)
