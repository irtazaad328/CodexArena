# 📝 CodexArena — Lablab.ai Hackathon Submission Statements

## Basic Information
- **Project Title:** CodexArena
- **Tagline:** Autonomous Adversarial Chaos & Self-Healing Engine for Mission-Critical Microservices
- **Category / Tags:** Cybersecurity, Autonomous Agents, Microservices, Chaos Engineering, FastMCP, IBM Bob
- **Repository:** https://github.com/irtazaad328/CodexArena

---

## 1. Problem & Solution Statement
*(Word count: ~310 words | Limit: 500 words)*

### The Problem
Modern software testing is broken where it matters most. Teams write thousands of unit tests and rely on CI/CD linters, but these only test predictable, single-threaded happy paths. They almost never catch real-world concurrency bugs, race conditions, negative amount drains, or transaction replay exploits. These vulnerabilities only emerge under live multi-threaded load or deliberate adversarial attacks. When they slip through to production, the consequences are catastrophic—from massive financial double-spending to multi-billion-dollar global outages like CrowdStrike. Developers only find out when systems crash and user balances are already corrupted.

### The Solution — CodexArena
We built CodexArena: an autonomous adversarial chaos and self-healing engine for microservices. Instead of hoping code survives production, CodexArena puts it into an active digital colosseum before deployment.

The architecture introduces an autonomous dual-agent arena:
1. **Red Agent (Adversarial Attacker):** Launches multi-vector stress simulations (such as TOCTOU concurrency bursts, negative drain probes, self-transfer loops, and idempotency replay attacks) directly against target services and standalone Python files.
2. **Blue Agent (Self-Healing Engineer):** Intercepts real-time crash telemetry, identifies the root cause (such as non-atomic database reads), synthesizes precision hot-patches (like single-statement atomic row locks and invariant guards), patches the files on disk, and immediately re-triggers the attack to mathematically prove immunity.

Everything is monitored in real-time through a dark-mode **Cyber War-Room HUD** featuring live combat event logs, a dynamic 0–100% Resilience Gauge, and a tamper-proof cryptographic **Resilience Certificate** complete with SHA-256 integrity hashes.

Developers can simply drop any Python microservice into the targets/ folder and watch CodexArena autonomously hunt vulnerabilities, patch them on disk, and certify 100% resilience with zero manual intervention.

---

## 2. IBM Bob Usage Statement
*(Word count: ~295 words | Limit: 500 words)*

### How We Leveraged IBM Bob
In CodexArena, IBM Bob wasn't just treated as a passive chat assistant for boilerplate code—Bob acted as the central autonomous operator and orchestrator driving the entire self-healing loop.

We connected IBM Bob directly to our engine using the **Model Context Protocol (FastMCP)** over standard I/O via .bob/mcp.json. Through five custom MCP tools, Bob commanded the end-to-end chaos lifecycle:

1. launch_arena_battle: Bob deployed the Red Agent against target services to simulate live hostile traffic.
2. get_crash_telemetry: When an exploit succeeded, Bob retrieved high-fidelity crash dumps, tracking balance drift, corrupted account states, and exploit traces.
3. apply_hot_patch: Bob evaluated the telemetry, determined the exact vulnerability vector (e.g., separating balance check from update in SQLite), and instructed the Blue Agent to synthesize atomic-level fixes.
4. verify_resilience: Bob commanded an immediate secondary assault to confirm that the vulnerability was permanently closed and resilience scored 100%.
5. export_resilience_certificate: Bob sealed the battle record into an auditable, cryptographically verifiable certificate.

### Task Execution & Productivity
In our recorded workspace session (Task ID: 4d6a28e9ae59ca148f27c3d07811d1b3), IBM Bob maintained high reasoning accuracy across **242.8k context tokens** and executed **25/25 multi-step implementation tasks** without losing state. Bob helped design the asynchronous event architecture between FastAPI, Server-Sent Events (SSE), and the hot-patching engine, while ensuring target file modifications remained non-destructive.

Bob proved that AI agents can move beyond writing simple functions to becoming proactive cyber-resilience partners that actively break, fix, and certify mission-critical systems.
