import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { catalogueApi } from '../api/service'
import type { Category, Product } from '../api/types'
import { ProductCard } from '../components/ProductCard'
import { EmptyState, ErrorBanner, Spinner, errMessage } from '../components/ui'

function ArrowRight() {
  return <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
}

function PromiseIcon({ children }: { children: string }) {
  return <span className="promise-icon" aria-hidden="true"><span className="text-lg">{children}</span></span>
}

export default function Home() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [categories, setCategories] = useState<Category[] | null>(null)
  const [productError, setProductError] = useState<string | null>(null)
  const [categoryError, setCategoryError] = useState<string | null>(null)
  const [productsLoading, setProductsLoading] = useState(true)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    let active = true
    void catalogueApi.listProducts({ page_size: 8 })
      .then(({ data }) => { if (active) { setProducts(data.items); setProductError(null) } })
      .catch((error: unknown) => { if (active) { setProductError(errMessage(error, 'Le catalogue est momentanément indisponible.')); setProducts(null) } })
      .finally(() => { if (active) setProductsLoading(false) })
    void catalogueApi.listCategories()
      .then(({ data }) => { if (active) { setCategories(data); setCategoryError(null) } })
      .catch((error: unknown) => { if (active) { setCategoryError(errMessage(error, 'Les catégories ne sont pas disponibles pour le moment.')); setCategories([]) } })
    return () => { active = false }
  }, [refresh])

  const retry = () => {
    setProductsLoading(true)
    setProductError(null)
    setCategoryError(null)
    setRefresh((value) => value + 1)
  }

  return (
    <>
      <div className="page-width hero-wrap">
        <section className="hero-panel" aria-labelledby="home-title">
          <div className="hero-copy">
            <p className="eyebrow">La coopérative des commerçants d’Adjamé</p>
            <h1 className="hero-title" id="home-title">Le marché d’Adjamé, <em>chez vous.</em></h1>
            <p className="hero-description">Les produits du marché réunis au même endroit. Découvrez les étals, comparez les prix en francs CFA et préparez votre commande en quelques instants.</p>
            <div className="hero-actions">
              <Link to="/catalogue" className="button-primary">Explorer le marché <ArrowRight /></Link>
              <Link to="/categories" className="button-secondary">Voir les rayons</Link>
            </div>
          </div>
          <div className="hero-art" aria-hidden="true">
            <img src="/hero-plants.svg" alt="" width="400" height="400" />
            <div className="hero-note"><strong>Les étals d’Adjamé</strong><span>Une vitrine de la coopérative</span></div>
          </div>
        </section>
        <div className="promise-strip" aria-label="Informations sur MarchéCI">
          <div className="promise-item"><PromiseIcon>⌖</PromiseIcon><span>Une sélection des commerçants d’Adjamé</span></div>
          <div className="promise-item"><PromiseIcon>₣</PromiseIcon><span>Des prix affichés en francs CFA</span></div>
          <div className="promise-item"><PromiseIcon>✓</PromiseIcon><span>Le stock revérifié avant la commande</span></div>
        </div>
      </div>

      <section className="page-width home-section" aria-labelledby="categories-title">
        <div className="home-section-head">
          <div><p className="eyebrow">Trouver son rayon</p><h2 className="section-heading" id="categories-title">Les rayons du marché</h2></div>
          <Link to="/categories" className="text-link">Tous les rayons <ArrowRight /></Link>
        </div>
        {categoryError && <div className="mt-5"><ErrorBanner message={categoryError} /></div>}
        {categories === null ? <Spinner label="Chargement des rayons…" /> : categories.length > 0 ? (
          <div className="category-grid">
            {categories.slice(0, 6).map((category) => (
              <Link to={`/catalogue?categorie=${encodeURIComponent(category.slug)}`} className="category-tile" key={category.id}>
                <div><strong>{category.name}</strong><span>{category.product_count ?? 0} produit{category.product_count === 1 ? '' : 's'}</span></div>
                <span className="category-arrow"><ArrowRight /></span>
              </Link>
            ))}
          </div>
        ) : !categoryError ? (
          <div className="mt-5"><EmptyState title="Les rayons se préparent" hint="La coopérative ajoutera bientôt ses premières catégories." /></div>
        ) : null}
      </section>

      <section className="page-width home-section pt-0" aria-labelledby="products-title">
        <div className="home-section-head">
          <div><p className="eyebrow">À découvrir</p><h2 className="section-heading" id="products-title">Sur les étals</h2><p className="section-copy">Des produits proposés par la coopérative, disponibles à la commande selon le stock indiqué.</p></div>
          <Link to="/catalogue" className="text-link">Voir le catalogue <ArrowRight /></Link>
        </div>
        {productError && <div className="mt-5"><ErrorBanner message={productError} /><button className="button-secondary mt-3" onClick={retry}>Réessayer</button></div>}
        {productsLoading ? <Spinner label="Chargement du catalogue…" /> : products && products.length > 0 ? (
          <div className="product-grid">
            {products.map((product) => <ProductCard key={product.id} product={product} />)}
          </div>
        ) : !productError ? (
          <div className="mt-5"><EmptyState title="Les étals se garnissent" hint="Aucun produit n’est encore publié. Revenez bientôt découvrir la sélection de la coopérative."><Link to="/catalogue" className="button-secondary mt-2">Parcourir le catalogue</Link></EmptyState></div>
        ) : null}
      </section>

      <section className="page-width">
        <div className="market-band">
          <div><h2>Une commande, sans détour.</h2><p>Composez votre panier. Les prix et les disponibilités sont revérifiés au moment de la validation.</p></div>
          <Link to="/catalogue" className="button-primary">Commencer mes achats <ArrowRight /></Link>
        </div>
      </section>
    </>
  )
}
