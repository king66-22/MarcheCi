import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner, Field, inputClass, errMessage } from '../components/ui'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const me = await login(email.trim(), password)
      // Un commerçant arrive directement dans son espace pour ajouter ses produits.
      navigate(me.role === 'COMMERCANT' ? '/commercant' : from, { replace: true })
    } catch (err) {
      setError(errMessage(err, 'Identifiants incorrects ou service indisponible.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page-width max-w-5xl py-8 sm:py-12">
      <div className="auth-shell">
        <aside className="auth-aside">
          <Link to="/" className="brand text-white"><span className="brand-mark bg-white/15"><span className="text-lg">M</span></span><span className="brand-name text-white">Marché<span>CI</span></span></Link>
          <div><h2>Vos achats, au rythme du marché.</h2><p>Retrouvez vos commandes et préparez votre prochain panier auprès de la coopérative d’Adjamé.</p></div>
        </aside>
        <div className="auth-form">
        <p className="eyebrow">Heureux de vous retrouver</p>
        <h1 className="font-display mt-2 text-3xl font-bold text-marche-900">Connexion</h1>
        <p className="mt-2 text-sm text-slate-500">
          Accédez à vos commandes et poursuivez vos achats. Les commerçants retrouvent
          directement leur espace de gestion.
        </p>
        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4" noValidate>
          <Field label="Adresse email" required>
            <input
              type="email"
              autoComplete="email"
              className={inputClass}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </Field>
          <Field label="Mot de passe" required>
            <input
              type="password"
              autoComplete="current-password"
              className={inputClass}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>
          <ErrorBanner message={error} />
          <button type="submit" className="button-primary justify-center" disabled={busy}>
            {busy ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>
        <p className="mt-6 text-sm text-slate-500">
          Pas encore de compte ?{' '}
          <Link to="/inscription" className="font-semibold text-terracotta-600 hover:underline">Inscrivez-vous</Link>
        </p>
        </div>
      </div>
    </div>
  )
}
