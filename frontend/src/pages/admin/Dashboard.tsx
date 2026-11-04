import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { catalogueApi, ordersApi, notificationsApi, usersApi } from '../../api/service'
import { fcfa } from '../../api/types'
import { ErrorBanner, Spinner } from '../../components/ui'

interface ServiceHealth {
  name: string
  status: 'up' | 'down' | 'unknown'
  detail?: string
}

const SERVICES: { name: string; path: string }[] = [
  { name: 'catalogue', path: '/catalogue/health' },
  { name: 'commandes', path: '/commandes/health' },
  { name: 'utilisateurs', path: '/utilisateurs/health' },
  { name: 'notifications', path: '/notifications/health' },
]

export default function Dashboard() {
  const [stats, setStats] = useState<{
    products: number
    categories: number
    orders: number
    ordersTotal: number
    revenue: number
    users: number
    notifications: number
  } | null>(null)
  const [health, setHealth] = useState<ServiceHealth[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        const [products, categories, orders, users, notifs] = await Promise.all([
          catalogueApi.listProducts({ page_size: 1 }),
          catalogueApi.listCategories(),
          ordersApi.all(1),
          usersApi.listAll(),
          notificationsApi.list(1),
        ])
        setStats({
          products: products.data.total,
          categories: categories.data.length,
          orders: orders.data.total,
          ordersTotal: orders.data.items
            .filter((o) => o.status !== 'ANNULEE')
            .reduce((s, o) => s + o.total_xof, 0),
          revenue: orders.data.items
            .filter((o) => ['CONFIRMEE', 'EN_PREPARATION', 'EXPEDIEE', 'LIVREE'].includes(o.status))
            .reduce((s, o) => s + o.total_xof, 0),
          users: users.data.length,
          notifications: notifs.data.total,
        })
      } catch (e) {
        setError((e as Error).message ?? 'Chargement des statistiques impossible')
        setStats(null)
      }
    })()
  }, [])

  useEffect(() => {
    void (async () => {
      const results = await Promise.all(
        SERVICES.map(async (s) => {
          try {
            const { data, status } = await api.get(s.path, { timeout: 4000 })
            return {
              name: s.name,
              status: (status === 200 ? 'up' : 'down') as ServiceHealth['status'],
              detail: Object.entries(data.components ?? {})
                .map(([k, v]) => `${k}: ${v as string}`)
                .join(' · '),
            }
          } catch {
            return { name: s.name, status: 'down' as ServiceHealth['status'], detail: 'Service injoignable' }
          }
        }),
      )
      setHealth(results)
    })()
  }, [])

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <ErrorBanner message={error} />
      </div>
    )
  }
  if (!stats) return <Spinner label="Consolidation des indicateurs…" />

  const cards: { label: string; value: string; to: string }[] = [
    { label: 'Produits actifs', value: String(stats.products), to: '/admin/produits' },
    { label: 'Catégories', value: String(stats.categories), to: '/admin/categories' },
    { label: 'Commandes', value: String(stats.orders), to: '/admin/commandes' },
    { label: 'Volume en cours (hors commandes annulées, page 1)', value: fcfa(stats.ordersTotal), to: '/admin/commandes' },
    { label: 'Clients', value: String(stats.users), to: '/admin/utilisateurs' },
    { label: 'Notifications (cumul)', value: String(stats.notifications), to: '/admin/notifications' },
  ]

  return (
    <div>
      <h1 className="text-2xl font-extrabold text-marche-800">Tableau de bord</h1>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => (
          <Link key={c.label} to={c.to} className="card p-5 transition hover:border-terracotta-300">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{c.label}</p>
            <p className="mt-2 text-2xl font-extrabold text-marche-800">{c.value}</p>
          </Link>
        ))}
      </div>

      <h2 className="mt-10 text-lg font-bold text-marche-800">Santé des microservices</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {health.map((h) => (
          <div key={h.name} className="card p-4">
            <p className="font-semibold text-slate-700">{h.name}</p>
            <p className={`mt-1 text-sm font-bold ${h.status === 'up' ? 'text-green-600' : 'text-red-600'}`}>
              {h.status === 'up' ? '✓ Opérationnel' : '✕ Indisponible'}
            </p>
            {h.detail && <p className="mt-1 text-xs text-slate-400">{h.detail}</p>}
          </div>
        ))}
      </div>

      <div className="card mt-10 bg-marche-800 p-5 text-sm text-slate-200">
        <p className="font-semibold text-white">Rappel d'exploitation</p>
        <p className="mt-1">
          Le paiement en ligne n'est <strong>pas activé</strong> sur MarchéCI : les commandes sont
          réglées au marché. Les e-mails/SMS de confirmation sont <strong>simulés</strong> (statut
          SIMULE_ENVOYE) — aucune passerelle réelle n'est branchée.
        </p>
      </div>
    </div>
  )
}
