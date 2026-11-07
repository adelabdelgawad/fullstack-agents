Fix `apply_discount` in `pricing.py`: it must return the price reduced by `percent` percent, so
`apply_discount(200, 25)` returns `150.0`. Keep `format_price` unchanged.
