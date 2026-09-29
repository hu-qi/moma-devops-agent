def reverse_words(sentence: str) -> str:
    """Return the sentence with the order of words reversed.

    Words are separated by single spaces.  Leading/trailing spaces
    are stripped from the result.

    Example
    -------
    >>> reverse_words("hello world")
    'world hello'
    """
    # BUG: reverses the characters, not the word order
    return sentence[::-1]
