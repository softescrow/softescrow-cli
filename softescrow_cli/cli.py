import click
import os
import sys

from math import ceil

import requests

BASE_URL = "https://portal.softescrow.com/api"
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


class SoftEscrowApi(object):
    def __init__(self, api_key: str, base_url: str = BASE_URL, debug: bool = False):
        self.api_key = api_key
        self.base_url = base_url or BASE_URL
        self.debug = debug or False

        self.artifact_id = None

    def upload_file(self, container_id: str, filepath: str, part_size: int):
        num_parts = calculate_parts(filepath, part_size)
        filename = os.path.basename(filepath)
        
        try:
            self.artifact_id = self.initialize_upload(container_id, filename)
            presigned_urls = self.get_presigned_urls(num_parts)
        except requests.HTTPError as e:
            raise SoftEscrowUserUploadException(f"Could not initialize upload: {e.response.json().get('errors')}")

        try:
            parts = upload_parts(filepath, presigned_urls)
            confirmation_url = self.confirm_upload(parts)
        except Exception as e:
            self.cancel_upload()
            raise e

        return confirmation_url

    def initialize_upload(self, container_id: str, filename: str) -> str:
        resp = requests.post(
            f"{self.base_url}/artifacts",
            auth=(self.api_key, ""),
            json={"container_id": container_id, "filename": filename},
        )
        resp.raise_for_status()

        return resp.json()["artifact_id"]

    def get_presigned_urls(self, num_parts: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/artifacts/{self.artifact_id}/generate-multipart-presigned-urls",
            json={"num_parts": num_parts},
            auth=(self.api_key, ""),
        )
        resp.raise_for_status()

        return resp.json()["presigned_urls"]

    def confirm_upload(self, parts: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/artifacts/{self.artifact_id}/confirm-multipart-upload",
            json={"parts": parts},
            auth=(self.api_key, ""),
        )
        resp.raise_for_status()

        confirmation_url = resp.json()["certificate_url"]
        return confirmation_url

    def cancel_upload(self) -> None:
        resp = requests.delete(
            f"{self.base_url}/artifacts/{self.artifact_id}", auth=(self.api_key, "")
        )
        resp.raise_for_status()


class SoftEscrowUserUploadException(Exception):
    pass


def calculate_part_size(filepath):
    file_size = os.stat(filepath).st_size

    allowed_chunk_sizes = [size * 1024**2 for size in range(10, 110, 10)]

    if file_size:
        for chunk_size in allowed_chunk_sizes:
            if ceil(file_size / chunk_size) < 10000:
                break
        else:
            max_file_size = chunk_size * 10000

            raise SoftEscrowUserUploadException(
                "File is too large to upload (size: {}, max: {})".format(
                    file_size, max_file_size
                )
            )

        multipart_chunksize = chunk_size
    else:
        # default to 25 mb
        multipart_chunksize = 25 * 1024**2

    return multipart_chunksize


def calculate_parts(filepath, part_size=None):
    if not part_size:
        part_size = calculate_part_size(filepath)
    file_size = os.stat(filepath).st_size
    return ceil(file_size / part_size)


def chunk(filepath, chunk_size=5 * 1024 * 1024):
    with open(filepath, "rb") as f:
        data = f.read(chunk_size)
        while data:
            yield data
            data = f.read(chunk_size)


def upload_parts(filepath: str, presigned_urls: list) -> list:
    parts = []
    for (ix, presigned_url), file_data in zip(presigned_urls.items(), chunk(filepath)):
        resp = requests.put(presigned_url, data=file_data)
        resp.raise_for_status()
        parts.append({"ETag": resp.headers["ETag"].strip('"'), "PartNumber": int(ix)})
    return parts


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("--api-key", help="SoftEscrow API key", required=True)
@click.option("--base-url", help="Alternative SoftEscrow Client Portal base URL")
@click.option("--debug", is_flag=True)
@click.pass_context
def cli(ctx, api_key, base_url, debug):
    ctx.obj = SoftEscrowApi(api_key, base_url, debug)


@cli.command(help="Upload a ZIP file to a Lincoln-Parry SoftEscrow Container")
@click.option("--container-id", help="SoftEscrow container ID", required=True)
@click.argument("filepath", type=click.Path(exists=True, dir_okay=False))
@click.option("--part-size", type=int, help="Part size for multipart uploads")
@click.pass_obj
def upload(api, container_id, filepath, part_size):
    try:
        confirmation_url = api.upload_file(container_id, filepath, part_size)
    except Exception as e:
        click.echo(e)
        sys.exit(1)

    click.echo(
        f"Your file has been uploaded successfully. Please visit the following URL to retrieve your deposit certificate:\n{confirmation_url}"
    )


if __name__ == "__main__":
    cli()
