"""Minimal Java .class parser: enough to read static int constants and method/field
descriptors from android.jar so we can validate smali references and read framework
resource ids (R$attr / R$style)."""
import struct
import zipfile


class ClassFile:
    def __init__(self, data):
        self.data = data
        assert data[:4] == b'\xca\xfe\xba\xbe', 'not a class file'
        self.minor, self.major, cp_count = struct.unpack('>HHH', data[4:10])
        self.cp = [None]
        i = 1
        p = 10
        while i < cp_count:
            tag = data[p]
            p += 1
            if tag == 1:
                ln = struct.unpack('>H', data[p:p + 2])[0]
                p += 2
                self.cp.append(('Utf8', data[p:p + ln].decode('utf-8', 'replace')))
                p += ln
            elif tag in (7, 8, 16, 19, 20):
                self.cp.append((tag, struct.unpack('>H', data[p:p + 2])[0]))
                p += 2
            elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
                self.cp.append((tag, data[p:p + 4]))
                p += 4
            elif tag in (5, 6):
                self.cp.append((tag, data[p:p + 8]))
                p += 8
                self.cp.append(None)
                i += 1
            elif tag == 15:
                self.cp.append((tag, data[p:p + 3]))
                p += 3
            else:
                raise ValueError('unknown cp tag %d' % tag)
            i += 1
        self.access, self.this_idx, self.super_idx = struct.unpack('>HHH', data[p:p + 6])
        p += 6
        niface = struct.unpack('>H', data[p:p + 2])[0]
        p += 2 + 2 * niface
        self.fields, p = self._members(p)
        self.methods, p = self._members(p)

    # --- helpers -----------------------------------------------------------
    def _skip_cp(self):
        data = self.data
        cp_count = struct.unpack('>H', data[8:10])[0]
        p = 10
        i = 1
        while i < cp_count:
            tag = data[p]
            p += 1
            if tag == 1:
                ln = struct.unpack('>H', data[p:p + 2])[0]
                p += 2 + ln
            elif tag in (7, 8, 16, 19, 20):
                p += 2
            elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
                p += 4
            elif tag in (5, 6):
                p += 8
                i += 1
            elif tag == 15:
                p += 3
            i += 1
        return p

    def _str(self, idx):
        e = self.cp[idx]
        return e[1] if e and e[0] == 'Utf8' else None

    def _members(self, p):
        n = struct.unpack('>H', self.data[p:p + 2])[0]
        p += 2
        out = []
        for _ in range(n):
            acc, nidx, didx, attrs = struct.unpack('>HHHH', self.data[p:p + 8])
            p += 8
            attr_bodies = []
            for _a in range(attrs):
                aname, alen = struct.unpack('>HI', self.data[p:p + 6])
                p += 6
                attr_bodies.append((self._str(aname), self.data[p:p + alen]))
                p += alen
            out.append((acc, self._str(nidx), self._str(didx), attr_bodies))
        return out, p

    # --- public API ---------------------------------------------------------
    def static_ints(self):
        """name -> value for fields carrying a ConstantValue int attribute."""
        res = {}
        for acc, name, desc, attrs in self.fields:
            for aname, body in attrs:
                if aname == 'ConstantValue':
                    vidx = struct.unpack('>H', body[0:2])[0]
                    e = self.cp[vidx]
                    if e and e[0] == 3:
                        res[name] = struct.unpack('>i', e[1])[0]
        return res

    def method_descriptors(self):
        return [(n, d) for (acc, n, d, _) in self.methods]

    def field_descriptors(self):
        return [(n, d) for (acc, n, d, _) in self.fields]


def load(jar, cls):
    with zipfile.ZipFile(jar) as z:
        return ClassFile(z.read(cls + '.class'))
