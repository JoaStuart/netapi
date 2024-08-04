import zlib
import gzip


def deflate(data: bytes, compresslevel: int = 9):
    compress = zlib.compressobj(
        compresslevel, zlib.DEFLATED, -zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL, 0
    )
    deflated = compress.compress(data)
    deflated += compress.flush()
    return deflated


def gzip_compress(data: bytes, compresslevel: int = 9):
    return gzip.compress(data, compresslevel)


ENCODINGS = [
    ("deflate", deflate),
    ("gzip", gzip_compress),
]
