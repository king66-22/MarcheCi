import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { catalogueApi } from '../../api/service'
import type { Product } from '../../api/types'
import { Spinner, errMessage } from '../../components/ui'
import { useAuth } from '../../context/AuthContext'

export default function MerchantDashboard() {
  const { user } = useAuth()
  const [products, setProducts] = useState<Product[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void catalogueApi
      .mine()
      .then(({ data }) => { setProducts(data.items); setError(null) })
      .catch((e) => setError(errMessage(e, 'Chargement de votre boutique impossible.')))
  }, [])

  if (error) {
    return (
      <div className="page-width max-w-3xl py-10">
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      </div>
    )
  }
  if (products === null) return <Spinner label="Chargement de votre espace…" />

  const active = products.filter((product) => product.is_active)
  const withPhoto = active.filter((product) => Boolean(product.image_url))
  const stock = active.reduce((sum, product) => sum + product.stock, 0)

  return (
    <div className="page-width py-8 sm:py-10">
      <p className="eyebrow">Espace commerçant</p>
      <h1 className="mt-2 font-display text-3xl font-bold text-marche-900 sm:text-4xl">
        Bonjour {user?.full_name.split(' ')[0] ?? 'commerçant'} 👋
      </h1>
      <p className="mt-2 max-w-2xl text-slate-600">
        Gérez votre boutique d’Adjamé : ajoutez vos produits, prenez leurs photos et mettez-les en vente
        en quelques clics.
      </p>

      <div className="mt-7 grid gap-4 sm:grid-cols-3">
        <div className="card p-5">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-400">Produits en vente</p>
          <p className="mt-2 text-3xl font-extrabold text-marche-800">{active.length}</p>
          <p className="mt-1 text-xs text-slate-500">sur {products.length} au total</p>
        </div>
        <div className="card p-5">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-400">Avec photo</p>
          <p className="mt-2 text-3xl font-extrabold text-marche-800">{withPhoto.length}</p>
          <p className="mt-1 text-xs text-slate-500">
            {active.length - withPhoto.length > 0
              ? `${active.length - withPhoto.length} produit(s) sans photo`
              : 'Tous vos produits ont une photo'}
          </p>
        </div>
        <div className="card p-5">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-400">Unités en stock</p>
          <p className="mt-2 text-3xl font-extrabold text-marche-800">{stock}</p>
          <p className="mt-1 text-xs text-slate-500">Tous vos produits actifs</p>
        </div>
      </div>

      <div className="mt-7 flex flex-wrap gap-3">
        <Link to="/commercant/produits" className="button-primary">
          + Ajouter un produit
        </Link>
        <Link to="/commercant/produits" className="button-secondary">
          Gérer mes produits et mes photos
        </Link>
        <Link to="/catalogue" className="button-secondary">
          Voir le marché
        </Link>
      </div>

      {active.length === 0 && (
        <div className="mt-8 rounded-2xl border border-dashed border-terracotta-300 bg-terracotta-50/50 p-6">
          <h2 className="font-bold text-marche-900">Votre vitrine est encore vide</h2>
          <p className="mt-1 max-w-xl text-sm text-slate-600">
            Commencez par votre produit le plus demandé. Vous pourrez choisir une photo dans votre galerie
            ou la prendre directement avec votre téléphone.
          </p>
          <Link to="/commercant/produits" className="button-primary mt-4">Créer mon premier produit</Link>
        </div>
      )}

      {active.length > 0 && (
        <div className="mt-8">
          <h2 className="font-bold text-marche-900">Derniers produits</h2>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {active.slice(0, 6).map((product) => (
              <li key={product.id}>
                <Link to={`/produit/${product.id}`} className="card flex items-center gap-3 p-3 transition hover:border-terracotta-300">
                  <img
                    src={product.image_url || '/product-placeholder.svg'}
                    alt=""
                    className="h-14 w-14 rounded-xl border border-sable-100 object-cover"
                    onError={(event) => { event.currentTarget.src = '/product-placeholder.svg' }}
                  />
                  <span className="min-w-0">
                    <span className="block truncate font-semibold text-slate-800">{product.name}</span>
                    <span className="block text-xs text-slate-500">{product.price_xof} FCFA · stock {product.stock}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
