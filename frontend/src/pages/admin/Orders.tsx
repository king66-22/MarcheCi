import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ordersApi } from '../../api/service'
import { fcfa, type Order, type OrderStatus } from '../../api/types'
import { ErrorBanner, Spinner, StatusBadge, Toast, errMessage, useConfirm } from '../../components/ui'

/**-machine à états : transitions autorisées (côté serveur aussi) */
const NEXT_STATUS: Record<string, OrderStatus[]> = {
  EN_ATTENTE: ['CONFIRMEE', 'ANNULEE'],
  CONFIRMEE: ['EN_PREPARATION', 'ANNULEE'],
  EN_PREPARATION: ['EXPEDIEE'],
  EXPEDIEE: ['LIVREE'],
  LIVREE: [],
  ANNULEE: [],
}

export default function AdminOrders() {
  const [orders, setOrders] = useState<Order[] | null>(null)
  const [page, setPage] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState<string | null>(null)
  const confirm = useConfirm()

  const load = useCallback(async () => {
    try {
      const { data } = await ordersApi.all(page)
      setOrders(data.items)
      setError(null)
    } catch (e) {
      setError(errMessage(e))
    } finally {
      setLoading(false)
    }
  }, [page])

  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { void load() }, [load])

  const transition = (o: Order, next: OrderStatus) => {
    confirm(
      next === 'ANNULEE'
        ? `Annuler la commande #${o.id} ? Le stock sera restitué au catalogue.`
        : `Passer la commande #${o.id} en « ${next} » ?`,
      () => {
        void ordersApi
          .setStatus(o.id, next)
          .then(() => {
            setToast(`Commande #${o.id} → ${next} ✓`)
            void load()
          })
          .catch((e) => setToast(errMessage(e, 'Transition refusée par le service')))
      },
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-extrabold text-marche-800">Suivi des commandes</h1>

      {error && <div className="mt-4"><ErrorBanner message={error} /></div>}

      {loading ? (
        <Spinner label="Chargement des commandes…" />
      ) : error && orders === null ? (
        <button className="button-secondary mt-4" onClick={() => { setLoading(true); void load() }}>Réessayer</button>
      ) : orders?.length === 0 ? (
        <p className="mt-6 text-sm text-slate-500">Aucune commande enregistrée.</p>
      ) : (
        <>
          <div className="mt-6 flex flex-col gap-4">
            {orders?.map((o) => (
              <article key={o.id} className="card p-5">
                <header className="flex flex-wrap items-center gap-3">
                  <span className="text-lg font-extrabold text-marche-800">#{o.id}</span>
                  <StatusBadge status={o.status} />
                  <span className="text-sm text-slate-400">
                    {new Date(o.created_at).toLocaleString('fr-FR')} — utilisateur #{o.user_id}
                  </span>
                  <span className="ml-auto text-lg font-bold text-terracotta-700">{fcfa(o.total_xof)}</span>
                </header>

                <div className="mt-3 grid gap-4 text-sm md:grid-cols-2">
                  <ul className="flex flex-col gap-1 text-slate-600">
                    {o.items.map((it) => (
                      <li key={it.product_id}>
                        {it.quantity} × {it.product_name} <span className="text-slate-400">({fcfa(it.unit_price_xof)}/u)</span>
                      </li>
                    ))}
                  </ul>
                  <p className="text-slate-500">
                    📍 {o.delivery_address} — ☎ {o.delivery_phone}
                  </p>
                </div>

                {NEXT_STATUS[o.status]?.length > 0 ? (
                  <footer className="mt-4 flex flex-wrap gap-2 border-t border-sable-100 pt-3">
                    <span className="text-xs font-semibold uppercase text-slate-400">Transitions :</span>
                    {NEXT_STATUS[o.status].map((next) => (
                      <button
                        key={next}
                        className={
                          next === 'ANNULEE'
                            ? 'rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-red-700 hover:bg-red-100'
                            : 'rounded-full border border-sable-200 px-3 py-1 text-xs font-semibold text-marche-800 hover:bg-sable-100'
                        }
                        onClick={() => transition(o, next)}
                      >
                        → {next}
                      </button>
                    ))}
                  </footer>
                ) : (
                  <footer className="mt-4 border-t border-sable-100 pt-3 text-xs text-slate-400">
                    Statut final {o.status === 'ANNULEE' ? '(commande annulée)' : '(commande livrée)'} — plus de transition possible.
                  </footer>
                )}
                <Link to={`/commande/${o.id}`} className="mt-2 inline-block text-xs font-semibold text-terracotta-600 hover:underline">
                  Vue détaillée →
                </Link>
              </article>
            ))}
          </div>

          <div className="mt-4 flex items-center justify-center gap-3">
            <button className="button-secondary" disabled={page <= 1} onClick={() => { setLoading(true); setPage((p) => p - 1) }}>← Précédent</button>
            <button className="button-secondary" disabled={orders !== null && orders.length < 50} onClick={() => { setLoading(true); setPage((p) => p + 1) }}>Suivant →</button>
          </div>
        </>
      )}
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
  )
}
