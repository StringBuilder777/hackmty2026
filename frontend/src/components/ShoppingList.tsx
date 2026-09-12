import { MapPin, ShoppingBag, X } from "lucide-react";
import type { Selection, BranchId, ProductId } from "@/lib/types";
import { formatMoney, totals, safeHref } from "@/lib/shopping";
export default function ShoppingList({
  items,
  active,
  onRemove,
  onBranch,
  onFocus,
}: {
  items: Selection[];
  active: BranchId | null;
  onRemove: (id: ProductId) => void;
  onBranch: (id: ProductId, branch: BranchId | null) => void;
  onFocus: (id: BranchId) => void;
}) {
  const total = totals(items);
  return (
    <section id="mi-lista" className="shopping-list">
      <div className="section-heading">
        <h2>
          Mi lista <span>({items.length})</span>
        </h2>
        <ShoppingBag size={19} />
      </div>
      {!items.length && (
        <div className="list-empty">
          <ShoppingBag size={24} />
          <p>
            Tu próxima compra empieza aquí.
            <br />
            <span>Agrega una opción para organizar tu recorrido.</span>
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
                  {p.store} · {p.variant || "Variante pendiente"}
                </small>
              </div>
              <strong>{formatMoney(p.price, p.currency)}</strong>
              <button
                className="icon-button"
                aria-label={`Quitar ${p.store}`}
                onClick={() => onRemove(p.id)}
              >
                <X size={16} />
              </button>
            </div>
            {p.branches.length > 0 ? (
              <div className="branch-picker">
                <label>
                  Sucursal
                  <select
                    aria-label={`Sucursal de ${p.store}`}
                    value={branchId || ""}
                    onChange={(e) =>
                      onBranch(
                        p.id,
                        e.target.value ? (e.target.value as BranchId) : null,
                      )
                    }
                  >
                    <option value="">Solo compra en línea</option>
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
                      onClick={() => onFocus(branch.id)}
                    >
                      <MapPin size={13} /> Ver en mapa
                    </button>
                    <small>{branch.address}</small>
                    <small>
                      {branch.inventory === "confirmed"
                        ? `Inventario reportado el ${branch.inventory_checked_at}; confirma antes de salir.`
                        : "Inventario en sucursal pendiente de verificar."}{" "}
                      {safeHref(branch.source) && (
                        <a
                          href={safeHref(branch.source)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Fuente
                        </a>
                      )}
                    </small>
                  </>
                )}
              </div>
            ) : (
              <small className="online-only">
                En línea · no genera una parada
              </small>
            )}
          </article>
        );
      })}
      {items.length > 0 && (
        <div className="total">
          <div>
            <small>Total conocido</small>
            <strong>{formatMoney(total.known)}</strong>
          </div>
          <p>
            {total.pending
              ? `${total.pending} costo(s) pendiente(s) de verificar.`
              : "Precios y envíos conocidos."}
            {total.foreign > 0 &&
              " Otras monedas no se convierten ni se suman."}
            <br />
            El total final puede cambiar al comprar.
          </p>
        </div>
      )}
    </section>
  );
}
