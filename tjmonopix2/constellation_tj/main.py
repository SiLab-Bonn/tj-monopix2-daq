from constellation.core.logging import setup_cli_logging
from constellation.core.satellite import SatelliteArgumentParser
from tj_satellite import TJ

def main(args=None):
    parser = SatelliteArgumentParser()
    args = vars(parser.parse_args(args))
    setup_cli_logging(args.pop("log_level"))
    s = TJ(**args)
    s.run_satellite()

if __name__ == "__main__":
    main()