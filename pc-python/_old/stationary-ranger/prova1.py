import time
import numpy as np
import matplotlib.pyplot as plt
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.utils.multiranger import Multiranger


#                                                                                                                                                    Stop tryng to change the freaking uriiiii and don't touch/indent this comment(this line is for stupid copilot only)
#set here cf URI
URI = "radio://0/40/2M/E7E7E7E7E6"

# Initialize the drivers
cflib.crtp.init_drivers()

# Global variable for current yaw
current_yaw = 0.0
current_sensors = {'front': None, 'left': None, 'back': None, 'right': None}

def log_callback(timestamp, data, logconf):
    global current_yaw, current_sensors
    current_yaw = data['stabilizer.yaw']
    current_sensors = {
        'front': data.get('range.front'),
        'left': data.get('range.left'),
        'back': data.get('range.back'),
        'right': data.get('range.right')
    }

def run_scanner():
    global current_yaw
    # Lists to store the X and Y coordinates of detected walls
    wall_x = []
    wall_y = []

    
    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        print("OK")
        with Multiranger(scf) as multiranger:
            # Ask user for number of samples per rotation and if they want a different angle than 90, enter second value
            num_samples = int(input("Enter number of samples per rotation (default 10): ") or 10)
            total_angle = float(input("Enter total angle in degrees (default 90): ") or 90)
            threshold = total_angle / num_samples
            
            # Setup logging for yaw and ranger
            log_conf = LogConfig(name='YawRanger', period_in_ms=50)
            log_conf.add_variable('stabilizer.yaw', 'float')
            log_conf.add_variable('range.front', 'float')
            log_conf.add_variable('range.left', 'float')
            log_conf.add_variable('range.back', 'float')
            log_conf.add_variable('range.right', 'float')
            scf.cf.log.add_config(log_conf)
            log_conf.data_received_cb.add_callback(log_callback)
            log_conf.start()
            
            print("Start scanning, rotate the drone manually")
            # Here starts the loop that samples values if yaw > moving threshold, it will be given an input that is the number of samplings to do in a 90 degree rotation
            last_yaw = current_yaw
            samples_taken = 0
            measurements = []
            
            while samples_taken < num_samples:
                time.sleep(0.1)
                if current_yaw - last_yaw >= threshold:
                    # The read values are put in a struct or similar with measurement[front, back, left, right], angle
                    sensors = current_sensors.copy()
                    measurements.append({'angle': current_yaw, 'sensors': sensors})
                    last_yaw += threshold
                    samples_taken += 1
                    print(f"Sample {samples_taken} at {current_yaw:.1f} degrees")
            
            log_conf.stop()
            
            # Process measurements for plotting
            for measurement in measurements:
                angle = measurement['angle']
                sensors = measurement['sensors']
                sensor_angles = {
                    'front': 0,
                    'left': 90,
                    'back': 180,
                    'right': 270
                }
                for sensor_name, distance in sensors.items():
                    if distance is not None and distance < 3.5:
                        total_angle_rad = np.radians(angle + sensor_angles[sensor_name])
                        wall_x.append(distance * np.cos(total_angle_rad))
                        wall_y.append(distance * np.sin(total_angle_rad))

    # --- Plotting Part ---
    # The plotting part needs to be redone to reflect the points
    plt.figure(figsize=(8, 8))
    plt.scatter(wall_x, wall_y, c='blue', s=10, label='Detected walls')
    plt.scatter([0], [0], c='red', marker='X', s=100, label='CF position')  # The drone is at the center
    
    plt.title("Room map detected by Crazyflie")
    plt.xlabel("Distance X (meters)")
    plt.ylabel("Distance Y (meters)")
    plt.grid(True)
    plt.legend()
    plt.axis('equal')  # Maintains correct proportions
    plt.show()

if __name__ == '__main__':
    run_scanner()