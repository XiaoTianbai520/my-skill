# Low-level design modelling guide

Use a diagram set rather than forcing an entire design into one crowded class
diagram. Start with the question the reader needs answered, then choose the
smallest complementary views.

| Design question | Primary diagram | Verify in the source |
| --- | --- | --- |
| What objects own data and collaborate? | Class | Responsibilities, interfaces, multiplicities, composition and dependencies |
| What happens during one request? | Sequence | Caller, service boundaries, ordering, responses and failure branches |
| What states can an entity occupy? | State | Initial/final states, named transitions, guards and terminal paths |
| What decision or background workflow runs? | Activity | Decisions, forks, joins and exceptional outcomes |
| Which deployable parts or external systems connect? | Component/deployment | Ports, adapters, storage, queues and external dependencies |

## Modelling rules

1. Put behavior on the class that owns the information needed to perform it.
   Do not turn every noun in a prompt into a class.
2. Model variation behind interfaces: for example `PricingStrategy`,
   `PaymentMethod`, `DispatchStrategy`, or `Subscriber`. Show the concrete
   implementations only when they change the design decision.
3. Use UML relationships precisely: `*--` for lifecycle ownership,
   `o--` for shared aggregation, `--` for association, `<|--` for inheritance,
   and `..>` for a dependency. Add multiplicities when a collection is part of
   the requirement.
4. Keep classifier kinds explicit after adding `hide circle`: use `interface
   Gateway <<interface>>` for a contract and a realization arrow `..|>`,
   `<<dataType>>` for a value type identified by value, `<<primitive>>` for an
   atomic value, and `enum Status <<enumeration>>` for a closed set of
   literals. Do not stereotype ordinary classes as `<<class>>`; use `abstract
   class` when it is not instantiable.
5. Separate domain entities from orchestration services and infrastructure.
   A class diagram should not impersonate a deployment diagram.
6. Show meaningful alternatives in behavioural diagrams (`alt`, `if`, guards,
   or error transitions), especially payment failure, capacity exhaustion, and
   retries.

## LLD delivery checklist

- State the assumptions that constrain the model.
- Produce at least one static and one behavioural view for multi-step systems.
- Keep labels and relation names domain-specific; avoid a generic `Manager`
  without a responsibility.
- Use the pure-CSS preamble from [the style guide](style-guide.md) in every
  independently renderable `.puml` file.
- Add `hide circle` after the preamble of every class diagram so class-kind
  ornaments do not distract from names and stereotypes.
- Render and inspect every diagram before delivery.
