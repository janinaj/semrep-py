import os
import errno
import argparse
import configparser
from medline import *

def process_directory(input_file_format, input_dir_path, output_dir_path = None):
    """Reads and processes files from a directory

    Args:
        input_file_format (str): format of the files to process (plaintext, medline, or medlinexml)
        input_dir_path (str): path to the directory to process
        output_dir_path (str): path to the output directory (optional)
    """

    for filename in os.listdir(input_dir_path):
        if filename != '.DS_Store': process_file(input_file_format, os.path.join(input_dir_path, filename), output_dir_path)

def process_file(input_file_format, input_file_path, output_file_path = None):
    """Reads and processes a single file

    Args:
        input_file_format (str): format of the files to process (plaintext, medline, or medlinexml)
        input_file_path (str): path to the file to process
        output_dir_path (str): path to the output file (optional)
    """
    if input_file_format == 'plaintext':
        docs = read_plaintext_file(input_file_path)
    elif input_file_format == 'medline':
        docs = parse_medline_file(input_file_path)
    elif input_file_format == 'medlinexml':
        docs = parse_medlinexml_file(input_file_path)

    for doc in docs:
        # print('PMID: {}'.format(doc.PMID))
        # print('Title: {}'.format(doc.title))
        if doc.title is not None:
            process_text(doc.title)
        process_text(doc.abstract)

def process_interactive(output_path = None):
    """Repeatedly processes a single line of input until user enters quit

    Args:
        output_path (str): path to the output file (optional)
    """
    print('Please enter text. Each input will be processed as a single document. Type quit to exit interactive session.')
    while True:
        text_input = input()
        if text_input != 'quit':
            process_text(text_input)
        else:
            exit()

def process_text(text):
    """Processes a single text input

    Returns:
        output: output
    """
    if text is not None:
        print('Input text has {} characters'.format(len(text.strip())))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract semantic predictions from sentences.')
    parser.add_argument('--config_file', type=str, help='File containing configurations (see default.config for default configuration)')
    parser.add_argument('--input_format', type=str, choices=['dir', 'file', 'interactive'],
                        help='Input format. Can be a single file, directory of files, or interactive input')
    parser.add_argument('--input_file_format', type=str, choices=['plaintext', 'medline', 'medlinexml'],
                        help='Format of the input file(s). input_format must be dir or file. Interactive defaults to plaintext.')
    parser.add_argument('--input_path', type=str, help='Path to input directory or file')
    parser.add_argument('--output_path', type=str, help='Path to output directory or file')

    args = parser.parse_args()

    # use config file provided by user, else use default config file
    if args.config_file is None:
        args.config_file = 'default.config'
        print('No configuration file specified. Using default configuration.')
    elif not os.path.exists(args.config_file):
        print('Unable to locate configuration file. Please check the specified file path.')
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), args.config_file)

    # read config file
    # raises an error if there are issues reading the config file
    config = configparser.ConfigParser()
    config.read(args.config_file)
    for arg, value in vars(args).items():
        if value is None and arg in config['I/O']:
            setattr(args, arg, config['I/O'][arg])

    # if input is a directory or file, the path must be specified
    if args.input_format in ['dir', 'file'] and (args.input_path is None or args.output_path is None):
        parser.error("Directory or file input format requires --input_path and --output_path.")

    if args.input_path is not None and not os.path.exists(args.input_path):
        parser.error("Input path does not exist. Please enter a valid input path.")

    if not os.path.exists(args.output_path):
        print('Output path does not exist. Creating directory..')
        os.makedirs(args.output_path)

    if args.input_format == 'dir':
        process_directory(args.input_file_format, args.input_path, args.output_path)
    elif args.input_format == 'file':
        process_file(args.input_file_format, args.input_path, args.output_path)
    else:
        process_interactive(args.output_path)