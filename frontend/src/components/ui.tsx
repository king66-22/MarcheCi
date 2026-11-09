import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// ---------- garde de routes ----------

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Spinner label="Chargement…" />
  if (!user) return <Navigate to="/connexion" state={{ from: location.pathname }} replace />
  return <>{children}</>
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner label="Chargement…" />
  if (!user) return <Navigate to="/connexion" replace />
  if (user.role !== 'ADMIN') return <Navigate to="/" replace />
  return <>{children}</>
}

/** Espace commerçant : réservé au rôle COMMERCANT (l'ADMIN garde son espace dédié). */
export function RequireMerchant({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Spinner label="Chargement de votre espace…" />
  if (!user) return <Navigate to="/connexion" state={{ from: location.pathname }} replace />
  if (user.role !== 'COMMERCANT') {
    return <Navigate to={user.role === 'ADMIN' ? '/admin' : '/'} replace />
  }
  return <>{children}</>
}

// ---------- basiques ----------

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16" role="status" aria-live="polite">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-terracotta-300 border-t-terracotta-600" />
      {label && <p className="text-sm text-slate-500">{label}</p>}
    </div>
  )
}

export function EmptyState({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-sable-200 bg-white py-14 text-center">
      <div className="text-4xl" aria-hidden>🧺</div>
      <h3 className="text-lg font-semibold text-slate-700">{title}</h3>
      {hint && <p className="max-w-md text-sm text-slate-500">{hint}</p>}
      {children}
    </div>
  )
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {message}
    </div>
  )
}

export function SuccessBanner({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div role="status" className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
      {message}
    </div>
  )
}

const STATUS_COLORS: Record<string, string> = {
  EN_ATTENTE: 'bg-amber-100 text-amber-800',
  CONFIRMEE: 'bg-sky-100 text-sky-800',
  EN_PREPARATION: 'bg-indigo-100 text-indigo-800',
  EXPEDIEE: 'bg-violet-100 text-violet-800',
  LIVREE: 'bg-green-100 text-green-800',
  ANNULEE: 'bg-red-100 text-red-700',
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_COLORS[status] ?? 'bg-slate-100 text-slate-700'}`}>
      {status.replace('_', ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase())}
    </span>
  )
}

// champ de formulaire validé
export function Field(
  { label, error, children, required }: { label: string; error?: string | null; children: ReactNode; required?: boolean },
) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">
        {label} {required && <span className="text-terracotta-600">*</span>}
      </span>
      {children}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  )
}

export const inputClass =
  'w-full rounded-lg border border-sable-200 bg-white px-3 py-2 text-sm shadow-sm transition focus:border-terracotta-500 focus:outline-none'

/** Confirmation avant les actions destructives (exigence UX) */
// oxlint-disable-next-line react/only-export-components
export function useConfirm() {
  return (message: string, onYes: () => void) => {
    if (window.confirm(message)) onYes()
  }
}

/** Toast minimal sans dépendance : file d'états visuels en haut à droite */
export function Toast({ message, onDone }: { message: string; onDone: () => void }) {
  useEffect(() => {
    const id = setTimeout(onDone, 2600)
    return () => clearTimeout(id)
  }, [message, onDone])
  return (
    <div className="fixed bottom-5 right-5 z-50 rounded-lg bg-marche-800 px-4 py-3 text-sm text-white shadow-lg" role="status">
      {message}
    </div>
  )
}

/** helper : extrait le premier détail lisible d'une erreur axios */
// oxlint-disable-next-line react/only-export-components
export function errMessage(e: unknown, fallback = 'Une erreur est survenue. Réessayez.'): string | null {
  const detail = (e as { response?: { data?: { detail?: string | { msg?: string }[] } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const first = detail[0]
    return first?.msg ?? fallback
  }
  if (e instanceof Error && e.message) return e.message
  return fallback
}
