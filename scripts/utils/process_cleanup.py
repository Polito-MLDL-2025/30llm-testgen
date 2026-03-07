import multiprocessing
import os
import signal
import time

try:
    import psutil
except ImportError:
    psutil = None


def kill_descendant_processes_sigkill(
    grace_seconds: float = 5.0,
    force_kill_seconds: float = 2.0,
) -> None:
    """
    Force kill all descendant processes of the current process using SIGKILL.
    """
    print("\nStopping child processes...", flush=True)
    cleaned = False

    if psutil is not None:
        try:
            current = psutil.Process(os.getpid())
            descendants = [proc for proc in current.children(recursive=True) if proc.pid != os.getpid()]
        except Exception as exc:
            print(f"Failed to inspect descendant processes via psutil: {exc}", flush=True)
            descendants = []

        if descendants:
            cleaned = True
            print(f"Found {len(descendants)} descendant process(es). Sending SIGKILL...", flush=True)
            for proc in descendants:
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    continue
                except Exception as exc:
                    print(f"Failed to kill pid {proc.pid}: {exc}", flush=True)

            _, alive = psutil.wait_procs(descendants, timeout=grace_seconds)
            if alive:
                print(f"Retrying SIGKILL for {len(alive)} remaining process(es)...", flush=True)
                for proc in alive:
                    try:
                        proc.kill()
                    except psutil.NoSuchProcess:
                        continue
                    except Exception as exc:
                        print(f"Failed to kill pid {proc.pid}: {exc}", flush=True)
                psutil.wait_procs(alive, timeout=force_kill_seconds)

    # Fallback and extra safety for multiprocessing children
    try:
        mp_children = multiprocessing.active_children()
    except Exception:
        mp_children = []

    if mp_children:
        cleaned = True
        print(f"Force killing {len(mp_children)} multiprocessing child(ren)...", flush=True)
        for child in mp_children:
            try:
                if child.is_alive():
                    if hasattr(child, "kill"):
                        child.kill()
                    else:
                        os.kill(child.pid, signal.SIGKILL)
            except Exception:
                continue

        deadline = time.monotonic() + grace_seconds
        for child in mp_children:
            try:
                remaining = max(0.0, deadline - time.monotonic())
                child.join(timeout=remaining)
            except Exception:
                continue

        for child in mp_children:
            try:
                if child.is_alive():
                    os.kill(child.pid, signal.SIGKILL)
                    child.join(timeout=force_kill_seconds)
            except Exception:
                continue

    if not cleaned:
        print("No active child processes detected.", flush=True)
