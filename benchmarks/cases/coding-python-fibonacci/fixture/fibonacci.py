def fib(n: int) -> int:
    """Return the n-th Fibonacci number (0-indexed).

    fib(0) = 0, fib(1) = 1, fib(2) = 1, fib(3) = 2, ...
    """
    if n <= 0:
        return 0
    # BUG: wrong base case – returns 0 for n==1 instead of 1
    if n == 1:
        return 0
    return fib(n - 1) + fib(n - 2)
