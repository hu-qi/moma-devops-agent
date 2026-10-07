def filter_long_names(names):
    results = []
    for name in names:
        if (n := len(name)) > 4:
            results.append((name, n))
    return results
