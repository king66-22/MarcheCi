import { Link } from 'react-router-dom'
import { fcfa, type Product } from '../api/types'

function PlusIcon() {
  return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
}

function ArrowIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
}

export function ProductCard({ product, onAdd }: { product: Product; onAdd?: (p: Product) => void }) {
  const image = product.image_url || '/product-placeholder.svg'
  return (
    <article className="product-card">
      <Link to={`/produit/${product.id}`} className="product-photo" aria-label={`Voir ${product.name}`}>
        <img src={image} alt={product.image_url ? product.name : ''} loading="lazy" onError={(event) => {
          if (event.currentTarget.src.endsWith('/product-placeholder.svg')) return
          event.currentTarget.src = '/product-placeholder.svg'
        }} />
        <span className="product-stock">{product.stock > 0 ? 'Disponible' : 'Épuisé'}</span>
      </Link>
      <div className="product-body">
        <Link to={`/produit/${product.id}`} className="product-title line-clamp-2">{product.name}</Link>
        <p className="product-description">{product.description || 'Un produit proposé par la coopérative des commerçants d’Adjamé.'}</p>
        <div className="product-buy">
          <span className="product-price">{fcfa(product.price_xof)}</span>
          {onAdd ? (
            <button className="product-add" type="button" disabled={product.stock <= 0} onClick={() => onAdd(product)} aria-label={`Ajouter ${product.name} au panier`} title="Ajouter au panier"><PlusIcon /></button>
          ) : (
            <Link className="product-add" to={`/produit/${product.id}`} aria-label={`Découvrir ${product.name}`} title="Découvrir le produit"><ArrowIcon /></Link>
          )}
        </div>
      </div>
    </article>
  )
}
