from backend.output import OutputDevice


class URL(OutputDevice):
    def api_headers(self) -> dict[str, str]:
        if "url" in self.data:
            return {"Location": self.data["url"]}
        return {}

    def api_response(self, orig: tuple[int, str]) -> tuple[int, str]:
        if "url" in self.data:
            return (301, "MOVED")
        return orig
