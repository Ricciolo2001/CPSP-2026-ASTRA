import argparse
import logging
import time


from astra.crazyflie import LineBuffer, get_bound_mac, set_bound_mac
import cflib
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie


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

        def _log(ts, data, _):
            print(f"[log] t={ts:.2f} s\t data={data}")

        logconf = LogConfig(name="rssi_sample", period_in_ms=100)
        logconf.add_variable("astra.bound_device_rssi", "int32_t")  # 4 bytes
        logconf.data_received_cb.add_callback(_log)

        scf.cf.log.add_config(logconf)
        logconf.start()

        try:
            while True:
                time.sleep(1.0)
        finally:
            logconf.stop()


if __name__ == "__main__":
    main()
