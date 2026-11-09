import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { usersApi } from '../api/service'
import { ErrorBanner, Field, SuccessBanner, inputClass, errMessage } from '../components/ui'

export default function Profile() {
  const { user, logout, refresh } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!user) return null

  const onSave = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      await usersApi.updateMe({
        full_name: fullName.trim(),
        phone: phone.trim() || undefined,
        ...(newPassword
          ? { current_password: currentPassword, new_password: newPassword }
          : {}),
      })
      await refresh()
      setSuccess('Profil mis à jour ✓')
      setCurrentPassword('')
      setNewPassword('')
    } catch (err) {
      setError(errMessage(err, 'Mise à jour impossible.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-extrabold text-marche-800">Mon profil</h1>

      <form className="card mt-6 flex flex-col gap-4 p-6" onSubmit={onSave} noValidate>
        <div className="flex items-center gap-4">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-marche-700 text-xl font-black text-white">
            {user.full_name.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <p className="font-bold text-slate-800">{user.email}</p>
            <p className="text-xs uppercase tracking-wide text-slate-400">Rôle : {user.role}</p>
          </div>
        </div>

        <Field label="Nom complet">
          <input className={inputClass} value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </Field>
        <Field label="Téléphone">
          <input className={inputClass} value={phone ?? ''} onChange={(e) => setPhone(e.target.value)} placeholder="07 xx xx xx xx" />
        </Field>

        <div className="border-t border-sable-200 pt-4">
          <p className="text-sm font-semibold text-slate-600">Changer le mot de passe (facultatif)</p>
          <div className="mt-3 flex flex-col gap-4">
            <Field label="Mot de passe actuel">
              <input type="password" className={inputClass} value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} autoComplete="current-password" />
            </Field>
            <Field label="Nouveau mot de passe (8+ caractères, lettres et chiffres)">
              <input type="password" className={inputClass} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" />
            </Field>
          </div>
        </div>

        <ErrorBanner message={error} />
        <SuccessBanner message={success} />
        <button className="button-primary justify-center" disabled={busy}>
          {busy ? 'Enregistrement…' : 'Enregistrer les modifications'}
        </button>
      </form>

      {user.role === 'COMMERCANT' && (
        <div className="card mt-4 flex flex-wrap items-center justify-between gap-3 p-4">
          <p className="text-sm text-slate-600">
            Votre espace commerçant vous permet d’ajouter vos produits et leurs photos.
          </p>
          <Link to="/commercant" className="button-primary">Mon espace commerçant</Link>
        </div>
      )}
      {user.role === 'CLIENT' && (
        <div className="card mt-4 p-4">
          <p className="text-sm text-slate-600">
            Vous voulez vendre vos produits sur MarchéCI ? Demandez à l’administration de passer
            votre compte en commerçant : vous pourrez ensuite ajouter vos produits et leurs photos.
          </p>
        </div>
      )}

      <div className="mt-6 flex justify-between">
        <span className="text-xs text-slate-400">
          Compte créé {user.created_at ? new Date(user.created_at).toLocaleDateString('fr-FR') : '—'}
        </span>
        <button className="button-danger" onClick={logout}>Se déconnecter</button>
      </div>
    </div>
  )
}
