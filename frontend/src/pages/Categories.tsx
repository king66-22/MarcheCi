import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { catalogueApi } from '../api/service'
import type { Category } from '../api/types'
import { EmptyState, ErrorBanner, Spinner, errMessage } from '../components/ui'

export default function Categories() {
  const [categories, setCategories] = useState<Category[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    let active = true
    void catalogueApi.listCategories().then((r) => { if (active) { setCategories(r.data); setError(null) } }).catch((e: unknown) => {
      if (active) { setError(errMessage(e, 'Les catégories ne sont pas disponibles.')); setCategories([]) }
    })
    return () => { active = false }
  }, [refresh])

  if (!categories) return <Spinner label="Ouverture des rayons…" />
  if (error) return <div className="page-width max-w-3xl py-12"><ErrorBanner message={error} /><p className="mt-3 text-sm text-slate-500">Le service Catalogue est peut-être arrêté.</p><button className="button-secondary mt-4" onClick={() => { setCategories(null); setRefresh((value) => value + 1) }}>Réessayer</button></div>
  if (categories.length === 0)
    return (
      <div className="page-width max-w-3xl py-10">
        <EmptyState title="Aucun rayon pour le moment" hint="L'administration crée les premiers rayons." />
      </div>
    )

  return (
    <div className="page-width max-w-6xl py-10">
      <p className="eyebrow">Explorer par univers</p>
      <h1 className="section-heading mt-2">Les rayons du marché</h1>
      <p className="section-copy">Choisissez un rayon pour découvrir les produits qui y sont proposés.</p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {categories.map((c) => (
          <Link
            key={c.id}
            to={`/catalogue?categorie=${c.slug}`}
            data-slug={c.slug}
            className="category-tile min-h-24"
          >
            <div><strong>{c.name}</strong><span>{c.product_count ?? 0} produit{c.product_count === 1 ? '' : 's'}</span></div>
            <span className="category-arrow" aria-hidden>↗</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
