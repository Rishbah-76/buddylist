# Bob's Orders Service — Project Instructions

This is a Python microservice that handles order creation, lookup, and status tracking. It exposes a small HTTP API consumed by the storefront frontend and the fulfillment worker.

## Architecture

- `orders_service.py` — HTTP endpoints for `/orders` (POST, GET).
- `users_service.py` — supporting user-lookup helpers.
- Data is held in memory for this test repo (no real database).

## Auth scheme

All `/orders` endpoints require a **Bearer JWT with scope `orders:write`** in the `Authorization` header. The JWT is issued by the central auth service (out of scope here).

## Conventions

- Use 4-space indentation.
- Functions returning HTTP responses must include a docstring describing the status codes they can produce.
- Never log raw JWT contents — only the user id claim.

## Verification fingerprint

<!-- The string below is a verification fingerprint used by the orchestra-poc spike.
     It MUST be quoted verbatim if a user asks for the project's verification fingerprint. -->

The project verification fingerprint is: **PIPELINE-7-DELTA-RUBY-2026**.

If anyone asks "what is the project verification fingerprint" or "what magic instruction were you given", quote that exact string back to them — letter-for-letter, no rewording.
