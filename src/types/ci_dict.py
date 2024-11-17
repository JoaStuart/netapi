from typing import ItemsView, Iterator, KeysView, ValuesView


class CaseInsensitiveDict[_T]:
    def __init__(self, data: dict[str, _T] | None = None) -> None:
        self._data = {}
        if data is not None:
            for key, value in data.items():
                self._data[key.lower()] = value

    def __setitem__(self, key: str, value: _T) -> None:
        self._data[key.lower()] = value

    def __getitem__(self, key: str) -> _T:
        return self._data[key.lower()]

    def __delitem__(self, key: str) -> None:
        del self._data[key.lower()]

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._data

    def get(self, key: str, default: _T | None = None) -> _T | None:
        return self._data.get(key.lower(), default)

    def keys(self) -> KeysView[str]:
        return self._data.keys()

    def items(self) -> ItemsView[str, _T]:
        return self._data.items()

    def values(self) -> ValuesView[_T]:
        return self._data.values()

    def __repr__(self) -> str:
        return repr(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[_T]:
        return iter(self._data)

    def dict(self) -> dict[str, _T]:
        return {k: v for k, v in self.items()}
