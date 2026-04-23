import argparse
import logging
import time

import cflib
import cflib.crtp
from astra.crazyflie import get_bound_mac, set_bound_mac
from astra.rssi import MedianEmaFilter, rssi_to_distance
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie


DEFAULT_TX_POWER = -90.0  # dBm at 1 m
DEFAULT_PATH_LOSS_N = 2.0  # Free-space path loss exponent
DEFAULT_ALPHA = 0.15  # EMA smoothing factor
DEFAULT_SAMPLE_NUM = 30  # Number of samples to keep for median filtering
DEFAULT_SAMPLE_INTERVAL_MS = 100  # Log sampling interval in milliseconds


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
        default=DEFAULT_TX_POWER,
        help=(
            "Beacon TX power at 1 m in dBm used by the log-distance model"
            f" (default: {DEFAULT_TX_POWER})"
        ),
    )
    parser.add_argument(
        "--path-loss-n",
        type=float,
        default=DEFAULT_PATH_LOSS_N,
        help=(
            "Path-loss exponent n for the log-distance model"
            f" (default: {DEFAULT_PATH_LOSS_N}, free-space)"
        ),
    )
    parser.add_argument(
        "--mac",
        default=None,
        metavar="AA:BB:CC:DD:EE:FF",
        help="BLE MAC address to bind before starting (use 00:00:00:00:00:00 to unbind). "
        "If omitted, the current bound device is used.",
    )
    parser.add_argument(
        "--sample-interval",
        type=int,
        default=DEFAULT_SAMPLE_INTERVAL_MS,
        help=f"Log sampling interval in milliseconds (default: {DEFAULT_SAMPLE_INTERVAL_MS})",
    )
    parser.add_argument(
        "--sample-num",
        type=int,
        default=DEFAULT_SAMPLE_NUM,
        help=f"Number of samples to keep for median filtering (default: {DEFAULT_SAMPLE_NUM})",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=DEFAULT_ALPHA,
        help=f"EMA smoothing factor alpha in (0, 1] (default: {DEFAULT_ALPHA})",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(level=logging.ERROR)
    cflib.crtp.init_drivers()

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        print(f"Connected to {args.uri}")

        # Print firmware DEBUG_PRINT messages directly to console
        # fw_log = LineBuffer(lambda line: print(f"[CF] {line}", flush=True))
        # scf.cf.console.receivedChar.add_callback(fw_log.feed)

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

        filter = MedianEmaFilter(window_size=args.sample_num, alpha=args.alpha)

        def _log(ts, data, _):
            rssi = data["astra.bound_device_rssi"]
            filter.update(rssi)
            distance = rssi_to_distance(
                filter.value,
                tx_power_dbm=args.tx_power,
                path_loss_n=args.path_loss_n,
            )
            print(
                f"[log] t={ts:.2f} s\t RSSI={rssi} dBm\t filtered={filter.value:.2f} dBm\t distance={distance:.2f} m"
            )

        logconf = LogConfig(name="rssi_sample", period_in_ms=args.sample_interval)
        logconf.add_variable("astra.bound_device_rssi", "int32_t")  # 4 bytes
        logconf.data_received_cb.add_callback(_log)

        scf.cf.log.add_config(logconf)
        logconf.start()

        print("Logging RSSI samples... Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logconf.stop()


if __name__ == "__main__":
    main()
