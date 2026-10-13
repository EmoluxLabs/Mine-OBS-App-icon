#!/usr/bin/env python3
"""Build the "Mine OBS" WebView wrapper APK.

Pipeline (no Android SDK required):
  1. resize the repo logo (exact pixels, Lanczos) into launcher icon densities
  2. assemble smali sources -> classes.dex            (smali.jar, pure Java)
  3. compile AndroidManifest.xml -> binary AXML       (axml.py)
  4. compile resources.arsc                           (arsc.py)
  5. zip + sign (JAR v1 + APK Signature Scheme v2)    (signer.py)

Usage:  python3 build.py [--tools DIR] [--out FILE]
"""
import argparse
import os
import shutil
import subprocess
import sys

from PIL import Image

import axml as A
import arsc as R
import signer

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

APP_NAME = 'Mine OBS'
PACKAGE = 'com.obsmainnet.app'
VERSION_NAME = '1.0.0'
VERSION_CODE = 1
HOME_URL = 'https://app.obsmainnet.us.ci'
ICON_SRC = os.path.join(REPO, 'obsidian-app-icon-1024.png')

MIN_SDK = 21
TARGET_SDK = 34
THEME = 0x0103012c          # android:style/Theme.DeviceDefault.Light.NoActionBar

# framework attribute resource ids (from android.jar R$attr)
ATTR_IDS = {
    'theme': 0x01010000,
    'label': 0x01010001,
    'icon': 0x01010002,
    'name': 0x01010003,
    'exported': 0x01010010,
    'launchMode': 0x0101001d,
    'configChanges': 0x0101001f,
    'minSdkVersion': 0x0101020c,
    'versionCode': 0x0101021b,
    'versionName': 0x0101021c,
    'windowSoftInputMode': 0x0101022b,
    'targetSdkVersion': 0x01010270,
    'allowBackup': 0x01010280,
    'hardwareAccelerated': 0x010102d3,
}
ANDROID_NS = 'http://schemas.android.com/apk/res/android'

DENSITIES = [('mdpi', 160, 48), ('hdpi', 240, 72), ('xhdpi', 320, 96),
             ('xxhdpi', 480, 144), ('xxxhdpi', 640, 192)]

STRING_DATA = -2            # sentinel: data == raw string index


def make_icons(workdir):
    img = Image.open(ICON_SRC).convert('RGBA')
    paths = {}
    for tag, dpi, size in DENSITIES:
        out_dir = os.path.join(workdir, 'res', 'mipmap-%s' % tag)
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, 'ic_launcher.png')
        if (img.width, img.height) == (size, size):
            resized = img
        else:
            resized = img.resize((size, size), Image.LANCZOS)
        resized.save(out, format='PNG')
        paths[tag] = out
    return paths


def assemble_dex(tools, workdir):
    java = os.environ.get('JAVA_BIN')
    if not java:
        try:
            import jdk4py
            java = str(jdk4py.JAVA)
        except ImportError:
            java = 'java'
    smali_jar = os.path.join(tools, 'jars', 'smali.jar')
    out = os.path.join(workdir, 'classes.dex')
    cmd = [java, '-jar', smali_jar, os.path.join(HERE, 'smali'),
           '-a', '21', '-o', out]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def build_manifest():
    w = A.AxmlWriter()
    for k, v in ATTR_IDS.items():
        w.set_attr_id(k, v)
    AND = ANDROID_NS

    def s(raw):
        return (None, None, raw, A.TYPE_STRING, STRING_DATA)

    def ans(raw):
        return (AND, 'name', raw, A.TYPE_STRING, STRING_DATA)

    def aint(name, val):
        return (AND, name, None, A.TYPE_INT_DEC, val)

    def abool(name, val):
        return (AND, name, None, A.TYPE_INT_BOOLEAN, 1 if val else 0)

    def aref(name, resid):
        return (AND, name, None, A.TYPE_REFERENCE, resid)

    w.start_namespace('android', AND)
    w.start_element('manifest', [
        (None, 'package', PACKAGE, A.TYPE_STRING, STRING_DATA),
        aint('versionCode', VERSION_CODE),
        (AND, 'versionName', VERSION_NAME, A.TYPE_STRING, STRING_DATA),
    ])
    w.start_element('uses-sdk', [
        aint('minSdkVersion', MIN_SDK),
        aint('targetSdkVersion', TARGET_SDK),
    ])
    w.end_element('uses-sdk')
    for perm in ('android.permission.INTERNET', 'android.permission.ACCESS_NETWORK_STATE'):
        w.start_element('uses-permission', [ans(perm)])
        w.end_element('uses-permission')
    w.start_element('application', [
        aref('theme', THEME),
        aref('label', 0x7f010000),       # @string/app_name
        aref('icon', 0x7f020000),        # @mipmap/ic_launcher
        abool('allowBackup', True),
        abool('hardwareAccelerated', True),
    ])
    w.start_element('activity', [
        (AND, 'name', PACKAGE + '.MainActivity', A.TYPE_STRING, STRING_DATA),
        abool('exported', True),
        aint('launchMode', 2),          # singleTask
        aint('configChanges', 0x0FB0),
        aint('windowSoftInputMode', 0x10),   # adjustResize
    ])
    w.start_element('intent-filter', [])
    w.start_element('action', [ans('android.intent.action.MAIN')])
    w.end_element('action')
    w.start_element('category', [ans('android.intent.category.LAUNCHER')])
    w.end_element('category')
    w.end_element('intent-filter')
    w.end_element('activity')
    w.end_element('application')
    w.end_element('manifest')
    w.end_namespace('android', AND)
    return w.build()


