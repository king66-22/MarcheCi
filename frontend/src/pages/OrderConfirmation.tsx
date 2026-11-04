import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { ordersApi } from '../api/service'
import { fcfa } from '../api/types'
import { ErrorBanner, Spinner, StatusBadge } from '../components/ui'
import type { Order } from '../api/types'

export default function OrderConfirmation() {
  const { id } = useParams()
  const location = useLocation()
  const justCreated = (location.state as { created?: boolean } | null)?.created ?? false
  const [order, setOrder] = useState<Order | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void ordersApi
      .get(Number(id))
      .then((r) => setOrder(r.data))
      .catch((e) => setError((e as Error).message ?? 'Commande introuvable'))
  }, [id])

  if (error) {
    return <div className="mx-auto max-w-2xl px-4 py-10"><ErrorBanner message={error} /></div>
  }
  if (!order) return <Spinner />

  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <div className="card p-8 text-center">
        {justCreated ? (
          <>
            <div className="text-5xl" aria-hidden>🎉</div>
            <h1 className="mt-3 text-2xl font-extrabold text-marche-800">Commande enregistrée !</h1>
            <p className="mt-2 text-sm text-slate-500">
              Un message de confirmation (simulé) vous a été envoyé. Réglement au marché au moment du retrait/livraison.
            </p>
          </>
        ) : (
          <>
            <div className="text-5xl" aria-hidden>🧾</div>
            <h1 className="mt-3 text-2xl font-extrabold text-marche-800">Commande #{order.id}</h1>
          </>
        )}
        <div className="mt-6 flex flex-col gap-4 text-left">
          <div className="flex items-center justify-between rounded-lg bg-sable-100 px-4 py-3">
            <span className="text-sm text-slate-600">Statut</span>
            <StatusBadge status={order.status} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-600">Total serveur (recalculé)</span>
            <span className="font-bold text-terracotta-700">{fcfa(order.total_xof)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-600">Livraison</span>
            <span className="text-sm text-slate-700">{order.delivery_address} — {order.delivery_phone}</span>
          </div>
          <ul className="flex flex-col gap-2 border-t border-sable-200 pt-3 text-sm">
            {order.items.map((it) => (
              <li key={it.product_id} className="flex justify-between">
                <span>{it.quantity} × {it.product_name}</span>
                <span className="font-semibold">{fcfa(it.unit_price_xof * it.quantity)}</span>
              </li>
            ))}
          </ul>
        </div>
        <Link to="/commandes" className="button-primary mt-8">Suivre mes commandes</Link>
      </div>
    </div>
  )
}
