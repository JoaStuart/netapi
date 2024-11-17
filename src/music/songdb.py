import abc
import os
import sqlite3

import locations
from music.song_types import PlayInfo, SongInfo
from types.singleton import singleton
from types.cleanup import CleanUp


class StreamedSong(abc.ABC):
    def __init__(self, song: SongInfo) -> None:
        self._song_info = song
        self._data: bytes | None = None

    def load(self) -> None:
        self._data = self._load_data()

    @abc.abstractmethod
    def _load_data(self) -> bytes:
        pass

    @property
    def data(self) -> bytes | None:
        return self._data

    @property
    def info(self) -> SongInfo:
        return self._song_info


@singleton
class SongDB(CleanUp):
    def __init__(self) -> None:
        from main import CLEANUP_STACK

        CLEANUP_STACK.append(self)

        file_path = os.path.join(locations.RESOURCES, "songs.db")

        self._db = sqlite3.connect(file_path)
        self._cur = self._db.cursor()

        self._cur.execute(
            "CREATE TABLE IF NOT EXISTS `songs` (`ID` INTEGER PRIMARY KEY AUTOINCREMENT , `title` TEXT NOT NULL , `artist` TEXT NOT NULL, `url` TEXT NOT NULL) ;"
        )
        self._cur.execute(
            "CREATE TABLE IF NOT EXISTS `playinfo` (`ID` INTEGER PRIMARY KEY AUTOINCREMENT , `song` INTEGER NOT NULL , `playtime` FLOAT NOT NULL , `boosts` INTEGER NOT NULL) ;"
        )
        self._db.commit()

    def update_playinfo(self, info: PlayInfo):
        self._cur.execute(
            "UPDATE `playinfo` SET `playtime` = ? , `boosts` = ? WHERE `ID` = ? ;",
            (info.playtime, info.boosts, info.id),
        )
        self._db.commit()

    def create_song(self, title: str, artist: str, url: str) -> SongInfo:
        self._cur.execute(
            "INSERT INTO `songs` (`title` , `artist` , `url`) VALUES (? , ? , ?) ; SELECT last_insert_rowid() ;",
            (title, artist, url),
        )
        self._db.commit()

        id: int = self._cur.fetchone()[0]
        return SongInfo(id, title, artist, url)

    def cleanup(self) -> None:
        self._db.close()
