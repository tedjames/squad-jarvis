import math

# Constants
GRID_SIZE = 300
DELIMITER = "K"

# Letters for X-axis
letter_list = ["No", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

# Numbers for Y-axis
number_list = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]

# Descriptions for mortar calculator output
description_1   = " Big-Grid-Scale  : "
description_2   = " Mortar Position : "
description_3   = " Target Position : "

# Distances from mortar interface
DISTANCES = (50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 950, 1000, 1050, 1100, 1150, 1200, 1250)

# Milliradians from mortar interface
MILS = (1579, 1558, 1538, 1517, 1496, 1475, 1453, 1431, 1409, 1387, 1364, 1341, 1317, 1292, 1267, 1240, 1212, 1183, 1152, 1118, 1081, 1039, 988, 918, 800)

def return_input_from_string(u_input, description):
    keypad_list = []
    # control the user inputs
    try:
        # Read x-axis
        x_value = u_input[0]

        # Read remaining string split by K
        zerlegt = list(map(int,u_input[1:].split(DELIMITER)))
        # Read y-axis
        y_value = int(zerlegt.pop(0))

        # Checks if inputs are valid
        # Check x-value
        if x_value not in letter_list:
            raise ValueError
        # Check y-value
        if y_value not in number_list:
            raise ValueError
        # Check keypad values
        for item in zerlegt:
            if int(item) > 9 or int(item) < 0:
               raise ValueError
            else:
                keypad_list.append(item)
        return x_value, y_value, keypad_list, u_input
    except:
        print(" Wrong input, use A1K1 or A10K9 or A1K1K5!")
        u_input = str(input(description)).upper()
        return return_input_from_string(u_input, description)

def convert_input_to_coordiantes(input_tuple):
    # Unpack input_tuple
    x, y, keypad_list, string_input = input_tuple

    x = int(ord(x.lower())-ord("a"))*GRID_SIZE
    y = (y-1) * GRID_SIZE

    # If no keypad is given
    if not keypad_list:
        x += GRID_SIZE / 2
        y += GRID_SIZE / 2

    # Get Keypad offsets
    else:
        keypadSize = GRID_SIZE
        for element in keypad_list:
            keypadSize /= 3  # Shrink keypad size by factor of 3
            keypad = int(element)

            # Add X Component of (Sub)Keypad
            if keypad == 2 or keypad == 5 or keypad == 8:
                x += keypadSize
            elif keypad == 3 or keypad == 6 or keypad == 9:
                x += 2*keypadSize

            # Add Y Component of (Sub)Keypad
            if keypad == 4 or keypad == 5 or keypad == 6:
                y += keypadSize
            elif keypad == 1 or keypad == 2 or keypad == 3:
                y += 2*keypadSize

        # Center point in (Sub)Keypad
        x += keypadSize / 2
        y += keypadSize / 2

    return (x, y)

def get_vektor(x1, y1, x2, y2):
    # Calculate connection vector
    x_bind_vek = x1 - x2
    y_bind_vek = y1 - y2
    # Calculate vector length
    distance = math.sqrt(x_bind_vek**2 + y_bind_vek**2)
    return distance

def get_angle(x1, y1, x2, y2):
    # Build north vector on arty-position
    nv_x = x1 - x1
    nv_y = (y1-1) - y1
    abs_nv = math.sqrt((nv_x ** 2) + (nv_y ** 2))
    # Build Target vector
    tv_x = x2 - x1
    tv_y = y2 - y1
    abs_tv = math.sqrt((tv_x ** 2) + (tv_y ** 2))
    # Scalar between nv and tv
    skalar = nv_x * tv_x + nv_y * tv_y

    if x1 != x2 or y1 != y2:
        angle = math.degrees(math.acos(skalar/(abs_nv*abs_tv)))
    # Shoot NE - QI
    if x2 > x1 and y2 < y1:
        angle = angle
    # Shoot NW - QII
    elif x2 < x1 and y2 < y1:
        angle = 360 - angle
    # Shoot SW - QIII
    elif x2 < x1 and y2 > y1:
        angle = 360 - angle
    # Shoot SE - QIV
    elif x2 > x1 and y2 > y1:
        angle = angle
    # Shoot direct North
    elif x2 == x1 and y2 < y1:
        angle = 0
    # Shoot direct South
    elif x2 == x1 and y2 > y1:
        angle = 180
    # Shoot direct East
    elif x2 > x1 and y2 == y1:
        angle = 90
    # Shoot direct West
    elif x2 < x1 and y2 == y1:
        angle = 270
    # Fail
    else:
        angle = 666
    return angle

def calcElevation(distance):
    if distance < DISTANCES[0]:
        return f"Out of Range (<{DISTANCES[0]}m)"
    elif distance > DISTANCES[-1]:
        return f"Out of Range (>{DISTANCES[-1]}m)"
    else:
        for i, value in enumerate(DISTANCES):
            if distance == value:
                return str(MILS[i])
            elif distance < value:
                m = (MILS[i] - MILS[i - 1]) / (DISTANCES[i] - DISTANCES[i - 1])
                return str(int(m * (distance - DISTANCES[i]) + MILS[i])) 
            
def calculate_fire_mission(input_arty, input_target, calculationHistory):
    """Calculate fire mission parameters and update history"""
    
    x1, y1 = convert_input_to_coordiantes(input_arty)
    x2, y2 = convert_input_to_coordiantes(input_target)
    angle = round(get_angle(x1, y1, x2, y2), 1)
    distance = int(get_vektor(x1, y1, x2, y2))
    click = calcElevation(distance)
    current_target = input_target[-1].replace(' ', '')

    # Update history
    if current_target != calculationHistory['current']['target'] and calculationHistory['current']['distance'] is not None:
        calculationHistory['previous'] = calculationHistory['current'].copy()
        
    calculationHistory['current'] = {
        'distance': distance,
        'angle': angle,
        'click': click,
        'target': current_target
    }
    
    return distance, angle, click, current_target
