import { Link } from 'react-router-dom'
import { fcfa, type Product } from '../api/types'

const placeholder = '/hero-plants.svg'

export function ProductCard({ product, onAdd }: { product: Product; onAdd?: (p: Product) => void }) {
  return (
    <article className="card group flex flex-col">
      <Link to={`/produit/${product.id}`} className="block bg-sable-100">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            loading="lazy"
            className="h-44 w-full object-cover transition group-hover:scale-[1.02]"
            onError={(e) => { (e.currentTarget.src = placeholder) }}
          />
        ) : (
          <div className="flex h-44 w-full items-center justify-center bg-sable-100 text-5xl" aria-hidden>🛍️</div>
        )}
      </Link>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="font-semibold text-slate-800">
          <Link to={`/produit/${product.id}`} className="hover:text-terracotta-600 line-clamp-2">{product.name}</Link>
        </h3>
        <p className="line-clamp-2 flex-1 text-xs text-slate-500">{product.description}</p>
        <div className="flex items-center justify-between">
          <span className="text-base font-bold text-terracotta-700">{fcfa(product.price_xof)}</span>
          {product.stock > 0 ? (
            <span className="text-xs text-slate-500">{product.stock} en stock</span>
          ) : (
            <span className="text-xs font-semibold text-red-500">Épuisé</span>
          )}
        </div>
        <button
          className="button-primary w-full justify-center"
          disabled={product.stock <= 0}
          onClick={() => onAdd?.(product)}
        >
          Ajouter au panier
        </button>
      </div>
    </article>
  )
}
