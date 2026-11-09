import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <section className="page-width grid min-h-[55vh] place-items-center py-12 text-center" aria-labelledby="not-found-title">
      <div className="max-w-lg">
        <span className="font-display text-7xl font-bold text-terracotta-600" aria-hidden="true">404</span>
        <h1 id="not-found-title" className="font-display mt-3 text-3xl font-bold text-marche-900">Ce rayon n’existe pas.</h1>
        <p className="mt-3 leading-6 text-slate-500">La page recherchée a peut-être changé d’adresse. Retrouvez les produits depuis le marché.</p>
        <Link to="/catalogue" className="button-primary mt-6">Retour au marché</Link>
      </div>
    </section>
  )
}
