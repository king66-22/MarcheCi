/**
 * Scénario de charge catalogue : lecture mixte cache Redis (60 s) + DB.
 *
 * Le trafic est 100 % HTTP via la gateway Nginx (port 80 -> /api/catalogue/),
 * exactement comme le trafic client réel.
 *   - 70 % de requêtes identiques (page 1) → chemin cache Redis
 *   - 30 % de recherches uniques           → chemin PostgreSQL (hors cache)
 *
 * Variables d'environnement k6 :
 *   BASE     — défaut http://host.docker.internal (Docker Desktop)
 *   VUS      — pic de virtual users (défaut 50)
 *   RAMP     — montée en charge en secondes (défaut 20)
 *   HOLD     — durée du palier (défaut 40)
 *   OUT_FILE — nom du fichier résumé écrit dans /results
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import { Trend, Counter } from 'k6/metrics'

const BASE = __ENV.BASE || 'http://host.docker.internal'
const VUS = Number(__ENV.VUS || 50)
const RAMP = Number(__ENV.RAMP || 20)
const HOLD = Number(__ENV.HOLD || 40)

// métriques personnalisées (comparaison 1 vs 3 répliques, rapport de charge)
const dur_cache = new Trend('produits_cache_duree_ms', true)
const dur_db = new Trend('produits_db_duree_ms', true)
const err_cache = new Counter('produits_cache_erreurs')
const err_db = new Counter('produits_db_erreurs')
const reqs_cache = new Counter('produits_cache_requetes')
const reqs_db = new Counter('produits_db_requetes')

export const options = {
  scenarios: {
    lecture_marche: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: `${RAMP}s`, target: VUS },
        { duration: `${HOLD}s`, target: VUS },
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '5s',
    },
  },
  thresholds: {
    'checks': ['rate>0.99'],                                   // < 1 % d'échec
    'produits_cache_duree_ms': ['p(95)<800'],                  // chemin Redis
    'produits_db_duree_ms': ['p(95)<1500'],                    // chemin PostgreSQL
  },
}

export default function () {
  if (Math.random() < 0.7) {
    // chemin CACHÉ : identique à chaque itération (TTL 60 s côté Redis)
    const r = http.get(`${BASE}/api/catalogue/products?page=1&page_size=12`)
    dur_cache.add(r.timings.duration)
    reqs_cache.add(1)
    check(r, { 'produits 200': (res) => res.status === 200 })
    if (r.status !== 200) err_cache.add(1)
  } else {
    // chemin POSTGRES : clé de recherche UNIQUE → jamais dans le cache
    const q = 'recherche-' + __ITER + '-' + Math.random().toString(36).slice(2, 8)
    const r = http.get(`${BASE}/api/catalogue/products?q=${q}&page_size=12`)
    dur_db.add(r.timings.duration)
    reqs_db.add(1)
    check(r, { 'recherche 200': (res) => res.status === 200 })
    if (r.status !== 200) err_db.add(1)
  }
  sleep(1)
}

/** Résumé structuré pour le rapport de charge. */
export function handleSummary(data) {
  const trendInfo = (name) => {
    const v = data.metrics[name]?.values
    if (!v) return null
    return {
      p50_ms: Math.round(v.med),
      p95_ms: Math.round(v['p(95)']),
      max_ms: Math.round(v.max),
    }
  }
  const summary = {
    scenario: 'load_catalogue',
    tag: __ENV.TAG_RUN || 'non-tag',
    vus_pic: VUS,
    ramp_s: RAMP,
    hold_s: HOLD,
    total: {
      requetes: data.metrics.http_reqs?.values?.count ?? 0,
      debit_rps: Number((data.metrics.http_reqs?.values?.rate ?? 0).toFixed(1)),
      p95_ms: Math.round(data.metrics.http_req_duration?.values['p(95)'] ?? 0),
      rate_checks: data.metrics.checks?.values?.rate ?? 0,
      duree_ms_total: Math.round(data.metrics.iteration_duration?.values?.avg ?? 0),
    },
    cache_redis: {
      ...(trendInfo('produits_cache_duree_ms') ?? {}),
      requetes: data.metrics.produits_cache_requetes?.values?.count ?? 0,
    },
    db_postgres: {
      ...(trendInfo('produits_db_duree_ms') ?? {}),
      requetes: data.metrics.produits_db_requetes?.values?.count ?? 0,
    },
    erreurs: {
      cache: data.metrics.produits_cache_erreurs?.values?.count ?? 0,
      db: data.metrics.produits_db_erreurs?.values?.count ?? 0,
    },
  }
  const safe = String(__ENV.OUT_FILE || 'summary_load.json')
  return { [`/results/${safe}`]: JSON.stringify(summary, null, 2) }
}
