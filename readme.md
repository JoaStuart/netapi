# NetAPI

## What is this thing?

The whole project is made to be a RestAPI controller for several devices inside a personal network, almost like an ecosystem.

We have one "main" device which acts like a backend server for any incoming API calls and an arbituary amount of frontend devices that basically recieve instructions from the backend server.

## Why did I start this project?

Idk tbh... I just had too much free time and other app/api based ecosystems didn't have some things I wanted, so I decided to make my own.

## How is my system setup?

###### My setup as of _October 2024_

```text
Network
 ╠> RaspberryPi             (Backend server)
 ║  ├> Arduino @ttyACM0     (Plant monitor)
 ║  └> Camera  @video1      (Sky camera (dont ask))
 ║
 ╠> My laptop               (Frontend device)
 ║  └> StreamDeck           (Subdevice)
```

## You want to use this for yourself?

Good luck in getting that thing to run 😅

Anyways you are always free to contact me, although I might not be able to really help, I just coded that thing for my system.
