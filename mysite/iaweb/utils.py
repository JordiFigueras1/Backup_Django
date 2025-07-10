def calculate_parasite_density(total_parasites: int,
                               leukocytes: int,
                               leukocytes_per_ul: int = 8000) -> float:
    """
    Estimación estándar de densidad parasitaria:
        densidad = (parásitos / leucocitos) × leucocitos/µL
    Si el número de leucocitos es 0, devuelve 0 para evitar división por cero.
    """
    if leukocytes == 0:
        return 0.0
    return (total_parasites / leukocytes) * leukocytes_per_ul
