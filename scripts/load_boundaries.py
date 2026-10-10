#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# load_boundaries.py
#
# Builds RapidPro-format admin boundary GeoJSON for the EAC countries from the
# HDX (Humanitarian Data Exchange) datasets, which are the maintained, up-to-date
# source (e.g. Burundi's 2023 reorganisation: 17 -> 5 provinces).
#
# Sources (both HDX-hosted):
#   * COD-AB      - the official Common Operational Datasets (single geojson zip
#                   per country; streamed with HTTP range requests so we don't
#                   download hundreds of MB of admin3/4 geometry).
#   * geoBoundaries - used only where a COD has no GeoJSON resource (Tanzania,
#                   Rwanda); per-level simplified GeoJSON.
#
# Output: fixtures/boundaries/<ISO>/R<relid>admin<L>_simplified.json in the exact
# format `manage.py import_geojson` expects
# (properties: osm_id, name, name_en, parent_id, + geometry).
#
# Import (inside the rapidpro container, parent->child order):
#   docker compose cp fixtures/boundaries rapidpro:/tmp/boundaries
#   docker compose exec rapidpro sh -c 'python manage.py import_geojson /tmp/boundaries/<ISO>/*.json'
#
# Usage:  python3 scripts/load_boundaries.py [KEN BDI COD ...]
# ---------------------------------------------------------------------------
import io
import json
import os
import re
import sys
import zipfile

import hashlib

import requests
import shapely
from shapely.geometry import mapping, shape
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTROOT = os.path.join(HERE, "..", "fixtures", "boundaries")

SIMPLIFY = 0.01      # degrees (~1km) topology-preserving simplification
PRECISION = 4        # coordinate decimal places
MAX_LEVEL = 2

COUNTRIES = {
    "KEN": {"relid": 192798, "cod": "cod-ab-ken"},
    "UGA": {"relid": 192796, "cod": "cod-ab-uga"},
    "BDI": {"relid": 195269, "cod": "cod-ab-bdi"},
    "SSD": {"relid": 1656678, "cod": "cod-ab-ssd"},
    "COD": {"relid": 192795, "cod": "cod-ab-cod"},
    "SOM": {"relid": 192799, "cod": "cod-ab-som"},
    # no GeoJSON resource in the COD -> use the HDX-hosted geoBoundaries dataset
    "TZA": {"relid": 195270, "gb": "geoboundaries-admin-boundaries-for-united-republic-of-tanzania"},
    "RWA": {"relid": 171496, "gb": "geoboundaries-admin-boundaries-for-rwanda"},
}


class HttpRangeFile(io.RawIOBase):
    """Minimal seekable file over HTTP range requests (for zipfile)."""

    def __init__(self, url):
        self.pos = 0
        # keep the ORIGINAL url: HDX 302s to a pre-signed S3 url which rejects our
        # Range requests (403); ranged requests on the HDX url work (206).
        self.url = url
        r = requests.head(url, allow_redirects=True, timeout=60)
        r.raise_for_status()
        self.size = int(r.headers["Content-Length"])

    def seekable(self):
        return True

    def readable(self):
        return True

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else (self.pos + offset if whence == 1 else self.size + offset)
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n <= 0 or self.pos >= self.size:
            return b""
        end = min(self.pos + n, self.size) - 1
        r = requests.get(self.url, headers={"Range": "bytes=%d-%d" % (self.pos, end)}, timeout=180)
        r.raise_for_status()
        self.pos += len(r.content)
        return r.content


def hdx_resources(pid):
    r = requests.get("https://data.humdata.org/api/3/action/package_show", params={"id": pid}, timeout=60)
    r.raise_for_status()
    return r.json()["result"].get("resources", [])


def fetch_json(url):
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return r.json()


