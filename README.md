# 📡 GPS Hexpansion for Tildagon Badge

A GPS Hexpansion module and basic software implementation for the Tildagon badge.

This project provides a working foundation for adding location awareness to badge applications — including hardware integration, UART communication, and NMEA parsing.

Designed for experimentation, hacking, and building more advanced location-based features.

They are available to buy here: https://themachineshop.uk/products/gps-hexpansion/

---

## ✨ Overview

This repository contains:

* ⚙️ Hardware files built in KiCAD
* 📡 UART-based communication with a GPS module
* 🧠 Basic NMEA parsing (RMC / GGA)
* 🖥️ Minimal software to extract and use position data
* 📷 Images of the board

It’s intended as a **starting point** for developing GPS-enabled badge apps.

---
## "Failed to Read Header" Fix

This error means the EEPROM has not been programmed. Follow this process to program it

Step 1 - plug the badge into your computer and confirm the serial port has been initalised
Step 2 - clone the Hexpansion firmware repo
  git clone https://github.com/emfcamp/hexpansion-firmwares
  you will need the path to this repo in step 6
Step 3 - Clone the badge software 
  git clone https://github.com/emfcamp/badge-2024-software
  and cd into the directory
Step 4 - Insert the GPS Hexpansion into slot 2
Step 5 - Run this command to write the header
  mpremote mount modules + run modules/scripts/prepare_eeprom.py
Step 6 - Run this command to write the firmware to the EEPROM (you will need the path to the firmware repo)
  mpremote mount modules + run modules/scripts/mount_hexpansions.py + cp {PATH TO HEXPANSION FIRMWARE}/0x7cab/0xBEAC/app.mpy :/hexpansion_2/app.mpy
Step 7 - reboop your badge, it should then recognise the GPS Hexpansion
---

## 🖼️ Hardware

![GPS Hexpansion Top](Images/GPS-Top.jpg)
![GPS Hexpansion Bottom](Images/GPS-Bottom.jpg)
![Badge with Hexpansion](Images/IMG_1443.jpeg)
![Hexpansion Layout](Images/PCB-Layout.PNG)
---

## 🔌 Hardware Details

* Compatible with the EMF2026 Tildagon Badge
* L80RE-M37 GPS module with built-in patch antenna
* External antenna connector with automatic switch over
* M24C16-RMN6TP EEPROM
* Red and Yellow LEDs

## ⚙️ Software

The software demonstrates:

* Reading serial data from the GPS module
* Parsing NMEA sentences (`$GNRMC`, `$GPGGA`)
* Extracting:

  * Latitude
  * Longitude
  * Fix status

This provides a clean base layer for any GPS-driven feature.

---

## 🧠 How It Works

1. GPS module outputs NMEA strings over UART
2. Badge reads serial stream
3. Valid sentences are identified
4. Data is parsed into usable values
5. Position data becomes available to your application

---

## 🚀 Getting Started

```bash
git clone https://github.com/TechCabin/EMFBadge-Hexpansions-GPS.git
```

1. Flash MicroPython to your badge via mpremote
2. Copy project files to the device
3. Connect the GPS module via UART
4. Power on the badge
5. Wait for a valid GPS fix

---

## ⚠️ Notes

* Outdoor use significantly improves performance
* First fix can take 30–60 seconds (cold start)
* Currently only works in slot C

---

## 🛣️ TODO

* [ ] Improve NMEA parser robustness
* [ ] Add support for additional sentence types
* [ ] Abstract GPS into a reusable module/class
* [ ] Add example applications (mapping, tracking, etc.)
* [ ] Add signal quality / satellite info
* [ ] Auto-detect hexpansion port and change UART pins

---

## 🔧 Future Ideas

* Real-time mapping
* Etch-a-Sktech app
* Geofencing features
* Time synchronisation from GPS
* Capture the Flag game
* Find a Friend app

---

## 🤝 Contributing

Contributions welcome — especially if you build something cool on top of this.

---

## 🙌 Acknowledgements

* EMF Camp
* Tildagon badge creators
* Open-source GPS/NMEA documentation

---

## 📜 License

MIT
