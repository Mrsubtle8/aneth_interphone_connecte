#!/usr/bin/env python3
"""Genere manifest.json a partir des fichiers du firmware (a lancer sur le PC).

Le manifest liste chaque fichier embarque avec son SHA-256. Le Pico compare ces
hashes a son etat local (version.json) et ne telecharge que ce qui a change.

Le firmware vit dans le dossier source/ : ce manifest est ecrit dans
source/manifest.json et le Pico le telecharge avec ota_path = "source/".

Usage :
    python3 tools/gen_manifest.py --version 1.2.0
    python3 tools/gen_manifest.py --version 1.2.0 --dir source main.py web.py

Sans liste de fichiers, prend tous les .py de --dir (defaut: source) sauf EXCLUDE.
Les secrets (config.py / config.json) ne doivent JAMAIS figurer dans le manifest.
"""
import argparse
import hashlib
import json
import os

# Ne JAMAIS inclure ces fichiers : secrets (config.py) ou etat local par
# appareil (config.json, version.json) ou le manifest lui-meme.
EXCLUDE = {"config.py", "config.json", "version.json", "manifest.json"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(4096), b""):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True, help="Version de cette release, ex 1.2.0")
    p.add_argument("--dir", default="source", help="Dossier du firmware (defaut: source)")
    p.add_argument("--out", help="Chemin du manifest (defaut: <dir>/manifest.json)")
    p.add_argument("files", nargs="*", help="Fichiers a inclure (defaut: tous les .py du dossier)")
    args = p.parse_args()

    out = args.out or os.path.join(args.dir, "manifest.json")

    # Grave la version dans le code (affichage de la version installee).
    with open(os.path.join(args.dir, "fwversion.py"), "w") as f:
        f.write("# Version du firmware. Genere automatiquement par "
                "tools/gen_manifest.py.\n")
        f.write("# Sert a afficher la version reellement installee "
                "(independamment de l'OTA).\n")
        f.write('VERSION = "%s"\n' % args.version)

    if args.files:
        candidates = args.files
    else:
        candidates = sorted(n for n in os.listdir(args.dir) if n.endswith(".py"))

    files = {}
    for name in candidates:
        if name in EXCLUDE:
            print("Ignore (exclu) :", name)
            continue
        full = os.path.join(args.dir, name)
        if not os.path.exists(full):
            print("Absent, ignore :", name)
            continue
        files[name] = sha256(full)
        print("  %s  %s" % (files[name][:12], name))

    manifest = {"version": args.version, "files": files}
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print("\n%s ecrit (version %s, %d fichiers)" % (out, args.version, len(files)))


if __name__ == "__main__":
    main()
