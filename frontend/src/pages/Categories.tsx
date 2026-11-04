import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { catalogueApi } from '../api/service'
import type { Category } from '../api/types'
import { EmptyState, Spinner } from '../components/ui'

export default function Categories() {
  const [categories, setCategories] = useState<Category[] | null>(null)

  useEffect(() => {
    void catalogueApi.listCategories().then((r) => setCategories(r.data))
  }, [])

  if (!categories) return <Spinner label="Ouverture des rayons…" />
  if (categories.length === 0)
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <EmptyState title="Aucun rayon pour le moment" hint="L'administration crée les premiers rayons." />
      </div>
    )

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-2xl font-extrabold text-marche-800">Catégories du marché</h1>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {categories.map((c) => (
          <Link
            key={c.id}
            to={`/catalogue?categorie=${c.slug}`}
            data-slug={c.slug}
            className="card flex flex-row items-center justify-between p-6 transition hover:border-terracotta-300"
          >
            <span className="text-lg font-bold text-marche-800">{c.name}</span>
            <span className="rounded-full bg-sable-100 px-3 py-1 text-xs font-semibold text-slate-600">
              {c.product_count ?? 0} produits
            </span>
          </Link>
        ))}
      </div>
    </div>
  )
}
