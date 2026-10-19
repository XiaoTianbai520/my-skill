# Pure-CSS style guide

Apply this preamble immediately after `@startuml`. It is the canonical
black-and-white style for new diagrams. Do not add `skinparam` commands.

```plantuml
<style>
root {
  FontName Helvetica
  FontSize 12
  FontColor #000000
  BackGroundColor #FFFFFF
  LineColor #000000
  LineThickness 0.75
  RoundCorner 0
  Shadowing 0
}

title { FontSize 14; FontStyle bold; FontColor #000000; BackGroundColor transparent; LineColor transparent; LineThickness 0 }
note { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }

sequenceDiagram {
  actor       { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  participant { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  lifeLine    { BackGroundColor #FFFFFF; LineColor #000000; LineStyle 5-5; LineThickness 0.75 }
  group       { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  arrow       { LineColor #000000; LineThickness 0.75; FontColor #000000 }
}

classDiagram {
  class { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  arrow { LineColor #000000; LineThickness 0.75 }
}

activityDiagram {
  activity { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000; RoundCorner 10 }
  diamond  { BackGroundColor #FFFFFF; LineColor #000000 }
  arrow    { LineColor #000000; LineThickness 0.75 }
}

useCaseDiagram {
  actor     { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  usecase   { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  rectangle { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  arrow     { LineColor #000000; LineThickness 0.75 }
}

componentDiagram {
  actor     { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  component { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  package   { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  node      { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  database  { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  cloud     { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  arrow     { LineColor #000000; LineThickness 0.75 }
}

stateDiagram {
  state { BackGroundColor #FFFFFF; LineColor #000000; FontColor #000000 }
  arrow { LineColor #000000; LineThickness 0.75 }
}
</style>
```

For every class diagram, add this line immediately after `</style>`:

```plantuml
hide circle
```

`hide circle` is a PlantUML display instruction, not a legacy style setting.
It suppresses the C/A/I class-kind ornaments that CSS cannot reliably remove.

For CJK labels, replace `FontName Helvetica` with the font selected by the
renderer's `--cjk` mode. Keep the pure-CSS preamble intact.
