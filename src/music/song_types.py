class SongInfo:
    def __init__(self, id: int, title: str, artist: str, url: str) -> None:
        self._id = id
        self._title = title
        self._artist = artist
        self._url = url

    @property
    def id(self) -> int:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def artist(self) -> str:
        return self._artist

    @property
    def url(self) -> str:
        return self._url


class PlayInfo:
    def __init__(self, id: int, song: SongInfo, playtime: float, boosts: int) -> None:
        self._id = id
        self._song = song
        self._playtime = playtime
        self._boosts = boosts

    @property
    def id(self) -> int:
        return self._id

    @property
    def song(self) -> SongInfo:
        return self._song

    @property
    def playtime(self) -> float:
        return self._playtime

    @property
    def boosts(self) -> float:
        return self._boosts

    def add_playtime(self, playtime: float) -> None:
        playtime = min(max(0, playtime), 1)

        self._playtime = (self._playtime + playtime) / 2

    def update(self) -> None:
        from music.songdb import SongDB

        SongDB().update_playinfo(self)
