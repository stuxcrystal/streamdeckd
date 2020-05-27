import os
import sys
import argparse
from streamdeckd.application import Streamdeckd


def main():
    parser = argparse.ArgumentParser(description="Run the streamdeck daemon.")
    parser.add_argument('--config', '-f', help="The configuration file to load.", default=os.environ.get("STREAMDECKD_CONFIG_PATH", None))
    args = parser.parse_args()

    sys.exit(Streamdeckd(args.config).start())