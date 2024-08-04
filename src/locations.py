import logging
import os
import zipfile

LOG = logging.getLogger()

SRC = os.path.dirname(__file__)
ROOT = os.path.join(SRC, "..")
PUBLIC = os.path.join(ROOT, "public")
PLUGINS = os.path.join(ROOT, "plugins")
PL_SENSOR = os.path.join(ROOT, "plugins/sensors")
PL_OUTPUT = os.path.join(ROOT, "plugins/output")
PL_BFUNC = os.path.join(ROOT, "plugins/bfunc")
PL_FFUNC = os.path.join(ROOT, "plugins/ffunc")


class ZipItem:
    def __init__(self) -> None:
        self.zpath = ""
        self.pdir = ""

    def compress(self, zip: zipfile.ZipFile) -> None:
        pass


class ZipDir(ZipItem):
    def __init__(self, zpath: str, dir: list[ZipItem] = [], root: bool = False) -> None:
        self.zpath = zpath
        self.dir = dir

        if root:
            self.iterate_zpath("")

    def iterate_zpath(self, parent) -> None:
        self.pdir = parent

        for k in self.dir:
            if isinstance(k, ZipFile):
                k.pdir = parent
            elif isinstance(k, ZipDir):
                npar = f"{parent}/{k.zpath}"
                k.iterate_zpath(npar.lstrip("/"))

    def make_dirs(self) -> None:
        os.makedirs(os.path.join(ROOT, self.pdir), exist_ok=True)
        for k in self.dir:
            if isinstance(k, ZipDir):
                k.make_dirs()

    def compress(self, zip: zipfile.ZipFile) -> None:
        for k in self.dir:
            k.compress(zip)


class ZipLiveDir(ZipDir):
    def __init__(self, zpath: str, root: bool = False) -> None:
        super().__init__(zpath, [], root)

    def compress(self, zip: zipfile.ZipFile, root: str | None = None) -> None:
        if root == None:
            root = self.pdir

        p = os.path.join(ROOT, str(root))
        for f in os.listdir(p):
            fp = os.path.join(p, f)
            if os.path.isfile(fp):
                zip.write(fp, f"{root}/{f}")
            elif os.path.isdir(fp) and not f.startswith("__"):
                self.compress(zip, f"{root}/{f}")


class ZipFile(ZipItem):
    def __init__(self, zname: str, zpath: str | None = None) -> None:
        self.zname = zname
        self.zpath = zpath or zname

    def compress(self, zip: zipfile.ZipFile):
        p = os.path.join(self.pdir, self.zname)
        zip.write(
            os.path.join(ROOT, p),
            f"{self.pdir}/{self.zpath}",
        )


dirtree = ZipDir(
    "",
    [
        ZipDir("logs"),
        ZipDir(
            "plugins",
            [
                ZipDir("bfunc", [ZipFile("_template.py")]),
                ZipDir("ffunc", [ZipFile("_template.py")]),
                ZipDir("output", [ZipFile("_template.py")]),
                ZipDir("sensors", [ZipFile("_template.py")]),
            ],
        ),
        ZipDir(
            "public",
            [ZipFile("favicon.ico", "favicon.ico")],
        ),
        ZipLiveDir("src"),
        ZipFile("_config.json"),
        ZipFile("run.sh"),
        ZipFile("run.bat"),
        ZipFile("requirements.txt"),
    ],
    True,
)


def make_dirs():
    dirtree.make_dirs()


def compress_pkg(zip_file: str):
    with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zip:
        dirtree.compress(zip)


def unpack(zip_file: str):
    with zipfile.ZipFile(zip_file, "r") as zip:
        zip.extractall(ROOT)
