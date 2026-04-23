import time
import numpy as np
import matplotlib.pyplot as plt

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.utils.multiranger import Multiranger


URI = "radio://0/40/2M/E7E7E7E7E6"

cflib.crtp.init_drivers()

# Stato globale
current_yaw = 0.0
current_sensors = {
    'front': None,
    'left': None,
    'back': None,
    'right': None
}


# ---------------------------
# Utility
# ---------------------------
def angle_diff(a, b):
    """Differenza tra angoli in gradi (gestisce wrap-around)"""
    d = a - b
    return (d + 180) % 360 - 180


# ---------------------------
# Callback logging
# ---------------------------
def log_callback(timestamp, data, logconf):
    global current_yaw, current_sensors

    current_yaw = data['stabilizer.yaw']

    current_sensors = {
        'front': data.get('range.front'),
        'left': data.get('range.left'),
        'back': data.get('range.back'),
        'right': data.get('range.right')
    }


# ---------------------------
# Scanner principale
# ---------------------------
def run_scanner():
    global current_yaw

    wall_x = []
    wall_y = []

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        print("Connected")

        # (Opzionale ma consigliato)
        scf.cf.param.set_value('stabilizer.estimator', '2')  # Kalman

        with Multiranger(scf):

            # Input utente
            num_samples = int(input("Samples per rotation (default 10): ") or 10)
            total_angle = float(input("Total angle deg (default 90): ") or 90)

            threshold = total_angle / num_samples

            # Config logging
            log_conf = LogConfig(name='YawRanger', period_in_ms=50)
            log_conf.add_variable('stabilizer.yaw', 'float')
            log_conf.add_variable('range.front', 'float')
            log_conf.add_variable('range.left', 'float')
            log_conf.add_variable('range.back', 'float')
            log_conf.add_variable('range.right', 'float')

            scf.cf.log.add_config(log_conf)
            log_conf.data_received_cb.add_callback(log_callback)
            log_conf.start()

            print("Rotate the drone manually...")

            # ---------------------------
            # Setup iniziale
            # ---------------------------
            time.sleep(1)  # stabilizzazione

            initial_yaw = current_yaw
            last_yaw = current_yaw
            accumulated_angle = 0.0

            samples_taken = 0
            measurements = []

            # ---------------------------
            # Loop acquisizione
            # ---------------------------
            while samples_taken < num_samples:
                time.sleep(0.05)

                # Delta yaw robusto
                delta = angle_diff(current_yaw, last_yaw)
                accumulated_angle += delta
                last_yaw = current_yaw

                if abs(accumulated_angle) >= threshold:
                    rel_yaw = angle_diff(current_yaw, initial_yaw)

                    sensors = current_sensors.copy()

                    measurements.append({
                        'angle': rel_yaw,
                        'sensors': sensors
                    })

                    samples_taken += 1
                    accumulated_angle = 0

                    print(f"Sample {samples_taken}: {rel_yaw:.1f}°")
                    print(f"Sensors: {sensors}")

            log_conf.stop()

    # ---------------------------
    # Processing dati
    # ---------------------------
    sensor_angles = {
        'front': 0,
        'left': 90,
        'back': 180,
        'right': 270
    }

    for m in measurements:
        base_angle = m['angle']
        sensors = m['sensors']

        for name, distance in sensors.items():
            if distance is None:
                continue

            # filtro rumore / outlier
            if distance <= 0 or distance > 3.5:
                continue

            total_angle = base_angle + sensor_angles[name]
            rad = np.radians(total_angle)

            x = distance * np.cos(rad)
            y = distance * np.sin(rad)

            wall_x.append(x)
            wall_y.append(y)
            
            distance_m = distance / 1000.0
            x = distance_m * np.cos(rad)
            y = distance_m * np.sin(rad)

            wall_x.append(x)
            wall_y.append(y)

    # ---------------------------
    # Plot
    # ---------------------------
    plt.figure(figsize=(8, 8))

    print("X range:", min(wall_x, default=0), max(wall_x, default=0))
    print("Y range:", min(wall_y, default=0), max(wall_y, default=0))
    
    plt.scatter(wall_x, wall_y, s=30)
    


    plt.xlim(-4, 4)
    plt.ylim(-4, 4)
    plt.grid(True)
    plt.axis('equal')
    plt.show()


# ---------------------------
# Main
# ---------------------------
if __name__ == '__main__':
    run_scanner()