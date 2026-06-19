"""Manual TextEdit smoke for macos-computer-use.

Run this only on macOS after granting Accessibility permission to the Python
process or terminal app.
"""

from macos_computer_use import MacOSComputerUseClient


def main() -> None:
    client = MacOSComputerUseClient(allowed_apps=("TextEdit",))
    print("readiness:", client.readiness().to_dict())
    print("open_app:", client.open_app("TextEdit").to_dict())
    print("observe:", client.observe(target_app="TextEdit").to_dict())
    typed = client.type_text(
        "hello from macos-computer-use",
        target_app="TextEdit",
    )
    print("type_text:", typed.to_dict())


if __name__ == "__main__":
    main()
