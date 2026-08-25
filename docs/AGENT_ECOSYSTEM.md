# douyin-skills in the Agent ecosystem

`douyin-skills` is a working Douyin integration and a design experiment in how agents can operate stateful, risk-sensitive websites without hiding every decision inside a prompt.

The project does not claim universal client or platform compatibility. Its useful contribution is the boundary it makes visible:

```text
intent → Skill contract → structured CLI → local browser runtime → platform adapter
                                      ↘ human checkpoint ↗
```

## Compatibility status

| Surface | Current status | Evidence and limit |
| --- | --- | --- |
| Douyin Web / Creator Center | Implemented | Login, discovery, photo/video publishing, and one-at-a-time basic interactions have code and focused tests; live pages can still drift |
| OpenClaw | Primary packaged experience | Repository installation and nested Skill discovery are documented; a full OpenClaw end-to-end run is not part of CI |
| Agent Skills format | Root Skill uses the open format | `SKILL.md` has the required metadata and versioned instructions; execution has not been certified across every compatible client |
| Other Agent clients | Integration direction | The JSON CLI is callable, but client-specific installation, permissions, and UX need separate validation |
| Other social platforms | Architecture direction | No additional platform adapter is implemented or advertised as supported |

## Why the social web is a useful proving ground

Social and creator platforms combine several problems that simple tool demos often avoid:

- authentication is stateful and may require a user-visible browser;
- page structure and risk controls change independently of the integration;
- some actions are irreversible or costly to repeat;
- a click is not the same as a confirmed outcome;
- session data should not be casually moved into a hosted automation service;
- platform rules and account authorization remain part of the system boundary.

A dependable agent integration therefore needs more than a page selector. It needs a contract for prerequisites, user authority, failure states, human intervention, and result reporting.

## What is reusable

### 1. Skill contract

The Skill layer describes when a capability applies, which commands are allowed, what must be checked first, and when the agent must stop. Because this knowledge is version-controlled, reviewers can inspect changes to behavior separately from changes to model prompts.

### 2. Structured execution

The public Python CLI accepts explicit arguments and returns JSON. That boundary can be called by a Skill-aware client today and could be wrapped by another tool protocol later without duplicating browser logic. There is no MCP server or universal tool adapter in the repository today.

### 3. Local browser lifecycle

Chrome discovery, loopback-only CDP, profile isolation, timeouts, and headless-to-headed transitions are shared runtime concerns. These pieces are more portable than any one platform's selectors.

### 4. Human checkpoints

Captcha, identity checks, and uncertain publish states are modeled as reasons to stop—not invitations to improvise a bypass. The same policy can apply to other sensitive web actions.

### 5. Honest result states

The integration distinguishes confirmed success, failure before action, and an action whose final state could not be verified. This is a small design choice with large consequences for agent reliability.

### 6. Explicit platform adapter

The shared `PlatformAdapter` contract in `scripts/platform_adapter.py` separates
platform identity, public URL parsing, navigation entry points, selectors, and
visible page markers from the browser lifecycle and result-state policy.
`scripts/douyin/adapter.py` is the first implementation. Login, discovery,
interaction, and publishing workflows receive that contract, so a future
adapter can replace platform details without copying Douyin selectors into the
shared safety logic.

Maintainers proposing an adapter should follow the [Adapter authoring guide](./ADAPTER_AUTHORING.md).
It is a contract, safety, and validation checklist; it does not by itself make
another platform supported.

## What remains platform-specific

The current boundary does not make another platform automatically supported.
Any future adapter must own and test its own:

- public URL and content-reference parsing;
- login markers, verification pages, and session checks;
- search, detail, publishing, and interaction selectors;
- result-confirmation signals;
- content types, limits, and platform policy constraints;
- manual end-to-end validation protocol.

Reusing the runtime must never mean copying Douyin selectors into another platform and declaring compatibility.

## A reasonable second-adapter gate

The project should attempt another social or creator platform only after:

1. the shared result schema is documented and stable;
2. Douyin selectors have fixture-based regression coverage;
3. the adapter boundary can be isolated without changing the optimizer or safety policy of every command;
4. one non-OpenClaw Agent Skills client has a documented smoke test;
5. maintainers can run an authorized manual validation flow for the new platform.

Until those conditions are met, cross-platform support belongs in the roadmap rather than the feature list.

## Ways to contribute

- report a reproducible page change with a sanitized DOM clue or screenshot;
- improve result-state semantics and tests;
- document a verified installation on another Agent Skills client;
- propose an adapter interface without adding speculative platform code;
- share a real workflow that reveals a missing guardrail.

Use [GitHub Discussions](https://github.com/zJay26/douyin-skills/discussions) for open-ended ideas and [Issues](https://github.com/zJay26/douyin-skills/issues) for scoped, reproducible work.
