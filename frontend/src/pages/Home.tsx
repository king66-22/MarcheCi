import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { catalogueApi } from '../api/service'
import type { Category, Product } from '../api/types'
import { Spinner, EmptyState } from '../components/ui'

export default function Home() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [categories, setCategories] = useState<Category[] | null>(null)

  useEffect(() => {
    void catalogueApi.listProducts({ page_size: 8 }).then((r) => setProducts(r.data.items))
    void catalogueApi.listCategories().then((r) => setCategories(r.data))
  }, [])

  if (!products) return <Spinner label="Le marché s'ouvre…" />

  return (
    <div>
      {/* Bandeau héros */}
      <section className="relative overflow-hidden bg-marche-800 text-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-16 md:py-24 md:grid-cols-2">
          <div className="flex flex-col justify-center gap-4">
            <p className="text-sm font-semibold uppercase tracking-widest text-or-500">Coopérative des commerçants d'Adjamé</p>
            <h1 className="text-4xl font-black leading-tight md:text-5xl">
              Le marché d'Adjamé, <span className="text-terracotta-300">en ligne.</span>
            </h1>
            <p className="max-w-lg text-slate-200">
              Attiéké, café, pagne, épices : achetez auprès de dizaines de commerçants de la
              coopérative. Prix justes en francs CFA, livraison à Abidjan.
            </p>
            <div className="flex gap-3">
              <Link to="/catalogue" className="button-primary !bg-terracotta-600 hover:!bg-terracotta-700">Découvrir le catalogue</Link>
              <Link to="/inscription" className="button-secondary">Créer un compte</Link>
            </div>
          </div>
          <div className="hidden items-center justify-center md:flex">
            <img src="/hero-plants.svg" alt="" width={380} height={380} className="drop-shadow-2xl" />
          </div>
        </div>
      </section>

      {/* Catégories */}
      <section className="mx-auto max-w-7xl px-4 py-10">
        <h2 className="text-xl font-bold text-marche-800">Rayons du marché</h2>
        {categories && categories.length > 0 ? (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {categories.slice(0, 6).map((c) => (
              <Link
                key={c.id}
                to={`/categories#${c.slug}`}
                className="card flex items-center justify-between p-4 transition hover:border-terracotta-300"
              >
                <span className="font-semibold text-slate-700">{c.name}</span>
                <span className="text-xs text-slate-400">{c.product_count ?? 0}</span>
              </Link>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">Les rayons s'installent — revenez rapidement !</p>
        )}
      </section>

      {/* Nouveautés */}
      <section className="mx-auto max-w-7xl px-4 pb-10">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-bold text-marche-800">Nouveautés</h2>
          <Link to="/catalogue" className="text-sm font-semibold text-terracotta-600 hover:underline">Tout voir →</Link>
        </div>
        {products.length === 0 ? (
          <EmptyState title="Aucun produit pour le moment" hint="Les commerçants préparent leurs étals." />
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {products.map((p) => (
              <Link key={p.id} to={`/produit/${p.id}`} className="card p-4 transition hover:border-terracotta-300">
                <h3 className="font-semibold text-slate-800">{p.name}</h3>
                <p className="line-clamp-2 text-sm text-slate-500">{p.description}</p>
                <p className="mt-2 font-bold text-terracotta-700">
                  {new Intl.NumberFormat('fr-FR').format(p.price_xof)} FCFA
                </p>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
