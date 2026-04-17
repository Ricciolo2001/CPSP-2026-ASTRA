import numpy as np

"""Inputs anchors {[x,y],[...]}"""

def trilateration_robust(anchors, distances):
    if len(anchors) < 3:
        raise ValueError("Servono almeno 3 punti")

    if len(anchors) != len(distances):
        raise ValueError("Il numero di ancore e distanze deve coincidere")

    if any(d < 0 for d in distances):
        raise ValueError("Le distanze non possono essere negative")

    x1, y1 = anchors[0]	
    d1 = distances[0]

    A = []
    b = []

    for i in range(1, len(anchors)):
        xi, yi = anchors[i]
        di = distances[i]

        A.append([2 * (xi - x1), 2 * (yi - y1)])
        b.append(d1**2 - di**2 - x1**2 + xi**2 - y1**2 + yi**2)

    A = np.array(A, dtype=float)
    b = np.array(b, dtype=float)

    if np.linalg.matrix_rank(A) < 2:
        raise ValueError("Configurazione geometrica non valida: punti allineati")

    point, _, _, _ = np.linalg.lstsq(A, b, rcond=None)

    residuals = []
    x, y = point

    for (xi, yi), di in zip(anchors, distances):
        d_est = np.sqrt((x - xi)**2 + (y - yi)**2)
        residuals.append(d_est - di)

    residuals = np.array(residuals)
    total_error = np.linalg.norm(residuals)

    return point, residuals, total_error