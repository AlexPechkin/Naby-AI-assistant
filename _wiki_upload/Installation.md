# Installation

Naby runs on **Windows 10/11, macOS 11+ and Linux**. All installers are free and signed by the author.

| System | File | How to install |
|---|---|---|
| 🪟 Windows 10 / 11 | [Naby_Setup.exe](https://neuralaibaby.tech/naby/dl.php?f=win) | Run it and click **Next**. Python and everything else Naby needs are already inside. |
| 🍎 macOS 11+ | [Naby_mac.zip](https://neuralaibaby.tech/naby/dl.php?f=mac) | Unzip it and drag **Naby.app** to **Applications**. |
| 🐧 Linux | [Naby_Install_Linux.sh](https://neuralaibaby.tech/naby/dl.php?f=linux) | `bash Naby_Install_Linux.sh` |

The same files are also attached to each [GitHub release](https://github.com/AlexPechkin/Naby-AI-assistant/releases).

## What happens on first start

1. **Language.** Naby asks for your language right away and switches the whole interface to it (English, Russian, Chinese and others).
2. **Profession (optional).** Naby offers to become a helper for your profession. Pick one, choose “Other profession” and Naby studies your field, or choose “I'll set it up myself” and Naby stays general.
3. **Your computer.** Naby checks your PC and suggests neural networks, a local model that fits your hardware, and the programs your work needs. It can install a missing program, suggest an alternative, or let you point to where it is.

## Updates

Naby checks for new builds and **updates itself**. It verifies the author's signature on every update before installing it. If something goes wrong after an update, you can roll back (see [Features → Memory, logs and rollbacks](Features#memory-logs-and-rollbacks)).

## System requirements

- Any modern PC or Mac. Naby works without a graphics card.
- A local model needs about 1–1.5 GB of disk space for the small LFM3 models (build 46) and more for larger models.
- You can choose how much of the computer Naby may use: 30 %, 50 % or 70 % (build 41).
- Internet is needed for cloud models, updates and web tasks. Local models, folder search and many tasks work offline.

## Moving to a new computer

Naby can keep an encrypted backup of its memory and character in places you choose (cloud folder, USB drive, another disk). On a new computer, install Naby, put the `.naby` file next to it, run the restore and enter your recovery phrase.
