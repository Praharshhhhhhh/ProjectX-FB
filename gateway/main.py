import uvicorn
from api import app
from network.wg import WireGuardManager

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    wg = WireGuardManager()
    wg.ensure_interface()

    uvicorn.run(app, host="0.0.0.0", port=8080)
