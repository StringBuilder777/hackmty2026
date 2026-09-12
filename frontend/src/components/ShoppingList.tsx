import { MapPin, ShoppingBag, X } from "lucide-react";
import type { Selection, BranchId, ProductId } from "@/lib/types";
import { formatMoney, totals, safeHref } from "@/lib/shopping";
import { useLang } from "@/lib/i18n";
export default function ShoppingList({
  items,
  active,
  onRemove,
  onBranch,
  onFocus,
  onOpenCart,
}: {
  items: Selection[];
  active: BranchId | null;
  onRemove: (id: ProductId) => void;
  onBranch: (id: ProductId, branch: BranchId | null) => void;
  onFocus: (id: BranchId) => void;
  onOpenCart?: () => void;
}) {
  const { t } = useLang();
  const total = totals(items);
  return (
    <section id="mi-lista" className="shopping-list">
      <div className="section-heading">
        <h2>
          {t.shoppingList.title} <span>({items.length})</span>
        </h2>
        <ShoppingBag size={19} />
      </div>
      {!items.length && (
        <div className="list-empty">
          <ShoppingBag size={24} />
          <p>
            {t.shoppingList.emptyTitle}
            <br />
            <span>{t.shoppingList.emptySub}</span>
          </p>
        </div>
      )}
      {items.map(({ product: p, branchId }) => {
        const branch = p.branches.find((b) => b.id === branchId);
        return (
          <article
            key={p.id}
            className={`list-item ${active && active === branchId ? "active" : ""}`}
          >
            <div className="list-item-top">
              <div>
                <strong>{p.name}</strong>
                <small>
                  {p.store} · {p.variant || t.shoppingList.pendingVariant}
                </small>
              </div>
              <strong>{formatMoney(p.price, p.currency)}</strong>
              <button
                className="icon-button"
                aria-label={t.shoppingList.removeAria(p.store)}
                onClick={() => onRemove(p.id)}
              >
                <X size={16} />
              </button>
            </div>
            {p.branches.length > 0 ? (
              <div className="branch-picker">
                <label>
                  {t.shoppingList.branchLabel}
                  <select
                    aria-label={t.shoppingList.branchAria(p.store)}
                    value={branchId || ""}
                    onChange={(e) =>
                      onBranch(
                        p.id,
                        e.target.value ? (e.target.value as BranchId) : null,
                      )
                    }
                  >
                    <option value="">{t.shoppingList.onlineOnlyOption}</option>
                    {p.branches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </label>
                {branch && (
                  <>
                    <button
                      className="text-button"
                      onClick={() => {
                        onFocus(branch.id);
                        onOpenCart?.();
                      }}
                    >
                      <MapPin size={13} /> {t.shoppingList.seeOnMap}
                    </button>
                    <small>{branch.address}</small>
                    <small>
                      {branch.inventory === "confirmed"
                        ? t.shoppingList.inventoryConfirmed(branch.inventory_checked_at)
                        : t.shoppingList.inventoryPending}{" "}
                      {safeHref(branch.source) && (
                        <a
                          href={safeHref(branch.source)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {t.shoppingList.source}
                        </a>
                      )}
                    </small>
                  </>
                )}
              </div>
            ) : (
              <small className="online-only">
                {t.shoppingList.onlineOnly}
              </small>
            )}
          </article>
        );
      })}
      {items.length > 0 && (
        <div className="total">
          <div>
            <small>{t.shoppingList.totalKnown}</small>
            <strong>{formatMoney(total.known)}</strong>
          </div>
          <p>
            {total.pending
              ? t.shoppingList.pendingCosts(total.pending)
              : t.shoppingList.pricesKnown}
            {total.foreign > 0 && t.shoppingList.otherCurrencies}
            <br />
            {t.shoppingList.totalDisclaimer}
          </p>
        </div>
      )}
    </section>
  );
}
