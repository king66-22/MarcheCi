import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ordersApi } from '../api/service'
import { fcfa, type Order } from '../api/types'
import { EmptyState, ErrorBanner, Spinner, StatusBadge, errMessage, useConfirm } from '../components/ui'
import { useAuth } from '../context/AuthContext'

const STATUS_FILTERS = ['', 'EN_ATTENTE', 'CONFIRMEE', 'EN_PREPARATION', 'EXPEDIEE', 'LIVREE', 'ANNULEE']

export default function Orders() {
  const { isAdmin } = useAuth()
  const [orders, setOrders] = useState<Order[] | null>(null)
  const [total, setTotal] = useState(0)
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const confirm = useConfirm()
  const load = useCallback(async () => {
    try {
      const { data } = isAdmin && !status
        ? await ordersApi.all(page)
        : await ordersApi.mine(page, status || undefined)
      setOrders(data.items)
      setTotal(data.total)
      setError(null)
    } catch (e) {
      setError(errMessage(e))
    } finally {
      setLoading(false)
    }
  }, [isAdmin, status, page])

  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { void load() }, [load])

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-2xl font-extrabold text-marche-800">
        {isAdmin && !status ? 'Toutes les commandes' : 'Mes commandes'}
      </h1>

      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Filtrer par statut">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s || 'all'}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
              status === s ? 'bg-terracotta-600 text-white' : 'bg-white text-slate-600 hover:bg-sable-100 border border-sable-200'
            }`}
            onClick={() => { if (status === s && page === 1) return; setLoading(true); setError(null); setPage(1); setStatus(s) }}
          >
            {s ? s.replace('_', ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase()) : 'Toutes'}
          </button>
        ))}
      </div>

      {error && <div className="mt-4"><ErrorBanner message={error} /></div>}

      {loading ? (
        <Spinner label="Chargement de vos commandes…" />
      ) : error && orders === null ? (
        <button className="button-secondary mt-4" onClick={() => { setLoading(true); void load() }}>Réessayer</button>
      ) : orders?.length === 0 ? (
        <EmptyState title="Aucune commande" hint="Passez votre première commande depuis le catalogue.">
          <Link to="/catalogue" className="button-primary mt-2">Aller au catalogue</Link>
        </EmptyState>
      ) : (
        <>
          <div className="mt-6 flex flex-col gap-3">
            {orders?.map((o) => (
              <div key={o.id} className="card flex flex-wrap items-center gap-3 p-4">
                <Link to={`/commande/${o.id}`} className="flex flex-wrap items-center gap-3">
                  <span className="font-bold text-marche-800">#{o.id}</span>
                  <StatusBadge status={o.status} />
                  <span className="text-sm text-slate-500">
                    {o.items.length} article(s) — {new Date(o.created_at).toLocaleDateString('fr-FR')}
                  </span>
                  <span className="font-bold text-terracotta-700">{fcfa(o.total_xof)}</span>
                </Link>
                {!isAdmin && ['EN_ATTENTE', 'CONFIRMEE'].includes(o.status) && (
                  <button
                    className="ml-auto text-xs font-semibold text-red-600 hover:underline"
                    onClick={(e) => {
                      e.stopPropagation()
                      confirm(`Annuler la commande #${o.id}? Le stock sera restitué.`, () =>
                        void ordersApi.cancel(o.id).then(load).catch((err) => setError(errMessage(err))))
                    }}
                  >
                    Annuler
                  </button>
                )}
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center justify-center gap-3">
            <button className="button-secondary" disabled={page <= 1} onClick={() => { setLoading(true); setPage((p) => p - 1) }}>← Précédent</button>
            <span className="text-sm text-slate-500">{total} commande(s)</span>
            <button className="button-secondary" disabled={page * 20 >= total} onClick={() => { setLoading(true); setPage((p) => p + 1) }}>Suivant →</button>
          </div>
        </>
      )}
    </div>
  )
}
