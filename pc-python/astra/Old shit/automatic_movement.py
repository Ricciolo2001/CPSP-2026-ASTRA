import numpy as np
import time
import cflib.crtp

# --- Definisci il tuo target (in metri rispetto a dove è partito) ---
target_x = 0
target_y = 0
target_z = 0.4


""" We can use the move function to move a certain distance the drone in a certain direction (Left, Right, Front, Back) """


def move_to_direction(scf, direction, distance):  # I 4 if sono belli
    initial_x = target_x
    initial_y = target_y
    if direction == "Left":
        target_y += distance
    if direction == "Right":
        target_y -= distance
    if direction == "Front":
        target_x += distance
    if direction == "Back":
        target_x -= distance

    scf.cf.commander.send_position_setpoint(target_x, target_y, target_z, 0)

    # Per fermarlo quando è "abbastanza" vicino:
    while True:
        dist = np.sqrt(
            (target_x - initial_x) ** 2 + (target_y - initial_y) ** 2
        )  # probably correct?
        if dist < 0.1:
            print("Vabbè, dai, sono arrivato più o meno.")
            scf.cf.commander.send_hover_setpoint(0, 0, 0, target_z)
            break
        print("Non ancora arrivato")
        time.sleep(0.5)


def line_scanning(scf, x_boundry, y_boundry, scanlines):
    """
    Performs a grid scan by moving the drone in a grid pattern.

    Args:
        scf: Crazyflie object
        grid_size: Number of points per side of the grid
        max_distance: Maximum distance to travel from starting position
    """
    for i in scanlines:
        move_to_direction(scf, x_boundry, "Left")
        move_to_direction(scf, x_boundry, "Right")
        move_to_direction(scf, y_boundry / scanlines, "Front")


def grid_scan(scf, grid_cell_x, grid_cell_y, grid_size_x, grid_size_y):
    celldim_x = grid_size_x / grid_cell_x
    celldim_y = grid_size_y / grid_cell_y
    for i in range(int(grid_cell_y / 2)):
        for j in range(grid_cell_x):
            move_to_direction(scf, celldim_x, "Left")
        move_to_direction(scf, celldim_y, "Front")
        for j in range(grid_cell_x):
            move_to_direction(scf, celldim_x, "Right")
        move_to_direction(scf, celldim_y, "Front")
