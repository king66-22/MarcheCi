import { Route, Routes } from 'react-router-dom'
import { Header, Footer } from './components/Layout'
import { RequireAdmin, RequireAuth } from './components/ui'
import Home from './pages/Home'
import Catalogue from './pages/Catalogue'
import ProductDetail from './pages/ProductDetail'
import Categories from './pages/Categories'
import Login from './pages/Login'
import Register from './pages/Register'
import Cart from './pages/Cart'
import Checkout from './pages/Checkout'
import OrderConfirmation from './pages/OrderConfirmation'
import Orders from './pages/Orders'
import Profile from './pages/Profile'
import Dashboard from './pages/admin/Dashboard'
import AdminProducts from './pages/admin/Products'
import AdminCategories from './pages/admin/Categories'
import AdminOrders from './pages/admin/Orders'
import AdminUsers from './pages/admin/Users'
import AdminNotifications from './pages/admin/Notifications'

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <Routes>
          {/* Public */}
          <Route path="/" element={<Home />} />
          <Route path="/catalogue" element={<Catalogue />} />
          <Route path="/produit/:id" element={<ProductDetail />} />
          <Route path="/categories" element={<Categories />} />
          <Route path="/connexion" element={<Login />} />
          <Route path="/inscription" element={<Register />} />

          {/* Client connecté */}
          <Route path="/panier" element={<Cart />} />
          <Route path="/checkout" element={<RequireAuth><Checkout /></RequireAuth>} />
          <Route path="/commande/:id" element={<RequireAuth><OrderConfirmation /></RequireAuth>} />
          <Route path="/commandes" element={<RequireAuth><Orders /></RequireAuth>} />
          <Route path="/profil" element={<RequireAuth><Profile /></RequireAuth>} />

          {/* Espace administration (rôle ADMIN only) */}
          <Route path="/admin" element={<RequireAdmin><Dashboard /></RequireAdmin>} />
          <Route path="/admin/produits" element={<RequireAdmin><AdminProducts /></RequireAdmin>} />
          <Route path="/admin/categories" element={<RequireAdmin><AdminCategories /></RequireAdmin>} />
          <Route path="/admin/commandes" element={<RequireAdmin><AdminOrders /></RequireAdmin>} />
          <Route path="/admin/utilisateurs" element={<RequireAdmin><AdminUsers /></RequireAdmin>} />
          <Route path="/admin/notifications" element={<RequireAdmin><AdminNotifications /></RequireAdmin>} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}
