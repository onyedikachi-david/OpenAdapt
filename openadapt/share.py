"""Copy a recording from one computer to another.

Usage:
    python -m openadapt.share send --recording_id=1
    python -m openadapt.share receive <wormhole_code>
    python -m openadapt.share visualize <db_name>
"""

from zipfile import ZIP_DEFLATED, ZipFile
import os
import re
import subprocess

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import fire

from openadapt import config, db, utils, visualize

LOG_LEVEL = "INFO"
utils.configure_logging(logger, LOG_LEVEL)


def export_recording_to_folder(recording_id: int) -> None:
    """Export a recording to a zip file.

    Args:
        recording_id (int): The ID of the recording to export.

    Returns:
        str: The path of the created zip file.
    """
    recording_db_path = db.export_recording(recording_id)

    assert recording_db_path, recording_db_path
    # Create the directory if it doesn't exist
    os.makedirs(config.RECORDING_DIRECTORY_PATH, exist_ok=True)

    # Get the timestamp from the recording_db_path
    timestamp = extract_timestamp_from_filename(os.path.basename(recording_db_path))

    # Path to the source db file
    db_filename = f"recording_{recording_id}_{timestamp}.db"

    # Path to the compressed file
    zip_filename = f"recording_{recording_id}_{timestamp}.zip"
    zip_path = os.path.join(config.RECORDING_DIRECTORY_PATH, zip_filename)

    # Create an in-memory zip file and add the db file
    with ZipFile(zip_path, "w", ZIP_DEFLATED, compresslevel=9) as zip_file:
        zip_file.write(recording_db_path, arcname=db_filename)

    logger.info(f"created {zip_path=}")

    # delete db file
    os.remove(recording_db_path)
    logger.info(f"deleted {recording_db_path=}")

    return zip_path


def extract_timestamp_from_filename(filename: str) -> int:
    """Extract timestamp from the filename.

    Args:
        filename (str): The filename containing the timestamp.

    Returns:
        int: The extracted timestamp.
    """
    # Regular expression to match the timestamp in the filename
    pattern = r"recording_\d+_(\d+)\.db"
    match = re.match(pattern, filename)
    if match:
        timestamp_str = match.group(1)
        return int(timestamp_str)
    else:
        raise ValueError("Invalid filename format.")


def send_file(file_path: str) -> None:
    """Send a file using the 'wormhole' command-line tool.

    Args:
        file_path (str): The path of the file to send.
    """
    # Construct the command
    command = ["wormhole", "send", file_path]

    # Execute the command
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error occurred while running 'wormhole send': {e}")


def send_recording(recording_id: int) -> None:
    """Export a recording to a zip file and send it to another computer.

    Args:
        recording_id (int): The ID of the recording to send.
    """
    zip_file_path = export_recording_to_folder(recording_id)
    print(zip_file_path)

    assert zip_file_path, zip_file_path
    try:
        send_file(zip_file_path)
        # File sent successfully
    except Exception as exc:
        logger.exception(exc)
    finally:
        # Delete the zip file after sending or in case of exception
        if os.path.exists(zip_file_path):
            os.remove(zip_file_path)
            logger.info(f"deleted {zip_file_path=}")


def receive_recording(wormhole_code: str) -> None:
    """Receive a recording zip file from another computer using a wormhole code.

    Args:
        wormhole_code (str): The wormhole code to receive the recording.
    """
    # Set the output directory path
    output_directory = config.RECORDING_DIRECTORY_PATH

    # Create the output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)

    zip_filename = "recording.zip"
    zip_path = os.path.join(output_directory, zip_filename)

    # Construct the command with the output directory option
    command = ["wormhole", "receive", "-o", zip_path, wormhole_code]

    # Execute the command
    try:
        subprocess.run(command, check=True)

        # Now, extract the database file from the zip file
        with ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(output_directory)

    except subprocess.CalledProcessError as exc:
        logger.exception(exc)
    finally:
        # Delete the zip file after receiving or in case of exception
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logger.info(f"deleted {zip_path=}")


def visualize_recording(db_name: str) -> None:
    """Visualize a recording from a SQLite database.

    This function loads the specified db file containing a recording and
    visualizes the data using the 'visualize.main' function.

    Args:
        db_name (str): The name of the SQLite database containing the recording.

    Raises:
        Exception: If there is an error accessing the database.
    """
    # Determine the recording path based on the database name
    if db_name == "openadapt.db":
        recording_path = os.path.join(config.ROOT_DIRPATH, db_name)
    else:
        recording_path = os.path.join(config.RECORDING_DIRECTORY_PATH, db_name)

    recording_url = f"sqlite:///{recording_path}"

    # Save the old value of DB_FNAME
    old_val = os.getenv("DB_FNAME")

    # Update the environment variable DB_FNAME and persist it
    config.persist_env("DB_FNAME", db_name)
    os.environ["DB_FNAME"] = db_name

    # Set the database URL
    config.set_db_url(db_name)

    engine = create_engine(recording_url)

    try:
        with Session(engine) as session:
            os.system("alembic upgrade head")
            # Visualize the recording
            visualize.main(None, False, session)
    except Exception as exc:
        # Handle any exceptions that may occur during visualization
        logger.exception(exc)
    finally:
        # Restore the old value of DB_FNAME in case of exceptions or at the end
        os.environ["DB_FNAME"] = old_val
        config.persist_env("DB_FNAME", old_val)


# Create a command-line interface using python-fire and utils.get_functions
if __name__ == "__main__":
    fire.Fire(
        {
            "send": send_recording,
            "receive": receive_recording,
            "visualize": visualize_recording,
        }
    )
