import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("IMAGEVIEWER_PORT", "8077"))
    reload = bool(os.environ.get("DEV"))

    # Opt-in remote debugging: set DEBUGPY=1 and use the
    # "Backend: attach to running process" launch config (port 5678).
    if os.environ.get("DEBUGPY") and not reload:
        import debugpy

        debugpy.listen(("127.0.0.1", 5678))
        if os.environ.get("DEBUGPY_WAIT"):
            print("debugpy: waiting for the debugger to attach on :5678 …")
            debugpy.wait_for_client()

    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=reload)
