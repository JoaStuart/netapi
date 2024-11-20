import logging
from device.api import APIFunct
from log import LOG


class Log(APIFunct):
    def api(self) -> dict | tuple[bytes, str]:
        if self.request is None:
            return {"message": "You need to remotely request this method!"}

        try:
            log_data = self.body
            if not log_data:
                return {
                    "message": "No log object was provided!",
                }
            ip = self.request._conn.sock().getpeername()[0]
            message: list[str] = [f"Remote log by {ip}:"]

            level: str = log_data.get("level", "INFO").upper()
            message.append(log_data.get("message", "No message provided!"))
            exc_trace: str | None = log_data.get("exception")

            if exc_trace:
                message.append(exc_trace)

            log_level = getattr(logging, level, logging.INFO)
            LOG.log(log_level, "\n".join(message))

        except Exception as e:
            LOG.exception(f"Exception while receiving log from {self.request}")

        return {}
