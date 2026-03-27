import numpy as np
from scipy.optimize import least_squares

def trilateration_objective(point, positions, distances):
    """
    Calcola la differenza tra la distanza euclidea calcolata
    e quella misurata per ogni punto di riferimento.
    """
    x, y = point
    # Calcola le distanze dal punto attuale a tutti i punti di riferimento
    computed_distances = np.sqrt((positions[:, 0] - x)**2 + (positions[:, 1] - y)**2)
    # Restituisce il vettore dei residui (l'errore)
    return computed_distances - distances

def estimate_position(dataset):
    """
    Argomenti:
        dataset: List di tuple o array numpy [[x1, y1, d1], [x2, y2, d2], ...]
    Ritorna:
        (x, y) stimati
    """
    data = np.array(dataset)
    positions = data[:, :2]  # Coordinate x, y dei sensori
    distances = data[:, 2]   # Distanze misurate d

    # Punto di partenza per l'ottimizzazione (media delle posizioni dei sensori)
    initial_guess = np.mean(positions, axis=0)

    # Minimizzazione dei minimi quadrati
    result = least_squares(trilateration_objective, initial_guess, args=(positions, distances))

    if result.success:
        return result.x
    else:
        raise ValueError("L'ottimizzazione non è confluita: dati troppo rumorosi o insufficienti.")


# Uses an array containg the X and Y values and a distance from the sensors measured at different positions
misure = [
    [0, 0, 5.1],
    [10, 0, 5.0],
    [5, 8, 3.2],
    [2, 2, 2.8]
]

coordinate_stimate = estimate_position(misure)
print(f"Posizione stimata dell'oggetto: x={coordinate_stimate[0]:.3f}, y={coordinate_stimate[1]:.3f}")
