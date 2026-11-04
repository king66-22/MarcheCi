import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { catalogueApi } from '../api/service'
import { fcfa, type Product } from '../api/types'
import { ErrorBanner, Spinner, Toast, errMessage, useConfirm } from '../components/ui'
import { useCart } from '../context/CartContext'

export default function ProductDetail() {
  const { id } = useParams()
  const [product, setProduct] = useState<Product | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [toast, setToast] = useState<string | null>(null)
  const { add } = useCart()
  const navigate = useNavigate()
  const confirm = useConfirm()

  useEffect(() => {
    setProduct(null)
    setError(null)
    void catalogueApi
      .getProduct(Number(id))
      .then((r) => setProduct(r.data))
      .catch((e) => setError(errMessage(e)))
  }, [id])

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <ErrorBanner message={error} />
        <Link to="/catalogue" className="button-secondary mt-4">← Retour au catalogue</Link>
      </div>
    )
  }
  if (!product) return <Spinner label="Produit en cours de préparation…" />

  const restricted = product.stock <= 0
  const maxQty = Math.max(1, product.stock)

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <nav className="mb-4 text-sm text-slate-500" aria-label="Fil d'ariane">
        <Link to="/catalogue" className="hover:text-terracotta-600">Catalogue</Link> <span aria-hidden>/</span>
        <span className="text-slate-700"> {product.name}</span>
      </nav>

      <div className="grid gap-8 md:grid-cols-2">
        <div className="card bg-sable-100">
          {product.image_url ? (
            <img src={product.image_url} alt={product.name} className="h-96 w-full object-cover" />
          ) : (
            <div className="flex h-96 items-center justify-center text-7xl" aria-hidden>🛍️</div>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <h1 className="text-3xl font-extrabold text-marche-800">{product.name}</h1>
          <p className="text-2xl font-bold text-terracotta-700">{fcfa(product.price_xof)}</p>
          <p className="text-slate-600">{product.description || 'Un produit du marché d\'Adjamé.'}</p>

          {!restricted ? (
            <p className="text-sm text-green-700">✓ En stock : {product.stock} disponibles</p>
          ) : (
            <p className="text-sm font-semibold text-red-600">Épuisé — contactez la coopérative pour le réapprovisionnement.</p>
          )}

          <div className="mt-2 flex items-center gap-3">
            <label htmlFor="qty" className="text-sm font-medium">Quantité</label>
            <input
              id="qty"
              type="number"
              min={1}
              max={maxQty}
              value={quantity}
              disabled={restricted}
              onChange={(e) => setQuantity(Math.min(maxQty, Math.max(1, Number(e.target.value) || 1)))}
              className="w-20 rounded-lg border border-sable-200 px-3 py-2 text-center"
            />
          </div>

          <div className="flex gap-3">
            <button
              className="button-primary flex-1 justify-center"
              disabled={restricted}
              onClick={() => {
                const err = add(product, quantity)
                if (err) setToast(err)
                else setToast('Ajouté au panier ✓')
              }}
            >
              Ajouter au panier
            </button>
            <button
              className="button-danger justify-center"
              onClick={() =>
                confirm(
                  `Supprimer définitivement le produit « ${product.name} » du catalogue ?`,
                  () => {
                    void catalogueApi
                      .deleteProduct(product.id)
                      .then(() => navigate('/admin/produits'))
                      .catch((e) => setToast(errMessage(e, 'Suppression impossible')))
                  },
                )
              }
              title="Action réservée à l'administration"
            >
              Supprimer
            </button>
          </div>
        </div>
      </div>
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
  )
}
