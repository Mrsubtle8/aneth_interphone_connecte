#!/usr/bin/env python3
"""Genere manifest.json a partir des fichiers du firmware (a lancer sur le PC).

Le manifest liste chaque fichier embarque avec son SHA-256. Le Pico compare ces
hashes a son etat local (version.json) et ne telecharge que ce qui a change.

Usage :
    python3 tools/gen_manifest.py --version 1.2.0
    python3 tools/gen_manifest.py --version 1.2.0 main.py web.py relay.py ota.py

Sans liste de fichiers, prend FIRMWARE_FILES ci-dessous.
Les secrets (config.json) ne doivent JAMAIS figurer dans le manifest.
"""
import argparse
import hashlib
import json
import os

# Fichiers du firmware geres par l'OTA (a adapter quand tu ajoutes tes modules).
FIRMWARE_FILES = [
    "main.py",
    "ota.py",
    "web.py",
    "relay.py",
    "pushover.py",
    "interphone.py",
    "wifi_manager.py",
    "config_store.py",
]

# Ne JAMAIS inclure ces fichiers (secrets / etat local par appareil).
EXCLUDE = {"config.json", "version.json", "manifest.json"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(4096), b""):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True, help="Version de cette release, ex 1.2.0")
    p.add_argument("--out", default="manifest.json")
    p.add_argument("files", nargs="*", help="Fichiers a inclure (defaut: FIRMWARE_FILES)")
    args = p.parse_args()

    candidates = args.files or FIRMWARE_FILES
    files = {}
    for name in candidates:
        if name in EXCLUDE:
            print("Ignore (exclu) :", name)
            continue
        if not os.path.exists(name):
            print("Absent, ignore :", name)
            continue
        files[name] = sha256(name)
        print("  %s  %s" % (files[name][:12], name))

    manifest = {"version": args.version, "files": files}
    with open(args.out, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print("\n%s ecrit (version %s, %d fichiers)" % (args.out, args.version, len(files)))


if __name__ == "__main__":
    main()
