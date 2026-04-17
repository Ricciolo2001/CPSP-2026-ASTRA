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


def euclidean_distance(p1, p2):
    return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def test_perfect_case():
    print("\n=== TEST 1: caso perfetto senza rumore ===")

    anchors = [(0, 0), (4, 0), (0, 3), (4, 3)]
    true_point = (2, 1)

    distances = [euclidean_distance(true_point, a) for a in anchors]

    estimated_point, residuals, total_error = trilateration_robust(anchors, distances)

    print("Punto vero:     ", true_point)
    print("Punto stimato:  ", estimated_point)
    print("Residui:        ", residuals)
    print("Errore totale:  ", total_error)

    assert np.allclose(estimated_point, true_point, atol=1e-6), "Il punto stimato non coincide col punto vero"
    assert total_error < 1e-6, "L'errore totale dovrebbe essere quasi nullo"

    print("Test 1 superato")


def test_noisy_case():
    print("\n=== TEST 2: caso con rumore ===")

    np.random.seed(42)

    anchors = [(0, 0), (4, 0), (0, 3), (4, 3)]
    true_point = (2, 1)

    true_distances = [euclidean_distance(true_point, a) for a in anchors]

    noise_std = 0.05
    noisy_distances = [d + np.random.normal(0, noise_std) for d in true_distances]

    estimated_point, residuals, total_error = trilateration_robust(anchors, noisy_distances)

    position_error = euclidean_distance(true_point, estimated_point)

    print("Punto vero:         ", true_point)
    print("Punto stimato:      ", estimated_point)
    print("Distanze rumorose:  ", noisy_distances)
    print("Residui:            ", residuals)
    print("Errore totale:      ", total_error)
    print("Errore posizione:   ", position_error)

    assert position_error < 0.3, "Errore di posizione troppo grande per un rumore piccolo"

    print("Test 2 superato")


def test_aligned_anchors():
    print("\n=== TEST 3: punti allineati ===")

    anchors = [(0, 0), (1, 0), (2, 0)]
    distances = [1.0, 1.2, 1.8]

    try:
        trilateration_robust(anchors, distances)
        assert False, "Mi aspettavo un ValueError per punti allineati"
    except ValueError as e:
        print("Eccezione correttamente sollevata:", e)
        print("Test 3 superato")


def test_invalid_lengths():
    print("\n=== TEST 4: numero ancore e distanze non coerente ===")

    anchors = [(0, 0), (4, 0), (0, 3)]
    distances = [2.0, 3.0]

    try:
        trilateration_robust(anchors, distances)
        assert False, "Mi aspettavo un ValueError per lunghezze diverse"
    except ValueError as e:
        print("Eccezione correttamente sollevata:", e)
        print("Test 4 superato")


def test_negative_distance():
    print("\n=== TEST 5: distanza negativa ===")

    anchors = [(0, 0), (4, 0), (0, 3)]
    distances = [2.0, -1.0, 3.0]

    try:
        trilateration_robust(anchors, distances)
        assert False, "Mi aspettavo un ValueError per distanza negativa"
    except ValueError as e:
        print("Eccezione correttamente sollevata:", e)
        print("Test 5 superato")


if __name__ == "__main__":
    test_perfect_case()
    test_noisy_case()
    test_aligned_anchors()
    test_invalid_lengths()
    test_negative_distance()

    print("\nTutti i test sono terminati con successo.")