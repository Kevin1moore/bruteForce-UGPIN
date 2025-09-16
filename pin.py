# generate_pins.py

def generate_pins(start=50000, end=99999, filename="pins1.txt"):
    """
    Generate all 5-digit PINs from `start` up to `end` inclusive
    and save them into a file.
    """
    with open(filename, "w") as f:
        for pin in range(start, end + 1):
            f.write(f"{str(pin).zfill(5)}\n")  # each PIN on a new line
    print(f"✅ Saved {end - start + 1} PINs into {filename}")


if __name__ == "__main__":
    generate_pins()
