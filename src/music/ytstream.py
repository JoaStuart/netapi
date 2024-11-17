from music.songdb import SongInfo, StreamedSong


class YTSong(StreamedSong):
    def __init__(self, song: SongInfo) -> None:
        super().__init__(song)
