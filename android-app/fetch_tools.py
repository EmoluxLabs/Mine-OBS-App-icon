#!/usr/bin/env python3
"""Download the (public, mirrored) Java tools needed by build.py.

smali/baksmali 2.0.6 are fetched from the TOSPlus/TPS GitHub mirror of the
standard smali releases via the GitHub blobs API (no release-asset CDN needed).
"""
import base64
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', 'android-build-tools')

SOURCES = [
    ('TOSPlus/TPS', 'build/tools/apktool/smali-2.0.6.jar', 'jars/smali.jar'),
    ('TOSPlus/TPS', 'build/tools/apktool/baksmali-2.0.6.jar', 'jars/baksmali.jar'),
]


def api(url):
    req = urllib.request.Request(url, headers={
        'Authorization': 'Bearer ' + os.environ.get('GH_TOKEN', ''),
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'mine-obs-build'})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())


def main():
    for repo, path, out in SOURCES:
        dest = os.path.join(TOOLS, out)
        if os.path.exists(dest):
            print('have', dest)
            continue
        meta = api('https://api.github.com/repos/%s/contents/%s' % (repo, path))
        blob = api('https://api.github.com/repos/%s/git/blobs/%s' % (repo, meta['sha']))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as f:
            f.write(base64.b64decode(blob['content']))
        print('fetched', dest, os.path.getsize(dest), 'bytes')


if __name__ == '__main__':
    main()
