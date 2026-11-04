import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { catalogueApi } from '../api/service'
import { fcfa } from '../api/types'
import { EmptyState, ErrorBanner, Toast, errMessage } from '../components/ui'
import { useCart } from '../context/CartContext'

export default function Cart() {
  const { lines, setQuantity, remove, total, clear } = useCart()
  const [toast, setToast] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  /** Revalidation du panier auprès du catalogue : prix et stock RÉELS (anti-triche). */
  const revalidate = async (): Promise<{ ok: boolean; lines: Record<number, { price: number; stock: number; name?: string }> } | null> => {
    try {
      const results: Record<number, { price: number; stock: number; name?: string }> = {}
      for (const line of lines) {
        const { data } = await catalogueApi.getProduct(line.product.id)
        results[line.product.id] = { price: data.price_xof, stock: data.stock, name: data.name }
      }
      return { ok: true, lines: results }
    } catch (e) {
      setError(
        errMessage(e, 'Validation du panier impossible : le catalogue ne répond pas. Réessayez dans un instant.'),
      )
      return null
    }
  }

  if (lines.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-14">
        <EmptyState title="Votre panier est vide" hint="Le catalogue du marché ne demande qu'à être exploré.">
          <Link to="/catalogue" className="button-primary mt-2">Aller au catalogue</Link>
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-extrabold text-marche-800">Mon panier</h1>
      {error && <div className="mt-4"><ErrorBanner message={error} /></div>}

      <div className="mt-6 flex flex-col gap-4">
        {lines.map((l) => (
          <div key={l.product.id} className="card flex items-center gap-4 p-4">
            <div className="hidden h-16 w-16 items-center justify-center rounded-lg bg-sable-100 text-2xl sm:flex" aria-hidden>🛍️</div>
            <div className="flex-1">
              <Link to={`/produit/${l.product.id}`} className="font-semibold hover:text-terracotta-600">{l.product.name}</Link>
              <p className="text-sm text-slate-500">{fcfa(l.product.price_xof)} / unité</p>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor={`q-${l.product.id}`} className="sr-only">Quantité</label>
              <input
                id={`q-${l.product.id}`}
                type="number"
                min={1}
                max={l.product.stock}
                value={l.quantity}
                onChange={(e) => {
                  const v = Math.min(l.product.stock, Math.max(1, Number(e.target.value) || 1))
                  setQuantity(l.product.id, v)
                }}
                className="input-search w-20 text-center"
              />
            </div>
            <p className="w-24 text-right font-bold text-terracotta-700">{fcfa(l.product.price_xof * l.quantity)}</p>
            <button
              className="text-slate-400 hover:text-red-600"
              aria-label={`Retirer ${l.product.name} du panier`}
              onClick={() => {
                remove(l.product.id)
                setToast('Produit retiré du panier')
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="mt-6 flex flex-col items-end gap-2">
        <p className="text-sm text-slate-500">{lines.length} article(s) — total estimé</p>
        <p className="text-2xl font-extrabold text-terracotta-700">{fcfa(total)}</p>
        <div className="mt-3 flex gap-3">
          <button
            className="button-secondary"
            onClick={() => {
              clear()
              setToast('Panier vidé')
            }}
          >
            Vider le panier
          </button>
          <button
            className="button-primary"
            onClick={async () => {
              const v = await revalidate()
              if (v) navigate('/checkout')
            }}
          >
            Valider ma commande
          </button>
        </div>
      </div>
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
  )
}
