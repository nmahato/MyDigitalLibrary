import os
import sys

# Make `app` importable regardless of the current working directory
# (IIS HttpPlatformHandler starts us with cwd = the site's physical path).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    # HTTP_PLATFORM_PORT is injected by IIS HttpPlatformHandler; fall back to our own.
    port = int(
        os.environ.get("HTTP_PLATFORM_PORT")
        or os.environ.get("IMAGEVIEWER_PORT", "8077")
    )
    host = os.environ.get("IMAGEVIEWER_HOST", "127.0.0.1")
    reload = bool(os.environ.get("DEV"))

    # Opt-in remote debugging: set DEBUGPY=1 and use the
    # "Backend: attach to running process" launch config (port 5678).
    if os.environ.get("DEBUGPY") and not reload:
        import debugpy

        debugpy.listen(("127.0.0.1", 5678))
        if os.environ.get("DEBUGPY_WAIT"):
            print("debugpy: waiting for the debugger to attach on :5678 ...")
            debugpy.wait_for_client()

    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
