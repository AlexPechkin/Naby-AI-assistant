# Professions

A profession is Naby set up for your work in one click. Naby looks up which models and tools are currently best in your field, then adjusts its skills, its local model and its interface to match.

## What a profession gives you

- **Models per task type.** Each kind of task (for a programmer: code edits, debugging, review) goes first to the strongest model you have connected for that kind.
- **A local model sized for your computer**, so simple tasks run free and offline.
- **Quick-start buttons** above the input box, plus knowledge sources for your field: laws, standards, references.
- **Programs.** Naby checks which programs you need, finds the ones you have, and offers to install a missing one, suggest an alternative, or let you point to where it is.
- **Private mode 🔒.** When a message contains someone else's personal data, Naby switches on its own and works only with the local model. For a doctor this mode is “Patient”, for a lawyer or financier “Client”, for a teacher “Students”.
- **Professional rules.** A medic does not diagnose or prescribe. A lawyer checks every reference to law and court practice. A financier calculates only with code and gives no investment advice. A scientist cites only real sources with a DOI.
- **Monthly review.** Once a month Naby checks what's new in your field and suggests updating the setup. Every change is visible and can be rolled back.

Where to set it: ⚙ Settings → “Profession”. On first start Naby offers this itself.

## 140 professions

The professions are grouped into 19 areas: engineering, software, science, finance, health, construction, design, marketing, education, services, management, logistics, writing, data and AI, law, media, public service, agriculture and energy.

- ✅ **10 verified professions** have calculation packages with tests: customs specialist, pharmacist, physicist, tax consultant, structural engineer, real estate appraiser, climate scientist, embedded engineer, investment analyst, actuary. Each package makes verifiable calculations, creates Word, Excel or PDF documents, and checks the result against evidence from your files.
- 🛠 **130 professions in progress:** the profile is ready, and the calculation package is not yet verified.

All of them are open in the repository: [professions/verified](https://github.com/AlexPechkin/Naby-AI-assistant/tree/main/professions/verified) · [professions/in-progress](https://github.com/AlexPechkin/Naby-AI-assistant/tree/main/professions/in-progress)

## Community professions *(build 50)*

Naby itself is the author's work, but **professions are open**. You can improve them, create new ones and share them under the [Naby Professions License 1.0](https://github.com/AlexPechkin/Naby-AI-assistant/blob/main/LICENSE.md).

**Install one for yourself, right now:**

```
install profession https://github.com/you/your-repo
```

1. Naby downloads it from github.com only (up to 20 MB) into quarantine.
2. It validates the profession: format, three languages, injected instructions, forbidden files.
3. It shows you what it is about to install (name, authors, version, warnings) and installs **only after your yes**.
4. Only the **profile** is installed: rules, task types, models, sources, programs. Package code from the community is **never executed**. It runs only after the author verifies it and ships it in a build.
5. The profession appears marked “community · not verified by the author”. A built-in profession cannot be replaced this way; send improvements to the author instead.

Other commands: `community professions` lists what you installed, `remove profession <id>` removes one.

**Send your profession to the author:** use the form at [neuralaibaby.tech/submit-profession.html](https://neuralaibaby.tech/submit-profession.html), or open a pull request into `professions/in-progress/<id>`. The author reviews the best submissions and ships them in the next Naby build, with your name.

## How to make a profession

- How professions work and how they plug into Naby: [docs/professions/HOW_IT_WORKS.md](https://github.com/AlexPechkin/Naby-AI-assistant/blob/main/docs/professions/HOW_IT_WORKS.md)
- Step-by-step guide: [docs/professions/CONTRIBUTING.md](https://github.com/AlexPechkin/Naby-AI-assistant/blob/main/docs/professions/CONTRIBUTING.md)
- Validator: `python tools/validate.py path/to/profession`

## License

Using Naby for professional tasks, for work or for any income requires a [commercial license](License-and-Pricing). Without a license you can change the profession once every 30 days; with a license, any time.
