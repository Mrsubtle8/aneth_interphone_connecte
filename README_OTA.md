# OTA via GitHub — Interphone Pickles

Mise à jour du firmware du **Pico 2 W** depuis GitHub, **sans rebrancher la carte**.
Conçu léger pour la faible RAM du Pico (streaming, aucun fichier entier en mémoire).

## Principe

1. Le PC génère `manifest.json` : la liste des fichiers du firmware + leur SHA-256 + une `version`.
2. Le Pico lit `manifest.json` via `raw.githubusercontent.com`.
3. Il compare aux hashes stockés localement (`version.json`) et **ne télécharge que ce qui a changé**.
4. Chaque fichier est streamé vers la flash en blocs de 512 o, hash vérifié à la volée, écrit en `*.new`.
5. Une fois **tous** les fichiers vérifiés, swap atomique `*.new` → fichier final, puis `version.json` est mis à jour.
6. Si une seule vérification échoue, **rien n'est appliqué** (pas de Pico à moitié à jour).

Les secrets (Wi-Fi, Pushover) restent dans `config.json` **local** : ce fichier n'est jamais
dans le manifest, donc jamais écrasé par l'OTA.

## Fichiers

| Fichier | Où | Rôle |
|---|---|---|
| `ota.py` | Pico | Le moteur de mise à jour (streaming + SHA-256). |
| `manifest.json` | Dépôt (racine) | Liste des fichiers + hashes + version. Généré sur le PC. |
| `version.json` | Pico | État local : version installée + hash de chaque fichier. |
| `tools/gen_manifest.py` | PC | Génère `manifest.json`. |
| `config.json` | Pico uniquement | Secrets, jamais dans le manifest. |

## Publier une mise à jour (workflow)

```bash
# 1. modifier les modules (main.py, web.py, ...)
# 2. régénérer le manifest avec une nouvelle version
python3 tools/gen_manifest.py --version 0.2.0

# 3. committer + pousser sur la branche que lit le Pico (ex. main)
git add manifest.json *.py
git commit -m "Firmware 0.2.0"
git push
```

Le Pico récupérera la mise à jour au prochain `check_and_update()`.

## Intégration côté Pico (ex. dans `main.py`)

```python
import ota, config_store
cfg = config_store.load()
res = ota.check_and_update(cfg["ota_repo"],            # ex. "mrsubtle8/aneth_interphone_connecte"
                           cfg.get("ota_branch", "main"))
if res["error"]:
    print("OTA erreur:", res["error"])
elif res["updated"]:
    print("Mis à jour ->", res["version"], res["changed"])
    import machine
    machine.reset()        # redémarre sur le nouveau firmware
else:
    print("Déjà à jour:", res["version"])
```

À déclencher au boot et/ou via un bouton « Mettre à jour » dans l'interface web.

## Clés à ajouter dans `config.json` (sur le Pico)

```json
{
  "ota_repo": "mrsubtle8/aneth_interphone_connecte",
  "ota_branch": "main",
  "ota_path": ""
}
```

`ota_path` permet de ranger le firmware dans un sous-dossier du dépôt
(ex. `"firmware/"`) ; laisser `""` si tout est à la racine.

## Notes mémoire (Pico 2 W)

- Lecture réseau → flash par blocs de **512 o** (`CHUNK`), jamais le fichier complet en RAM.
- `gc.collect()` entre chaque fichier pour limiter la fragmentation (évite les `ENOMEM`).
- Le manifest est petit, il est le seul élément chargé entièrement en mémoire.
- Téléchargement étagé `*.new` → coupure de courant pendant l'OTA = ancien firmware intact.
