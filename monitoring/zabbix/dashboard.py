r"""Crée ou met à jour le tableau de bord Zabbix « MarcheCI - Supervision ».

Le script est idempotent : un tableau de bord existant portant le même nom est
mis à jour (même identifiant). Il suppose que `provisioning.py` a déjà créé
l'hôte et les sondes HTTP. Utilisation, depuis la racine du dépôt :

    .\.venv\Scripts\python.exe monitoring\zabbix\dashboard.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import provisioning as p  # noqa: E402  (dépend du chemin ajouté ci-dessus)

NOM = "MarcheCI - Supervision"

# Ordre d'affichage des tuiles, sur trois colonnes de 16 unités.
TUILES = [
    ("health.gateway", "Gateway"),
    ("health.catalogue", "Catalogue"),
    ("health.commandes", "Commandes"),
    ("health.utilisateurs", "Utilisateurs"),
    ("health.notifications", "Notifications"),
    ("agent.ping", "Agent Zabbix 2"),
]


def construire_widgets(hostid: str, itemids: dict[str, str]) -> list[dict]:
    """Widgets : liste des problèmes actifs puis une tuile par sonde."""
    widgets = [
        {
            "type": "problems",
            "name": "Problèmes actifs",
            "x": 0,
            "y": 0,
            "width": 48,
            "height": 3,
            "view_mode": 0,
            "fields": [
                {"type": 3, "name": "hostids.0", "value": hostid},
                # 2 = mode « Problèmes » du widget (valeurs acceptées : 1, 2, 3).
                {"type": 0, "name": "show", "value": 2},
                {"type": 0, "name": "show_recovery_time", "value": 0},
                {"type": 0, "name": "show_info", "value": 0},
                {"type": 0, "name": "show_host", "value": 0},
                {"type": 0, "name": "show_update", "value": 0},
                {"type": 0, "name": "show_actions", "value": 0},
            ],
        }
    ]
    for position, (cle, libelle) in enumerate(TUILES):
        widgets.append(
            {
                "type": "item",
                "name": libelle,
                "x": (position % 3) * 16,
                "y": 3 + (position // 3) * 2,
                "width": 16,
                "height": 2,
                "view_mode": 0,
                "fields": [
                    {"type": 4, "name": "itemid.0", "value": itemids[cle]},
                    {"type": 0, "name": "value_size", "value": 12},
                    {"type": 0, "name": "desc_size", "value": 10},
                ],
            }
        )
    return widgets


def main() -> None:
    z = p.Zbx()
    z.login_wait(*p.get_admin_credentials())

    hotes = z.call("host.get", {"filter": {"host": p.HOST_NAME}})
    if not hotes:
        raise RuntimeError(f"Hôte '{p.HOST_NAME}' absent : exécuter provisioning.py d'abord.")
    hostid = hotes[0]["hostid"]

    itemids = {i["key_"]: i["itemid"] for i in z.call("item.get", {"hostids": hostid})}
    manquants = [cle for cle, _ in TUILES if cle not in itemids]
    if manquants:
        raise RuntimeError(f"Sondes manquantes : {', '.join(manquants)}")

    widgets = construire_widgets(hostid, itemids)
    existants = [
        d for d in z.call("dashboard.get", {"output": ["dashboardid", "name"]}) if d["name"] == NOM
    ]
    if existants:
        dashboardid = existants[0]["dashboardid"]
        detail = z.call(
            "dashboard.get",
            {"dashboardids": [dashboardid], "selectPages": "extend"},
        )[0]
        page = detail["pages"][0]
        z.call(
            "dashboard.update",
            {
                "dashboardid": dashboardid,
                "pages": [
                    {
                        "dashboard_pageid": page["dashboard_pageid"],
                        "name": page["name"],
                        "display_period": page["display_period"],
                        "widgets": widgets,
                    }
                ],
            },
        )
        print(f"Tableau de bord « {NOM} » mis à jour : dashboardid={dashboardid}")
        return

    resultat = z.call(
        "dashboard.create",
        {
            "name": NOM,
            "display_period": 30,
            "auto_start": 1,
            "pages": [{"name": "Vue d'ensemble", "widgets": widgets}],
        },
    )
    print(f"Tableau de bord « {NOM} » créé : dashboardid={resultat['dashboardids'][0]}")


if __name__ == "__main__":
    main()
