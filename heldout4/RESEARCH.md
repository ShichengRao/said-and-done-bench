# Public workflow grounding

Research completed before task writing on October 29, 2026 (America/Chicago). Every company, operational policy, event, and customer record in the tasks is fictional. These are engineering applications of documented workflows; they are not claims that named customers deployed these exact applications.

- [Reflection — Introducing Beam](https://reflection.ai/blog/introducing-beam): coding, reasoning, and agentic workloads.
- [Reflection — Beam is now available](https://reflection.ai/blog/beam-is-available): repository agents, code review, integrations, and hosted or private deployment.
- [Reflection Developer Docs — Mirror CLI overview](https://developers.reflection.ai/mirror-overview): repository inspection, editing, command execution, and user permissions.
- [Reflection Developer Docs — Mirror connections and MCP servers](https://developers.reflection.ai/mirror-mcp): enterprise issue/search/observability connections, connection-specific authorization, and scoped tools. Grounds fictional tenant data, audit ingestion, and connector access tasks.
- [Reflection Developer Docs — Serving in production with Kubernetes](https://developers.reflection.ai/serving-kubernetes): on-prem deployments with shared storage, replica placement, verification, and separate production gateway/redundancy configuration. Grounds deployment and recovery tasks.
- [Reflection Developer Docs — Beam Verifier](https://developers.reflection.ai/beam-verifier): protocol and serving validation. Grounds release and production conformance evidence.
- [Reflection Developer Docs — Streaming](https://developers.reflection.ai/streaming): incremental event streams and terminal usage. Grounds fictional metering reconciliation.
- [Reflection Developer Docs — Tool calling](https://developers.reflection.ai/tool-calling): validated arguments and tool-call/result association. Grounds fictional transactional refund and retry workflows.
- [Reflection Developer Docs — Beam Responsible Use Guide](https://developers.reflection.ai/responsible-use-guide): enterprise retrieval and CRM/ticket automation with access, change, spending, and data controls. Grounds fictional finance, migration, and customer-data workflows.
- [Reflection — Beam Safety Technical Report](https://reflection.ai/beam-safety-report): the Andon Labs vending pilot covers procurement, pricing, inventory, suppliers, and spending constraints. It is an operational pilot, not a general enterprise case study.
- [Dell — Build, Reason and Act with Reflection Beam on Dell AI Factory](https://www.dell.com/en-us/blog/build-reason-and-act-with-reflection-beam-on-dell-ai-factory/): on-prem enterprise deployment and planned governed enterprise-data/tool architecture. Planned capabilities are not represented as shipped customer behavior.

No public named enterprise billing or migration case study was found. Billing and migration tasks are explicitly fictional extrapolations. Source titles appear without URLs in individual task.toml comment blocks as required by the brief.

## Calibration model identity

The existing deepseek-v3 configuration resolves to deepseek/deepseek-chat through OpenRouter with StreamLake pinned and provider fallbacks disabled. OpenRouter’s [DeepSeek V3 listing](https://openrouter.ai/deepseek/deepseek-chat), checked during this round, identifies this model as the December 26, 2024 release. Actual response model/provider identifiers and usage are retained in this round’s run records.
