"""architex entry point script."""

from architex import __app_name__, view


def main():
    view.app(prog_name=__app_name__)


if __name__ == "__main__":
    main()
