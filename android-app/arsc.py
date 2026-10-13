"""Writer for resources.arsc (the Android resource table).

Layout produced (matches aapt output):
  ResTable_header (0x0002)
  global value StringPool (UTF-8)      <- string values and file paths
  ResTable_package (0x0200, headerSize 284)
      typeStrings pool, keyStrings pool
      per type: ResTable_typeSpec (0x0202), then one ResTable_type (0x0201) per config
"""
import struct

from axml import StringPool

RES_TABLE_TYPE = 0x0002
RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_SPEC_TYPE = 0x0202
RES_TABLE_TYPE_TYPE = 0x0201

TYPE_STRING = 0x03

CONFIG_SIZE = 32                       # config through sdkVersion/minorVersion
ACONFIGURATION_DENSITY = 0x0100
NO_ENTRY = 0xFFFFFFFF


class ResValue:
    """An entry value: a string, a file path or a raw typed int."""

    def __init__(self, kind, payload):
        self.kind = kind               # 'string' | 'file' | 'int'
        self.payload = payload


class Config:
    def __init__(self, density=0):
        self.density = density
        self.entries = {}              # key -> ResValue

    def put(self, key, value):
        self.entries[key] = value

    def bytes(self):
        cfg = bytearray(CONFIG_SIZE)
        struct.pack_into('<I', cfg, 0, CONFIG_SIZE)
        struct.pack_into('<H', cfg, 14, self.density)
        return bytes(cfg)


class TypeGroup:
    def __init__(self, tid, name):
        self.tid = tid
        self.name = name
        self.keys = []
        self.configs = []

    def add_key(self, key):
        if key not in self.keys:
            self.keys.append(key)

    def add_config(self, config):
        for k in config.entries:
            self.add_key(k)
        self.configs.append(config)
        return config

    def build_spec(self):
        n = len(self.keys)
        flags = ACONFIGURATION_DENSITY if len(self.configs) > 1 else 0
        out = struct.pack('<HHIBBHI', RES_TABLE_TYPE_SPEC_TYPE, 8, 16 + 4 * n,
                          self.tid, 0, 0, n)
        out += struct.pack('<%dI' % n, *([flags] * n))
        return out

    def build_config(self, cfg, key_strings, values):
        n = len(self.keys)
        offsets = []
        payload = bytearray()
        for key in self.keys:
            val = cfg.entries.get(key)
            if val is None:
                offsets.append(NO_ENTRY)
                continue
            offsets.append(len(payload))
            if val.kind in ('string', 'file'):
                dtype, data = TYPE_STRING, values.add(val.payload)
            else:
                dtype, data = val.payload
            payload += struct.pack('<HHIHBBI', 8, 0, key_strings.index[key],
                                   8, 0, dtype, data)
        hdr_size = 20 + CONFIG_SIZE
        entries_start = hdr_size + 4 * n
        size = entries_start + len(payload)
        out = bytearray(struct.pack('<HHIBBHII', RES_TABLE_TYPE_TYPE, hdr_size,
                                    size, self.tid, 0, 0, n, entries_start))
        out += cfg.bytes()
        out += struct.pack('<%dI' % n, *offsets)
        out += payload
        return bytes(out)


class ResourceTable:
    def __init__(self, package_id=0x7f, package_name=''):
        self.package_id = package_id
        self.package_name = package_name
        self.values = StringPool()
        self.types = []

    def add_type(self, name):
        g = TypeGroup(len(self.types) + 1, name)
        self.types.append(g)
        return g

    def res_id(self, type_name, key):
        g = next(t for t in self.types if t.name == type_name)
        return (self.package_id << 24) | (g.tid << 16) | g.keys.index(key)

    def build(self):
        type_strings = StringPool()
        key_strings = StringPool()
        for g in self.types:
            type_strings.add(g.name)
            for k in g.keys:
                key_strings.add(k)
        type_strings_b = type_strings.build()
        key_strings_b = key_strings.build()

        body = bytearray()
        for g in self.types:
            body += g.build_spec()
            for cfg in g.configs:
                body += g.build_config(cfg, key_strings, self.values)

        values_b = self.values.build()
        pkg_hdr = 284
        pkg_size = pkg_hdr + len(type_strings_b) + len(key_strings_b) + len(body)
        pkg = bytearray()
        pkg += struct.pack('<HHII', RES_TABLE_PACKAGE_TYPE, pkg_hdr, pkg_size,
                           self.package_id)
        pkg += self.package_name.encode('utf-16-le')[:256].ljust(256, b'\x00')
        pkg += struct.pack('<IIII', pkg_hdr, len(self.types),
                           pkg_hdr + len(type_strings_b), len(key_strings.strings))
        pkg += type_strings_b + key_strings_b + body

        total = 12 + len(values_b) + len(pkg)
        return struct.pack('<HHII', RES_TABLE_TYPE, 12, total, 1) + values_b + bytes(pkg)
