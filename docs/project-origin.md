# Why I started DayMirror

DayMirror was initiated by [Arsen1668](https://github.com/Arsen1668). The product concept, priorities, and interview design were directed by the project initiator; implementation and documentation were developed with AI assistance.

Official repository: https://github.com/Arsen1668/DayMirror-AI

## The problem

Starting from a blank journal page can feel demanding. A broad question such as "What did you do today?" asks the user to organize an entire day before the conversation has begun. DayMirror uses one question at a time to make daily reflection easier to start and easier to continue.

## The design

The first version combines ten basic questions with ten AI-generated follow-up questions. AI handles conversation and synthesis. Python handles validation, progress, local storage, and Markdown exports without calling a model service.

Pause and resume are part of the core workflow: save a question before displaying it, save an answer before moving on, and resume from disk. Unknown metrics stay empty. Suggested actions remain distinct from commitments and completed actions. Local storage does not imply local model inference.

Early user feedback identified an opening that felt too broad and insufficiently engaging. Version 0.1.1 changed the first five questions to start with the user's current state and one small moment, then ease into time use, task progress, and focus. Optional answer choices help users find an entry point while preserving free-form responses and uncertainty.

## Development record

These milestones describe local development recorded on 2026-10-10 (Asia/Shanghai). They are not asserted GitHub release dates. Public publication dates should be checked against the repository's release records.

| Version | Local milestone |
| --- | --- |
| 0.1.0 | Local interview tools, pause/resume/save workflow, privacy guidance, synthetic demo, and MIT packaging. |
| 0.1.1 | Gentler opening, optional choices, contextual follow-ups, and regression checks for letter-only answers and existing sessions. |
| 0.1.2 | Explicit project attribution, citation metadata, this design record, and a prepared release note. |

This record identifies the origin and evolution of the DayMirror project. It does not claim that interview-based reflection or AI journaling was first invented here. No systematic prior-art review has been completed.

Only product decisions and synthetic examples are included. Personal interview answers and private journals are excluded from publication.

## Attribution and reuse

Please cite [CITATION.cff](../CITATION.cff) when referencing or building on this project. Reuse is governed by the [MIT License](../LICENSE); the citation request does not add a license restriction.

## Adaptive interviews — local update on 2026-10-14

Further feedback found fixed openings and choices on every question too repetitive. Version 0.1.3 removes the prefilled question bank from new sessions. Both rounds now generate questions from the latest answers, using choices for the first three questions and at most the first five. Follow-ups balance the previous answer with unexplored time periods and life contexts. This is a local development milestone, not an asserted release date.
