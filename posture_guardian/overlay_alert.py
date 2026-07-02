import sys

from posture_guardian.alerts import show_overlay


def main() -> None:
    message = sys.argv[1] if len(sys.argv) > 1 else "Check your posture"
    show_overlay(message)


if __name__ == "__main__":
    main()
