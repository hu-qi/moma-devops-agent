import threading


class HitCounter:
    def __init__(self):
        self.count = 0

    def increment(self):
        # Unsynchronized read-modify-write
        self.count += 1

    def get(self):
        return self.count


counter = HitCounter()


def worker(n: int):
    for _ in range(n):
        counter.increment()


def run_parallel(num_threads: int = 4, increments_per_thread: int = 100_000):
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker, args=(increments_per_thread,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print(f"Expected: {num_threads * increments_per_thread}, Got: {counter.get()}")


if __name__ == "__main__":
    run_parallel()
