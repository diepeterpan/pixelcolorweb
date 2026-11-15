import asyncio
import logging
from typing import Any, Dict, List, Optional
from bleak import BleakScanner
from pypixelcolor.client import AsyncClient
from pypixelcolor.commands.send_image import _build_send_plan, _resize_image, _process_loaded_bytes
from pypixelcolor.lib.constants import WRITE_UUID
from pypixelcolor.lib.transport.send_plan import SendPlan, _chunk_bytes
from .config_manager import config_manager
from .script_runner import script_manager

logger = logging.getLogger("BLEWorker")

class BLEWorker:
    def __init__(self):
        self.client: Optional[AsyncClient] = None
        self.connected: bool = False
        self.is_connecting: bool = False
        self.current_address: Optional[str] = None
        self._last_scan_rssi: Dict[str, int] = {}
        self._cached_adapter_info: Optional[Dict[str, str]] = None
        self._send_lock: asyncio.Lock = asyncio.Lock()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None
        self.last_status: Dict[str, Any] = {
            "connected": False,
            "address": None,
            "name": None,
            "status_msg": "Initializing",
            "ble_info": {
                "version": "BLE 4.2",
                "phy_speed": "1.0 Mbps (LE 1M + DLE)",
                "max_throughput": "~80-100 KB/s",
                "rssi": None,
                "signal_quality": "Offline",
                "mcu_version": None,
                "firmware_version": None
            }
        }

    async def start(self):
        logger.info("Starting BLE background worker...")
        self.worker_task = asyncio.create_task(self._process_queue())
        self.reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self):
        """
        Background daemon that continuously checks connection health and
        auto-reconnects every 15 seconds if configured device is disconnected.
        """
        while True:
            try:
                cfg = config_manager.get()
                dev_cfg = cfg.get("device", {})
                target_addr = dev_cfg.get("address")
                auto_conn = dev_cfg.get("auto_connect", True)

                if auto_conn and target_addr and not self.connected and not self.is_connecting:
                    logger.info(f"[BLEWorker] Auto-reconnecting to configured device: {target_addr}...")
                    await self.connect_device(target_addr, dev_cfg.get("name"))

            except Exception as e:
                logger.error(f"[BLEWorker] Reconnect loop error: {e}")

            await asyncio.sleep(15)

    async def scan_devices(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        logger.info(f"Scanning for Bluetooth devices ({timeout}s) with advertisement data...")
        found_devices = []
        try:
            # discover with return_adv=True captures real local_name and accurate rssi
            discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
            for addr, (d, adv) in discovered.items():
                name = d.name or adv.local_name or "Unknown Device"
                uuids = [u.lower() for u in (adv.service_uuids or [])]
                
                # Highlight compatible matrices based on name and known service UUIDs
                is_pixel = any(k in name.lower() for k in ["pixel", "led", "matrix", "bglight", "bk", "ble"]) \
                           or any("fa02" in u or "fa03" in u or "5a01" in u for u in uuids)

                rssi_val = adv.rssi if adv.rssi is not None else 0
                if addr:
                    self._last_scan_rssi[addr.upper()] = rssi_val
                found_devices.append({
                    "address": addr,
                    "name": name,
                    "rssi": rssi_val,
                    "recommended": is_pixel,
                    "service_uuids": adv.service_uuids or []
                })
        except Exception as e:
            logger.error(f"Error scanning BLE devices: {e}")

        # Sort recommended first, then strongest RSSI signal
        return sorted(found_devices, key=lambda x: (not x["recommended"], -x["rssi"]))

    async def _query_adapter_info(self) -> Dict[str, str]:
        if self._cached_adapter_info:
            return self._cached_adapter_info
        try:
            import dbus_fast.aio
            from dbus_fast import Message, BusType
            bus = await dbus_fast.aio.MessageBus(bus_type=BusType.SYSTEM).connect()
            msg = Message(
                destination='org.bluez',
                path='/org/bluez/hci0',
                interface='org.freedesktop.DBus.Properties',
                member='GetAll',
                signature='s',
                body=['org.bluez.Adapter1']
            )
            reply = await bus.call(msg)
            ver = reply.body[0].get('Version')
            ver_val = ver.value if ver else 8
            hci_map = {
                6: ('BLE 4.0', '1.0 Mbps (LE 1M)', '~30-40 KB/s'),
                7: ('BLE 4.1', '1.0 Mbps (LE 1M)', '~40-50 KB/s'),
                8: ('BLE 4.2', '1.0 Mbps (LE 1M + DLE)', '~80-100 KB/s'),
                9: ('BLE 5.0', '2.0 Mbps (LE 2M PHY)', '~150-180 KB/s'),
                10: ('BLE 5.1', '2.0 Mbps (LE 2M PHY)', '~150-180 KB/s'),
                11: ('BLE 5.2', '2.0 Mbps (LE 2M PHY)', '~150-180 KB/s'),
                12: ('BLE 5.3', '2.0 Mbps (LE 2M PHY)', '~150-180 KB/s'),
                13: ('BLE 5.4', '2.0 Mbps (LE 2M PHY)', '~150-180 KB/s')
            }
            b_ver, phy, max_tp = hci_map.get(ver_val, ('BLE 4.2', '1.0 Mbps (LE 1M + DLE)', '~80-100 KB/s'))
            self._cached_adapter_info = {
                "version": b_ver,
                "phy_speed": phy,
                "max_throughput": max_tp
            }
            return self._cached_adapter_info
        except Exception:
            return {
                "version": "BLE 4.2",
                "phy_speed": "1.0 Mbps (LE 1M + DLE)",
                "max_throughput": "~80-100 KB/s"
            }

    async def connect_device(self, address: str, name: Optional[str] = None) -> bool:
        if self.connected and self.current_address == address:
            return True

        if self.is_connecting:
            logger.warning("Connection attempt already in progress, skipping duplicate request.")
            return False

        self.is_connecting = True
        self.last_status["status_msg"] = f"Connecting to {name or address}..."
        try:
            if self.client:
                try:
                    await asyncio.wait_for(self.client.disconnect(), timeout=3.0)
                except Exception:
                    pass

            self.client = AsyncClient(address)
            # Guard with 8s timeout to avoid indefinite DBus freezes
            await asyncio.wait_for(self.client.connect(), timeout=8.0)
            device_info = self.client.get_device_info()
            
            # Check supported matrix resolution (Currently limited to 96x16)
            dev_w = getattr(device_info, "width", 96) if device_info else 96
            dev_h = getattr(device_info, "height", 16) if device_info else 16
            dev_type = getattr(device_info, "device_type", None)

            if (dev_w, dev_h) != (96, 16):
                err_msg = f"Unsupported display resolution {dev_w}x{dev_h} (Type byte: {dev_type}). Currently only 96x16 matrices are supported."
                logger.warning(err_msg)
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
                self.connected = False
                self.last_status = {
                    "connected": False,
                    "address": address,
                    "name": name,
                    "status_msg": err_msg
                }
                return False

            self.connected = True
            self.current_address = address

            # Prepare telemetry info
            adapter_info = await self._query_adapter_info()
            scan_rssi = self._last_scan_rssi.get(address.upper())
            if scan_rssi:
                if scan_rssi >= -60:
                    sig_label = f"{scan_rssi} dBm (Excellent)"
                elif scan_rssi >= -75:
                    sig_label = f"{scan_rssi} dBm (Good)"
                elif scan_rssi >= -85:
                    sig_label = f"{scan_rssi} dBm (Fair)"
                else:
                    sig_label = f"{scan_rssi} dBm (Weak)"
            else:
                sig_label = "Connected (Active)"

            mcu_v = getattr(device_info, "mcu_version", "1.0") if device_info else "1.0"
            wifi_v = getattr(device_info, "wifi_version", "1.0") if device_info else "1.0"

            self.last_status = {
                "connected": True,
                "address": address,
                "name": name or "PixelColor Display",
                "status_msg": "Connected",
                "ble_info": {
                    "version": adapter_info["version"],
                    "phy_speed": adapter_info["phy_speed"],
                    "max_throughput": adapter_info["max_throughput"],
                    "rssi": scan_rssi,
                    "signal_quality": sig_label,
                    "mcu_version": f"v{mcu_v} ({dev_w}x{dev_h})",
                    "firmware_version": f"v{wifi_v}"
                }
            }
            config_manager.update({
                "device": {
                    "address": address,
                    "name": name or "PixelColor Display",
                    "connected": True
                }
            })
            logger.info(f"Successfully connected to BLE device: {address}")
            
            # Auto sync initial brightness & orientation from config
            cfg = config_manager.get()
            matrix_cfg = cfg.get("matrix", {})
            await self.set_brightness(matrix_cfg.get("brightness", 80))
            await self.set_power(matrix_cfg.get("power", True))
            await self.set_orientation(matrix_cfg.get("orientation", 0))
            
            # Apply configured startup mode
            await self.apply_current_mode()
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Connection to BLE device {address} timed out (display might be offline/asleep).")
            self.connected = False
            self.last_status = {
                "connected": False,
                "address": address,
                "name": name,
                "status_msg": "Device unreachable (timed out)"
            }
            return False
        except Exception as e:
            logger.error(f"Failed to connect to BLE device {address}: {e}")
            self.connected = False
            self.last_status = {
                "connected": False,
                "address": address,
                "name": name,
                "status_msg": f"Offline ({str(e)})"
            }
            return False
        finally:
            self.is_connecting = False

    async def disconnect(self):
        if self.client:
            try:
                await asyncio.wait_for(self.client.disconnect(), timeout=3.0)
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
        self.connected = False
        self.current_address = None
        self.last_status["connected"] = False
        self.last_status["status_msg"] = "Disconnected"

    async def apply_current_mode(self):
        cfg = config_manager.get()
        mode = cfg.get("mode", "image")
        logger.info(f"Applying startup mode: {mode}")
        if mode == "image":
            img_file = cfg.get("active_image")
            if img_file:
                from pathlib import Path
                p = Path(img_file)
                if not p.is_absolute():
                    p = Path("data/uploads") / img_file
                if p.exists():
                    await self.send_image(str(p))

    async def send_text(
        self,
        text: str,
        color: str = "#FFFFFF",
        bg_color: Optional[str] = None,
        rainbow_mode: int = 0,
        animation: int = 1,
        speed: int = 80,
        font: str = "UNIFONT"
    ):
        if not self.connected or not self.client:
            logger.warning("Cannot send text: Not connected to BLE device.")
            return False
        clean_color = color.lstrip("#") if color else "FFFFFF"
        clean_bg = bg_color.lstrip("#") if bg_color and bg_color != "transparent" else None
        
        try:
            await self.client.send_text(
                text=text,
                color=clean_color,
                bg_color=clean_bg,
                rainbow_mode=rainbow_mode,
                animation=animation,
                speed=speed,
                font=font
            )
            return True
        except Exception as e:
            logger.error(f"Error sending text to matrix: {e}")
            return False

    async def _send_plan_fast(self, plan: SendPlan, ack_timeout: float = 3.0) -> bool:
        """
        Fast-path GATT transport for 96x16 frames:
        Uses Write Without Response (response=False) with 1.5ms pacing between chunks
        and waits for matrix hardware ACK (window_event & all_event on NOTIFY_UUID).
        Falls back to response=True if response=False fails or times out.
        """
        if not self.client or not self.client._session:
            return False

        session = self.client._session
        bleak_client = session._client
        ack_mgr = session._ack_mgr

        if not bleak_client or not ack_mgr:
            return False

        async def _execute_transport(use_unack: bool) -> bool:
            for idx, win in enumerate(plan.windows):
                ack_mgr.reset()
                for chunk in _chunk_bytes(win.data, plan.chunk_size):
                    await bleak_client.write_gatt_char(WRITE_UUID, chunk, response=not use_unack)
                    if use_unack:
                        await asyncio.sleep(0.0015)  # 1.5ms pacing to avoid BLE RX buffer overrun
                if plan.ack_policy.ack_per_window and win.requires_ack:
                    await asyncio.wait_for(ack_mgr.window_event.wait(), timeout=ack_timeout)

            if plan.ack_policy.ack_final:
                await asyncio.wait_for(ack_mgr.all_event.wait(), timeout=ack_timeout)

            return True

        # Try fast path (response=False)
        try:
            return await _execute_transport(use_unack=True)
        except Exception as e:
            logger.warning(f"Fast-path write (response=False) failed ({e}), falling back to response=True...")

        # Fallback to standard write request (response=True)
        try:
            return await _execute_transport(use_unack=False)
        except Exception as err:
            logger.error(f"Fallback transport also failed: {err}")
            return False

    async def send_image(self, file_path: str):
        if not self.connected or not self.client:
            logger.warning("Cannot send image: Not connected to BLE device.")
            return False
        async with self._send_lock:
            try:
                from pathlib import Path
                p = Path(file_path)
                if not p.exists() or not p.is_file():
                    logger.error(f"Image file not found: {file_path}")
                    return False
                with open(p, "rb") as f:
                    file_bytes = f.read()
                file_bytes, is_gif = _process_loaded_bytes(file_bytes, p.suffix.lower())
                dev_info = self.client.get_device_info()
                target_w = getattr(dev_info, "width", 96) if dev_info else 96
                target_h = getattr(dev_info, "height", 16) if dev_info else 16
                processed_bytes = _resize_image(file_bytes, is_gif, target_w, target_h)
                plan = _build_send_plan(processed_bytes, is_gif, plan_name="send_image_fast")
                return await self._send_plan_fast(plan)
            except Exception as e:
                logger.error(f"Error sending image to matrix: {e}")
                return False

    async def send_image_bytes(self, image_bytes: bytes, file_ext: str = ".png"):
        """Send image directly from in-memory bytes using fast-path SendPlan and concurrency lock."""
        if not self.connected or not self.client:
            logger.warning("Cannot send image bytes: Not connected to BLE device.")
            return False
        async with self._send_lock:
            try:
                is_gif = file_ext.lower() == ".gif"
                # If image is already a 96x16 PNG frame (standard PixelWeb rendered frame), build SendPlan directly
                plan = _build_send_plan(image_bytes, is_gif, plan_name="send_image_bytes_fast")
                return await self._send_plan_fast(plan)
            except Exception as e:
                logger.error(f"Error sending image bytes to matrix: {e}")
                return False

    async def set_brightness(self, level: int):
        if self.connected and self.client:
            try:
                await self.client.set_brightness(level)
            except Exception as e:
                logger.error(f"Error setting brightness: {e}")

    async def set_power(self, on: bool):
        if self.connected and self.client:
            try:
                await self.client.set_power(on)
            except Exception as e:
                logger.error(f"Error setting power: {e}")

    async def set_orientation(self, orientation: int):
        if self.connected and self.client:
            try:
                await self.client.set_orientation(int(orientation))
                logger.info(f"Matrix orientation set to {orientation}")
            except Exception as e:
                logger.error(f"Error setting orientation: {e}")

    async def set_clock(self, style: int = 1, show_date: bool = True, format_24: bool = True):
        if self.connected and self.client:
            try:
                await self.client.set_clock_mode(style=style, show_date=show_date, format_24=format_24)
            except Exception as e:
                logger.error(f"Error setting clock mode: {e}")

    async def _process_queue(self):
        while True:
            cmd = await self.queue.get()
            try:
                action = cmd.get("action")
                args = cmd.get("args", {})
                if action == "send_text":
                    await self.send_text(**args)
                elif action == "send_image":
                    await self.send_image(**args)
            except Exception as e:
                logger.error(f"Error executing queued action: {e}")
            finally:
                self.queue.task_done()

ble_worker = BLEWorker()
