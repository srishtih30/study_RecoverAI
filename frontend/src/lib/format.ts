/** Amounts everywhere in the API are integers in the smallest currency unit (paise for INR) — see backend/app/domain/events.py. */
export function formatAmount(amountInSmallestUnit: number, currency = "INR"): string {
  const major = amountInSmallestUnit / 100;
  if (currency === "INR") {
    return `₹${major.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${major.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}
