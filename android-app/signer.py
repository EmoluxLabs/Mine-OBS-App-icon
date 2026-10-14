"""APK signer: JAR (v1) signature + APK Signature Scheme v2 block, pure Python.

v1: MANIFEST.MF / CERT.SF / CERT.RSA (PKCS#7 detached, SHA-256, RSA)
v2: APK Signing Block with chunked (1 MB) SHA-256 content digests,
    RSASSA-PKCS1-v1_5 signatures (algorithm id 0x0103).
"""
import base64
import hashlib
import io
import struct
import zipfile
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

V2_RSA_PKCS1_SHA256 = 0x0103
APK_SIGNING_BLOCK_MAGIC = b'APK Sig Block 42'
CHUNK_SIZE = 1024 * 1024


# --------------------------------------------------------------------------
# key material
# --------------------------------------------------------------------------
def generate_keypair(common_name='Mine OBS'):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'OBS Mainnet'),
    ])
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(datetime(2049, 12, 31, tzinfo=timezone.utc))
            .sign(key, hashes.SHA256()))
    return key, cert


# --------------------------------------------------------------------------
# v1 (JAR) signing
# --------------------------------------------------------------------------
def _b64(d):
    return base64.b64encode(d).decode()


def _manifest_entry(name, data):
    digest = hashlib.sha256(data).digest()
    return 'Name: %s\r\nSHA-256-Digest: %s\r\n\r\n' % (name, _b64(digest))


def build_v1(entries, key, cert):
    """entries: ordered dict name -> uncompressed bytes. Returns dict of META-INF files."""
    manifest = 'Manifest-Version: 1.0\r\nCreated-By: 1.0 (Android)\r\n\r\n'
    for name, data in entries.items():
        manifest += _manifest_entry(name, data)
    manifest_b = manifest.encode()

    sf = ('Signature-Version: 1.0\r\n'
          'Created-By: 1.0 (Android)\r\n'
          'SHA-256-Digest-Manifest: %s\r\n'
          'X-Android-APK-Signed: 2\r\n\r\n' % _b64(hashlib.sha256(manifest_b).digest()))
    for name, data in entries.items():
        section = _manifest_entry(name, data).encode()
        sf += 'Name: %s\r\nSHA-256-Digest: %s\r\n\r\n' % (name, _b64(hashlib.sha256(section).digest()))
    sf_b = sf.encode()

    rsa_der = (pkcs7.PKCS7SignatureBuilder()
               .set_data(sf_b)
               .add_signer(cert, key, hashes.SHA256())
               .sign(serialization.Encoding.DER,
                     [pkcs7.PKCS7Options.Binary, pkcs7.PKCS7Options.DetachedSignature]))
    return {'META-INF/MANIFEST.MF': manifest_b,
            'META-INF/CERT.SF': sf_b,
            'META-INF/CERT.RSA': rsa_der}


def write_zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2025, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    return buf.getvalue()


# --------------------------------------------------------------------------
# v2 signing
# --------------------------------------------------------------------------
def _chunked_digest(*sections):
    """apksig-compatible chunked content digest: each zip section is chunked
    into 1 MB pieces *independently* (section boundaries are chunk
    boundaries), exactly like AOSP apksig / the Android package verifier."""
    digests = []
    for sec in sections:
        for i in range(0, len(sec), CHUNK_SIZE):
            c = sec[i:i + CHUNK_SIZE]
            digests.append(hashlib.sha256(b'\xa5' + struct.pack('<I', len(c)) + c).digest())
    top = b'\x5a' + struct.pack('<I', len(digests)) + b''.join(digests)
    return hashlib.sha256(top).digest()


def _lp(b):
    return struct.pack('<I', len(b)) + b


def _find_eocd(data):
    idx = data.rfind(b'PK\x05\x06')
    if idx < 0:
        raise ValueError('no EOCD')
    return idx


def sign_v2(apk_bytes, key, cert):
    eocd = _find_eocd(apk_bytes)
    cd_off = struct.unpack_from('<I', apk_bytes, eocd + 16)[0]
    # section 3 = EOCD with the central-directory offset field treated as the
    # signing-block offset (for the digest only)
    sec3 = bytearray(apk_bytes[eocd:])
    struct.pack_into('<I', sec3, 16, cd_off)
    digest = _chunked_digest(apk_bytes[:cd_off], apk_bytes[cd_off:eocd], bytes(sec3))

    cert_der = cert.public_bytes(serialization.Encoding.DER)
    pub_der = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo)

    digest_entry = struct.pack('<I', V2_RSA_PKCS1_SHA256) + _lp(digest)
    digests_seq = _lp(digest_entry)
    certs_seq = _lp(cert_der)
    signed_data = _lp(digests_seq) + _lp(certs_seq) + _lp(b'')   # + additional attributes
    signature = key.sign(signed_data, padding.PKCS1v15(), hashes.SHA256())
    signatures_seq = _lp(struct.pack('<I', V2_RSA_PKCS1_SHA256) + _lp(signature))
    signer = _lp(signed_data) + _lp(signatures_seq) + _lp(pub_der)
    # pair value = length-prefixed *sequence* of length-prefixed signers
    signers_seq = _lp(_lp(signer))

    pair_value = signers_seq
    pair = struct.pack('<Q', len(pair_value) + 4) + struct.pack('<I', 0x7109871a) + pair_value
    block_body = pair
    block_size = len(block_body) + 8 + 16
    block = struct.pack('<Q', block_size) + block_body + struct.pack('<Q', block_size) + APK_SIGNING_BLOCK_MAGIC
    signed = bytearray(apk_bytes[:cd_off] + block + apk_bytes[cd_off:])
    # EOCD must point at the *physical* central directory (after the block);
    # the "offset == signing block start" substitution is digest-only.
    struct.pack_into('<I', signed, eocd + len(block) + 16, cd_off + len(block))
    return bytes(signed)


def sign_apk(entries, key, cert):
    v1 = build_v1(entries, key, cert)
    all_entries = dict(entries)
    all_entries.update(v1)
    apk = write_zip(all_entries)
    return sign_v2(apk, key, cert)
