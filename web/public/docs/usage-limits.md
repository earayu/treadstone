# Usage & Limits

Every time a sandbox is running, it consumes Compute Units (CU). Your plan comes with a monthly CU budget. When the budget is exhausted, new sandboxes cannot start until the next billing period or until you upgrade.

## What Is a Compute Unit?

A Compute Unit is a measure of compute resources consumed over time. The rate depends on the template you choose — larger templates burn CU faster.

The unit is **CU-hours (CU-h)**: one CU-h is one Compute Unit running for one hour.

| Template | CPU | Memory | CU/h |
|---|---|---|---|
| `aio-sandbox-tiny` | 0.25 core | 1 GiB | **0.25** |
| `aio-sandbox-small` | 0.5 core | 2 GiB | **0.5** |
| `aio-sandbox-medium` | 1 core | 4 GiB | **1.0** |
| `aio-sandbox-large` | 2 cores | 8 GiB | **2.0** |
| `aio-sandbox-xlarge` | 4 cores | 16 GiB | **4.0** |

A sandbox only consumes CU while it is in the **running** state. A stopped or deleted sandbox does not burn compute.

## How the Budget Works

Each plan includes a fixed number of CU-hours per month plus a persistent storage quota:

| Plan | CU-h / month | Persistent storage quota | Concurrent sandboxes | Max auto-stop setting |
|---|---:|---:|---:|---|
| Free | 10 | 0 GiB | 1 | up to 2 hr |
| Pro | 180 | 20 GiB | 5 | Never allowed |
| Ultra | 480 | 60 GiB | 15 | Never allowed |
| Custom | 1800 | 200 GiB | 50 | Never allowed |

**Example**: running an `aio-sandbox-tiny` (0.25 CU/h) for 8 hours costs 2 CU-h. On the Free plan that leaves 8 CU-h for the rest of the month.

Persistent storage quota is the total hot disk you can keep attached across your persistent sandboxes. Stopped sandboxes do not burn compute, but their attached disks still count against storage quota until deleted or moved out of hot storage.

## Controlling Consumption

The most effective lever is `--auto-stop-interval`. New sandboxes default to **60 minutes**. A sandbox automatically stops after this many minutes of inactivity, so it stops consuming CU even if you forget to stop it manually.

```bash
# Stop automatically after 60 minutes of inactivity
$ treadstone sandboxes create --template aio-sandbox-tiny --name demo --auto-stop-interval 60
```

Free users can configure auto-stop up to 2 hours. Pro, Ultra, and Custom can set `0` (`Never`) when they want long-running agents or persistent personal dev hosts.

Use `--auto-delete-interval -1` (the default) to keep the sandbox around after it stops so you can restart it later without losing state.

## Checking Your Balance

The Console at [/app/usage](/app/usage) shows a live breakdown of your CU consumption for the current billing period.

From the CLI:

```bash
$ curl -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  https://api.treadstone-ai.dev/v1/usage
```

The response includes `compute.total_remaining` (CU-h left) and `limits.current_running` (sandboxes currently consuming compute).

## When You Hit a Limit

- **Compute quota exhausted** — wait for the next billing period to reset, or upgrade your plan.
- **Concurrent limit reached** — stop one running sandbox before creating or starting another.
- **Template not allowed on your plan** — `aio-sandbox-large` and above require Pro or higher.

## Read Next

- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
- [Error Reference](/docs/error-reference.md)
