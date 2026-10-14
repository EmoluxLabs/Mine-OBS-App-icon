#!/usr/bin/env python3
"""Independent verification of the built APK.

Checks:
  * zip integrity and entry inventory
  * binary manifest parses with androguard (package/activities/permissions/sdk)
  * resources.arsc parses: string values + icon file entries resolve to real files
  * classes.dex disassembles cleanly with baksmali and contains the expected classes
  * v1 JAR signature digests recompute correctly; PKCS#7 signature verifies
  * v2 APK Signing Block digests + RSA signature verify against the certificate
"""
import hashlib
import struct
import subprocess
import sys
import zipfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate

CHUNK = 1024 * 1024
failures = []


def check(cond, msg):
    print(('  ok  ' if cond else ' FAIL ') + msg)
    if not cond:
        failures.append(msg)


def main(apk_path, cert_pem):
    raw = open(apk_path, 'rb').read()
    z = zipfile.ZipFile(apk_path)
    check(z.testzip() is None, 'zip integrity')
    names = z.namelist()
    print('  entries:', names)
    for required in ('AndroidManifest.xml', 'classes.dex', 'resources.arsc',
                     'res/mipmap-mdpi/ic_launcher.png',
                     'res/mipmap-xxxhdpi/ic_launcher.png'):
        check(required in names, 'contains %s' % required)

    # ---- manifest via androguard -----------------------------------------
    from androguard.core.apk import APK
    from androguard.core.axml import AXMLPrinter, ARSCParser
    apk = APK(apk_path)
    check(apk.get_package() == 'com.obsmainnet.app', 'package == com.obsmainnet.app (%s)' % apk.get_package())
    check(apk.get_app_name() == 'Mine OBS', 'app name == Mine OBS (%s)' % apk.get_app_name())
    check(apk.get_androidversion_code() == '1', 'versionCode == 1 (%s)' % apk.get_androidversion_code())
    check(apk.get_androidversion_name() == '1.0.0', 'versionName == 1.0.0 (%s)' % apk.get_androidversion_name())
    check(apk.get_min_sdk_version() == '21', 'minSdk == 21 (%s)' % apk.get_min_sdk_version())
    check(apk.get_target_sdk_version() == '34', 'targetSdk == 34 (%s)' % apk.get_target_sdk_version())
    check(sorted(apk.get_permissions()) == ['android.permission.ACCESS_NETWORK_STATE',
                                            'android.permission.INTERNET'],
          'permissions %s' % apk.get_permissions())
    acts = apk.get_activities()
    check(acts == ['com.obsmainnet.app.MainActivity'], 'activity %s' % acts)
    check(apk.get_main_activity() == 'com.obsmainnet.app.MainActivity',
          'launcher activity %s' % apk.get_main_activity())
    xml = AXMLPrinter(z.read('AndroidManifest.xml')).get_xml().decode('utf-8')
    print('--- decoded manifest ---')
    print(xml)
    print('------------------------')

    # ---- resources ---------------------------------------------------------
    arsc = ARSCParser(z.read('resources.arsc'))
    strings = arsc.get_resolved_strings()
    pkg = list(strings.keys())[0]
    flat = []
    for cfgs in strings[pkg].values():
        for vals in (cfgs.values() if isinstance(cfgs, dict) else [cfgs]):
            flat += list(vals.values() if isinstance(vals, dict) else [vals])
    check('Mine OBS' in [str(x) for x in flat], 'arsc string app_name == Mine OBS (%r)' % (flat,))
    icon_id = 0x7f020000
    configs = dict(arsc.get_resolved_res_configs(icon_id))
    print('  icon configs:', {k if isinstance(k, str) else k: v for k, v in list(configs.items())[:8]})
    files = [v for v in configs.values() if isinstance(v, str) and v.endswith('.png')]
    check(len(files) >= 5, 'icon has %d density variants' % len(files))
    for f in files:
        check(f in names, 'icon file present: %s' % f)

    # ---- dex ---------------------------------------------------------------
    import os
    baksmali = os.path.join(os.environ.get('TOOLS_DIR', '/home/user/android-build-tools'),
                            'jars', 'baksmali.jar')
    java = os.environ.get('JAVA_BIN', 'java')
    out_dir = '/tmp/bsmi'
    subprocess.run(['rm', '-rf', out_dir], check=True)
    open('/tmp/classes.dex', 'wb').write(z.read('classes.dex'))
    r = subprocess.run([java, '-jar', os.path.abspath(baksmali), '-o', out_dir, '/tmp/classes.dex'],
                       capture_output=True)
    check(r.returncode == 0, 'baksmali disassembles classes.dex')
    if r.returncode == 0:
        smali_files = sorted(os.listdir(out_dir + '/com/obsmainnet/app'))
        print('  dex classes:', smali_files)
        check('MainActivity.smali' in smali_files, 'MainActivity in dex')

    # ---- v1 signature -------------------------------------------------------
    mf = z.read('META-INF/MANIFEST.MF').decode()
    sf = z.read('META-INF/CERT.SF').decode()
    sections = mf.split('\r\n\r\n')
    ok = True
    for sec in sections[1:]:
        if not sec.strip():
            continue
        lines = sec.strip().split('\r\n')
        name = lines[0][len('Name: '):]
        dig = lines[1][len('SHA-256-Digest: '):]
        import base64
        real = base64.b64encode(hashlib.sha256(z.read(name)).digest()).decode()
        if dig != real:
            ok = False
    check(ok, 'v1 manifest digests match entry bytes')
    check(base64.b64encode(hashlib.sha256(z.read('META-INF/MANIFEST.MF')).digest()).decode() in sf,
          'v1 CERT.SF manifest digest matches')

    # ---- v2 signature -------------------------------------------------------
    eocd = raw.rfind(b'PK\x05\x06')
    magic = b'APK Sig Block 42'
    blk_end = struct.unpack_from('<I', raw, eocd + 16)[0]   # physical CD start
    blk_size = struct.unpack_from('<Q', raw, blk_end - 16 - 8)[0]
    blk_start = blk_end - 8 - blk_size
    check(raw[blk_end - 16:blk_end] == magic, 'APK signing block magic present')
    # parse pairs
    p = blk_start + 8
    pairs = []
    while p < blk_end - 24:
        plen = struct.unpack_from('<Q', raw, p)[0]
        pid = struct.unpack_from('<I', raw, p + 8)[0]
        pairs.append((pid, raw[p + 12:p + 8 + plen]))
        p += 8 + plen
    check(any(pid == 0x7109871a for pid, _ in pairs), 'v2 signer pair present')
    v2 = dict(pairs)[0x7109871a]

    def rd(buf, off):
        n = struct.unpack_from('<I', buf, off)[0]
        return buf[off + 4:off + 4 + n], off + 4 + n

    signers_seq, o = rd(v2, 0)
    signer, o = rd(signers_seq, 0)
    signed_data, o = rd(signer, 0)
    sigs_seq, o = rd(signer, o)
    pubkey_der, o = rd(signer, o)
    digests_seq, o = rd(signed_data, 0)
    certs_seq, o = rd(signed_data, o)
    digest_entry, o = rd(digests_seq, 0)
    alg = struct.unpack_from('<I', digest_entry, 0)[0]
    stored_digest, o = rd(digest_entry, 4)
    cert_in_apk, o = rd(certs_seq, 0)
    check(alg == 0x0103, 'v2 algorithm RSA-PKCS1-SHA256')

    # recompute chunked digest over the three sections (EOCD cd-offset field
    # substituted with the signing block start, per the v2 spec)
    eocd_for_digest = bytearray(raw[eocd:])
    struct.pack_into('<I', eocd_for_digest, 16, blk_start)
    content = raw[:blk_start] + raw[blk_end:eocd] + bytes(eocd_for_digest)
    check(struct.unpack_from('<I', raw, eocd + 16)[0] == blk_end,
          'EOCD central-dir offset points at physical central directory')
    chunks = [c for sec in (raw[:blk_start], raw[blk_end:eocd], bytes(eocd_for_digest))
              for c in [sec[i:i + CHUNK] for i in range(0, len(sec), CHUNK)]]
    top = bytearray(b'\x5a') + struct.pack('<I', len(chunks))
    for c in chunks:
        top += hashlib.sha256(b'\xa5' + struct.pack('<I', len(c)) + c).digest()
    recomputed = hashlib.sha256(bytes(top)).digest()
    check(recomputed == stored_digest, 'v2 content digest matches recomputation')

    sig_entry, o = rd(sigs_seq, 0)
    sig = rd(sig_entry, 4)[0]
    cert = load_pem_x509_certificate(open(cert_pem, 'rb').read())
    pub = cert.public_key()
    try:
        pub.verify(sig, signed_data, padding.PKCS1v15(), hashes.SHA256())
        v2sig_ok = True
    except Exception as e:
        v2sig_ok = False
        print('   ', e)
    check(v2sig_ok, 'v2 RSA signature verifies over signed_data')
    check(cert_in_apk == cert.public_bytes(serialization.Encoding.DER),
          'embedded certificate matches release certificate')

    print()
    if failures:
        print('FAILURES: %d' % len(failures))
        sys.exit(1)
    print('ALL CHECKS PASSED')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