def build_resources(icon_paths):
    t = R.ResourceTable(0x7f, PACKAGE)
    strings = t.add_type('string')
    cfg = R.Config(0)
    cfg.put('app_name', R.ResValue('string', APP_NAME))
    strings.add_config(cfg)

    mips = t.add_type('mipmap')
    default = R.Config(0)
    default.put('ic_launcher', R.ResValue('file', 'res/mipmap-xxxhdpi/ic_launcher.png'))
    mips.add_config(default)
    for tag, dpi, _ in DENSITIES:
        c = R.Config(dpi)
        c.put('ic_launcher', R.ResValue('file', 'res/mipmap-%s/ic_launcher.png' % tag))
        mips.add_config(c)
    assert t.res_id('string', 'app_name') == 0x7f010000
    assert t.res_id('mipmap', 'ic_launcher') == 0x7f020000
    return t.build()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tools', default=os.path.join(REPO, '..', 'android-build-tools'))
    ap.add_argument('--out', default=os.path.join(HERE, 'dist',
                                                   'Mine-OBS-v%s.apk' % VERSION_NAME))
    ap.add_argument('--keydir', default=os.path.join(REPO, '..', 'mine-obs-signing'))
    args = ap.parse_args()

    workdir = os.path.join(HERE, 'build')
    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir, exist_ok=True)

    print('* resizing launcher icons from repo logo (lossless Lanczos downscale)')
    icon_paths = make_icons(workdir)

    print('* assembling classes.dex from smali')
    dex = assemble_dex(os.path.abspath(args.tools), workdir)

    print('* compiling AndroidManifest.xml (binary AXML) and resources.arsc')
    manifest = build_manifest()
    resources = build_resources(icon_paths)

    entries = {'AndroidManifest.xml': manifest,
               'classes.dex': open(dex, 'rb').read(),
               'resources.arsc': resources}
    for tag, dpi, _ in DENSITIES:
        p = icon_paths[tag]
        entries['res/mipmap-%s/ic_launcher.png' % tag] = open(p, 'rb').read()

    keydir = os.path.abspath(args.keydir)
    os.makedirs(keydir, exist_ok=True)
    key_pem = os.path.join(keydir, 'release-key.pem')
    cert_pem = os.path.join(keydir, 'release-cert.pem')
    if os.path.exists(key_pem):
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.x509 import load_pem_x509_certificate
        key = load_pem_private_key(open(key_pem, 'rb').read(), password=None)
        cert = load_pem_x509_certificate(open(cert_pem, 'rb').read())
        print('* reusing existing signing key from %s' % keydir)
    else:
        key, cert = signer.generate_keypair(APP_NAME)
        from cryptography.hazmat.primitives import serialization
        open(key_pem, 'wb').write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        open(cert_pem, 'wb').write(cert.public_bytes(serialization.Encoding.PEM))
        print('* generated new signing key in %s' % keydir)

    print('* packaging + signing (v1 JAR + v2 APK Signature Scheme)')
    apk = signer.sign_apk(entries, key, cert)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'wb') as f:
        f.write(apk)
    print('* wrote %s (%d bytes)' % (args.out, len(apk)))


if __name__ == '__main__':
    main()
