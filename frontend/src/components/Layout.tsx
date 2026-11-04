import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import { Toast } from './ui'

export function Header() {
  const { user, isAdmin, logout } = useAuth()
  const { count } = useCart()
  const navigate = useNavigate()
  const [toast, setToast] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  const link = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm font-medium transition ${
      isActive ? 'bg-terracotta-600 text-white' : 'text-slate-600 hover:bg-sable-100 hover:text-marche-800'
    }`

  return (
    <header className="sticky top-0 z-40 border-b border-sable-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
        <Link to="/" className="flex items-center gap-2" aria-label="MarchéCI — accueil">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-terracotta-600 text-lg font-black text-white">M</span>
          <span className="text-lg font-extrabold tracking-tight text-marche-800">
            Marché<span className="text-terracotta-600">CI</span>
          </span>
        </Link>

        <nav className="hidden flex-1 items-center gap-1 md:flex" aria-label="Navigation principale">
          <NavLink to="/" className={link} end>Accueil</NavLink>
          <NavLink to="/catalogue" className={link}>Catalogue</NavLink>
          <NavLink to="/categories" className={link}>Catégories</NavLink>
          {user && <NavLink to="/commandes" className={link}>Mes commandes</NavLink>}
          {isAdmin && (
            <NavLink to="/admin" className={link}>Administration</NavLink>
          )}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <Link
            to="/panier"
            className="relative rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-sable-100"
            aria-label={`Panier : ${count} article(s)`}
          >
            🛒 Panier
            {count > 0 && (
              <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-terracotta-600 px-1 text-xs font-bold text-white">
                {count}
              </span>
            )}
          </Link>
          {user ? (
            <div className="relative">
              <button
                onClick={() => setOpen((o) => !o)}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-sable-100"
                aria-expanded={open}
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-marche-700 text-xs font-bold text-white">
                  {user.full_name.slice(0, 1).toUpperCase()}
                </span>
                <span className="hidden sm:inline">{user.full_name.split(' ')[0]}</span> ▾
              </button>
              {open && (
                <div className="absolute right-0 mt-2 w-52 overflow-hidden rounded-xl border border-sable-200 bg-white shadow-lg">
                  <Link to="/profil" onClick={() => setOpen(false)} className="block px-4 py-2.5 text-sm hover:bg-sable-100">Mon profil</Link>
                  <Link to="/commandes" onClick={() => setOpen(false)} className="block px-4 py-2.5 text-sm hover:bg-sable-100">Mes commandes</Link>
                  {isAdmin && (
                    <Link to="/admin" onClick={() => setOpen(false)} className="block px-4 py-2.5 text-sm hover:bg-sable-100">Espace admin</Link>
                  )}
                  <button
                    onClick={() => {
                      logout()
                      setOpen(false)
                      setToast('Déconnecté. À bientôt sur MarchéCI !')
                      navigate('/')
                    }}
                    className="block w-full px-4 py-2.5 text-left text-sm text-red-600 hover:bg-red-50"
                  >
                    Se déconnecter
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <Link to="/connexion" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-sable-100">
                Connexion
              </Link>
              <Link to="/inscription" className="button-primary">
                S'inscrire
              </Link>
            </>
          )}
        </div>
      </div>
      <button onClick={() => setOpen((o) => !o)} className="sr-only">menu</button>
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </header>
  )
}

export function Footer() {
  return (
    <footer className="mt-16 border-t border-sable-200 bg-white">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-3">
        <div>
          <p className="text-lg font-extrabold text-marche-800">Marché<span className="text-terracotta-600">CI</span></p>
          <p className="mt-2 text-sm text-slate-500">
            La boutique commune de la coopérative des commerçants d'Adjamé. Produits du marché,
            prix en francs CFA, livraison à Abidjan.
          </p>
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-700">Acheter</p>
          <ul className="mt-2 space-y-1.5 text-sm text-slate-500">
            <li><Link to="/catalogue" className="hover:text-terracotta-600">Catalogue complet</Link></li>
            <li><Link to="/categories" className="hover:text-terracotta-600">Catégories</Link></li>
            <li><Link to="/commandes" className="hover:text-terracotta-600">Suivi des commandes</Link></li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-700">Paiement</p>
          <p className="mt-2 text-sm text-slate-500">
            Le paiement en ligne n'est <strong>pas encore activé</strong> — les commandes sont
            réglées au marché lors du retrait ou de la livraison (à régler auprès du commerçant).
          </p>
        </div>
      </div>
      <div className="border-t border-sable-200 py-3 text-center text-xs text-slate-400">
        © 2026 MarchéCI — architecture microservices cloud-native.
      </div>
    </footer>
  )
}
