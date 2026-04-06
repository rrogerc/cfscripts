def get_rating_color(rating):
    if isinstance(rating, str): return "grey"
    if rating < 1200: return "grey"
    if rating < 1400: return "green"
    if rating < 1600: return "cyan"
    if rating < 1900: return "blue"
    if rating < 2100: return "magenta"
    if rating < 2400: return "yellow"
    return "red"

def get_participation_type_color(ptype):
    return "green" if ptype == "contestant" else ("yellow" if ptype == "virtual" else "cyan")

def get_delta_color(delta):
    return "white" if isinstance(delta, str) else ("red" if delta < 0 else ("green" if delta > 0 else "white"))
