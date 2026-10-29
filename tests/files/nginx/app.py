LOREM = b"""Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
Duis aute irure dolor in reprehenderit in voluptate velit esse cillum.
"""

SIZE = 8 * 1024  # 8 KiB
HEADER = b"Hello from Gunicorn!\n"
CHUNK = LOREM + b"\n"


def app(environ, start_response):
    repetitions = (SIZE - len(HEADER)) // len(CHUNK)
    content_length = len(HEADER) + repetitions * len(CHUNK)

    start_response(
        "200 OK",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(content_length)),
        ],
    )

    def generate_body():
        yield HEADER
        for _ in range(repetitions):
            yield CHUNK

    return generate_body()
