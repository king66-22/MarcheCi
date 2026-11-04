import { useCallback, useEffect, useState } from 'react'
import { catalogueApi } from '../../api/service'
import type { Category, Product } from '../../api/types'
import { ErrorBanner, Spinner, SuccessBanner, Toast, Field, inputClass, errMessage, useConfirm } from '../../components/ui'

const EMPTY_FORM = { slug: '', name: '', description: '', price_xof: '', stock: '', category_id: '', image_url: '' }

export default function AdminProducts() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [total, setTotal] = useState(0)
  const [categories, setCategories] = useState<Category[]>([])
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const confirm = useConfirm()

  const load = useCallback(async () => {
    setProducts(null)
    try {
      const list = await catalogueApi.listProducts({ page_size: 100 })
      setProducts(list.data.items)
      setTotal(list.data.total)
      const cats = await catalogueApi.listCategories()
      setCategories(cats.data)
    } catch (e) {
      setError(errMessage(e))
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const startEdit = (p: Product) => {
    setEditingId(p.id)
    setForm({
      slug: p.slug,
      name: p.name,
      description: p.description,
      price_xof: String(p.price_xof),
      stock: String(p.stock),
      category_id: p.category_id ? String(p.category_id) : '',
      image_url: p.image_url ?? '',
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const submit = async () => {
    setError(null)
    setSuccess(null)

    const price = Number(form.price_xof)
    const stock = Number(form.stock)
    if (!form.name.trim()) return setError('Le nom du produit est obligatoire.')
    if (!Number.isInteger(price) || price < 0) return setError('Prix invalide : entier de FCFA (≥ 0).')
    if (!Number.isInteger(stock) || stock < 0) return setError('Stock invalide : entier (≥ 0).')
    if (!editingId && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(form.slug.trim()))
      return setError("Slug invalide : minuscules, chiffres et tirets (ex : attieke-1kg).")

    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      description: form.description.trim(),
      price_xof: price,
      stock,
      category_id: form.category_id ? Number(form.category_id) : null,
      image_url: form.image_url.trim() || null,
    }
    setBusy(true)
    try {
      if (editingId) {
        await catalogueApi.updateProduct(editingId, payload)
        setSuccess(`Produit « ${form.name} » mis à jour ✓`)
      } else {
        await catalogueApi.createProduct({ ...payload, slug: form.slug.trim() })
        setSuccess(`Produit « ${form.name} » créé ✓`)
      }
      setForm({ ...EMPTY_FORM })
      setEditingId(null)
      await load()
    } catch (e) {
      setError(errMessage(e, "Enregistrement impossible (slug déjà utilisé ?)"))
    } finally {
      setBusy(false)
    }
  }

  const softDelete = (p: Product) => {
    confirm(
      p.stock > 0
        ? `Désactiver « ${p.name} » ?\nLe produit disparaîtra du catalogue public mais restera dans l'historique des commandes.`
        : `Désactiver « ${p.name} » ?`,
      () => {
        void catalogueApi
          .deleteProduct(p.id)
          .then(() => {
            setToast(`« ${p.name} » désactivé (suppression douce, historique conservé)`)
            void load()
          })
          .catch((e) => setToast(errMessage(e, 'Suppression impossible')))
      },
    )
  }

  const adjust = (p: Product, delta: number) => {
    void catalogueApi
      .adjustStock(p.id, delta)
      .then((r) => {
        setToast(`Stock de « ${p.name} » → ${r.data.stock_after}`)
        void load()
      })
      .catch((e) => setToast(errMessage(e, 'Ajustement refusé : stock résultant négatif')))
  }

  return (
    <div>
      <h1 className="text-2xl font-extrabold text-marche-800">Gestion des produits</h1>

      <form
        className="card mt-6 grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-3"
        onSubmit={(e) => { e.preventDefault(); void submit() }}
        noValidate
      >
        <h2 className="sm:col-span-2 lg:col-span-3 font-bold text-slate-700">
          {editingId ? `Modifier le produit #${editingId}` : 'Nouveau produit'}
        </h2>
        <Field label="Slug (URL)" required error={!editingId ? undefined : null}>
          <input
            className={inputClass}
            value={form.slug}
            disabled={editingId !== null}
            placeholder="attieke-tresor-1kg"
            onChange={(e) => setForm({ ...form, slug: e.target.value })}
          />
        </Field>
        <Field label="Nom" required>
          <input className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Catégorie">
          <select className={inputClass} value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
            <option value="">— Sans rayon —</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Prix (FCFA, entier)" required>
          <input type="number" min={0} className={inputClass} value={form.price_xof} onChange={(e) => setForm({ ...form, price_xof: e.target.value })} />
        </Field>
        <Field label="Stock" required>
          <input type="number" min={0} className={inputClass} value={form.stock} onChange={(e) => setForm({ ...form, stock: e.target.value })} />
        </Field>
        <Field label="URL de l'image (facultatif)">
          <input className={inputClass} placeholder="https://…" value={form.image_url} onChange={(e) => setForm({ ...form, image_url: e.target.value })} />
        </Field>
        <div className="sm:col-span-2 lg:col-span-3">
          <Field label="Description">
            <textarea rows={2} className={inputClass} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
        </div>
        <div className="flex gap-3 sm:col-span-2 lg:col-span-3">
          <button className="button-primary" disabled={busy}>
            {editingId ? 'Enregistrer les modifications' : 'Créer le produit'}
          </button>
          {editingId && (
            <button
              type="button"
              className="button-secondary"
              onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }) }}
            >
              Annuler l'édition
            </button>
          )}
        </div>
        <div className="sm:col-span-2 lg:col-span-3">
          <ErrorBanner message={error} />
          <SuccessBanner message={success} />
        </div>
      </form>

      {products === null ? (
        <Spinner label="Chargement du catalogue…" />
      ) : (
        <>
          <p className="mt-8 text-sm text-slate-500">{total} produit(s) au total</p>
          <div className="card mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-sable-100 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Produit</th>
                  <th className="px-4 py-3">Rayon</th>
                  <th className="px-4 py-3">Prix</th>
                  <th className="px-4 py-3">Stock</th>
                  <th className="px-4 py-3">État</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id} className="border-t border-sable-100">
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-800">{p.name}</p>
                      <p className="text-xs text-slate-400">{p.slug}</p>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {categories.find((c) => c.id === p.category_id)?.name ?? '—'}
                    </td>
                    <td className="px-4 py-3 font-semibold">{p.price_xof} FCFA</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          className="rounded border border-sable-200 px-2 py-0.5 hover:bg-sable-100"
                          aria-label={`Retirer 1 au stock de ${p.name}`}
                          onClick={() => adjust(p, -1)}
                        >
                          −1
                        </button>
                        <span className="w-10 text-center font-bold">{p.stock}</span>
                        <button
                          className="rounded border border-sable-200 px-2 py-0.5 hover:bg-sable-100"
                          aria-label={`Ajouter 1 au stock de ${p.name}`}
                          onClick={() => adjust(p, 1)}
                        >
                          +1
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {p.is_active
                        ? <span className="text-xs font-semibold text-green-700">actif</span>
                        : <span className="text-xs font-semibold text-slate-400">désactivé</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button className="text-xs font-semibold text-terracotta-600 hover:underline" onClick={() => startEdit(p)}>
                        Modifier
                      </button>
                      {p.is_active && (
                        <button className="ml-3 text-xs font-semibold text-red-600 hover:underline" onClick={() => softDelete(p)}>
                          Désactiver
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {products.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucun produit — créez le premier ci-dessus.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
  )
}
