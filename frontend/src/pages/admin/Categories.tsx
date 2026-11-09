import { useCallback, useEffect, useState } from 'react'
import { catalogueApi } from '../../api/service'
import type { Category } from '../../api/types'
import { ErrorBanner, Spinner, Field, inputClass, Toast, errMessage, useConfirm } from '../../components/ui'

export default function AdminCategories() {
  const [categories, setCategories] = useState<Category[] | null>(null)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const confirm = useConfirm()

  const load = useCallback(async () => {
    try {
      const { data } = await catalogueApi.listCategories()
      setCategories(data)
      setError(null)
    } catch (e) {
      setError(errMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { void load() }, [load])

  const slugify = (v: string) =>
    v.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')

  const submit = async () => {
    setError(null)
    const finalSlug = slug.trim() || slugify(name)
    if (!name.trim()) return setError('Le nom du rayon est obligatoire.')
    if (!finalSlug) return setError('Slug vide : précisez un nom.')
    try {
      await catalogueApi.createCategory({ slug: finalSlug, name: name.trim() })
      setName('')
      setSlug('')
      setToast(`Rayon « ${name.trim()} » créé ✓`)
      await load()
    } catch (e) {
      setError(errMessage(e, 'Création impossible (slug déjà pris ?)'))
    }
  }

  const remove = (c: Category) => {
    confirm(
      `Supprimer le rayon « ${c.name} » ? Les produits liés resteront sans rayon.`,
      () => {
        void catalogueApi
          .deleteCategory(c.id)
          .then(() => { setToast(`Rayon « ${c.name} » supprimé`); void load() })
          .catch((e) => setToast(errMessage(e, 'Suppression impossible')))
      },
    )
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-extrabold text-marche-800">Gestion des catégories</h1>

      <form
        className="card mt-6 flex flex-col gap-4 p-6"
        onSubmit={(e) => { e.preventDefault(); void submit() }}
        noValidate
      >
        <Field label="Nom du rayon" required>
          <input
            className={inputClass}
            value={name}
            placeholder="Épices & Condiments"
            onChange={(e) => { setName(e.target.value); setSlug(slugify(e.target.value)) }}
          />
        </Field>
        <Field label="Slug (généré automatiquement, modifiable)">
          <input className={inputClass} value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="epices-condiments" />
        </Field>
        <ErrorBanner message={error} />
        <button className="button-primary w-fit">Créer le rayon</button>
      </form>

      {categories === null ? (loading ? (
        <Spinner label="Chargement des rayons…" />
      ) : (
        <button className="button-secondary mt-4" onClick={() => { setLoading(true); void load() }}>Réessayer</button>
      )) : categories.length === 0 ? (
        <p className="mt-6 text-sm text-slate-500">Aucun rayon pour l'instant.</p>
      ) : (
        <ul className="mt-6 flex flex-col gap-2">
          {categories.map((c) => (
            <li key={c.id} className="card flex items-center gap-4 px-4 py-3">
              <div>
                <p className="font-semibold text-slate-800">{c.name}</p>
                <p className="text-xs text-slate-400">/{c.slug} — {c.product_count ?? 0} produit(s)</p>
              </div>
              <button
                className="ml-auto text-xs font-semibold text-red-600 hover:underline"
                onClick={() => remove(c)}
              >
                Supprimer
              </button>
            </li>
          ))}
        </ul>
      )}
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
  )
}
