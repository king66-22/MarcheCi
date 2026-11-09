import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner, Field, inputClass, errMessage } from '../components/ui'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    password: '',
    confirm: '',
    role: 'CLIENT' as 'CLIENT' | 'COMMERCANT',
  })
  const [errors, setErrors] = useState<Record<string, string | null>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const validate = (): boolean => {
    const next: typeof errors = {}
    if (form.full_name.trim().length < 2) next.full_name = 'Entrez votre nom complet.'
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) next.email = 'Adresse email invalide.'
    if (form.phone && form.phone.replace(/\D/g, '').length < 8) next.phone = 'Numéro de téléphone invalide.'
    if (form.password.length < 8 || !/\d/.test(form.password) || !/[a-zA-Z]/.test(form.password))
      next.password = 'Minimum 8 caractères avec lettres et chiffres.'
    if (form.confirm !== form.password) next.confirm = 'Les mots de passe ne correspondent pas.'
    setErrors(next)
    return Object.values(next).every((v) => v === undefined || v === null)
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!validate()) return
    setBusy(true)
    try {
      await register({
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name.trim(),
        phone: form.phone.trim() || undefined,
        role: form.role,
      })
      navigate(form.role === 'COMMERCANT' ? '/commercant' : '/')
    } catch (err) {
      setError(errMessage(err, 'Inscription impossible. Réessayez.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page-width max-w-5xl py-8 sm:py-12">
      <div className="auth-shell">
        <aside className="auth-aside">
          <Link to="/" className="brand text-white"><span className="brand-mark bg-white/15"><span className="text-lg">M</span></span><span className="brand-name text-white">Marché<span>CI</span></span></Link>
          <div><h2>Le marché d’Adjamé, à votre portée.</h2><p>Créez votre compte pour suivre vos commandes et retrouver votre panier en toute simplicité.</p></div>
        </aside>
        <div className="auth-form">
        <p className="eyebrow">Bienvenue sur MarchéCI</p>
        <h1 className="font-display mt-2 text-3xl font-bold text-marche-900">Créer mon compte</h1>
        <p className="mt-2 text-sm text-slate-500">Quelques informations suffisent pour commencer.</p>
        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4" noValidate>
          <Field label="Nom complet" required error={errors.full_name ?? undefined}>
            <input className={inputClass} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
          </Field>
          <Field label="Adresse email" required error={errors.email ?? undefined}>
            <input type="email" className={inputClass} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          </Field>
          <Field label="Téléphone (optionnel, format ivoirien)" error={errors.phone ?? undefined}>
            <input className={inputClass} placeholder="07 xx xx xx xx" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </Field>

          <fieldset>
            <legend className="mb-2 block text-sm font-medium text-slate-700">Je crée un compte pour…</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className={`flex cursor-pointer items-start gap-2 rounded-xl border p-3 text-sm transition ${form.role === 'CLIENT' ? 'border-terracotta-500 bg-terracotta-50/60' : 'border-sable-200 bg-white hover:border-terracotta-300'}`}>
                <input
                  type="radio"
                  name="role"
                  value="CLIENT"
                  checked={form.role === 'CLIENT'}
                  onChange={() => setForm({ ...form, role: 'CLIENT' })}
                  className="mt-1"
                />
                <span>
                  <span className="block font-semibold text-slate-800">Acheter</span>
                  <span className="block text-xs text-slate-500">Compte client : panier et commandes.</span>
                </span>
              </label>
              <label className={`flex cursor-pointer items-start gap-2 rounded-xl border p-3 text-sm transition ${form.role === 'COMMERCANT' ? 'border-terracotta-500 bg-terracotta-50/60' : 'border-sable-200 bg-white hover:border-terracotta-300'}`}>
                <input
                  type="radio"
                  name="role"
                  value="COMMERCANT"
                  checked={form.role === 'COMMERCANT'}
                  onChange={() => setForm({ ...form, role: 'COMMERCANT' })}
                  className="mt-1"
                />
                <span>
                  <span className="block font-semibold text-slate-800">Vendre mes produits</span>
                  <span className="block text-xs text-slate-500">Espace commerçant : produits et photos.</span>
                </span>
              </label>
            </div>
          </fieldset>
          <Field label="Mot de passe" required error={errors.password ?? undefined}>
            <input type="password" className={inputClass} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          </Field>
          <Field label="Confirmation du mot de passe" required error={errors.confirm ?? undefined}>
            <input type="password" className={inputClass} value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} required />
          </Field>
          <ErrorBanner message={error} />
          <button type="submit" className="button-primary justify-center" disabled={busy}>
            {busy ? 'Création…' : 'Créer mon compte'}
          </button>
        </form>
        <p className="mt-6 text-sm text-slate-500">
          Déjà client ? <Link to="/connexion" className="font-semibold text-terracotta-600 hover:underline">Connectez-vous</Link>
        </p>
        </div>
      </div>
    </div>
  )
}