def levels_for(cfg):
    """Return {level: FeatureCollection} for a country (0..N)."""
    out = {}
    if cfg.get("cod"):
        res = [r for r in hdx_resources(cfg["cod"]) if (r.get("format") or "").upper() == "GEOJSON"]
        if res:
            zf = zipfile.ZipFile(HttpRangeFile(res[0]["url"]))
            members = [i.filename for i in zf.infolist()
                       if i.filename.lower().endswith(".geojson") and "_admin" in i.filename.lower()]
            for lvl in range(0, MAX_LEVEL + 1):
                m = next((n for n in members if n.lower().endswith("_admin%d.geojson" % lvl)), None)
                if m:
                    out[lvl] = json.loads(zf.read(m))
            if out:
                return out
    if cfg.get("gb"):
        for r in hdx_resources(cfg["gb"]):
            mt = re.search(r"-ADM(\d)_simplified\.geojson$", r["url"])
            if mt:
                out[int(mt.group(1))] = fetch_json(r["url"])
    return out


def _round(obj, nd):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, (list, tuple)):
        return [_round(v, nd) for v in obj]
    return obj


def _short(s):
    """osm_id column is varchar(15); geoBoundaries shapeIDs overflow it -> hash."""
    if not s or len(s) <= 15:
        return s
    return "R" + hashlib.sha1(s.encode()).hexdigest()[:13]


def _parts(props, level):
    """(id, name, name_en, explicit_parent) for COD or geoBoundaries schemas."""
    if "adm%d_pcode" % level in props:
        return (_short(props.get("adm%d_pcode" % level)),
                props.get("adm%d_name" % level) or "",
                props.get("adm%d_name1" % level) or props.get("adm%d_name" % level) or "",
                _short(props.get("adm%d_pcode" % (level - 1))) if level else None)
    if "shapeName" in props:  # geoBoundaries
        sid = props.get("shapeID") or props.get("shapeISO") or props.get("shapeName")
        return (_short(sid), props.get("shapeName") or "", props.get("shapeName") or "", None)
    return (None, "", "", None)


def build_country(iso3, cfg):
    levels = levels_for(cfg)
    if not levels:
        print("  %s: no data" % iso3)
        return
    outdir = os.path.join(OUTROOT, iso3)
    os.makedirs(outdir, exist_ok=True)
    prev = []          # list of (id, shapely geometry) from the level above
    tree = None
    summary = []
    for lvl in sorted(levels):
        feats = []
        here = []
        for feat in levels[lvl].get("features", []):
            geom = feat.get("geometry")
            if not geom or not geom.get("coordinates"):
                continue
            gid, name, name_en, parent = _parts(feat.get("properties", {}), lvl)
            if not gid:
                continue
            try:
                g = shapely.make_valid(shape(geom))
                if g.is_empty:
                    continue
                if lvl > 0 and parent is None and tree is not None:
                    for pt in (g.representative_point(), g.centroid):
                        for i in tree.query(pt):
                            if prev[i][1].contains(pt):
                                parent = prev[i][0]
                                break
                        if parent:
                            break
                    if parent is None:  # simplified geometry slivers -> nearest
                        try:
                            parent = prev[int(tree.nearest(g.centroid))][0]
                        except Exception:
                            pass
                g = g.simplify(SIMPLIFY, preserve_topology=True)
                if g.is_empty:
                    continue
            except Exception:
                continue
            feats.append({"type": "Feature",
                          "properties": {"osm_id": gid, "name": name, "name_en": name_en, "parent_id": parent},
                          "geometry": _round(mapping(g), PRECISION)})
            here.append((gid, g))
        if not feats:
            continue
        path = os.path.join(outdir, "R%dadmin%d_simplified.json" % (cfg["relid"], lvl))
        with open(path, "w") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"))
        summary.append("a%d=%d" % (lvl, len(feats)))
        prev = here
        tree = STRtree([g for _, g in prev]) if prev else None
    print("  %s: %s -> fixtures/boundaries/%s" % (iso3, " ".join(summary), iso3))


def main(argv):
    for iso3 in (argv or list(COUNTRIES)):
        cfg = COUNTRIES.get(iso3)
        if not cfg:
            print("skip %s" % iso3)
            continue
        print("== %s" % iso3)
        build_country(iso3, cfg)


if __name__ == "__main__":
    main(sys.argv[1:])
