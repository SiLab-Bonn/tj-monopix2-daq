from argparse import ArgumentParser
from tjmonopix2.analysis import analysis


def parse_args():
    """Parse command line arguments."""
    parser = ArgumentParser(
             description='Offline analysis of h5 file')
    add_arg = parser.add_argument
    add_arg('-f', '--file', type=str, default="", help='Path to h5 file')

    return parser.parse_args()


def offline_analyze(raw_data_file):
    with analysis.Analysis(raw_data_file=raw_data_file) as a:
        a.analyze_data()


if __name__ == '__main__':
    args = parse_args()
    offline_analyze(args.file)
