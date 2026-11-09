import { useState, type FormEvent } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import { Toast } from './ui'

function SearchIcon({ size = 18 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8" stroke="currentColor" strokeWidth="1.8"/><path d="m16 16 4.4 4.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
}

function BasketIcon({ size = 19 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m4 10 1.4 10h13.2L20 10H4Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/><path d="m8 10 4-6 4 6M8.7 13.5v3m3.3-3v3m3.3-3v3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>
}

function Brand() {
  return (
    <Link to="/" className="brand" aria-label="MarchéCI, accueil">
      <span className="brand-mark" aria-hidden="true"><BasketIcon size={22} /></span>
      <span className="brand-name">Marché<span>CI</span></span>
    </Link>
  )
}

export function Header() {
  const { user, isAdmin, logout } = useAuth()
  const { count } = useCart()
  const navigate = useNavigate()
  const [toast, setToast] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [query, setQuery] = useState('')
  const linkClass = ({ isActive }: { isActive: boolean }) => `nav-link${isActive ? ' active' : ''}`

  const search = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const value = query.trim()
    navigate(value ? `/catalogue?q=${encodeURIComponent(value)}` : '/catalogue')
    setMenuOpen(false)
  }

  const closeMenu = () => setMenuOpen(false)
  const accountControl = user ? (
    <div className="header-user">
      <button className="header-action" onClick={() => setUserMenuOpen((open) => !open)} aria-expanded={userMenuOpen}>
        <span className="grid h-7 w-7 place-items-center rounded-full bg-marche-800 text-xs font-bold text-white">
          {user.full_name.slice(0, 1).toUpperCase()}
        </span>
        <span className="hidden xl:inline">{user.full_name.split(' ')[0]}</span>
        <span aria-hidden="true">⌄</span>
      </button>
      {userMenuOpen && (
        <div className="user-menu">
          <Link to="/profil" onClick={() => setUserMenuOpen(false)}>Mon profil</Link>
          <Link to="/commandes" onClick={() => setUserMenuOpen(false)}>Mes commandes</Link>
          {isAdmin && <Link to="/admin" onClick={() => setUserMenuOpen(false)}>Administration</Link>}
          <button onClick={() => {
            logout()
            setUserMenuOpen(false)
            setToast('Vous êtes déconnecté·e.')
            navigate('/')
          }}>Se déconnecter</button>
        </div>
      )}
    </div>
  ) : (
    <Link to="/connexion" className="header-action">Connexion</Link>
  )

  return (
    <>
      <div className="topline">
        <div className="topline-inner"><span aria-hidden="true">✦</span> La coopérative d’Adjamé à portée de main · Prix affichés en FCFA</div>
      </div>
      <header className="site-header">
        <div className="page-width header-main">
          <Brand />
          <form className="header-search" onSubmit={search} role="search">
            <SearchIcon />
            <input aria-label="Rechercher un produit" placeholder="Que cherchez-vous aujourd’hui ?" value={query} onChange={(event) => setQuery(event.target.value)} />
            <button aria-label="Lancer la recherche" type="submit"><SearchIcon size={17} /></button>
          </form>
          <div className="header-actions">
            {accountControl}
            {!user && <Link to="/inscription" className="header-action hidden lg:inline-flex">Créer un compte</Link>}
            <Link to="/panier" className="header-action cart-action" aria-label={`Panier, ${count} article${count > 1 ? 's' : ''}`}>
              <BasketIcon /> <span className="hidden sm:inline">Panier</span>{count > 0 && <span className="cart-count">{count}</span>}
            </Link>
            <button className="mobile-menu-button" onClick={() => setMenuOpen((open) => !open)} aria-label={menuOpen ? 'Fermer le menu' : 'Ouvrir le menu'} aria-expanded={menuOpen}>
              {menuOpen ? <span aria-hidden="true" className="text-xl leading-none">×</span> : <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>}
            </button>
          </div>
        </div>
        <nav className="header-nav" aria-label="Navigation principale">
          <div className="page-width header-nav-inner">
            <NavLink to="/" className={linkClass} end>Accueil</NavLink>
            <NavLink to="/catalogue" className={linkClass}>Le marché</NavLink>
            <NavLink to="/categories" className={linkClass}>Catégories</NavLink>
            {user && <NavLink to="/commandes" className={linkClass}>Mes commandes</NavLink>}
            {isAdmin && <NavLink to="/admin" className={linkClass}>Administration</NavLink>}
            <span className="ml-auto hidden text-xs font-medium text-slate-400 md:inline">Les étals d’Adjamé, sélectionnés par la coopérative</span>
          </div>
        </nav>
        {menuOpen && (
          <div className="mobile-menu">
            <form className="mobile-search" onSubmit={search} role="search">
              <input aria-label="Rechercher dans le marché" placeholder="Rechercher un produit" value={query} onChange={(event) => setQuery(event.target.value)} />
              <button aria-label="Lancer la recherche" type="submit"><SearchIcon /></button>
            </form>
            <NavLink to="/" className={linkClass} end onClick={closeMenu}>Accueil</NavLink>
            <NavLink to="/catalogue" className={linkClass} onClick={closeMenu}>Le marché</NavLink>
            <NavLink to="/categories" className={linkClass} onClick={closeMenu}>Catégories</NavLink>
            {user && <NavLink to="/commandes" className={linkClass} onClick={closeMenu}>Mes commandes</NavLink>}
            {user && <NavLink to="/profil" className={linkClass} onClick={closeMenu}>Mon profil</NavLink>}
            {isAdmin && <NavLink to="/admin" className={linkClass} onClick={closeMenu}>Administration</NavLink>}
            {!user && <NavLink to="/connexion" className={linkClass} onClick={closeMenu}>Connexion</NavLink>}
            {!user && <NavLink to="/inscription" className={linkClass} onClick={closeMenu}>Créer un compte</NavLink>}
          </div>
        )}
      </header>
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </>
  )
}

export function Footer() {
  return (
    <footer className="mt-12 border-t border-sable-200 bg-white">
      <div className="page-width grid gap-8 py-10 sm:grid-cols-3">
        <div>
          <Brand />
          <p className="mt-3 max-w-sm text-sm leading-6 text-slate-500">Une vitrine commune pour découvrir les produits des commerçants d’Adjamé, à Abidjan.</p>
        </div>
        <div>
          <p className="text-sm font-bold text-marche-800">Explorer</p>
          <ul className="mt-3 space-y-2 text-sm text-slate-500">
            <li><Link to="/catalogue" className="hover:text-terracotta-700">Tous les produits</Link></li>
            <li><Link to="/categories" className="hover:text-terracotta-700">Rayons du marché</Link></li>
            <li><Link to="/commandes" className="hover:text-terracotta-700">Suivre mes commandes</Link></li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-bold text-marche-800">Commande et paiement</p>
          <p className="mt-3 text-sm leading-6 text-slate-500">Le paiement en ligne n’est pas activé. Le règlement se fait au retrait ou à la livraison, selon les modalités convenues avec la coopérative.</p>
        </div>
      </div>
      <div className="border-t border-sable-100 py-3 text-center text-xs text-slate-400">© 2026 MarchéCI · Coopérative des commerçants d’Adjamé</div>
    </footer>
  )
}
