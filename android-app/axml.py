"""Writer for the Android binary XML (AXML) format used by AndroidManifest.xml.

Produces output structurally identical to aapt/aapt2: a RES_XML chunk containing a
string pool (UTF-8), a resource-id map and the namespace/element event stream.
Attribute strings are placed first in the pool (sorted by framework resource id)
so the resource map is a plain prefix array, exactly like aapt output.
"""
import struct

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_NAMESPACE_TYPE = 0x0100
RES_XML_END_NAMESPACE_TYPE = 0x0101
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
RES_XML_RESOURCE_MAP_TYPE = 0x0180

# Res_value data types
TYPE_REFERENCE = 0x01
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12

NO_STRING = 0xFFFFFFFF
STRING_DATA = -2        # sentinel: typed value data == raw string pool index


class StringPool:
    """UTF-8 resource string pool chunk."""

    def __init__(self):
        self.strings = []
        self.index = {}

    def add(self, s):
        if s not in self.index:
            self.index[s] = len(self.strings)
            self.strings.append(s)
        return self.index[s]

    def build(self):
        count = len(self.strings)
        offsets = []
        blob = bytearray()
        for s in self.strings:
            offsets.append(len(blob))
            raw = s.encode('utf-8')
            nchars = len(s)
            if nchars > 0x7F:
                blob += bytes([0x80 | (nchars >> 8), nchars & 0xFF])
            else:
                blob += bytes([nchars])
            nbytes = len(raw)
            if nbytes > 0x7F:
                blob += bytes([0x80 | (nbytes >> 8), nbytes & 0xFF])
            else:
                blob += bytes([nbytes])
            blob += raw + b'\x00'
        while len(blob) % 4:
            blob += b'\x00'
        header_size = 28
        strings_start = header_size + 4 * count
        chunk_size = strings_start + len(blob)
        out = bytearray(struct.pack('<HHIIIIII', RES_STRING_POOL_TYPE, header_size,
                                    chunk_size, count, 0, 0x00000100,
                                    strings_start, 0))
        if count:
            out += struct.pack('<%dI' % count, *offsets)
        out += bytes(blob)
        return bytes(out)


class _Elem:
    def __init__(self, name, attrs):
        self.name = name
        # attrs: list of (ns_uri_or_None, attr_name, raw_str_or_None, dtype, data)
        self.attrs = attrs


class AxmlWriter:
    """Builds a compiled AndroidManifest-style binary XML document."""

    def __init__(self):
        self.attr_ids = {}        # attr name -> framework resource id
        self.events = []
        self.other_strings = []
        self._seen = set()

    def set_attr_id(self, name, res_id):
        self.attr_ids[name] = res_id

    def _other(self, s):
        if s not in self._seen:
            self._seen.add(s)
            self.other_strings.append(s)

    def start_namespace(self, prefix, uri):
        self._other(prefix)
        self._other(uri)
        self.events.append(('ns_start', prefix, uri))

    def end_namespace(self, prefix, uri):
        self.events.append(('ns_end', prefix, uri))

    def start_element(self, name, attrs):
        self._other(name)
        for ns_uri, aname, raw, dtype, data in attrs:
            if aname not in self.attr_ids:
                self._other(aname)
            if ns_uri is not None:
                self._other(ns_uri)
            if raw is not None:
                self._other(raw)
        self.events.append(('start', _Elem(name, attrs)))

    def end_element(self, name):
        self.events.append(('end', name))

    # -- emission ----------------------------------------------------------
    def build(self):
        pool = StringPool()
        attr_names = sorted(self.attr_ids, key=lambda n: self.attr_ids[n])
        for n in attr_names:
            pool.add(n)
        for s in self.other_strings:
            pool.add(s)

        body = bytearray()
        for ev in self.events:
            kind = ev[0]
            if kind == 'ns_start':
                _, prefix, uri = ev
                body += struct.pack('<HHIIIII', RES_XML_START_NAMESPACE_TYPE, 16, 24,
                                    1, NO_STRING, pool.add(prefix), pool.add(uri))
            elif kind == 'ns_end':
                _, prefix, uri = ev
                body += struct.pack('<HHIIIII', RES_XML_END_NAMESPACE_TYPE, 16, 24,
                                    1, NO_STRING, pool.add(prefix), pool.add(uri))
            elif kind == 'start':
                elem = ev[1]
                attrs = sorted(elem.attrs, key=lambda a: pool.add(a[1]))
                size = 36 + 20 * len(attrs)
                body += struct.pack('<HHIIIIIHHHHHH', RES_XML_START_ELEMENT_TYPE,
                                    16, size, 1, NO_STRING,
                                    NO_STRING, pool.add(elem.name),
                                    20, 20, len(attrs), 0, 0, 0)
                for ns_uri, aname, raw, dtype, data in attrs:
                    ns = NO_STRING if ns_uri is None else pool.add(ns_uri)
                    rawv = NO_STRING if raw is None else pool.add(raw)
                    if dtype == TYPE_STRING and data == STRING_DATA:
                        data = rawv
                    body += struct.pack('<IIIHBBI', ns, pool.add(aname), rawv,
                                        8, 0, dtype, data)
            elif kind == 'end':
                body += struct.pack('<HHIIIII', RES_XML_END_ELEMENT_TYPE, 16, 24,
                                    1, NO_STRING, NO_STRING, pool.add(ev[1]))
        pool_b = pool.build()
        resmap = [self.attr_ids[n] for n in attr_names]
        map_b = bytearray(struct.pack('<HHI', RES_XML_RESOURCE_MAP_TYPE, 8,
                                      8 + 4 * len(resmap)))
        if resmap:
            map_b += struct.pack('<%dI' % len(resmap), *resmap)
        total = 8 + len(pool_b) + len(map_b) + len(body)
        return struct.pack('<HHI', RES_XML_TYPE, 8, total) + pool_b + bytes(map_b) + bytes(body)
