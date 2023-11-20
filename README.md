# Lincoln-Parry SoftEscrow CLI

This repo provides a command line interface and reference implementation for how to integrate with Lincoln-Parry SoftEscrow's deposit upload API.

## Upload Workflow

The Deposit Upload API uses a presigned multipart upload pattern enabling direct-to-S3 uploads for SoftEscrow source code deposits.

### 1. Create a Deposit Container

Prior to uploading deposit files, you must create a container in the SoftEscrow Client Portal using the form at https://portal.softescrow.com/containers/new

Once you've configured and created the deposit container, you will be provided with a container number in the form of `<agreement ID>.<container ID>`, as well as your API key.

### 2. Initialize an upload

Once you have the container ID, send a `POST` request to `/api/artifacts` with the following JSON-encoded body:

```
{
    "container_id": container_id, 
    "filename": filename
}
```

This will return a response in the following format:

```
{
    "artifact_id": artifact_id
}
```

The `artifact_id` is a unique identifier for a specific upload - store this until you've completed the upload successfully.

### 3. Request presigned URLs

Presigned URLs are used to enable multipart uploads direct to Amazon S3. For large file sizes, the API uses multipart uploads with an individual presigned URL per part.

You can chunk your upload into as many as 10,000 parts, with a max part size of 5GB.

To generate presigned URLs for each part, submit a `POST` request to `/api/artifacts/<artifact_id>/generate-multipart-presigned-urls` with the following JSON-encoded body:

```
{
    "num_parts": num_parts
}
```

Where `num_parts` is the number of parts you would like to use for uploading your deposit. The response will be as follows:

```
{
    "presigned_urls": {
        1: <part_1_presigned_url>,
        2: <part_2_presigned_url>,
        ...
    }
}
```

You'll receive a JSON-encoded dictionary where the keys to the individual part numbers, and the values are the corresponding presigned URLs.

### 4. Upload the file parts

From there, iterate over subsequent chunks of your file to upload, `POSTing` each part to the corresponding presigned URL. Save the value of the `ETag` header returned by each part upload, and associate it with the corresponding part number. Make sure to strip the quotations from the header value. 

You should end up with a "parts" list with the following structure:

```
[
    {
        "PartNumber": 1,
        "ETag": <etag for part 1>
    },
    {
        "PartNumber": 2,
        "ETag": <etag for part 2>
    }
]
```

### 5. Confirm the upload
Once you've finished uploading all of the parts, confirm the multipart upload by sending a `POST` request to `/api/<artifact_id>/confirm-multipart-upload` with the following JSON-encoded body:

```
{
    "parts": <parts list from step 4>
}
```

This confirms the upload and causes the Client Portal to generate the Deposit Certificate and send any Deposit Confirmations selected at the time of container creation.

The response from this request will be structured as follows:

```
{
    "certificate_url": <url to view/download Deposit Certificate>
}
```

You can visit the URL returned in a web browser to view and/or download the Deposit Certificate for your container.

### Aborting a multipart upload
If you need to cancel a multipart upload, send a `DELETE` request to `/api/artifacts/<artifact_id>`. This will cancel the upload and destroy the partial deposit. Once you've done this you'll need to restart the upload workflow.

## Authentication

The Client Portal API uses HTTPS Basic authentication with a per-user API key to authenticate all requests to the API. Pass your API key as the `user` part of the `Authentication` header in the HTTP request. In `cURL`, you would pass:

```
curl -X POST -u <api_key>: https://portal.softescrow.com/api/artifacts
```
