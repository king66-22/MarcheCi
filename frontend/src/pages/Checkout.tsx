import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ordersApi } from '../api/service'
import { fcfa } from '../api/types'
import { ErrorBanner, Field, inputClass, errMessage } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'

export default function Checkout() {
  const { lines, total, clear } = useCart()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [address, setAddress] = useState('')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (lines.length === 0) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-14 text-center">
        <p className="text-slate-500">Votre panier est vide.</p>
        <Link to="/catalogue" className="button-primary mt-4">Aller au catalogue</Link>
      </div>
    )
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (address.trim().length < 10) {
      setError('Indiquez une adresse de livraison complète (quartier, rue…).')
      return
    }
    if (phone.replace(/\D/g, '').length < 8) {
      setError('Numéro de téléphone ivoirien invalide.')
      return
    }
    setBusy(true)
    try {
      // MAJOR : le prix n'est PAS envoyé — le service commandes le revalide auprès du catalogue
      const { data: order } = await ordersApi.create({
        items: lines.map((l) => ({ product_id: l.product.id, quantity: l.quantity })),
        delivery_address: address.trim(),
        delivery_phone: phone.trim(),
      })
      clear()
      navigate(`/commande/${order.id}`, { state: { created: true, orderId: order.id } })
    } catch (err) {
      setError(
        errMessage(
          err,
          'La commande n\'a pas été enregistrée. Vérifiez votre panier et réessayez.',
        ),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-extrabold text-marche-800">Valider ma commande</h1>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <form className="card flex flex-col gap-4 p-6" onSubmit={onSubmit} noValidate>
          <h2 className="font-bold text-slate-700">Livraison</h2>
          <Field label="Adresse complète" required>
            <textarea
              className={inputClass}
              rows={3}
              placeholder="Quartier Adjamé, rue 12, la maison au portail rouge…"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              required
            />
          </Field>
          <Field label="Téléphone du destinataire" required>
            <input className={inputClass} value={phone} onChange={(e) => setPhone(e.target.value)} required />
          </Field>
          <ErrorBanner message={error} />
          <button type="submit" className="button-primary justify-center" disabled={busy}>
            {busy ? 'Enregistrement…' : 'Confirmer la commande'}
          </button>
          <p className="text-xs text-slate-400">
            Paiement en ligne non activé : vous réglerez au marché auprès du commerçant
            lors du retrait ou de la livraison.
          </p>
        </form>

        <aside className="card h-fit p-6">
          <h2 className="font-bold text-slate-700">Récapitulatif</h2>
          <ul className="mt-4 flex flex-col gap-3 text-sm">
            {lines.map((l) => (
              <li key={l.product.id} className="flex justify-between gap-4">
                <span className="text-slate-600">{l.quantity} × {l.product.name}</span>
                <span className="font-semibold">{fcfa(l.product.price_xof * l.quantity)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-4 border-t border-sable-200 pt-3 text-right">
            <span className="text-xs text-slate-500">Estimation (recalculée par le serveur)</span>
            <p className="text-xl font-extrabold text-terracotta-700">{fcfa(total)}</p>
          </div>
        </aside>
      </div>
    </div>
  )
}
