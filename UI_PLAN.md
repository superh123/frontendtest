# Economy God Mode UI Plan

This is the agreed UI direction for the hackathon. The frontend turns the backend’s economic simulation into an experience a judge can understand and explore.

The core story is: **healthy economy → bank shock → cascading consequences → AI intervention → compare futures.**

## Product direction

Build a dark, polished financial command center with an animated city as the main visual. Prioritize a clear end-to-end demo, readable financial information, and inspectable agent decisions.

The backend calculates balances, transactions, economic metrics, defaults, intervention outcomes, and action statuses. Frontend visuals reflect those results.

## 1. Main screen: the living economy

Use a large city view in the center. Buildings represent businesses and banks; residential districts can group households.

- Show economic activity and financial stress with color and subtle animation. Include labels or icons so color is not the only signal.
- Display payment events as brief flows between buildings.
- Open financial details when a building is clicked.
- Start with simple shapes or an isometric illustration; keep the city readable.

Place simulation controls across the top: **Create World, Play/Pause, Speed, Reset**, and the current simulation tick.

Show a compact metrics strip with **Employment, Household Cash, Business Defaults, Bank Stress, and Public Intervention Cost**. Keep units and definitions consistent across views.

## 2. Crisis controls

Provide a visible **Trigger Crisis** panel where the user selects a bank and applies an asset-loss shock. Default to the demo scenario: a **40% loss in one asset category**.

After the shock, show a live event feed explaining the chain of consequences. For example:

> Bank 2 suffers an asset loss → lending contracts → Café 14 cannot refinance → payroll is missed.

This is an illustrative sequence; show it only when the backend produces the corresponding events. Events should be clickable so users can inspect the institution involved.

## 3. Institution and agent inspector

Open a right-side drawer when the user selects a household, business, or bank.

Show:

- Cash, assets, debt, and obligations.
- Employer, bank, borrowers, or suppliers as appropriate.
- Recent transactions.
- For AI agents: observations, proposed action, explanation, validation result, and settlement status.

This view lets judges trace visible outcomes to financial transactions and agent actions.

## 4. Financial network view

Provide a **City / Network** toggle.

The network shows banks and businesses connected by loans, obligations, and payments. Selecting a node highlights its counterparties. Selecting a connection shows its exposure amount. Defaults visibly affect connected institutions according to backend events.

Keep the selected institution and simulation state consistent when switching between city and network views.

## 5. Fork Reality

Make **Fork Reality** a prominent action. It opens three futures calculated from the same starting state:

| Branch | Intervention |
| --- | --- |
| No intervention | Let the crisis unfold. |
| Emergency bank lending | Support bank liquidity. |
| Direct household support | Support household spending. |

Each branch shows matching charts for employment, defaults, bank stress, and intervention cost, with a synchronized timeline and consistent chart scales.

Include the AI central bank’s recommendation and a short explanation of the tradeoff. Present the actual calculated outcomes, including cases where an intervention performs poorly.

The initial scope is these three branches. Additional branches can be added after the core comparison works.

## 6. Agentic payment demo

Inside the business inspector, support one clear workflow:

**Café needs inventory → two supplier offers → agent selects terms → backend validates → payment settles → future obligation appears.**

A compact sequential activity card is enough. Show whether each action is proposed, approved, rejected, or settled, using backend status values. Display relevant offer terms, payment amounts, and future obligations.

## Build order

1. Main layout, simulation controls, metrics, and clickable institutions.
2. Live events and institution/agent inspector.
3. Crisis trigger and visible consequences.
4. Fork Reality comparison.
5. Network view and payment workflow polish.

Build against mock data initially, then connect the backend API and live events. Mock data should use the agreed backend response shapes and remain clearly identified during development.

## Frontend and backend agreement

Agree early on world state, institution identifiers, metrics, events, and action statuses. The frontend needs:

- World creation, play/pause, speed, and reset controls.
- Current state and institution detail responses.
- A crisis trigger accepting a bank, asset category, and loss percentage.
- A live event stream with simulation ID, tick, event ordering, involved institutions, and applicable amounts.
- Branch creation and comparison results from a shared snapshot.
- Agent decision traces, offers, contracts, and settlement results.

Display money with currency units; backend monetary values use integer cents. Handle loading, empty, disconnected, and failed-action states. Refresh authoritative state after reconnecting.

## Demo acceptance criteria

A judge can complete the following without opening a terminal:

1. Create and run a healthy world.
2. Trigger a bank crisis.
3. Watch consequences and inspect why a business is struggling.
4. Inspect an agent’s decision and payment workflow.
5. Watch the AI test interventions.
6. Compare three futures and understand the recommendation and its cost.

## Scope guardrail

Keep the city, financial network, Fork Reality, and agent inspector focused on the same simulation. Finish the complete crisis-to-intervention demo before expanding into additional screens or sponsor-specific UI.

The project concept and engineering strategy remain documented in [the original engineering plan](./ECONOMY%20GOD%20MODE%20%E2%80%94%20Detailed%20Engineering%20%26%20Track%20Strategy.docx).
