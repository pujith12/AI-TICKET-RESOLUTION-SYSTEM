# System Performance Troubleshooting Guide

This guide outlines steps to diagnose and resolve an application or system that is running slowly.

## Phase 1: Preparation & Information Gathering
Before taking action, establish the scope and context of the issue.

*   **Define the Problem:** Is it a global issue (all users) or localized? Is it constant, or does it happen during specific times/tasks?
*   **Establish a Baseline:** What has changed recently? (deployments, configuration updates)
*   **Gather Data:** Check application logs for errors or timeouts.

## Phase 2: Diagnostics
Determine where the bottleneck is occurring.

1.  **Client-Side:** Check if the browser is using high CPU or memory. Check network requests in developer tools.
2.  **Network/Load Balancer:** Check network latency and load balancer health.
3.  **Application Server:** Check CPU and memory usage on the server. Inspect threaded processes and memory limits.
4.  **Database:** Look for slow-running queries, high I/O, or database lock contentions.

## Phase 3: Common Mitigations
*   **Restart Applications:** Process restarts can clear memory leaks temporarily.
*   **Increase Resources:** Allocate more RAM or CPU to the specific service experiencing bottlenecks.
*   **Clear Caches:** Invalidate cache stores if they are overloaded or corrupted.
