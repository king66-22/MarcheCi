import httpx

r = httpx.get("http://localhost/", timeout=5)
print("GET / :", r.status_code, "| React OK" if 'id="root"' in r.text else "PAS D'APP")
r = httpx.get("http://localhost/catalogue", timeout=5)
print("GET /catalogue (SPA fallback) :", r.status_code, "| React OK" if 'id="root"' in r.text else "PAS D'APP")
r = httpx.get("http://localhost/produit-inexistant/xhtml", timeout=5)
print("GET route inconnue :", r.status_code, "| React OK" if 'id="root"' in r.text else "PAS D'APP")
