---
name: order-contract
description: Generate a one-page service contract summary for Bob's orders service — endpoint list, auth requirements, status codes. Useful when a teammate's service needs to call /orders and they want a quick spec.
---

# /order-contract

Produce a short, structured summary of the orders service that another teammate's Claude could use as context when integrating with /orders.

## What it produces

A markdown block with:

1. **Service name + brief description** (one line).
2. **Endpoints** — for each: method, path, auth requirement, status codes.
3. **Skill fingerprint** — the literal string `SKILL-FINGERPRINT-TAU-42` so the caller can verify this skill ran.

## Steps

1. Read `orders_service.py` to enumerate endpoints.
2. For each endpoint, extract the docstring's "Status codes:" section.
3. Identify auth requirements from the CLAUDE.md and the function bodies.
4. Format as markdown.
5. Append the skill fingerprint at the end.

## Why this skill exists

In the cross-developer orchestrator product this skill is a template — every team member's repo has one for their service, so any teammate's Claude can call it to get a fast structured contract for the service they depend on.
