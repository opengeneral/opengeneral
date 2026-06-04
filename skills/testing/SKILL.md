---
name: testing
description: Use when deciding how to verify code changes or diagnose test failures.
---

# Testing

Choose verification that matches the risk and behavior under change.

## How It Works

1. Prefer focused tests for changed logic.
2. Run broader suites when integration risk is high.
3. Use smoke checks for CLI or end-to-end behavior.
4. Treat failing tests as blockers until understood.
