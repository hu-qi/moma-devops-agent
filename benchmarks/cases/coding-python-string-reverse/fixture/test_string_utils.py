from string_utils import reverse_words


def main() -> None:
    assert reverse_words("hello world") == "world hello"
    assert reverse_words("a b c") == "c b a"
    assert reverse_words("one") == "one"
    assert reverse_words("the quick brown fox") == "fox brown quick the"
    assert reverse_words("") == ""


if __name__ == "__main__":
    main()
