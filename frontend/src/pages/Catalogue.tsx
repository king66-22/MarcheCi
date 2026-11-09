import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { catalogueApi } from '../api/service'
import type { Category, Product } from '../api/types'
import { ProductCard } from '../components/ProductCard'
import { EmptyState, ErrorBanner, Spinner, Toast, errMessage } from '../components/ui'
import { useCart } from '../context/CartContext'

export default function Catalogue() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [products, setProducts] = useState<Product[] | null>(null)
  const [total, setTotal] = useState(0)
  const [categories, setCategories] = useState<Category[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState<string | null>(null)
  const { add } = useCart()

  const q = searchParams.get('q') ?? ''
  const category = searchParams.get('categorie') ?? ''
  const inStock = searchParams.get('stock') === '1'
  const page = Number(searchParams.get('page') ?? '1')
  const pageSize = 12

  useEffect(() => {
    void catalogueApi.listCategories().then((r) => setCategories(r.data)).catch(() => setCategories([]))
  }, [])

  const load = useCallback(async () => {
    try {
      const { data } = await catalogueApi.listProducts({
        q: q || undefined,
        category: category || undefined,
        in_stock: inStock || undefined,
        page,
        page_size: pageSize,
      })
      setProducts(data.items)
      setTotal(data.total)
      setError(null)
    } catch (e) {
      setError(errMessage(e))
    } finally {
      setLoading(false)
    }
  }, [q, category, inStock, page])

  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { void load() }, [load])

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    if (next.toString() === searchParams.toString()) return
    setLoading(true)
    setError(null)
    setSearchParams(next)
  }

  const pages = Math.max(1, Math.ceil(total / pageSize))
  const addToCart = (p: Product) => {
    const err = add(p)
    setToast(err ?? 'Ajouté au panier ✓')
  }

  return (
    <div className="page-width py-8 sm:py-10">
      <p className="eyebrow">La sélection de la coopérative</p>
      <h1 className="section-heading mt-2">Le marché d’Adjamé</h1>
      <p className="section-copy">Parcourez les produits, filtrez par rayon et ajoutez vos trouvailles au panier.</p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[260px_1fr]">
        {/* Filtres */}
        <aside className="card h-fit rounded-2xl p-5 lg:sticky lg:top-32">
          <h2 className="font-display text-xl font-bold text-marche-900">Affiner la recherche</h2>
          <form onSubmit={(event) => { event.preventDefault(); update('q', String(new FormData(event.currentTarget).get('q') ?? '').trim()) }} className="mt-4 flex flex-col gap-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">Recherche</span>
              <input
                name="q"
                type="search"
                className="input-search"
                placeholder="attiéké, café…"
                defaultValue={q}
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">Rayon</span>
              <select className="input-search" value={category} onChange={(e) => update('categorie', e.target.value)}>
                <option value="">Tous les rayons</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.slug}>{c.name}</option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={inStock} onChange={(e) => update('stock', e.target.checked ? '1' : '')} />
              Uniquement les produits disponibles
            </label>
            <button type="submit" className="button-primary w-full">Rechercher</button>
            {(q || category || inStock) && (
              <button className="button-secondary justify-center" onClick={() => setSearchParams(new URLSearchParams())}>
                Réinitialiser les filtres
              </button>
            )}
          </form>
        </aside>

        {/* Liste */}
        <section aria-live="polite" aria-busy={products === null && !error}>
          {error ? (
            <div className="card flex flex-col items-start gap-4 p-6"><ErrorBanner message={error} /><p className="text-sm text-slate-500">Le service Catalogue n’a pas répondu. Vérifiez que MarchéCI est démarré.</p><button className="button-secondary" onClick={() => void load()}>Réessayer</button></div>
          ) : loading || products === null ? (
            <Spinner label="Les commerçants déballent…" />
          ) : products?.length === 0 ? (
            <EmptyState
              title="Rien sur cet étal"
              hint="Aucun produit ne correspond. Essayez un autre mot ou rayon."
            />
          ) : (
            <>
              <p className="mb-3 text-sm text-slate-500">{total} produit(s) — page {page} / {pages}</p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {products?.map((p) => <ProductCard key={p.id} product={p} onAdd={addToCart} />)}
              </div>
              {pages > 1 && (
                <nav className="mt-6 flex items-center justify-center gap-2" aria-label="Pagination">
                  <button className="button-secondary" disabled={page <= 1} onClick={() => update('page', String(page - 1))}>
                    ← Précédent
                  </button>
                  <span className="text-sm text-slate-500">{page} / {pages}</span>
                  <button className="button-secondary" disabled={page >= pages} onClick={() => update('page', String(page + 1))}>
                    Suivant →
                  </button>
                </nav>
              )}
            </>
          )}
        </section>
      </div>
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
  )
}
