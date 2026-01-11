import asyncio
from time import time

from vehicle_controller.nats import NATS, Msg
from vehicle_controller.shared import Heartbeat


async def run_coordinator(
    nc: NATS,
    subject_heartbeat_req: str,
    subject_heartbeat_resp: str,
    heartbeat_interval: float,
    heartbeat_missed_limit: int,
):
    clients = {}

    async def message_handler(msg: Msg):
        hb = Heartbeat.model_validate_json(msg.data)
        if hb.active:
            if hb.worker_id not in clients:
                print(f"[+] New client registered: {hb.worker_id}")
            clients[hb.worker_id] = time()
        else:
            if hb.worker_id in clients:
                print(f"[-] Client {hb.worker_id} disconnected gracefully.")
                del clients[hb.worker_id]

    sub = await nc.subscribe(subject_heartbeat_resp, cb=message_handler)

    try:
        while True:
            await nc.publish(subject_heartbeat_req, b"")

            now = time()
            threshold = heartbeat_interval * heartbeat_missed_limit + 0.5

            to_evict = []
            print(f"--- Active Clients: {len(clients)} ---")

            for cid, last_seen in clients.items():
                delta = now - last_seen
                if delta > threshold:
                    to_evict.append(cid)
                else:
                    print(f"ID: {cid} | Last Seen: {delta:.2f}s ago")

            for cid in to_evict:
                print(f"[!] EVICTING {cid} (Timeout)")
                del clients[cid]

            await asyncio.sleep(heartbeat_interval)
    finally:
        await sub.unsubscribe()
