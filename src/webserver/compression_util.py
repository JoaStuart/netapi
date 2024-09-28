import zlib
import gzip


def deflate(data: bytes, compresslevel: int = 9) -> bytes:
    """Deflates the data

    Args:
        data (bytes): Data to be deflated
        compresslevel (int, optional): Compression level. Defaults to 9.

    Returns:
        bytes: The compressed body
    """

    compress = zlib.compressobj(
        compresslevel, zlib.DEFLATED, -zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL, 0
    )
    deflated = compress.compress(data)
    deflated += compress.flush()
    return deflated


def gzip_compress(data: bytes, compresslevel: int = 9):
    """Compresses the data using GZip

    Args:
        data (bytes): Data to be compressed
        compresslevel (int, optional): Compression level. Defaults to 9.

    Returns:
        _type_: _description_
    """

    return gzip.compress(data, compresslevel)


ENCODINGS = [
    #("deflate", deflate),
    #("gzip", gzip_compress),
]
