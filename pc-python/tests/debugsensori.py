import logging
import time
from threading import Timer

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

# Configura l'URI del tuo Crazyflie
URI = 'radio://0/40/2M/E7E7E7E7E6'

# Semplice callback per stampare i dati ricevuti
def log_data_callback(timestamp, data, logconf):
    print(f"[{timestamp}][{logconf.name}]: ", end="")
    print(f"Roll: {data['stabilizer.roll']:6.2f} | Pitch: {data['stabilizer.pitch']:6.2f} | ", end="")
    print(f"GyroX: {data['gyro.x']:6.2f} | GyroY: {data['gyro.y']:6.2f}")

if __name__ == '__main__':
    # Inizializza i driver radio
    cflib.crtp.init_drivers()

    # Configurazione del Logging
    # Leggiamo sia lo stato stimato (stabilizer) che i dati quasi-grezzi (gyro)
    lg_conf = LogConfig(name='StabilizerGyro', period_in_ms=100)
    lg_conf.add_variable('stabilizer.roll', 'float')
    lg_conf.add_variable('stabilizer.pitch', 'float')
    lg_conf.add_variable('gyro.x', 'float')
    lg_conf.add_variable('gyro.y', 'float')
    
    

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        
        scf.cf.param.set_value('kalman.mNGyro_rollpitch', '0.01')
        scf.cf.param.set_value('kalman.pNAtt', '0.00000001')
                
        # 1. Reset dell'estimatore (opzionale, utile per pulire drift iniziali)
        scf.cf.param.set_value('kalman.resetEstimation', '1')
        time.sleep(0.1)
        scf.cf.param.set_value('kalman.resetEstimation', '0')
        time.sleep(1.0) # Aspetta che il filtro si stabilizzi

        # 2. Aggiungi la configurazione di log
        scf.cf.log.add_config(lg_conf)
        lg_conf.data_received_cb.add_callback(log_data_callback)
        
        print("Inizio logging... Premi Ctrl+C per fermare.")
        lg_conf.start()

        # Mantieni il programma attivo
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            lg_conf.stop()
            print("Logging terminato.")