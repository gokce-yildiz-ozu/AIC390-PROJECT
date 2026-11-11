# Use case preference form (handbook Appendix C)

Submitted once per team in the first session. The instructor assigns one use case per team; no two teams share one.

| Choice | Use case | Why this one? (one sentence) |
|---|---|---|
| 1st | UC3 Property management assistant | Tenants must only ever see their own unit, so we can enforce access control in both retrieval and tools and measure leakage directly, and its tasks (repair tickets, contractor bookings, rent status) have exact expected end states we can test. |
| 2nd | UC5 HR helpdesk assistant | It poses the same access-control problem with country- and contract-specific policies, and leave-day calculations must come from a tool, which makes correctness measurable. |
| 3rd | UC7 IT helpdesk for small businesses | Error codes such as 0x80070005 make keyword search essential, so the gap between BM25, dense and hybrid retrieval is directly measurable, and the identity check for password resets can be enforced in code. |

**Intended first customer for UC3:** a property management company in Istanbul that runs three residential blocks
(about 120 units) and today handles tenant requests by phone and messaging apps.

| Team member | Student ID | Planned role |
|---|---|---|
| Serap Gökçe Yıldız | S028899 | Evaluation and safety lead |
| Enes Kemal Köylü | TBD | TBD |
| Mert Bozma | TBD | TBD |

**Domain experience (optional):** Serap Gökçe Yıldız did an AI internship at Turkcell and, at Akbank, built a
semantic analysis demo that classifies customer service conversations, which is directly relevant to the request
classifier and support workflows in all three choices.
