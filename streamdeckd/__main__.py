import sys
from importlib import import_module
from importlib.util import find_spec

def main():
    if len(sys.argv) == 1:
        print("Command missing,")


    try:
        del sys.argv[0]
        appname = sys.argv[0]
        sys.argv[0] = f"streamdeckd-{appname}"
        if appname.startswith("_"):
            raise AttributeError

        initializer = import_module("streamdeckd.commands." + appname.lower())
        initializer.main()
    except (ImportError, AttributeError):
        try:
            find_spec("streamdeckd.commands." + appname.lower())
        except ModuleNotFoundError:
            print("Unknown command", appname)
        else:
            raise

if __name__ == "__main__":
    main()