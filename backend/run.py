import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("IMAGEVIEWER_PORT", "8077"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=bool(os.environ.get("DEV")))
