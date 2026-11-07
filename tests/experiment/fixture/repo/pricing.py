"""Price helpers for the experiment fixture."""


def apply_discount(price, percent):
    return price * percent / 100


def format_price(value):
    return f"{value:.2f}"
