# Interphone Pickles — Firmware & mises à jour OTA

Firmware MicroPython pour **Pico 2 W** : détection de sonnerie, notifications
Pushover, ouverture de porte, **interface web de configuration** et
**mise à jour du code depuis GitHub** (sans rebrancher la carte).

## Workflow

```
  Claude Code / PC                GitHub (branche main)              Pico 2 W
 ┌────────────────┐   git push   ┌──────────────────────┐  bouton   ┌──────────┐
 │ éditer source/ │ ───────────▶ │ source/*.py          │   web     │ rapatrie │
 │ gen_manifest   │              │ source/manifest.json │ ────────▶ │ + reboot │
 └────────────────┘              └──────────────────────┘           └──────────┘
```

1. On développe dans **`source/`** (ici, sur Claude Code).
2. On régénère **`source/manifest.json`** avec une nouvelle `version`.
3. On pousse sur **`main`** → c'est le firmware « officiel ».
4. Sur la page web du Pico, le bouton **« Mettre à jour le firmware »** compare
   la `version` distante à la version installée et **rapatrie uniquement les
   fichiers modifiés**, puis redémarre.

## Conçu léger pour le Pico 2 W

- Téléchargement **en streaming** (blocs de 512 o) directement vers la flash :
  aucun fichier entier en RAM → évite les `ENOMEM`.
- SHA-256 vérifié **à la volée** ; on ne télécharge que les fichiers dont le
  hash a changé.
- Téléchargement **étagé** (`*.new`) puis swap : une coupure de courant pendant
  la mise à jour laisse l'ancien firmware intact.
- `gc.collect()` entre chaque fichier.

## Fichiers

| Fichier | Où | Rôle |
|---|---|---|
| `source/main.py` | Pico | Boucle principale. |
| `source/web.py` | Pico | Interface web (config + actions + bouton update). |
| `source/config_store.py` | Pico | Charge/sauve `config.json` (tous les paramètres). |
| `source/ota.py` | Pico | Moteur OTA (streaming + SHA-256). |
| `source/relay.py`, `interphone.py`, `pushover.py`, `wifi_manager.py` | Pico | Modules métier. |
| `source/config.py` | Pico | Valeurs d'usine (jamais dans l'OTA). |
| `source/manifest.json` | Dépôt | Liste fichiers + hashes + version. |
| `config.json` | Pico uniquement | Config sauvegardée (secrets). `.gitignore`, jamais dans l'OTA. |
| `version.json` | Pico uniquement | Version installée + hashes. Créé par l'OTA. |
| `tools/gen_manifest.py` | PC | Génère `source/manifest.json`. |

## Publier une mise à jour

```bash
# 1. éditer les modules dans source/
# 2. régénérer le manifest avec une nouvelle version
python3 tools/gen_manifest.py --version 1.1.0

# 3. committer + pousser sur main
git add source/ && git commit -m "Firmware 1.1.0" && git push origin main
```

Puis, sur la page web du Pico → **« Mettre à jour le firmware »**.

## Configuration (page web)

Tout est éditable et **sauvegardé dans `config.json`** : Wi-Fi (nom + mot de
passe), Pushover (clés, message, sonnerie, priorité, retry/expire), relais
(durée d'impulsion, active-low), anti-double détection, dépôt/branche OTA, et
le mot de passe admin. Après « Enregistrer », le Pico redémarre pour appliquer.

Au **premier démarrage** (pas de `config.json`), les valeurs d'usine de
`config.py` sont utilisées ; dès la première sauvegarde, `config.json` prend le
relais et `config.py` n'est plus que le filet de secours.

## ⚠️ Sécurité des secrets

`source/config.py` contient actuellement le **vrai mot de passe Wi-Fi et les
clés Pushover en clair**, et il est poussé sur GitHub. C'est exclu de l'OTA,
mais l'exposition dans l'historique git reste un risque. Recommandé :
- régénérer le token Pushover et changer le mot de passe Wi-Fi exposés ;
- à terme, vider les secrets de `config.py` (placeholders) et ne garder les
  vraies valeurs que dans `config.json` (local, gitignoré).

## Fiabilité (depuis la 1.7.0)

Objectif : ne plus jamais avoir à débrancher le Pico.

- **Watchdog matériel** : si le programme se fige plus de ~8-16 s, le Pico redémarre seul.
- **Timeout de 4 s** sur toutes les requêtes (Telegram, Pushover) : plus de blocage infini.
- **Surveillance réseau** : plus aucune réponse pendant 5 min → relance du Wi-Fi ; 10 min → redémarrage.
  Pendant une vraie panne internet, le délai double à chaque fois (10, 20, 40, 80 min, puis 2 h max).
- **Redémarrage préventif chaque nuit** à 4 h (heure de Paris, réglable dans la page, `-1` = jamais).
- **Erreur imprévue** → notée dans `crash.log` ; si elle se répète, redémarrage propre.
- **Message Telegram silencieux « en ligne »** après chaque redémarrage imprévu, avec la cause
  (sauf la maintenance de nuit). La cause est aussi visible sur la page web et dans 📊 État.
- **Surveillance externe optionnelle** : une URL healthchecks.io (gratuit) dans la page → tu es
  alerté si le Pico se tait.

### Travailler en USB (Thonny) avec le watchdog
Un **Ctrl-C** (bouton Stop de Thonny) passe le Pico en **mode maintenance** : le watchdog reste
nourri, tu peux copier des fichiers sans redémarrage intempestif. Pour tout couper, mets
« Watchdog » sur `non` dans la page, enregistre, puis redémarre.
