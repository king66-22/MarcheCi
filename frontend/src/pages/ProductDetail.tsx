import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { catalogueApi } from '../api/service'
import { fcfa, type Product } from '../api/types'
import { ErrorBanner, Spinner, Toast, errMessage, useConfirm } from '../components/ui'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'

export default function ProductDetail() {
  const { id } = useParams()
  const [product, setProduct] = useState<Product | null>(null)
  const [activeImage, setActiveImage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [toast, setToast] = useState<string | null>(null)
  const { add } = useCart()
  const { user, isAdmin } = useAuth()
  const navigate = useNavigate()
  const confirm = useConfirm()

  useEffect(() => {
    void catalogueApi
      .getProduct(Number(id))
      .then((r) => {
        setProduct(r.data)
        setActiveImage(r.data.image_url ?? r.data.images?.[0]?.url ?? null)
        setError(null)
      })
      .catch((e) => setError(errMessage(e)))
  }, [id])

  if (error) {
    return (
    <div className="page-width max-w-3xl py-10">
        <ErrorBanner message={error} />
        <Link to="/catalogue" className="button-secondary mt-4">← Retour au catalogue</Link>
      </div>
    )
  }
  if (!product || product.id !== Number(id)) return <Spinner label="Produit en cours de préparation…" />

  const restricted = product.stock <= 0
  const maxQty = Math.max(1, product.stock)
  const gallery = product.images?.length
    ? product.images.map((image) => image.url)
    : product.image_url
      ? [product.image_url]
      : []
  const ownerCanManage = Boolean(
    user && (isAdmin || (user.role === 'COMMERCANT' && product.owner_id === user.id)),
  )

  return (
    <div className="page-width py-8 sm:py-10">
      <nav className="mb-5 flex items-center gap-2 text-sm text-slate-500" aria-label="Fil d’ariane">
        <Link to="/catalogue" className="hover:text-terracotta-600">Le marché</Link><span aria-hidden="true">/</span>
        <span className="truncate text-slate-700">{product.name}</span>
      </nav>

      <div className="grid items-start gap-8 md:grid-cols-2 lg:gap-12">
        <div>
          <div className="card rounded-3xl bg-sable-100">
            <img src={activeImage || '/product-placeholder.svg'} alt={activeImage ? product.name : ''} className="aspect-[4/3] w-full object-cover" onError={(event) => {
              if (!event.currentTarget.src.endsWith('/product-placeholder.svg')) event.currentTarget.src = '/product-placeholder.svg'
            }} />
          </div>
          {gallery.length > 1 && (
            <ul className="mt-3 grid grid-cols-4 gap-2 sm:grid-cols-5" aria-label="Autres photos du produit">
              {gallery.map((url) => (
                <li key={url}>
                  <button
                    type="button"
                    onClick={() => setActiveImage(url)}
                    className={`block w-full overflow-hidden rounded-xl border-2 transition ${activeImage === url ? 'border-terracotta-500' : 'border-transparent hover:border-sable-300'}`}
                    aria-label="Afficher cette photo"
                  >
                    <img src={url} alt="" className="aspect-square w-full object-cover" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex flex-col items-start gap-4 py-1">
          <p className="eyebrow">Sélection de la coopérative</p>
          <h1 className="font-display text-4xl font-bold leading-tight text-marche-900 sm:text-5xl">{product.name}</h1>
          <p className="text-3xl font-extrabold tracking-tight text-terracotta-700">{fcfa(product.price_xof)}</p>
          <p className="max-w-xl whitespace-pre-line leading-7 text-slate-600">{product.description || 'Un produit du marché d’Adjamé, proposé par la coopérative.'}</p>

          {!restricted ? (
            <p className="inline-flex items-center gap-2 rounded-full bg-green-50 px-3 py-1.5 text-sm font-semibold text-green-800"><span aria-hidden>✓</span> Disponible · {product.stock} en stock</p>
          ) : (
            <p className="rounded-full bg-red-50 px-3 py-1.5 text-sm font-semibold text-red-700">Épuisé — commande indisponible pour le moment.</p>
          )}

          <div className="mt-1 flex items-center gap-3">
            <label htmlFor="qty" className="text-sm font-medium">Quantité</label>
            <input
              id="qty"
              type="number"
              min={1}
              max={maxQty}
              value={quantity}
              disabled={restricted}
              onChange={(e) => setQuantity(Math.min(maxQty, Math.max(1, Number(e.target.value) || 1)))}
              className="h-12 w-24 rounded-xl border border-sable-200 bg-white px-3 text-center"
            />
          </div>

          <div className="flex w-full flex-wrap gap-3">
            <button
              className="button-primary flex-1"
              disabled={restricted}
              onClick={() => {
                const err = add(product, quantity)
                if (err) setToast(err)
                else setToast('Ajouté au panier ✓')
              }}
            >
              Ajouter au panier · {fcfa(product.price_xof * quantity)}
            </button>
            {ownerCanManage && !isAdmin && (
              <Link
                to="/commercant/produits"
                state={{ editProductId: product.id }}
                className="button-secondary justify-center"
              >
                Gérer mes photos
              </Link>
            )}
            {isAdmin && <button
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
            </button>}
          </div>
          <p className="mt-2 border-t border-sable-200 pt-4 text-xs leading-5 text-slate-500">Les montants et le stock affichés sont vérifiés auprès du catalogue lorsque vous passez commande. Le paiement en ligne n’est pas activé.</p>
        </div>
      </div>
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
  )
}
