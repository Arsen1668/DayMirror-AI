# DayMirror v0.1.2

**Created and maintained by [Arsen1668](https://github.com/Arsen1668).** Product concept and interview design by the project initiator, with AI-assisted implementation.

[Official repository](https://github.com/Arsen1668/DayMirror-AI) · [Design origin](docs/project-origin.md) · [Changelog](CHANGELOG.md) · [Citation](CITATION.cff)

Let AI interview you one question at a time and turn your day into a structured Markdown journal, with progress you can pause and resume.

This release includes **10 basic questions + 10 dynamically generated follow-up questions**, skipping, pausing, resuming, ending early, correcting answers, and versioned journal exports. Real interviews run in an AI client with file access and Python execution. Python handles local storage and validation and requires no API key.

The Skill instructions, reference documents, and sample journal are currently written in Chinese. This README is in English.

## Interview experience (v0.1.1)

The first five questions ease into the conversation through your current state, one small moment, where your time went, progress on one task, and one period of focus. Each question offers brief, neutral answer choices alongside free-form answers, uncertainty, and skipping. Follow-up questions build on what you have shared and include their own choices.

Selecting a letter is enough to answer. Choices are saved with the question and are never converted into guessed scores or missing facts. New interviews use the updated opening; existing sessions resume with their original questions and answers.

## Quick installation (Codex)

Copy the entire prompt below into a Codex conversation with file read/write access and Python execution. The installer downloads the complete `daymirror` directory from GitHub, including instructions, scripts, templates, and reference documents.

```text
$skill-installer Install the DayMirror Skill from https://github.com/Arsen1668/DayMirror-AI/tree/main/daymirror.
Check that Python 3.10+ is available. Use the same Python interpreter that will run the Skill scripts to install the dependencies in the Skill's requirements.txt.
Run the Skill's demo command to verify the synthetic interview → pause → resume → save workflow.
Report the actual installation path, verification results, and how to start using the Skill.
```

Once installation is complete, send this in your next turn:

```text
$daymirror Start today's reflection interview.
First ask me to choose an absolute path for my journal workspace and an IANA time zone. Then ask one question at a time and save the journal automatically when the interview is complete.
```

If the Skill does not appear after installation, restart Codex and try again. Codex can install Skills from other GitHub repositories; see the [official installation guide](https://learn.chatgpt.com/docs/build-skills#install-curated-skills-for-local-use). The Python dependencies are PyYAML and tzdata. The local scripts require no API key.

Other agents need Agent Skills support, file read/write access, and Python execution. Use the installation method provided by your client. Other clients have not yet been individually tested.

## Quick demo

Clone or extract the repository into a directory of your choice. In PowerShell, enter the repository root, install the dependencies, and run the demo. Replace `YOUR_CLONE_DIRECTORY` with the actual path:

```powershell
Set-Location 'YOUR_CLONE_DIRECTORY'
python -m pip install -r requirements.txt
python -X utf8 daymirror/scripts/daymirror.py demo
```

The command uses clearly marked synthetic questions and answers: answer 3 questions → pause and exit the process → resume at question 4 in a new process → finish both rounds → save the journal. The `journal_path` in the output is the absolute path to the generated file. Each demo uses a new directory under `work/demo`.

The offline demo verifies the storage workflow. During a real interview, AI generates follow-up questions and summaries from your answers. The demo questions are not a fixed interview question bank.

You can also read the [synthetic sample journal](daymirror/assets/example-journal.md) and [local verification report](docs/verification.md).

## Start a real interview

Send the prompt below to an AI client with local file access and Python execution. Replace `YOUR_SKILL_PATH` with the absolute path to `daymirror/SKILL.md` in the repository, and replace `YOUR_WORKSPACE` with a private data directory of your choice. `Asia/Shanghai` is an example; use your own IANA time zone.

```text
Read YOUR_SKILL_PATH and follow the DayMirror workflow to interview me about today.
Use YOUR_WORKSPACE as the workspace and Asia/Shanghai as the time zone.
Ask one question at a time and save the journal automatically when the interview is complete.
```

This lets you try the Skill by reading its instructions directly. If your client supports Agent Skills installation, install the `daymirror` folder in its skills directory. In Codex, invoke it with `$daymirror`; other clients use their own invocation methods.

During the interview, you can say "skip", "pause", "continue", "stop here and save what we have", or "change my answer to question 3". To resume, provide the original workspace and session ID. Without an ID, the tool prioritizes the most recent unfinished session.

A completed interview is saved automatically. Pausing keeps a recoverable draft. Ending early creates a journal marked as incomplete, which you can continue later. Correcting an exported answer creates a new journal version and keeps the previous file.

## Dependencies and verification

Requires Python 3.10+, PyYAML 6.x, and tzdata. To install missing dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
```

Run the tests, validate the Skill, and build the release package:

```powershell
python -X utf8 -m unittest discover -s tests -v
python -X utf8 tools/validate_skill.py
python -X utf8 tools/package_release.py
```

The last command creates a local distribution ZIP and file manifest. It does not upload to GitHub. Packaging uses a fixed allowlist that excludes personal records, runtime data, and temporary files.

Tested on Windows with Python 3.10.9 and PyYAML 6.0.3. The code is organized for portability, but other operating systems and AI clients have not been tested in practice.

## Data and privacy

When running from the repository, the default workspace is `private/workspace`: `sessions` stores JSON answers and progress, `journals` stores versioned Markdown files, and `inputs` stores private command inputs. For an installed Skill, explicitly choose a data workspace.

Unknown metrics remain `null`, rather than being replaced with zero. Mood, energy, and stress scores come only from explicit user ratings. Every non-null metric references its source question. Journal entries distinguish user-reported facts, subjective assessments, and unverified AI hypotheses. Suggested actions are not recorded as actions already taken.

**Local storage and local inference are separate.** The Python tools do not connect to the network. Your AI client may still send conversations and file contents to its model provider. Records are stored as plain text. See the [privacy notes](daymirror/references/privacy.md).

## Further reading

- [v0.1 requirements and acceptance criteria](docs/v0.1-requirements.md)
- [Skill workflow](daymirror/SKILL.md)
- [Command and data interfaces](daymirror/references/schema.md)
- [Interview protocol](daymirror/references/interview.md)

v0.2 is planned to add historical statistics, periodic reports, and tracking of suggested actions and their outcomes. v0.1 preserves structured metrics and the original interview context, but does not automatically generate weekly or monthly reports.

## Attribution and citation

If you use or build on DayMirror, please cite the project using [CITATION.cff](CITATION.cff). Citation is appreciated; reuse is governed by the MIT License. The standalone Skill includes its own citation metadata and [provenance notes](daymirror/references/provenance.md).

The design-origin record documents this project's development. It does not claim global first-invention of AI journaling or interview-based reflection. A publication-ready [v0.1.2 release note](docs/releases/v0.1.2.md) is included; preparing it locally does not publish a GitHub Release or register a DOI.

## License

Copyright (c) 2026 Arsen1668 and DayMirror contributors.

This project is released under the [MIT License](LICENSE). The standalone `daymirror` Skill directory includes the same license.
