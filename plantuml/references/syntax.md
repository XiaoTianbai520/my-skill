# Diagram syntax guide

Select the smallest diagram type that expresses the user's question.

| Request | Use | Key notation |
| --- | --- | --- |
| Calls, request/response, hand-offs | Sequence | `actor`, `participant`, `->`, `-->`, `activate` |
| Domain entities and relationships | Class | `class`, multiplicities, `--`, `o--`, `*--` |
| Decisions and process steps | Activity | `start`, `:step;`, `if`, `fork`, `stop` |
| Roles and system capabilities | Use case | `actor`, `usecase`, `rectangle`, `..>` |
| Services and infrastructure | Component/deployment | `package`, `[Component]`, `node`, `database`, `cloud` |
| Lifecycle and transitions | State | `[*]`, `state`, `-->` |
| Schedule | Gantt | `@startgantt`, `[Task] lasts 3 days` |
| Hierarchy or brainstorming | Mind map | `@startmindmap`, `*`, `**`, `***` |

## Essential patterns

### Sequence

```plantuml
actor User
participant API
User -> API: Submit request
activate API
API --> User: Result
deactivate API
```

### Class

```plantuml
hide circle
class Order {
  +id: UUID
  +total(): Decimal
}
class Item
Order "1" *-- "*" Item : contains
```

### Activity

```plantuml
start
:Validate request;
if (Valid?) then (yes)
  :Process request;
else (no)
  :Reject request;
endif
stop
```

### Use case

```plantuml
left to right direction
actor Customer
rectangle Store {
  usecase "Place order" as PlaceOrder
}
Customer --> PlaceOrder
```

### State

```plantuml
[*] --> Draft
Draft --> Published : approve
Published --> Archived : retire
```

Use text stereotypes for interface, abstract, and enumeration classifiers:
`interface Gateway <<interface>>`, `abstract class Entity`, and `enum Status
<<enumeration>>`. With `hide circle`, the explicit stereotypes are required:
PlantUML otherwise may render only italic interface names and omit the semantic
label. Model value objects as `class Money <<dataType>>`; use `<<primitive>>`
only for atomic value types. An ordinary class needs no `<<class>>` stereotype.

```plantuml
hide circle
interface PaymentGateway <<interface>> {
  +authorize(amount: Money): PaymentStatus
}
class Money <<dataType>> {
  +amount: Decimal
}
class Weight <<primitive>>
enum PaymentStatus <<enumeration>> {
  Pending
  Approved
  Declined
}
class CardPayment
CardPayment ..|> PaymentGateway
```
