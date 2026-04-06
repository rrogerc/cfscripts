_printer = print

def log(*args, **kwargs):
    _printer(*args, **kwargs)

def set_printer(fn):
    global _printer
    _printer = fn

def reset_printer():
    global _printer
    _printer = print
