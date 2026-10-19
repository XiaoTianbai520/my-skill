---
name: plantuml
description: Create and render monochrome UML-style PlantUML diagrams. Use when a user asks for a UML, architecture, workflow, sequence, state, deployment, Gantt, or mind-map diagram.
---

# PlantUML Diagram Generator

Turn a user's description into valid PlantUML source and, when a renderer is
available, an SVG, PNG, PDF, or text diagram. The target appearance is the
black-and-white UML reference style used by uml-diagrams.org.

## Workflow

1. Identify the diagram type and the essential participants, relationships,
   states, or activities. Ask a focused question only if a missing fact changes
   the diagram's meaning.
2. Create a `.puml` file with the matching pure-CSS preamble from
   [the style guide](references/style-guide.md). New diagrams must not contain
   `skinparam`, themes, gradients, or decorative colours.
3. Use [the syntax guide](references/syntax.md) for a diagram-specific pattern.
   For low-level design or system-design requests, also use the
   [LLD modelling guide](references/low-level-design.md). Prefer standard UML
   notation over custom shapes.
4. Render locally when the user asks for output or visual validation:

   ```bash
   python scripts/generate_plantuml.py input.puml output_dir --format svg
   ```

   The script tries local Kroki Docker, local PlantUML Docker, a native command
   or JAR, then the public Kroki server only with `--use-public-server`.
5. Report the `.puml` and rendered output paths. Mention layout, A4, CJK, or
   backend warnings that affect the result.

## Visual contract

- Use pure white `#FFFFFF` fills, black `#000000` text and strokes, 0.75pt
  lines, and no shadows. Keep classifiers and containers square; rounded
  activity actions are allowed where UML notation calls for them.
- Preserve classifier semantics with visible text stereotypes: use `interface
  Service <<interface>>`, `class Money <<dataType>>`, `class Weight
  <<primitive>>`, and `enum Status <<enumeration>>`. Do not add `<<class>>`
  to an ordinary class. Use `abstract class` for an abstract class.
- Add `hide circle` to every class diagram. This PlantUML display command is
  required because CSS cannot reliably remove the class-kind C/A/I circle.
- Sequence lifelines are dashed and activation bars are white with a black
  border. Use case actors remain stick figures and use cases remain ellipses.
- Use `--cjk` whenever the source contains Chinese, Japanese, or Korean text.
- Preserve a user-requested non-default visual style; otherwise apply the
  reference style.

## Privacy and safety

Rendering is local by default. `--use-public-server` uploads the complete
diagram source to a Kroki endpoint, so obtain the user's approval before using
it for non-public diagrams. Do not add credentials, secrets, or sensitive
system details to diagram source.

## Compatibility

The renderer can sanitize legacy `skinparam` input for migration, but the skill
must generate pure CSS source. For a reproducible renderer check, run:

```bash
python scripts/generate_plantuml.py --help
```

For repository development, `npm run test:visual` renders the pure-CSS fixture
set and verifies monochrome SVG output.
