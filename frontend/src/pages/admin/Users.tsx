import { useCallback, useEffect, useState } from 'react'
import { usersApi } from '../../api/service'
import type { User } from '../../api/types'
import { ErrorBanner, Spinner, errMessage } from '../../components/ui'

export default function AdminUsers() {
  const [users, setUsers] = useState<User[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (page: number) => {
    setUsers(null)
    try {
      const { data } = await usersApi.listAll(page)
      setUsers(data)
    } catch (e) {
      setError(errMessage(e as unknown))
    }
  }, [])

  useEffect(() => { void load(1) }, [load])

  if (error) {
    return <div className="mx-auto max-w-3xl"><ErrorBanner message={error} /></div>
  }
  if (users === null) return <Spinner label="Chargement des comptes…" />

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-extrabold text-marche-800">Comptes clients</h1>
      <p className="mt-1 text-sm text-slate-500">
        Les rôles sont gérés côté service utilisateurs (base dédiée) ; cette vue est en lecture seule
        — aucune modification de rôle ne se fait depuis le navigateur, uniquement via l'API et la base.
      </p>

      <div className="card mt-6 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-sable-100 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">ID</th>
              <th className="px-4 py-3">Nom</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Rôle</th>
              <th className="px-4 py-3">État</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-sable-100">
                <td className="px-4 py-3 text-slate-400">#{u.id}</td>
                <td className="px-4 py-3 font-semibold text-slate-800">{u.full_name}</td>
                <td className="px-4 py-3 text-slate-600">{u.email}</td>
                <td className="px-4 py-3">
                  <span className={u.role === 'ADMIN' ? 'rounded-full bg-marche-700 px-2 py-0.5 text-xs font-bold text-white' : 'rounded-full bg-sable-100 px-2 py-0.5 text-xs font-semibold text-slate-600'}>
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {u.is_active === false
                    ? <span className="text-xs font-semibold text-red-500">désactivé</span>
                    : <span className="text-xs font-semibold text-green-700">actif</span>}
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Aucun compte.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
