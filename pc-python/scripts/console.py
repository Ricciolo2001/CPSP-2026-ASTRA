# Script principale
#
#
# Flow:
# // 1. Connettersi al CF
# // 2. Impostare il MAC address del BLE
# // 3. Armare il CF
# // 4. Loop x3:
# //   - "Crea un punto"
# //  -  Imposta setpoint sul CF a quel punto
# //    -Attendi che il CF raggiunga il setpoint
# //   - Campiona il RSSI e la distanza stimata per tot secondi
# 5. Plot dei risultati

import argparse
import logging
import time
import math
import threading


from astra.crazyflie import LineBuffer, get_bound_mac, set_bound_mac
import cflib
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie


# =================================================================#


def move_to_pos(
    scf: SyncCrazyflie,
    target_x: float,
    target_y: float,
    height: float = 0.5,
    arrival_radius: float = 0.15,
):
    cf = scf.cf

    sem = threading.Semaphore(0)

    last_time = 0.0

    log_period = 500 / 1000.0  # log every 500 ms

    def _on_pos(ts, data, _):
        nonlocal last_time
        x, y, vbat = data["stateEstimate.x"], data["stateEstimate.y"], data["pm.vbat"]

        if last_time == 0.0:
            last_time = ts
        elif ts - last_time < log_period:
            return

        dist = math.sqrt((x - target_x) ** 2 + (y - target_y) ** 2)
        print(
            f"  [pos cb] dist={dist:.3f} m"
            f"\t pos=({x:.3f}, {y:.3f})"
            f"\t dest=({target_x:.3f}, {target_y:.3f})"
            f"\t vbat={vbat:.2f} V"
        )

        if dist <= arrival_radius:
            print(f"  [pos cb] entro in area di arrivo (dist={dist:.3f} m)")
            sem.release()

    # Listen to postion estimates

    logconf = LogConfig(name="move_to_pos", period_in_ms=50)
    logconf.add_variable("stateEstimate.x", "FP16")  # 2 bytes
    logconf.add_variable("stateEstimate.y", "FP16")  # 2 bytes
    logconf.add_variable("pm.vbat", "FP16")  # 2 bytes

    scf.cf.log.add_config(logconf)
    logconf.data_received_cb.add_callback(_on_pos)

    try:
        logconf.start()

        # --- takeoff ---
        print(f"[fly_to_and_land] takeoff → {height:.2f} m")
        cf.high_level_commander.takeoff(height, 2.0)
        time.sleep(2.5)

        # --- go_to ---
        print(f"[fly_to_and_land] go_to ({target_x:.2f}, {target_y:.2f})")
        cf.high_level_commander.go_to(target_x, target_y, height, 0, 0.3)

        # wait until we enter the arrival radius
        while True:
            if sem.acquire(timeout=0.1):
                print(f"[fly_to_and_land] arrived at ({target_x:.2f}, {target_y:.2f})")
                break
    finally:
        logconf.stop()

    # stop the CF
    print("[fly_to_and_land] landing")
    cf.high_level_commander.land(0.0, 2.0)
    time.sleep(2.5)


def sample_rssi(
    scf: SyncCrazyflie,
    duration: float,
    tx_power: float,
    path_loss_n: float,
):
    cf = scf.cf

    logconf = LogConfig(name="rssi_sample", period_in_ms=100)
    logconf.add_variable("astra.bound_device_rssi", "int32_t")  # 4 bytes
    cf.log.add_config(logconf)

    samples = []

    def _on_rssi(ts, data, _):
        rssi_raw = data["astra.bound_device_rssi"]
        rssi_filtered = (
            rssi_raw - tx_power + 10 * path_loss_n * math.log10(1.0)
        )  # distance=1m
        print(
            f"  [rssi cb] t={ts:.2f} s\t rssi_raw={rssi_raw} dBm\t rssi_filtered={rssi_filtered:.2f} dBm"
        )
        samples.append((ts, rssi_raw, rssi_filtered))

    logconf.data_received_cb.add_callback(_on_rssi)

    try:
        logconf.start()
        print(f"[sample_rssi] sampling for {duration:.2f} seconds...")
        time.sleep(duration)
    finally:
        logconf.stop()

    mean = sum(r[1] for r in samples) / len(samples) if samples else 0.0
    distance = 10 ** ((tx_power - mean) / (10 * path_loss_n))
    print(
        f"[sample_rssi] estimated distance: {distance:.2f} m (using tx_power={tx_power} dBm and path_loss_n={path_loss_n})"
    )

    return distance, samples


def emergency_stop(cf):
    """Atterra e disarma immediatamente."""
    print("\n[emergency_stop] Ctrl+C ricevuto — atterra e disarma...")
    try:
        cf.high_level_commander.land(0.0, 2.0)
        time.sleep(2.5)
    except Exception as e:
        print(f"[emergency_stop] errore nel land: {e}")
    try:
        cf.param.set_value("system.arm", "0")
    except Exception:
        pass
    print("[emergency_stop] done.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--uri",
        default="radio://0/83/2M/E7E7E7E7EA",
        help="Crazyflie radio URI (default: radio://0/83/2M/E7E7E7E7EA)",
    )
    parser.add_argument(
        "--tx-power",
        type=float,
        default=-59.0,
        help="Beacon TX power at 1 m in dBm used by the log-distance model (default: -59.0)",
    )
    parser.add_argument(
        "--path-loss-n",
        type=float,
        default=2.0,
        help="Path-loss exponent n for the log-distance model (default: 2.0, free-space)",
    )
    parser.add_argument(
        "--save-csv",
        default=None,
        metavar="FILE",
        help="Save (t, x, y, yaw, rssi_raw, rssi_filtered) rows to FILE as CSV on exit",
    )
    parser.add_argument(
        "--mac",
        default=None,
        metavar="AA:BB:CC:DD:EE:FF",
        help="BLE MAC address to bind before starting (use 00:00:00:00:00:00 to unbind). "
        "If omitted, the current bound device is used.",
    )
    parser.add_argument(
        "--triangle-side",
        type=float,
        default=0.6,
        help="Triangle side length in metres for manual guide overlay (default: 0.6)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(level=logging.ERROR)
    cflib.crtp.init_drivers(enable_debug_driver=True)

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        print(f"Connected to {args.uri}")

        # Print firmware DEBUG_PRINT messages directly to console
        fw_log = LineBuffer(lambda line: print(f"[CF] {line}", flush=True))
        scf.cf.console.receivedChar.add_callback(fw_log.feed)

        scf.cf.param.set_value("stabilizer.estimator", "2")

        # ---- BLE MAC setup ----
        if args.mac is not None:
            print(f"Setting bound device MAC → {args.mac}")
            set_bound_mac(scf, args.mac)
            time.sleep(0.2)  # allow the firmware callback to run

        current_mac = get_bound_mac(scf)
        if current_mac == "00:00:00:00:00:00":
            print("Bound device: (none — unbound)")
        else:
            print(f"Bound device MAC: {current_mac}")

        # ---- fly to and land in a target position with feedback loop ----
        try:
            for target_x, target_y in [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]:
                print(f"\n=== Fly to ({target_x}, {target_y}) ===")
                move_to_pos(scf, target_x, target_y)


                distance, samples = sample_rssi(
                    scf,
                    duration=5.0,
                    tx_power=args.tx_power,
                    path_loss_n=args.path_loss_n,
                )

        except KeyboardInterrupt:
            emergency_stop(scf.cf)


        


if __name__ == "__main__":
    main()
