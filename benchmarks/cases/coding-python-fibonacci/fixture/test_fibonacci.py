from fibonacci import fib


def main() -> None:
    assert fib(0) == 0
    assert fib(1) == 1
    assert fib(2) == 1
    assert fib(5) == 5
    assert fib(10) == 55


if __name__ == "__main__":
    main()
