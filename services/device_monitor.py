from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import SessionLocal
# pyrefly: ignore [missing-import]
from models import Device, DeviceStatus
# pyrefly: ignore [missing-import]
from services.zerotier_controller import check_member_status
# pyrefly: ignore [missing-import]
# wireguard_controller no longer exposes check_peer_status
import asyncio
import logging

logger = logging.getLogger(__name__)


async def refresh_device_statuses():
    db: Session = SessionLocal()
    try:
        devices = db.query(Device).filter(Device.is_approved == True).all()
        for device in devices:
            # For wireguard: must have wg_public_key
            if device.tunnel_type == "wireguard" and device.wg_public_key:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                if device.updated_at and (now - device.updated_at) < timedelta(seconds=45):
                    if device.status != DeviceStatus.active:
                        device.status = DeviceStatus.active
                    continue

                from routers.devices import LIVE_WG_STATUSES
                import time
                last_handshake = LIVE_WG_STATUSES.get(device.wg_public_key, 0)
                status_str = "active" if last_handshake > 0 and (time.time() - last_handshake) < 180 else "offline"
                new_status = DeviceStatus(status_str)
                if device.status != new_status:
                    device.status = new_status
            # For zerotier: must have network_id and zerotier_node_id
            elif device.tunnel_type == "zerotier" and device.network_id and device.zerotier_node_id:
                # If the device has sent a heartbeat recently (within 2 minutes),
                # mark/keep it active and bypass the ZeroTier controller check.
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                if device.updated_at and (now - device.updated_at) < timedelta(seconds=45):
                    if device.status != DeviceStatus.active:
                        device.status = DeviceStatus.active
                    continue

                status_str = await check_member_status(device.network_id, device.zerotier_node_id)
                new_status = DeviceStatus(status_str)
                if device.status != new_status:
                    device.status = new_status
        db.commit()
    except Exception as e:
        logger.error(f"Device monitor error: {e}")
    finally:
        db.close()


async def run_monitor_loop(interval: int = 5):
    while True:
        await refresh_device_statuses()
        await asyncio.sleep(interval)
