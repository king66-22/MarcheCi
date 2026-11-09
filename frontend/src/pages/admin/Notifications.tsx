import { useCallback, useEffect, useState } from 'react'
import { notificationsApi } from '../../api/service'
import { ErrorBanner, Spinner } from '../../components/ui'
import type { NotificationRow } from '../../api/types'

const STATUS_STYLE: Record<string, string> = {
  SIMULE_ENVOYE: 'bg-green-100 text-green-800',
  ENVOYE: 'bg-green-100 text-green-800',
  ECHOUE: 'bg-red-100 text-red-700',
  EN_ATTENTE: 'bg-amber-100 text-amber-800',
}

export default function AdminNotifications() {
  const [rows, setRows] = useState<NotificationRow[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const { data } = await notificationsApi.list(page)
      setRows(data.items)
      setTotal(data.total)
      setError(null)
    } catch (e) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Chargement impossible')
    } finally {
      setLoading(false)
    }
  }, [page])

  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { void load() }, [load])

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-extrabold text-marche-800">Journal des notifications</h1>

      <div className="card mt-4 bg-sable-100 p-4 text-sm text-slate-600">
        Les e-mails et SMS sont <strong>simulés</strong> (statut <code>SIMULE_ENVOYE</code>) : aucune
        passerelle réelle n'est branchée sur MarchéCI. Les messages sont générés par le service
        notifications à la réception de l'événement <code>order.created</code> (RabbitMQ, durable +
        DLQ).
      </div>

      {error && <div className="mt-4"><ErrorBanner message={error} /></div>}

      {loading ? (
        <Spinner label="Chargement du journal…" />
      ) : error && rows === null ? (
        <button className="button-secondary mt-4" onClick={() => { setLoading(true); void load() }}>Réessayer</button>
      ) : (
        <>
          <p className="mt-6 text-sm text-slate-500">{total} notification(s)</p>
          <div className="card mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-sable-100 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">#</th>
                  <th className="px-4 py-3">Commande</th>
                  <th className="px-4 py-3">Canal</th>
                  <th className="px-4 py-3">Destinataire</th>
                  <th className="px-4 py-3">Modèle</th>
                  <th className="px-4 py-3">Statut</th>
                  <th className="px-4 py-3">Tentatives</th>
                  <th className="px-4 py-3">Date</th>
                </tr>
              </thead>
              <tbody>
                {rows?.map((n) => (
                  <tr key={n.id} className="border-t border-sable-100">
                    <td className="px-4 py-3 text-slate-400">#{n.id}</td>
                    <td className="px-4 py-3 font-semibold text-slate-700">
                      {n.order_id !== null ? `#${n.order_id}` : '—'}
                    </td>
                    <td className="px-4 py-3 uppercase text-xs">{n.channel}</td>
                    <td className="px-4 py-3 text-slate-600">{n.recipient}</td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{n.template}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[n.status] ?? 'bg-slate-100 text-slate-600'}`}>
                        {n.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">{n.attempts}</td>
                    <td className="px-4 py-3 text-xs text-slate-400">{new Date(n.created_at).toLocaleString('fr-FR')}</td>
                  </tr>
                ))}
                {rows?.length === 0 && (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Aucune notification — passez une commande pour en générer.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex items-center justify-center gap-3">
            <button className="button-secondary" disabled={page <= 1} onClick={() => { setLoading(true); setPage((p) => p - 1) }}>← Précédent</button>
            <button className="button-secondary" disabled={rows !== null && rows.length < 20} onClick={() => { setLoading(true); setPage((p) => p + 1) }}>Suivant →</button>
          </div>
        </>
      )}
    </div>
  )
}
