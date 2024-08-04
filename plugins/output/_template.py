from backend.output import OutputDevice


class TemplateOutput(OutputDevice):
    def api_resp(self) -> dict:
        data = self.data

        # maniplulate data

        return data
