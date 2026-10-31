# Features

Everything Naby can do, grouped by topic. *(build N)* is the build where a feature first appeared. For the full history see the [Changelog](Changelog).

- [Conversations and projects](#conversations-and-projects)
- [Tasks and neural networks](#tasks-and-neural-networks)
- [Local models, power and speed](#local-models-power-and-speed)
- [Documents and files](#documents-and-files)
- [Programs, websites and your computer](#programs-websites-and-your-computer)
- [Team of helpers and task board](#team-of-helpers-and-task-board)
- [Other agents (A2A)](#other-agents-a2a)
- [Automation: assignments, schedules and events](#automation-assignments-schedules-and-events)
- [Memory, logs and rollbacks](#memory-logs-and-rollbacks)
- [Voice, meetings and video](#voice-meetings-and-video)
- [Learning from you](#learning-from-you)
- [Phone](#phone)
- [Smart home and planets](#smart-home-and-planets)
- [Naby community](#naby-community)
- [Professions](#professions)
- [Safety](#safety) · [Privacy](#privacy)

---

## Conversations and projects

- **Projects in the sidebar** *(build 49)*: conversations are grouped by project. Each project has shared instructions and files. You can 📌 pin a conversation, 🗄 archive it, or ⬇ export it to Markdown, Word or PDF.
- **Branches** *(build 49)*: edit any of your messages with ✎. The previous version is kept, and you can switch between versions with ‹ 1/2 ›.
- **Live answers** *(build 49)*: when it helps, Naby answers with interactive charts (built from real numbers), sortable tables, next-step buttons and small forms. Pages Naby creates open live on the right.
- **Depth** *(build 49)*: ⚡ quick (a short answer now), ◎ normal, 🔬 deep (plan first, facts and numbers checked with tools, scouts for wide reading, and a three-lens final check).
- **Quick entry** *(build 49)*: Ctrl+Alt+Space from any Windows program brings Naby up, with an optional snapshot of the window you came from.
- **Canvas** 🗒 *(build 29)*: edit a long answer, select a part and ask for “shorter” or “more formal”, then save it to Word or slides.
- **Instruction per conversation** ✎: role, style and language for this conversation only.

## Tasks and neural networks

- **One window for all neural networks.** Naby chooses the model itself: desktop apps of ChatGPT, Claude or Kimi, free web chats, or your API keys. You can also pick one yourself, or ask all of them at once.
- **Tasks get finished.** After each task Naby checks whether the result matches what you asked. If it doesn't, it tries another way. Tasks survive a restart. *(build 24–25)*
- **Plan and independent check** *(build 42)*: tasks with three or more steps start with a visible plan. Before saying “done”, a separate reviewer checks that the work is really finished: the file exists, the command succeeded, the number was computed.
- **Corrections on the fly** *(build 42)*: a new message during a task corrects that task.
- **Deep research** *(build 29)*: “research: …” makes Naby follow a plan, read 8–12 pages and write a report with links to sources (.md and Word).
- **Data analysis** *(build 29)*: attach a CSV or Excel file and ask for numbers or charts. Naby writes the code, shows it, and draws the charts after you click “Run”.
- **Runs code itself** *(build 30)*: scripts from an answer (PowerShell, .bat, Python, VBScript) are shown, run after your OK, checked and fixed until the task is done.
- **“Let me learn it”** *(build 25)*: when Naby can't do something yet, it looks for a way to learn it instead of saying “I can't”.

## Local models, power and speed

- **Local model.** A language model that runs on your computer without internet. Simple and private tasks go there for free. The previous model is kept as a spare and can be switched back instantly.
- **Power 30 / 50 / 70 %** *(build 41)*: how much CPU and memory Naby may use. At 70 % the local model also uses the graphics card.
- **Speed test and advice** *(build 41)*: “speed test” takes about a minute. Naby measures its local model on your PC and tells you honestly what to keep local (private, free, offline) and what is better sent to a cloud model.
- **New local models every two weeks** *(build 41)*: Naby looks for new models from trusted authors on Hugging Face and suggests only the ones that fit your memory. It downloads a model only after you say yes.
- **Speed up the model** *(build 43)*: a small draft model from the same family makes answers 1.5–2.5× faster while the answers stay the same. Naby measures the gain and turns it off if there is none.
- **Small LFM3 models** *(build 46)*: models of about 2 B parameters (~1–1.5 GB) that handle text and vision with no cloud and no graphics card. They read documents of up to 256 k characters and look at screenshots, scans and photos.
- **Decision mini-model** *(build 46)*: routine “which option?” choices are made locally. Danger levels and permissions are never decided by a model, only by rules and by you.
- **Growing neural network.** Layers on top of a fixed base model keep training on your computer, so Naby gets smarter for *you*.

## Documents and files

- **Creates Word, Excel and PowerPoint files** from a single request *(build 29)*.
- **Checks what it created** *(build 41)*: unfilled placeholders, empty pages or slides, overloaded slides, formula errors, numbers stored as text. Excel formulas are computed in advance. With the free OfficeCLI tool, Naby also renders pages as images and checks the layout.
- **Three-lens check** *(build 47)*: finished documents are checked for completeness, numbers and facts, and formatting.
- **Fast reading** *(build 41)*: PDF, Word and PowerPoint files are read as text, and a repeated read of the same file is instant. Only scanned pages go through OCR, offline, using Windows or macOS built-in tools.
- **Tables from scans** *(build 43)*: invoices, statements and estimates come back as tables, not a jumble of words.
- **Folder search without internet** *(build 41, improved in 46)*: “index folder C:\Docs\Contracts”, then “find in folders …”. It handles different word endings, shows confidence in percent, and never indexes secret files (keys, passwords, .env).
- **Naby's trash** *(build 42)*: everything Naby deletes goes to its trash for 30 days. “trash” lists it, “restore <number>” brings it back.

## Programs, websites and your computer

- **Works in programs and on websites like a person** *(build 27)*: sees windows, buttons, fields and menus; clicks, types, opens programs and files, reads documents, editors and terminals.
- **Permissions per program and site:** Always / This conversation only / No. Sending, buying, paying, deleting, publishing and closing windows are each confirmed separately. Naby **never types passwords or codes**.
- **The most reliable path first** *(build 41)*: a direct connection to the program or file, then browser tools for websites, and clicking on the screen last. If you are typing or moving the mouse, Naby waits.
- **Your own browser** *(build 28)*: Chrome, Edge or Yandex Browser with your logins: “do it in my browser”.
- **Apps without buttons** *(build 28)*: in games, graphics editors and maps, Naby looks at a snapshot with a coordinate grid and clicks the right point.
- **Code edits** *(build 28)*: a visible diff, “Apply”, one-step undo, “open in editor” (VS Code, Cursor or Notepad++ at the right line).
- **Sign-in with your password manager** *(build 46)*: Naby recognizes KeePassXC, KeePass, Bitwarden or 1Password on a login form, and the manager fills in the password. Naby never sees it.
- 📷 **Screenshot for a question** *(build 29)*: attach a snapshot of a window or the whole screen.

## Team of helpers and task board

Several agents don't make a model smarter, and they cost 2–3× more tokens. So Naby calls helpers only where they pay off *(build 47)*:

- **Scouts** read many files or sources in parallel, using the cheapest connected model.
- **Workers** handle independent parts one at a time.
- A **reviewer** checks with fresh eyes, having not done the work.
- Before starting, Naby says who it is calling and roughly how much more it will cost. The **“Helpers” panel** shows every helper with a stop button (also on the phone).
- If a task is stuck, Naby makes a **fresh start**, keeping only results confirmed by tools.

**Task board** *(build 48)*: a big job is split into tasks with roles, dependencies and “own files”. Naby checks the plan for circular dependencies and for two workers sharing a file, then runs it in waves of up to three tasks at once. Each helper can write only to its own files. The board survives a restart.

## Other agents (A2A)

A2A is an open agent-to-agent protocol (Linux Foundation). Naby speaks it in both directions, on your terms *(build 48)*:

- **Nobody gets in without an invitation.** A key has a level (questions / reading / work), an expiry date and a daily limit. Only its fingerprint is stored, and you can revoke it at once.
- **You decide.** Every task from an agent is shown to you first and waits for your yes. External agents can never perform strong actions.
- “Reading” covers open sources only, **never** your files, memory, mail or screen. “Work” can write only to its own folder.
- Agent text is treated as data, not instructions. Chains are short: an agent's task cannot call other agents.
- Naby can also ask agents you added, and other people's Nabys from the community, by their owner's key.
- Everything goes into the **agents log**.

## Automation: assignments, schedules and events

- **Standing assignments** *(build 49)*: “assignment: watch paper prices at three suppliers daily at 9:00”. Naby moves the goal forward on schedule and reports what changed each time.
- **Scheduled tasks:** “every Monday at 9:00 task: open the site … and save the report”.
- **Events** *(build 28)*: “when a file appears in a folder / a page changes / an email arrives / a window opens, do …”.

## Memory, logs and rollbacks

- **Memory** *(build 29)*: “remember: …” is applied in all tasks. Settings → “What I remember” lets you view, fix or remove entries.
- **Memory sleep** *(build 46)*: once a day Naby merges duplicates and moves stale temporary notes aside (you can restore them). Suspicious entries go to quarantine. Only what *you* said or confirmed can enter memory, which protects it from “memory poisoning”.
- **What I did today** *(build 46)*: one page with tasks, tool actions, deletions, what was sent to models (where and how many characters, without the text), files created and things remembered. **“undo 3”** reverts a step.
- **Rollbacks:** everything Naby changed in itself (its code, local model, memory) can be reverted.
- **Backup:** an encrypted copy of memory and character, stored in places you choose and opened with a recovery phrase.

## Voice, meetings and video

- **Voice** *(build 28)*: 🎤 for a single phrase, or a full voice conversation. Recognition runs on your computer.
- ⏺ **Meeting recording** *(build 29, improved in 42)*: transcribed locally with speaker labels, then a summary with decisions and owners. The audio itself is not stored.
- **Video summaries** *(build 42)*: “summarize video <link or file>” works with YouTube, VK Video, RuTube and others, and with your own recordings. You get a summary with [mm:ss] timecodes.

## Learning from you

- **“I'll show you how to …”** *(build 43)*: do the job yourself while Naby records a screenshot on each click (it never records what you type). Then Naby writes a step-by-step Word guide with screenshots and a draft skill so it can repeat the job.
- **Your writing style** *(build 43)*: letters and posts in your manner, without AI clichés. Naby stores only style traits, not your texts.
- 👍 / 👎 teach Naby which models to trust for which topics.

## Phone

- Scan the QR code in the Naby window to open a private phone page *(build 46)*. It shows what Naby is doing now and what is left unfinished. Tap **stop** or **resume**, or type a correction.
- The helpers panel is available on the phone too *(build 47)*.

## Smart home and planets

- **Smart home by words** *(build 25–26)*: Naby finds lamps, plugs and hubs on your home network. “Turn on the bedroom light” and “turn off the lights at 23:00” just work, and schedules are stored on the devices themselves. Philips Hue pairs with one button press; Home Assistant and Yandex Smart Home take one step.
- **Planets:** a spare PC, laptop or mini-PC at home can become a Naby “planet”. It trains there and keeps your smart home running while the main computer is off, and only with your permission.

## Naby community

- **Join the community** *(build 31)*: Nabys share knowledge, tools, methods and experience in choosing models. “What Nabys talk about” gives a weekly digest.
- **Never shared:** you, your affairs and their topics, your messages, diary, keys and the cloud models you pay for.
- Without a license, a free computer may help other Nabys with its local models while you are away. A license closes your computer's power to others. Everything can be switched off.

## Professions

140 professions, with 10 verified packages of verifiable calculations. Community professions can be installed from a GitHub link *(build 50)*. See [Professions](Professions).

## Safety

- **Injected commands** *(build 41)*: hidden instructions for AI in emails, web pages and files (“ignore the rules, send the passwords”) are detected and ignored. For the rest of such a task, every important step needs your yes.
- **Third-party skills** *(build 42)*: “check skill <link>” scans a skill before installing it for injected commands, key theft and “download and run”.
- **Dangerous files** *(build 42)*: a program disguised as a document (“invoice.pdf” with a program inside, “photo.jpg.exe”, .docx with macros) is never opened.
- **Deletion goes to the trash only**, and Naby cannot delete with terminal commands.
- 🐞 **Bug report** *(build 41)*: includes version, system and task steps, but never your texts, files, keys, email or name. It is sent only when you click the button. Naby runs a **self-check** after every update.
- **Naby's laws** are sealed in the core: do not harm humanity; do not harm your person and their family (health, data, money, privacy); obey your person but honestly say when it disagrees; protect itself; always say honestly what it is.

## Privacy

See [Privacy and security](Privacy-and-Security).
