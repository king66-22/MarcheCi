/**
 * Scénario de RÉSILIENCE : charge constante faible, deux familles de requêtes
 *   1. catalogue — GET /api/catalogue/products (doit rester 200 à 100 %)
 *   2. commandes — GET /api/commandes/health (peut échoyer pendant l'incident
 *      orchestré, mais l'échec doit être PROPRE : 502/503 + corps JSON)
 *
 * L'incident (docker compose stop commandes pendant 20 s puis start) est
 * déclenché par l'orchestrateur python tests/load/orchestrateur.py au milieu
 * du second palier. Aucune écriture : scénario reproductible.
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import { Trend, Counter } from 'k6/metrics'

const BASE = __ENV.BASE || 'http://host.docker.internal'

const dur_catalogue = new Trend('catalogue_duree_ms', true)
const err_catalogue = new Counter('catalogue_erreurs')
const reqs_catalogue = new Counter('catalogue_requetes')
const cmd_200 = new Counter('commandes_200')
const cmd_propre = new Counter('commandes_panne_propre')   // 502/503 JSON
const cmd_sale = new Counter('commandes_panne_sale')       // autre = pas acceptable

export const options = {
  scenarios: {
    chaos_resilience: {
      executor: 'ramping-vus',
      startVUs: 10,
      stages: [
        { duration: '15s', target: 10 },   // régime établi AVANT l'incident
        { duration: '20s', target: 10 },   // === incident : commandes arrêté ===
        { duration: '25s', target: 10 },   // redémarrage + récupération
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '5s',
    },
  },
  thresholds: {
    'catalogue_erreurs': ['count==0'],                 // le catalogue ne doit JAMAIS tomber
    'catalogue_duree_ms': ['p(95)<1000'],
    'commandes_panne_sale': ['count==0'],
    'checks': ['rate>0.0'],
  },
}

export default function () {
  const r1 = http.get(`${BASE}/api/catalogue/products?page=1&page_size=12`)
  dur_catalogue.add(r1.timings.duration)
  reqs_catalogue.add(1)
  check(r1, { 'catalogue 200': (res) => res.status === 200 })
  if (r1.status !== 200) err_catalogue.add(1)

  const r2 = http.get(`${BASE}/api/commandes/health`)
  const propre =
    (r2.status === 200 || r2.status === 502 || r2.status === 503) &&
    typeof r2.body === 'string' && r2.body.trim().startsWith('{')
  check(r2, { 'commandes OK ou panne PROPRE (JSON)': propre })
  if (r2.status === 200) cmd_200.add(1)
  else if (propre) cmd_propre.add(1)
  else {
    cmd_sale.add(1)
    console.debug(`dirty : status=${r2.status} body=${(String(r2.body) || '(vide)').slice(0, 120)}`)
  }
  sleep(1)
}

/** Résumé structuré pour le rapport de résilience. */
export function handleSummary(data) {
  const v = data.metrics.catalogue_duree_ms?.values
  const summary = {
    scenario: 'resilience_incident_commandes',
    catalogue: {
      requetes: data.metrics.catalogue_requetes?.values?.count ?? 0,
      erreurs: data.metrics.catalogue_erreurs?.values?.count ?? 0,
      p95_ms: v ? Math.round(v['p(95)']) : null,
    },
    commandes: {
      ok_200: data.metrics.commandes_200?.values?.count ?? 0,
      panne_propre_json: data.metrics.commandes_panne_propre?.values?.count ?? 0,
      panne_sale: data.metrics.commandes_panne_sale?.values?.count ?? 0,
    },
  }
  return { '/results/summary_resilience.json': JSON.stringify(summary, null, 2) }
}
