import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner, Field, inputClass, errMessage } from '../components/ui'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', password: '', confirm: '' })
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
      await register({ email: form.email.trim(), password: form.password, full_name: form.full_name.trim() })
      navigate('/')
    } catch (err) {
      setError(errMessage(err, 'Inscription impossible. Réessayez.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-14">
      <div className="card p-8">
        <h1 className="text-2xl font-extrabold text-marche-800">Créer mon compte</h1>
        <p className="mt-1 text-sm text-slate-500">Achetez et suivez vos commandes en quelques clics.</p>
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
  )
}
