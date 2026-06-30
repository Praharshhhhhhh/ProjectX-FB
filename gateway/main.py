import uvicorn
from api import app
from network.wg import WireGuardManager

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    wg = WireGuardManager()
    wg.ensure_interface()

    uvicorn.run(app, host="127.0.0.1", port=8080)
