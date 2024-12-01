from enum import Enum
import json
import logging
import os
from typing import Any

from backend.backend import BFUNC
from backend.interval import Schedule
from backend.output import OUTPUTS
from backend.sensor import SENSORS
import locations
import utils


LOG = logging.getLogger()


class AutomationState(Enum):
    NORMAL = 0
    WAITING = 1


class Automation:
    @staticmethod
    def load_all() -> None:
        for f in os.listdir(locations.AUTOMATION):
            if not f.endswith(".json"):
                continue

            with open(os.path.join(locations.AUTOMATION, f), "r") as rf:
                data = rf.read()
            automation = Automation._load_by_str(data)

            if isinstance(automation, bool):
                if not automation:
                    LOG.warning("Could not load automation file %s", f)
                return

            Schedule.add_schedule(automation.schedule)

    @staticmethod
    def _load_by_str(data: str) -> "Automation | bool":
        try:
            jdata = json.loads(data)
            if jdata.get("@type") != "automation":
                return False

            return Automation(jdata)
        except KeyError:
            pass
        except json.JSONDecodeError:
            pass

        return True

    def __init__(self, data: dict[str, Any]) -> None:
        self._state: AutomationState = AutomationState.NORMAL

        self._title: str = data["title"]
        self._frequency: float = data["frequency"]
        self._if: dict[str, Any] = data["if"]
        self._then: list[dict[str, Any]] = data["then"]
        self._wait: dict[str, Any] = data.get("wait", {})

        self._vars: dict[str, Any] = {}

        self.schedule = Schedule(self._frequency, self.tick)

    def _inject_vars(self, varstr: str) -> str:
        """Replaces all variables in the given string with their declared values

        Args:
            varstr (str): The string containing the variable names

        Returns:
            str: The input string replaced with the given variables
        """

        for k, v in self._vars.items():
            varstr = varstr.replace(k, str(v))

        return varstr

    def _load_vars(self, body: dict[str, Any], result: dict) -> None:
        """Loads all variables the user wants to declare

        Args:
            body (dict[str, Any]): The body that contains the variable declarations
            result (dict): The result from which to pull the variable contents
        """

        for k, v in body.items():
            if k.startswith("$"):
                self._vars[k] = utils.load_dict_var(result, v)

    def check(self, body: dict[str, Any]) -> bool:
        """Checks either the `IF` of the `WAIT` portion

        Args:
            body (dict[str, Any]): The body of the action to check

        Returns:
            bool: Whether the check succeeded
        """

        path: list[str] = [i for i in body["query"].split("/") if len(i) > 0]
        check: str = body["check"]
        result: dict = {}

        for p in path:
            result |= self._query_sensor(p.split("."), body.get("body", {}))

        self._load_vars(body, result)

        check = self._inject_vars(check)

        return bool(eval(check, {}, {}))

    def then(self) -> None:
        """Executes the `THEN` part of the automation"""

        for r in self._then:
            path: list[str] = [i for i in r["path"].split("/") if len(i) > 0]
            body: dict[str, Any] = r.get("body", {})

            for k, v in body.items():
                if isinstance(v, str):
                    body[k] = self._inject_vars(v)

            for p in path:
                self._execute_backend(p.split("."), body)

    def _execute_backend(self, fargs: list[str], body: dict) -> None:
        """Execute a backend function without needing a WebRequest

        Args:
            fargs (list[str]): Arguments of the current command
            body (dict): Body for the current command
        """

        for name, fclass in BFUNC.items():
            if name.lower() == fargs[0].lower():
                fclass(None, fargs[1:], body).api()

                return

        LOG.warning("[%s] Could not find BFunc for `%s`!", self._title, ".".join(fargs))

    def _query_sensor(self, fargs: list[str], body: dict) -> dict[str, Any]:
        """Query a sensor without needing a WebRequest

        Args:
            fargs (list[str]): Arguments of the current command
            body (dict): Body for the current command

        Returns:
            dict[str, Any]: Response body
        """

        for name, inst in SENSORS.items():
            if name.lower() == fargs[0].lower():
                inst.tpoll()
                if inst.data is None:
                    continue

                out = OUTPUTS["default"](body)
                inst.to(out, fargs[1:])

                return out.api_resp()

        return {}

    def tick(self) -> None:
        """Executes a tick of the automation"""

        try:
            if self._state == AutomationState.NORMAL:
                LOG.debug("Checking IF tick for %s", self._title)
                if self.check(self._if):  # Execute IF part
                    LOG.debug("Executing THEN for %s", self._title)
                    self.then()  # Execute THEN part
                    self._state = AutomationState.WAITING

            elif self._state == AutomationState.WAITING:
                LOG.debug("Checking WAIT tick for %s", self._title)
                if self.check(self._wait):  # Execute WAIT part
                    self._state = AutomationState.NORMAL

        except:
            LOG.exception("Failed tick:")
