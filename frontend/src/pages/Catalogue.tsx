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
    setProducts(null)
    setError(null)
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
    } catch (e) {
      setError(errMessage(e))
    }
  }, [q, category, inStock, page])

  useEffect(() => { void load() }, [load])

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setSearchParams(next)
  }

  const pages = Math.max(1, Math.ceil(total / pageSize))
  const addToCart = (p: Product) => {
    const err = add(p)
    setToast(err ?? 'Ajouté au panier ✓')
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-2xl font-extrabold text-marche-800">Catalogue du marché</h1>

      <div className="mt-6 grid gap-6 lg:grid-cols-[260px_1fr]">
        {/* Filtres */}
        <aside className="card h-fit p-4 lg:sticky lg:top-20">
          <form onSubmit={(e) => e.preventDefault()} className="flex flex-col gap-4">
            <label className="block">
              <span className="mb-1 block text-sm font-medium">Recherche</span>
              <input
                type="search"
                className="input-search"
                placeholder="attiéké, café…"
                defaultValue={q}
                onBlur={(e) => update('q', e.target.value.trim())}
                onKeyDown={(e) => { if (e.key === 'Enter') update('q', (e.target as HTMLInputElement).value.trim()) }}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium">Rayon</span>
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
            {(q || category || inStock) && (
              <button className="button-secondary justify-center" onClick={() => setSearchParams(new URLSearchParams())}>
                Réinitialiser les filtres
              </button>
            )}
          </form>
        </aside>

        {/* Liste */}
        <section aria-live="polite">
          {error && <ErrorBanner message={error} />}
          {products === null && !error ? (
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
