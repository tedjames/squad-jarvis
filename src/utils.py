import os

NATO_PHONETIC = {
    'A': 'Alpha',
    'B': 'Bravo',
    'C': 'Charlie',
    'D': 'Delta',
    'E': 'Echo',
    'F': 'Foxtrot',
    'G': 'Golf',
    'H': 'Hotel',
    'I': 'India',
    'J': 'Juliet',
    'K': 'Kilo',
    'L': 'Lima',
    'M': 'Mike',
    'N': 'November',
    'O': 'Oscar',
    'P': 'Papa',
    'Q': 'Quebec',
    'R': 'Romeo',
    'S': 'Sierra',
    'T': 'Tango',
    'U': 'Uniform',
    'V': 'Victor',
    'W': 'Whiskey',
    'X': 'X-ray',
    'Y': 'Yankee',
    'Z': 'Zulu'
}


def convert_to_phonetic_alphabet(input_string):
    """Convert first letter of coordinate to NATO phonetic alphabet"""
    if not input_string:
        return ""
    
    first_letter = input_string[0].upper()
    phonetic_letter = NATO_PHONETIC.get(first_letter, first_letter)
    
    # Add space before each 'K' in the remaining string
    remaining = input_string[1:].replace('K', ' K')
    
    return f"{phonetic_letter} {remaining}"

def format_coordinates(coords_tuple, convert_to_phonetic=False):
    """
    Format coordinates tuple into a clean string representation.
    Args:
        coords_tuple: Tuple containing (x_value, y_value, keypad_list, original_input)
    Returns:
        str: Formatted coordinate string without spaces
    """
    if not coords_tuple or len(coords_tuple) < 4:
        return ""
        
    output = coords_tuple[-1].replace(' ', '')
    if convert_to_phonetic:
        output = convert_to_phonetic_alphabet(output)
    # if DEBUG_MODE:
    #     print(f"Formatted coordinates: {output}")
    return output


def clear():
    # For Windows
    if os.name == 'nt':
        os.system('cls')
    # For Unix/Linux/MacOS
    else:
        os.system('clear')
