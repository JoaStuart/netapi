import abc
from enum import Enum
import threading
from typing import Type

from music.songdb import SongDB, StreamedSong
from music.song_types import SongInfo
from music.ytstream import YTSong


class MusicPlayer(abc.ABC):
    def __init__(self, sample_rate: int = 41000) -> None:
        self._buffer = b""
        self._sample_rate = sample_rate
        self._callbacks: list[tuple[int, threading.Event]] = []

    def put_data(self, data: bytes) -> None:
        self._buffer += data

    def sample_rate(self) -> int:
        return self._sample_rate

    def add_callback(self, data_remaining: int) -> threading.Event:
        self._callbacks.append((data_remaining, evt := threading.Event()))
        return evt

    def __len__(self) -> int:
        return len(self._buffer)


class MusicState(Enum):
    STOPPED = 0
    PLAYING = 1
    LOADING = 2


class MusicMaster:
    STREAM: Type[StreamedSong] = YTSong
    RETRIES: int = 5

    def __init__(
        self, player: MusicPlayer, start_song: SongInfo, db: SongDB = SongDB()
    ) -> None:
        self._player = player
        self._current_song: StreamedSong | None = None
        self._query: list[StreamedSong] = []
        self._db = db
        self._state: MusicState = MusicState.STOPPED

    def _set_state(self, state: MusicState) -> None:
        self._state = state

    def add_query(self, song: SongInfo) -> None:
        self._query.append(MusicMaster.STREAM(song))

    def _next(self) -> None:
        if len(self._query) == 0:
            return

        self._current_song = self._query.pop(0)

        self._player.put_data(self._get_song_data(self._current_song))
        self._state = MusicState.PLAYING

    def _get_song_data(self, song: StreamedSong) -> bytes:
        for _ in range(MusicMaster.RETRIES):
            if song.data is not None:
                break

            song.load()
        else:
            if song.data is None:
                raise ValueError(f"The song {song.info} could not be loaded!")

        return song.data

    def _preload_song(self) -> None:
        if len(self._query) == 0:
            return

        song = self._query[0]
        if song.data is None:
            song.load()
