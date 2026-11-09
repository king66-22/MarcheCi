import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { catalogueApi } from '../../api/service'
import type { Category, Product, ProductImage } from '../../api/types'
import { ErrorBanner, Field, Spinner, SuccessBanner, Toast, errMessage, inputClass, useConfirm } from '../../components/ui'
import { ImageUploader } from '../../components/ImageUploader'

const EMPTY_FORM = { name: '', description: '', price_xof: '', stock: '', category_id: '' }

function slugify(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 150)
}

function isConflict(error: unknown): boolean {
  return (error as { response?: { status?: number } })?.response?.status === 409
}

export default function MerchantProducts() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [editingId, setEditingId] = useState<number | null>(null)
  const [images, setImages] = useState<ProductImage[]>([])
  const [coverUrl, setCoverUrl] = useState<string | null>(null)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const confirm = useConfirm()
  const location = useLocation()
  const initialEditId = (location.state as { editProductId?: number } | null)?.editProductId
  const handledInitialEdit = useRef(false)

  const load = useCallback(async () => {
    try {
      const list = await catalogueApi.mine()
      setProducts(list.data.items)
      const cats = await catalogueApi.listCategories()
      setCategories(cats.data)
      setError(null)
    } catch (e) {
      setError(errMessage(e, 'Chargement de votre boutique impossible.'))
    }
  }, [])

  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { void load() }, [load])

  const resetForm = () => {
    setEditingId(null)
    setForm({ ...EMPTY_FORM })
    setImages([])
    setCoverUrl(null)
    setPendingFiles([])
    setError(null)
    setSuccess(null)
  }

  const startEdit = async (product: Product) => {
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      const { data } = await catalogueApi.getProduct(product.id)
      setEditingId(data.id)
      setForm({
        name: data.name,
        description: data.description,
        price_xof: String(data.price_xof),
        stock: String(data.stock),
        category_id: data.category_id ? String(data.category_id) : '',
      })
      setImages(data.images ?? [])
      setCoverUrl(data.image_url)
      setPendingFiles([])
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e) {
      setError(errMessage(e, 'Ouverture du produit impossible.'))
    } finally {
      setBusy(false)
    }
  }

  // Arrivée depuis la fiche publique « Gérer mes photos » : ouvrir directement le produit.
  useEffect(() => {
    if (handledInitialEdit.current || !initialEditId || products === null) return
    const target = products.find((product) => product.id === initialEditId)
    if (!target) return
    handledInitialEdit.current = true
    // oxlint-disable-next-line react/set-state-in-effect
    void startEdit(target)
  }, [initialEditId, products])

  const productPayload = () => {
    const price = Number(form.price_xof)
    const stock = Number(form.stock)
    if (!form.name.trim()) {
      setError('Le nom du produit est obligatoire.')
      return null
    }
    if (!Number.isInteger(price) || price < 0) {
      setError('Prix invalide : indiquez un montant entier en FCFA (≥ 0).')
      return null
    }
    if (!Number.isInteger(stock) || stock < 0) {
      setError('Stock invalide : indiquez un nombre entier (≥ 0).')
      return null
    }
    return {
      name: form.name.trim(),
      description: form.description.trim(),
      price_xof: price,
      stock,
      category_id: form.category_id ? Number(form.category_id) : null,
    }
  }

  const uploadPendingPhotos = async (productId: number): Promise<string[]> => {
    const failures: string[] = []
    for (const file of pendingFiles) {
      try {
        await catalogueApi.uploadProductImage(productId, file)
      } catch (e) {
        failures.push(errMessage(e, `« ${file.name} » n'a pas pu être envoyée.`) ?? '')
      }
    }
    return failures
  }

  const createProduct = async (payload: Record<string, unknown>): Promise<Product> => {
    const base = slugify(form.name) || `produit-${Date.now()}`
    let lastError: unknown = null
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const slug = attempt === 0 ? base : `${base}-${attempt + 1}`
      try {
        const { data } = await catalogueApi.createProduct({ ...payload, slug })
        return data
      } catch (e) {
        lastError = e
        if (!isConflict(e)) throw e
      }
    }
    throw lastError ?? new Error('Création impossible')
  }

  const openCreatedProduct = async (created: Product, failures: string[]) => {
    setEditingId(created.id)
    setForm({
      name: created.name,
      description: created.description,
      price_xof: String(created.price_xof),
      stock: String(created.stock),
      category_id: created.category_id ? String(created.category_id) : '',
    })
    setPendingFiles([])
    try {
      const { data } = await catalogueApi.getProduct(created.id)
      setImages(data.images ?? [])
      setCoverUrl(data.image_url)
    } catch {
      setImages([])
      setCoverUrl(created.image_url)
    }
    if (failures.length > 0) {
      setError(`Produit créé, mais certaines photos n'ont pas été envoyées : ${failures.join(' ')}`)
      setSuccess(null)
    } else {
      setSuccess(`Produit « ${created.name} » créé ✓ Vous pouvez compléter ses photos ci-dessous.`)
    }
  }

  const submit = async () => {
    setError(null)
    setSuccess(null)
    const payload = productPayload()
    if (!payload) return

    setBusy(true)
    try {
      if (editingId) {
        await catalogueApi.updateProduct(editingId, payload)
        setSuccess(`Produit « ${form.name.trim()} » mis à jour ✓`)
        await load()
      } else {
        const created = await createProduct(payload)
        const failures = await uploadPendingPhotos(created.id)
        await openCreatedProduct(created, failures)
        await load()
      }
    } catch (e) {
      setError(errMessage(e, 'Enregistrement impossible. Vérifiez les informations saisies.'))
    } finally {
      setBusy(false)
    }
  }

  const deactivate = (product: Product) => {
    confirm(
      `Retirer « ${product.name} » de votre boutique ?\nIl ne sera plus visible dans le catalogue public.`,
      () => {
        void catalogueApi
          .deleteProduct(product.id)
          .then(async () => {
            setToast(`« ${product.name} » retiré du catalogue`)
            if (editingId === product.id) resetForm()
            await load()
          })
          .catch((e) => setToast(errMessage(e, 'Suppression impossible')))
      },
    )
  }

  const handleUploaded = (image: ProductImage) => {
    setImages((current) => [...current, image])
    setCoverUrl((current) => current ?? image.url)
    setSuccess('Photo ajoutée ✓')
    void load()
  }

  const handleDeleted = (imageId: number) => {
    setImages((current) => current.filter((image) => image.id !== imageId))
    if (editingId) {
      void catalogueApi
        .getProduct(editingId)
        .then(({ data }) => {
          setImages(data.images ?? [])
          setCoverUrl(data.image_url)
        })
        .catch(() => undefined)
    }
    setToast('Photo supprimée')
    void load()
  }

  const handleCover = (image: ProductImage) => {
    setCoverUrl(image.url)
    setToast('Photo de couverture mise à jour')
    void load()
  }

  const activeCount = products?.filter((product) => product.is_active).length ?? 0

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Espace commerçant</p>
          <h1 className="mt-1 text-2xl font-extrabold text-marche-800">Mes produits</h1>
          <p className="mt-1 text-sm text-slate-500">
            {products === null
              ? 'Chargement de votre boutique…'
              : `${products.length} produit(s) · ${activeCount} en vente`}
          </p>
        </div>
        <button type="button" className="button-secondary" onClick={resetForm}>
          + Nouveau produit
        </button>
      </div>

      <form
        className="card mt-6 grid gap-4 p-6 sm:grid-cols-2"
        onSubmit={(event) => { event.preventDefault(); void submit() }}
        noValidate
      >
        <h2 className="font-bold text-slate-700 sm:col-span-2">
          {editingId ? `Modifier « ${form.name || 'produit'} »` : 'Ajouter un produit'}
        </h2>

        <div className="sm:col-span-2">
          <Field label="Nom du produit" required>
            <input
              className={inputClass}
              value={form.name}
              placeholder="Attiéké frais 1 kg"
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </Field>
        </div>

        <Field label="Prix (FCFA)" required>
          <input
            type="number"
            min={0}
            step={1}
            className={inputClass}
            value={form.price_xof}
            placeholder="1500"
            onChange={(event) => setForm({ ...form, price_xof: event.target.value })}
          />
        </Field>

        <Field label="Stock disponible" required>
          <input
            type="number"
            min={0}
            step={1}
            className={inputClass}
            value={form.stock}
            placeholder="20"
            onChange={(event) => setForm({ ...form, stock: event.target.value })}
          />
        </Field>

        <Field label="Rayon du marché">
          <select
            className={inputClass}
            value={form.category_id}
            onChange={(event) => setForm({ ...form, category_id: event.target.value })}
          >
            <option value="">— Choisir un rayon (facultatif) —</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>{category.name}</option>
            ))}
          </select>
        </Field>

        <div className="sm:col-span-2">
          <Field label="Description">
            <textarea
              rows={3}
              className={inputClass}
              value={form.description}
              placeholder="Décrivez votre produit, son origine, sa qualité…"
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </Field>
        </div>

        <div className="sm:col-span-2">
          <ImageUploader
            productId={editingId}
            images={images}
            coverUrl={coverUrl}
            pending={pendingFiles}
            onPendingChange={setPendingFiles}
            onUploaded={handleUploaded}
            onDeleted={handleDeleted}
            onCover={handleCover}
            disabled={busy}
          />
        </div>

        <div className="flex flex-wrap gap-3 sm:col-span-2">
          <button className="button-primary" disabled={busy}>
            {busy ? 'Enregistrement…' : editingId ? 'Enregistrer les modifications' : 'Créer le produit'}
          </button>
          {editingId && (
            <button type="button" className="button-secondary" onClick={resetForm} disabled={busy}>
              Créer un autre produit
            </button>
          )}
        </div>

        <div className="sm:col-span-2">
          <ErrorBanner message={error} />
          <SuccessBanner message={success} />
        </div>
      </form>

      {products === null ? (
        <Spinner label="Chargement de vos produits…" />
      ) : (
        <div className="card mt-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-sable-100 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Photo</th>
                <th className="px-4 py-3">Produit</th>
                <th className="px-4 py-3">Rayon</th>
                <th className="px-4 py-3">Prix</th>
                <th className="px-4 py-3">Stock</th>
                <th className="px-4 py-3">État</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} className="border-t border-sable-100">
                  <td className="px-4 py-3">
                    <img
                      src={product.image_url || '/product-placeholder.svg'}
                      alt=""
                      className="h-12 w-12 rounded-lg border border-sable-100 object-cover"
                      onError={(event) => { event.currentTarget.src = '/product-placeholder.svg' }}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-semibold text-slate-800">{product.name}</p>
                    <p className="text-xs text-slate-400">{product.slug}</p>
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {categories.find((category) => category.id === product.category_id)?.name ?? '—'}
                  </td>
                  <td className="px-4 py-3 font-semibold">{product.price_xof} FCFA</td>
                  <td className="px-4 py-3">{product.stock}</td>
                  <td className="px-4 py-3">
                    {product.is_active
                      ? <span className="text-xs font-semibold text-green-700">en vente</span>
                      : <span className="text-xs font-semibold text-slate-400">retiré</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      className="text-xs font-semibold text-terracotta-600 hover:underline"
                      onClick={() => void startEdit(product)}
                    >
                      Modifier · photos
                    </button>
                    {product.is_active && (
                      <button
                        type="button"
                        className="ml-3 text-xs font-semibold text-red-600 hover:underline"
                        onClick={() => deactivate(product)}
                      >
                        Retirer
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {products.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-400">
                    Votre boutique est vide. Ajoutez votre premier produit ci-dessus, avec ses photos.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
  )
}
