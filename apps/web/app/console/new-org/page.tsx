import { NewOrgForm } from "../../../components/console/NewOrgForm";

export const metadata = { title: "New organisation" };

export default function NewOrgPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold leading-[34px] text-nx-text">New organisation</h1>
        <p className="mt-1 text-sm text-nx-text-muted">
          Organisations share products, billing and API keys. You become its owner.
        </p>
      </div>
      <NewOrgForm />
    </div>
  );
}
