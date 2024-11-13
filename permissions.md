# Permissions

## Level ⇄ Action

| Level | Actions                |
| ----: | ---------------------- |
|   `0` | Checking sensor data   |
|       | Changing output device |
|  `50` | Backend functions      |
|       | Frontend functions     |

Level a device needs to execute the described action.

## Type ⇄ Level

| Type      | Level |
| --------- | ----- |
| Default   | `0`   |
| Subdevice | `50`  |
| Device    | `100` |

Level the device of a certain type has.
